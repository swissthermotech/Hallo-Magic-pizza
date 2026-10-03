"""Carte Fidélité – server-side loyalty rules (loyalty.py + compute_order / push_status wiring).

Runs against the sandbox DB with a throw-away customer account; orders are created through the same functions as
POST /orders (compute_order_reserving_loyalty + insert) and completed via finish_order / push_status – acceptance
(= PrintNode ticket) is deliberately NOT part of the flow, so nothing is printed. Everything is cleaned up at the end.
Test names contain "requires" so the legacy autouse PIN fixture is skipped.
"""
import asyncio
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import loyalty as lm  # noqa: E402
from server import db, OrderIn, OrderItemIn, CustomerIn, collection_fields  # noqa: E402

API = "http://localhost:8001/api"
PHONE = "079 555 01 01"
PHONE2 = "079 555 01 02"


def call(method, path, body=None, tok=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {tok}"} if tok else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


async def _catalog():
    cats = {c["slug"]: str(c["_id"]) for c in await db.categories.find({}).to_list(50)}
    marg = await db.products.find_one({"name.fr": "Margherita", "deleted_at": None})
    drink = await db.products.find_one({"$or": [{"category_id": cats["boissons"]}, {"category_id": server.oid(cats["boissons"])}], "deleted_at": None, "is_alcohol": {"$ne": True}})
    dessert = await db.products.find_one({"$or": [{"category_id": cats["dessert"]}, {"category_id": server.oid(cats["dessert"])}], "deleted_at": None})
    extra = await db.extras.find_one({"$or": [{"_id": {"$in": [server.oid(x) for x in marg.get("allowed_extra_ids", []) if len(x) == 24]}},
                                              {"key": {"$in": marg.get("allowed_extra_ids", [])}}]})
    return marg, drink, dessert, extra


def _item(p, size=None, qty=1, extras=None):
    return OrderItemIn(product_id=str(p["_id"]), quantity=qty, size_key=size, extras=extras or [])


async def _place(user, items, **kw):
    body = OrderIn(type="pickup", items=items, customer=CustomerIn(first_name="Fidel", last_name="Test", phone=user["phone"], email=user.get("email")),
                   requested_time="asap", age_confirmed=True, language="fr")
    order = await server.compute_order_reserving_loyalty(body, user, enforce_minimum=False, enforce_hours=False, **kw)
    doc = order.to_mongo()
    doc.update(collection_fields(order.payment_method, order.total))
    doc["_fidelity_test"] = True
    res = await db.orders.insert_one(doc)
    return await db.orders.find_one({"_id": res.inserted_id})


async def _complete(doc):
    await server.finish_order(doc, "picked_up", None)
    return await db.orders.find_one({"_id": doc["_id"]})


async def _cancel(doc):
    await server.push_status(doc, "cancelled", None)
    return await db.orders.find_one({"_id": doc["_id"]})


async def _state(uid):
    return await lm.summary(db, uid)


async def _cleanup(uid):
    await db.orders.delete_many({"_fidelity_test": True})
    await db.loyalty.delete_one({"_id": uid})
    await db.users.delete_many({"phone": {"$in": [server.auth_mod.normalize_phone(PHONE), server.auth_mod.normalize_phone(PHONE2)]}})


async def _scenario():
    log = []
    # fresh customer account through the real registration endpoint (gives us a JWT like a phone / browser would have)
    for ph in (PHONE, PHONE2):
        await db.users.delete_many({"phone": server.auth_mod.normalize_phone(ph)})
    st, reg = call("POST", "/auth/register", {"first_name": "Fidel", "last_name": "Test", "phone": PHONE, "email": "fidel.test@example.com", "password": "Fidelity2026!"})
    assert st in (200, 201), reg
    tok_a = reg["access_token"]
    user = await db.users.find_one({"phone": server.auth_mod.normalize_phone(PHONE)})
    uid = str(user["_id"])
    await db.loyalty.delete_one({"_id": uid})
    marg, drink, dessert, _extra = await _catalog()
    sizes = {s["key"]: s["price"] for s in marg["sizes"]}   # 32: 14.00, 40: 25.00, 50: 31.00
    small, mid, big = sorted(sizes, key=lambda k: sizes[k])
    try:
        # 1) 0 stamps + 1 pizza -> no discount; 1/10 after completion
        o = await _place(user, [_item(marg, small)])
        log.append(("0 stamps + 1 pizza: no discount at checkout", o["loyalty"]["rewards_applied"] == 0 and o["loyalty"]["discount"] == 0 and o["total"] == sizes[small]))
        s = await _state(uid)
        log.append(("... stamps NOT yet added while order is open (0/10)", s["stamps"] == 0))
        o = await _complete(o)
        s = await _state(uid)
        log.append(("... 1/10 after completion", s["stamps"] == 1 and o["loyalty"]["finalized"] and o["loyalty"]["stamps_after"] == 1))

        # 2) drinks / desserts: no stamps
        o = await _place(user, [_item(drink), _item(dessert)])
        log.append(("drink + dessert: 0 pizzas, no loyalty block", o.get("loyalty") is None and all(i["loyalty_stamps"] == 0 for i in o["items"])))
        await _complete(o)
        log.append(("... still 1/10", (await _state(uid))["stamps"] == 1))

        # 3) 8 stamps + 1 pizza -> 9/10, no discount
        await db.loyalty.update_one({"_id": uid}, {"$set": {"stamps": 8}})
        o = await _place(user, [_item(marg, small)])
        log.append(("8 stamps + 1 pizza: no discount", o["loyalty"]["rewards_applied"] == 0 and o["total"] == sizes[small]))
        await _complete(o)
        log.append(("... 9/10 after completion", (await _state(uid))["stamps"] == 9))

        # 4) 9 stamps + 1 pizza -> 50 % on that pizza, cycle resets after completion
        o = await _place(user, [_item(marg, mid)])
        exp = round(sizes[mid] / 2, 2)
        log.append((f"9 stamps + 1 pizza (CHF {sizes[mid]:.2f}): -50% = CHF {exp:.2f}", o["loyalty"]["rewards_applied"] == 1 and o["loyalty"]["discount"] == exp and o["total"] == round(sizes[mid] - exp, 2) and o["items"][0]["loyalty_discount"] == exp))
        s = await _state(uid)
        log.append(("... reward held while order is open (reserved=1, available=0)", s["rewards_reserved"] == 1 and s["rewards_available"] == 0))
        o = await _complete(o)
        s = await _state(uid)
        log.append(("... cycle reset after completion (0/10, nothing banked, nothing reserved)", s["stamps"] == 0 and s["rewards_available"] == 0 and s["rewards_reserved"] == 0 and o["loyalty"]["stamps_after"] == 0))

        # 5) retried completion -> no duplicate stamps
        await lm.finalize(db, o, "completed")
        await lm.finalize(db, o, "completed")
        s = await _state(uid)
        log.append(("retried finalize on the same order: still 0/10, rewards_used counted once", s["stamps"] == 0 and s["rewards_used"] == 1 and s["lifetime_pizzas"] == 3))

        # 6) 9 stamps + several differently priced pizzas -> cheapest gets the 50 %
        await db.loyalty.update_one({"_id": uid}, {"$set": {"stamps": 9}})
        o = await _place(user, [_item(marg, big), _item(marg, small), _item(marg, mid)])
        exp = round(sizes[small] / 2, 2)
        cheap_line = next(i for i in o["items"] if i["size"]["key"] == small)
        others = [i for i in o["items"] if i["size"]["key"] != small]
        log.append((f"9 stamps + 3 pizzas ({sizes[big]:.0f}/{sizes[small]:.0f}/{sizes[mid]:.0f}): one reward on the cheapest (CHF {exp:.2f})",
                    o["loyalty"]["rewards_applied"] == 1 and o["loyalty"]["discount"] == exp and cheap_line["loyalty_discount"] == exp and all(i["loyalty_discount"] == 0 for i in others)
                    and o["total"] == round(sizes[big] + sizes[small] + sizes[mid] - exp, 2)))
        o = await _complete(o)
        log.append(("... 9+3 = 12 -> 2/10 after completion", (await _state(uid))["stamps"] == 2 and o["loyalty"]["stamps_after"] == 2))

        # 7) supplements stay full price; discount only on the base pizza price (a pizza that allows extras)
        await db.loyalty.update_one({"_id": uid}, {"$set": {"stamps": 9}})
        pz = await db.products.find_one({"allowed_extra_ids.0": {"$exists": True}, "sizes.0": {"$exists": True}, "deleted_at": None, "category_id": {"$in": [cid for cid in [str(c["_id"]) for c in await db.categories.find({"slug": "pizza"}).to_list(5)]]}})
        extra = await db.extras.find_one({"key": pz["allowed_extra_ids"][0]}) if pz else None
        if pz and extra:
            from server import OrderExtraIn
            pz_small = min(pz["sizes"], key=lambda s: s["price"])
            o = await _place(user, [_item(pz, pz_small["key"], extras=[OrderExtraIn(extra_id=str(extra["_id"]), quantity=1)])])
            ex_unit = o["items"][0]["extras"][0]["unit_price"]
            exp = round(pz_small["price"] / 2, 2)
            log.append((f"{pz['name']['fr']} {pz_small['label']} CHF {pz_small['price']:.2f} + supplement CHF {ex_unit:.2f}: discount = CHF {exp:.2f} (base only), supplement full price",
                        o["loyalty"]["discount"] == exp and o["extras_total"] == ex_unit and o["total"] == round(pz_small["price"] + ex_unit - exp, 2) and o["items"][0]["loyalty_discount"] == exp))
            await _cancel(o)  # keep 9 stamps for the next cases
        else:
            log.append(("supplement case skipped (no pizza with extras configured)", True))

        # 8) cancelled order -> no stamps, reward not consumed
        await db.loyalty.update_one({"_id": uid}, {"$set": {"stamps": 9, "reserved": 0, "rewards": 0}})
        o = await _place(user, [_item(marg, small), _item(marg, mid)])
        log.append(("cancel test: reward applied at checkout", o["loyalty"]["rewards_applied"] == 1 and (await _state(uid))["rewards_reserved"] == 1))
        o = await _cancel(o)
        s = await _state(uid)
        log.append(("cancelled -> still 9/10, reservation released, no reward consumed", s["stamps"] == 9 and s["rewards_reserved"] == 0 and o["loyalty"]["outcome"] == "cancelled" and s["rewards_used"] == 2))

        # 9) multi-threshold: 9 stamps + 11 pizzas -> 2 rewards on the two cheapest, 0/10 after
        o = await _place(user, [_item(marg, big, qty=9), _item(marg, small), _item(marg, mid)])
        exp = round(sizes[small] / 2, 2) + round(sizes[mid] / 2, 2)
        log.append(("9 stamps + 11 pizzas: 2 rewards (cheapest two), 0/10 after", o["loyalty"]["rewards_applied"] == 2 and round(o["loyalty"]["discount"], 2) == round(exp, 2)))
        o = await _complete(o)
        log.append(("... (9+11)=20 -> 0/10, no banked reward", (await _state(uid))["stamps"] == 0 and (await _state(uid))["rewards_available"] == 0))

        # 10) concurrent orders with 9 stamps: the reward can be used only once
        await db.loyalty.update_one({"_id": uid}, {"$set": {"stamps": 9, "reserved": 0, "rewards": 0}})
        a, b = await asyncio.gather(_place(user, [_item(marg, small)]), _place(user, [_item(marg, small)]))
        applied = [a["loyalty"]["rewards_applied"], b["loyalty"]["rewards_applied"]]
        log.append((f"two simultaneous orders @9 stamps: rewards applied = {applied} (exactly one)", sorted(applied) == [0, 1] and (await _state(uid))["rewards_reserved"] == 1))
        winner, loser = (a, b) if a["loyalty"]["rewards_applied"] else (b, a)
        await _complete(winner)
        s = await _state(uid)
        log.append(("... winner completed: 0/10, nothing reserved", s["stamps"] == 0 and s["rewards_reserved"] == 0))
        await _complete(loser)
        log.append(("... loser completed afterwards: 1/10 (its pizza is the 1st of the new cycle)", (await _state(uid))["stamps"] == 1))

        # 11) cross-device / logout-login: a second JWT (other device) and the API both read the same server state
        st, login = call("POST", "/auth/login", {"phone": PHONE, "password": "Fidelity2026!"})
        tok_b = login["access_token"]
        s1 = call("GET", "/me/loyalty", None, tok_a)[1]
        s2 = call("GET", "/me/loyalty", None, tok_b)[1]
        log.append(("GET /me/loyalty identical for two sessions (two devices): " + f"{s1['stamps']}/10", s1["stamps"] == s2["stamps"] == 1 and s1["rewards_available"] == s2["rewards_available"]))
        log.append(("GET /me/loyalty without token -> 401", call("GET", "/me/loyalty")[0] == 401))

        # 12) checkout quote endpoint (no reservation, no order number consumed)
        await db.loyalty.update_one({"_id": uid}, {"$set": {"stamps": 9}})
        seq_before = (await db.counters.find_one({"_id": "orders"}))["seq"]
        st, q = call("POST", "/loyalty/quote", {"type": "pickup", "items": [{"product_id": str(marg["_id"]), "quantity": 1, "size_key": small}]}, tok_b)
        seq_after = (await db.counters.find_one({"_id": "orders"}))["seq"]
        s = await _state(uid)
        log.append((f"POST /loyalty/quote @9 stamps: discount CHF {q.get('discount')}, total CHF {q.get('total')}", st == 200 and q["rewards_applied"] == 1 and q["discount"] == round(sizes[small] / 2, 2) and q["total"] == round(sizes[small] / 2, 2)))
        log.append(("... quote reserved nothing and consumed no order number", s["rewards_reserved"] == 0 and seq_before == seq_after))
        st, q0 = call("POST", "/loyalty/quote", {"type": "pickup", "items": [{"product_id": str(drink["_id"]), "quantity": 2}]}, tok_b)
        log.append(("quote with drinks only: 0 pizzas, no discount", st == 200 and q0["pizzas"] == 0 and q0["discount"] == 0))

        # 13) guest order (no account): no loyalty at all
        body = OrderIn(type="pickup", items=[_item(marg, small)], customer=CustomerIn(first_name="Guest", phone="079 555 01 03", email="g@example.com"), requested_time="asap", age_confirmed=True)
        g = await server.compute_order_reserving_loyalty(body, None, enforce_minimum=False, enforce_hours=False)
        log.append(("guest order: no loyalty block, full price", g.loyalty is None and g.total == sizes[small]))

        # 14) Manager profile exposes the digital progress
        st, lg = call("POST", "/auth/staff/login", {"password": "Preview-Manager-2026!"})
        prof = call("GET", f"/customers/{uid}/profile", None, lg["access_token"])[1]
        log.append(("Manager customer profile contains loyalty summary", prof.get("loyalty") is not None and prof["loyalty"]["stamps"] == 9))
    finally:
        await _cleanup(uid)
    return log


def test_requires_fidelity_card_rules():
    log = asyncio.run(_scenario())
    for label, ok in log:
        print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    assert all(ok for _, ok in log), [l for l, ok in log if not ok]

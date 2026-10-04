"""Carte Fidélité – FINAL rules (32/40 cm = 1 stamp, 50 cm = 2; 10 stamps = -50 % on ONE 32 cm pizza) – loyalty.py + compute_order / push_status wiring.

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
    sizes = {s["key"]: s["price"] for s in marg["sizes"]}   # Margherita 32: 14.00, 40: 25.00, 50: 31.00
    p32, p40, p50 = sizes["32"], sizes["40"], sizes["50"]
    pizza_cats = [str(c["_id"]) for c in await db.categories.find({"slug": {"$in": ["pizza", "creer-votre-pizza"]}}).to_list(5)]
    # a second pizza whose 32 cm is MORE expensive than the Margherita (cheapest-32-cm rule)
    other = await db.products.find_one({"_id": {"$ne": marg["_id"]}, "deleted_at": None, "category_id": {"$in": pizza_cats},
                                        "sizes": {"$elemMatch": {"key": "32", "price": {"$gt": p32}}}})
    o32 = next(s["price"] for s in other["sizes"] if s["key"] == "32")
    bambino = await db.products.find_one({"deleted_at": None, "category_id": {"$in": pizza_cats}, "sizes": {"$elemMatch": {"key": "26"}}})
    calzone = await db.products.find_one({"deleted_at": None, "category_id": {"$in": pizza_cats}, "sizes": {"$in": [[], None]}})

    async def reset(stamps=0, rewards=0):
        await db.loyalty.update_one({"_id": uid}, {"$set": {"stamps": stamps, "rewards": rewards, "reserved": 0}}, upsert=True)

    try:
        # ---- stamp values -------------------------------------------------------------------------------------
        o = await _place(user, [_item(marg, "32")])
        log.append(("32 cm: 1 stamp planned, no discount, full price", o["loyalty"]["stamps"] == 1 and o["loyalty"]["rewards_applied"] == 0 and o["total"] == p32 and o["items"][0]["loyalty_stamps"] == 1))
        log.append(("... stamps NOT added while the order is open (0/10)", (await _state(uid))["stamps"] == 0))
        await _complete(o)
        log.append(("32 cm completed -> 1/10", (await _state(uid))["stamps"] == 1))

        o = await _place(user, [_item(marg, "40")])
        log.append(("40 cm: 1 stamp planned", o["loyalty"]["stamps"] == 1 and o["items"][0]["loyalty_stamps"] == 1))
        await _complete(o)
        log.append(("40 cm completed -> 2/10", (await _state(uid))["stamps"] == 2))

        o = await _place(user, [_item(marg, "50")])
        log.append(("50 cm: 2 stamps planned", o["loyalty"]["stamps"] == 2 and o["items"][0]["loyalty_stamps"] == 2 and o["loyalty"]["pizzas"] == 1))
        await _complete(o)
        s = await _state(uid)
        log.append(("50 cm completed -> 4/10 (lifetime 3 pizzas)", s["stamps"] == 4 and s["lifetime_pizzas"] == 3))

        o = await _place(user, [_item(marg, "50", qty=2)])
        log.append(("2x 50 cm: 4 stamps planned", o["loyalty"]["stamps"] == 4 and o["items"][0]["loyalty_stamps"] == 4))
        await _cancel(o)

        # ---- products that never count / Calzone = 1 stamp but never discounted --------------------------------
        if bambino:
            o = await _place(user, [_item(bambino, "26")])
            log.append((f"Bambino/kids 26 cm ({o['items'][0]['name']['fr']}): no stamps, no loyalty block", o.get("loyalty") is None and o["items"][0]["loyalty_stamps"] == 0 and o["items"][0]["loyalty_discount"] == 0))
            await _complete(o)
            log.append(("... still 4/10", (await _state(uid))["stamps"] == 4))
        if calzone:
            o = await _place(user, [_item(calzone)])
            log.append((f"Calzone ({o['items'][0]['name']['fr']}, no size): 1 stamp like a 32 cm, full price", o["loyalty"]["stamps"] == 1 and o["items"][0]["loyalty_stamps"] == 1 and o["loyalty"]["rewards_applied"] == 0 and o["total"] == calzone["price"]))
            await _complete(o)
            log.append(("Calzone completed -> 5/10", (await _state(uid))["stamps"] == 5))
            await reset(stamps=4, rewards=1)
            o = await _place(user, [_item(calzone)])
            log.append(("reward + Calzone only: NO discount (not a 32 cm), reward kept, 1 stamp", o["loyalty"]["rewards_applied"] == 0 and o["loyalty"]["rewards_kept"] == 1 and o["loyalty"]["discount"] == 0 and o["items"][0]["loyalty_discount"] == 0 and o["loyalty"]["stamps"] == 1))
            await _cancel(o)
            await reset(stamps=4)
        o = await _place(user, [_item(drink), _item(dessert)])
        log.append(("drink + dessert: no stamps, no loyalty block", o.get("loyalty") is None and all(i["loyalty_stamps"] == 0 for i in o["items"])))
        await _complete(o)
        log.append(("... still 4/10", (await _state(uid))["stamps"] == 4))

        # ---- 8 stamps + one 50 cm -> reaches 10 -> reward earned (banked: a 50 cm is never discounted) -------
        await reset(stamps=8)
        o = await _place(user, [_item(marg, "50")])
        log.append(("8 stamps + one 50 cm: full price, reward NOT applied to the 50 cm (kept)", o["loyalty"]["rewards_applied"] == 0 and o["loyalty"]["rewards_kept"] == 1 and o["loyalty"]["discount"] == 0 and o["total"] == p50 and o["loyalty"]["stamps_preview"] == 0))
        log.append(("... nothing reserved", (await _state(uid))["rewards_reserved"] == 0))
        o = await _complete(o)
        s = await _state(uid)
        log.append(("... completed: 0/10 and 1 reward available", s["stamps"] == 0 and s["rewards_available"] == 1 and o["loyalty"]["rewards_after"] == 1))

        # ---- reward + only 40/50 cm -> no discount, reward stays available --------------------------------------
        o = await _place(user, [_item(marg, "40"), _item(marg, "50")])
        log.append(("reward + 40 cm + 50 cm: no discount, full price, reward kept", o["loyalty"]["rewards_applied"] == 0 and o["loyalty"]["rewards_kept"] == 1 and o["loyalty"]["discount"] == 0 and o["total"] == round(p40 + p50, 2) and all(i["loyalty_discount"] == 0 for i in o["items"])))
        o = await _complete(o)
        s = await _state(uid)
        log.append(("... completed: reward still available, 3/10", s["rewards_available"] == 1 and s["rewards_reserved"] == 0 and s["stamps"] == 3 and o["loyalty"]["rewards_after"] == 1))

        # ---- reward + one 32 cm -> 50 % off that 32 cm ------------------------------------------------------------
        o = await _place(user, [_item(marg, "32")])
        exp = round(p32 / 2, 2)
        log.append((f"reward + one 32 cm (CHF {p32:.2f}): -50 % = CHF {exp:.2f}", o["loyalty"]["rewards_applied"] == 1 and o["loyalty"]["discount"] == exp and o["total"] == round(p32 - exp, 2) and o["items"][0]["loyalty_discount"] == exp))
        s = await _state(uid)
        log.append(("... reward held while the order is open (reserved 1, available 0)", s["rewards_reserved"] == 1 and s["rewards_available"] == 0))
        discounted_doc = o
        o = await _complete(o)
        s = await _state(uid)
        log.append(("... completed: reward consumed, 4/10", s["rewards_available"] == 0 and s["rewards_reserved"] == 0 and s["rewards_used"] == 1 and s["stamps"] == 4 and o["loyalty"]["rewards_after"] == 0))

        # ---- ticket / receipt line ------------------------------------------------------------------------------
        settings = await server.get_settings()
        ticket = server.strip_escpos(server.build_ticket(discounted_doc, settings))
        receipt = server.build_receipt(discounted_doc, settings)
        log.append(("kitchen ticket prints 'Carte Fidélité -50% pizza 32cm  -CHF 7.00' above TOTAL", f"Carte Fidélité -50% pizza 32cm" in ticket and f"-CHF {exp:.2f}" in ticket and ticket.index("Carte Fidélité") < ticket.index("TOTAL:")))
        log.append(("receipt prints the same loyalty row", "Carte Fidélité -50% pizza 32cm" in receipt and f"-CHF {exp:.2f}" in receipt))

        # ---- reward + several 32 cm (+ 40/50) -> discount on the CHEAPEST 32 cm only --------------------------------
        await reset(stamps=4, rewards=1)
        o = await _place(user, [_item(other, "32"), _item(marg, "32"), _item(marg, "40"), _item(marg, "50")])
        exp = round(p32 / 2, 2)
        by_line = {(i["name"]["fr"], i["size"]["key"]): i["loyalty_discount"] for i in o["items"]}
        log.append((f"reward + {other['name']['fr']} 32 (CHF {o32:.2f}) + Margherita 32 (CHF {p32:.2f}) + 40 + 50: -50 % on the Margherita 32 only",
                    o["loyalty"]["rewards_applied"] == 1 and o["loyalty"]["discount"] == exp and by_line[("Margherita", "32")] == exp
                    and by_line[(other["name"]["fr"], "32")] == 0 and by_line[("Margherita", "40")] == 0 and by_line[("Margherita", "50")] == 0
                    and o["total"] == round(o32 + p32 + p40 + p50 - exp, 2) and o["loyalty"]["stamps"] == 5))
        o = await _complete(o)
        log.append(("... completed: 4+5 = 9/10, no reward left", (await _state(uid))["stamps"] == 9 and (await _state(uid))["rewards_available"] == 0))

        # ---- 9 stamps + one 32 cm -> the 10th stamp's pizza itself is -50 % (same order) -------------------------
        o = await _place(user, [_item(marg, "32")])
        log.append(("9 stamps + one 32 cm: reward earned by this order applied to that 32 cm", o["loyalty"]["rewards_applied"] == 1 and o["loyalty"]["discount"] == round(p32 / 2, 2)))
        o = await _complete(o)
        s = await _state(uid)
        log.append(("... completed: cycle reset 0/10, nothing banked", s["stamps"] == 0 and s["rewards_available"] == 0 and s["rewards_reserved"] == 0))

        # ---- 9 stamps + one 40 cm -> reward earned but banked (40 cm never discounted) --------------------------
        await reset(stamps=9)
        o = await _place(user, [_item(marg, "40")])
        log.append(("9 stamps + one 40 cm: full price, reward kept for later", o["loyalty"]["rewards_applied"] == 0 and o["loyalty"]["rewards_kept"] == 1 and o["total"] == p40))
        await _complete(o)
        log.append(("... completed: 0/10 and 1 reward available", (await _state(uid))["stamps"] == 0 and (await _state(uid))["rewards_available"] == 1))

        # ---- 8 stamps + 6x 50 cm + one 32 cm -> 8+12+1 = 21 -> 2 rewards earned: 1 applied (32 cm), 1 banked -----
        await reset(stamps=8)
        o = await _place(user, [_item(marg, "50", qty=6), _item(marg, "32")])
        log.append(("8 stamps + 6x 50 cm + one 32 cm: 2 rewards earned, 1 applied to the 32 cm, 1 kept", o["loyalty"]["stamps"] == 13 and o["loyalty"]["rewards_applied"] == 1 and o["loyalty"]["rewards_kept"] == 1 and o["loyalty"]["discount"] == round(p32 / 2, 2)))
        o = await _complete(o)
        s = await _state(uid)
        log.append(("... completed: 1/10, 1 reward banked", s["stamps"] == 1 and s["rewards_available"] == 1))

        # ---- ONE reward per order maximum (production case: 10x Hawaii 32 cm, 9 stamps + 1 banked reward) -----------
        hawaii = await db.products.find_one({"name.fr": {"$regex": "^hawa", "$options": "i"}, "deleted_at": None, "category_id": {"$in": pizza_cats}})
        hw32 = next(s["price"] for s in hawaii["sizes"] if s["key"] == "32")
        await reset(stamps=9, rewards=1)
        o = await _place(user, [_item(hawaii, "32", qty=10)])
        log.append((f"9 stamps + 1 banked reward + 10x Hawaii 32 cm (CHF {hw32 * 10:.2f}): ONE reward only -> -CHF {hw32 / 2:.2f}, 1 kept",
                    o["subtotal"] == round(hw32 * 10, 2) and o["loyalty"]["rewards_applied"] == 1 and o["loyalty"]["rewards_kept"] == 1
                    and o["loyalty"]["discount"] == round(hw32 / 2, 2) and o["total"] == round(hw32 * 10 - hw32 / 2, 2) and o["items"][0]["loyalty_discount"] == round(hw32 / 2, 2)))
        log.append(("... only one reward reserved", (await _state(uid))["rewards_reserved"] == 1))
        o = await _complete(o)
        s = await _state(uid)
        log.append(("... completed: (9+10) -> 9/10, 1 reward used, 1 still banked for a future order", s["stamps"] == 9 and s["rewards_available"] == 1 and s["rewards_reserved"] == 0 and o["loyalty"]["rewards_after"] == 1))
        await reset(stamps=0, rewards=2)
        o = await _place(user, [_item(marg, "32"), _item(other, "32")])
        log.append((f"2 banked rewards + Margherita 32 + {other['name']['fr']} 32: ONE reward on the cheapest only, 1 kept",
                    o["loyalty"]["rewards_applied"] == 1 and o["loyalty"]["rewards_kept"] == 1 and o["loyalty"]["discount"] == round(p32 / 2, 2)
                    and o["items"][0]["loyalty_discount"] == round(p32 / 2, 2) and o["items"][1]["loyalty_discount"] == 0))
        await _cancel(o)
        log.append(("... cancelled: both rewards available again", (await _state(uid))["rewards_available"] == 2))

        # ---- extras stay full price -------------------------------------------------------------------------------
        pz = await db.products.find_one({"allowed_extra_ids.0": {"$exists": True}, "sizes": {"$elemMatch": {"key": "32"}}, "deleted_at": None, "category_id": {"$in": pizza_cats}})
        extra = await db.extras.find_one({"key": pz["allowed_extra_ids"][0]}) if pz else None
        if pz and extra:
            from server import OrderExtraIn
            base = next(s["price"] for s in pz["sizes"] if s["key"] == "32")
            o = await _place(user, [_item(pz, "32", extras=[OrderExtraIn(extra_id=str(extra["_id"]), quantity=1)])])
            ex_unit = o["items"][0]["extras"][0]["unit_price"]
            exp = round(base / 2, 2)
            log.append((f"reward + {pz['name']['fr']} 32 cm CHF {base:.2f} + supplement CHF {ex_unit:.2f}: discount CHF {exp:.2f} (base only), supplement full price",
                        o["loyalty"]["discount"] == exp and o["extras_total"] == ex_unit and o["total"] == round(base + ex_unit - exp, 2) and o["items"][0]["loyalty_discount"] == exp))
            await _cancel(o)
        else:
            log.append(("supplement case skipped (no 32 cm pizza with extras configured)", True))

        # ---- cancellation: no stamps, reward not consumed ------------------------------------------------------
        await reset(stamps=9)
        o = await _place(user, [_item(marg, "32"), _item(marg, "50")])
        log.append(("cancel test: 9 + 3 stamps -> reward applied to the 32 cm, reserved", o["loyalty"]["rewards_applied"] == 1 and (await _state(uid))["rewards_reserved"] == 1))
        used_before = (await _state(uid))["rewards_used"]
        life_before = (await _state(uid))["lifetime_pizzas"]
        o = await _cancel(o)
        s = await _state(uid)
        log.append(("cancelled -> still 9/10, reservation released, no reward consumed, no stamps", s["stamps"] == 9 and s["rewards_reserved"] == 0 and s["rewards_available"] == 0 and s["rewards_used"] == used_before and s["lifetime_pizzas"] == life_before and o["loyalty"]["outcome"] == "cancelled"))
        await reset(stamps=0, rewards=1)
        o = await _place(user, [_item(marg, "32")])
        o = await _cancel(o)
        s = await _state(uid)
        log.append(("banked reward + 32 cm cancelled -> reward available again", s["rewards_available"] == 1 and s["rewards_reserved"] == 0 and s["stamps"] == 0))

        # ---- retry / concurrency protection ----------------------------------------------------------------------
        o = await _place(user, [_item(marg, "32")])
        o = await _complete(o)
        await lm.finalize(db, o, "completed")
        await lm.finalize(db, o, "completed")
        s = await _state(uid)
        log.append(("retried finalize on the same order: 1/10 once, reward used once", s["stamps"] == 1 and s["rewards_available"] == 0 and s["rewards_used"] == used_before + 1))

        await reset(stamps=1, rewards=1)
        a, b = await asyncio.gather(_place(user, [_item(marg, "32")]), _place(user, [_item(marg, "32")]))
        applied = [a["loyalty"]["rewards_applied"], b["loyalty"]["rewards_applied"]]
        log.append((f"two simultaneous 32 cm orders with 1 reward: rewards applied = {applied} (exactly one)", sorted(applied) == [0, 1] and (await _state(uid))["rewards_reserved"] == 1))
        winner, loser = (a, b) if a["loyalty"]["rewards_applied"] else (b, a)
        await _complete(winner)
        s = await _state(uid)
        log.append(("... winner completed: reward consumed, 2/10", s["rewards_available"] == 0 and s["rewards_reserved"] == 0 and s["stamps"] == 2))
        await _complete(loser)
        log.append(("... loser completed afterwards at full price: 3/10", (await _state(uid))["stamps"] == 3))

        # ---- API: same state on every device, quote endpoint -----------------------------------------------------
        st, login = call("POST", "/auth/login", {"phone": PHONE, "password": "Fidelity2026!"})
        tok_b = login["access_token"]
        s1 = call("GET", "/me/loyalty", None, tok_a)[1]
        s2 = call("GET", "/me/loyalty", None, tok_b)[1]
        log.append(("GET /me/loyalty identical for two sessions: " + f"{s1['stamps']}/10", s1["stamps"] == s2["stamps"] == 3 and s1["rewards_available"] == s2["rewards_available"]))
        log.append(("GET /me/loyalty without token -> 401", call("GET", "/me/loyalty")[0] == 401))

        await reset(stamps=3, rewards=1)
        seq_before = (await db.counters.find_one({"_id": "orders"}))["seq"]
        st, q = call("POST", "/loyalty/quote", {"type": "pickup", "items": [{"product_id": str(marg["_id"]), "quantity": 1, "size_key": "32"}]}, tok_b)
        seq_after = (await db.counters.find_one({"_id": "orders"}))["seq"]
        s = await _state(uid)
        log.append((f"POST /loyalty/quote reward + 32 cm: stamps {q.get('stamps')}, discount CHF {q.get('discount')}, total CHF {q.get('total')}",
                    st == 200 and q["stamps"] == 1 and q["rewards_applied"] == 1 and q["rewards_kept"] == 0 and q["discount"] == round(p32 / 2, 2) and q["total"] == round(p32 / 2, 2)))
        log.append(("... quote reserved nothing and consumed no order number", s["rewards_reserved"] == 0 and seq_before == seq_after))
        st, q50 = call("POST", "/loyalty/quote", {"type": "pickup", "items": [{"product_id": str(marg["_id"]), "quantity": 1, "size_key": "50"}]}, tok_b)
        log.append(("quote reward + 50 cm only: 2 stamps, no discount, reward kept", st == 200 and q50["stamps"] == 2 and q50["rewards_applied"] == 0 and q50["rewards_kept"] == 1 and q50["discount"] == 0 and q50["total"] == p50))
        st, q0 = call("POST", "/loyalty/quote", {"type": "pickup", "items": [{"product_id": str(drink["_id"]), "quantity": 2}]}, tok_b)
        log.append(("quote with drinks only: 0 stamps, no discount", st == 200 and q0["pizzas"] == 0 and q0["stamps"] == 0 and q0["discount"] == 0))

        # ---- guest order (no account): no loyalty at all -----------------------------------------------------------
        body = OrderIn(type="pickup", items=[_item(marg, "32")], customer=CustomerIn(first_name="Guest", phone="079 555 01 03", email="g@example.com"), requested_time="asap", age_confirmed=True)
        g = await server.compute_order_reserving_loyalty(body, None, enforce_minimum=False, enforce_hours=False)
        log.append(("guest order: no loyalty block, full price", g.loyalty is None and g.total == p32))

        # ---- Manager profile exposes the digital progress --------------------------------------------------------
        st, lg = call("POST", "/auth/staff/login", {"password": "Preview-Manager-2026!"})
        prof = call("GET", f"/customers/{uid}/profile", None, lg["access_token"])[1] if st == 200 else {}
        log.append(("Manager customer profile contains loyalty summary (3/10, 1 reward)", prof.get("loyalty") is not None and prof["loyalty"]["stamps"] == 3 and prof["loyalty"]["rewards_available"] == 1))
    finally:
        await _cleanup(uid)
    return log


def test_requires_fidelity_card_rules():
    log = asyncio.run(_scenario())
    for label, ok in log:
        print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    assert all(ok for _, ok in log), [l for l, ok in log if not ok]

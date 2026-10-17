"""Staff corrections of a customer file (manager + phone): PUT /customers/{id}, saved-address edit/delete, address of an
in-progress order, guest -> customer file. Runs against the local sandbox API; every document it creates is inserted
directly in Mongo (NO order is accepted through the API -> no PrintNode ticket) and deleted at the end."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from server import db  # noqa: E402

API = "http://localhost:8001/api"
MANAGER_PW = os.environ.get("TEST_MANAGER_PASSWORD", "Preview-Manager-2026!")
PHONE_PW = os.environ.get("TEST_PHONE_PASSWORD", "Preview-Phone-2026!")
KITCHEN_PW = os.environ.get("TEST_KITCHEN_PASSWORD", "Preview-Cuisine-2026!")
TAG = uuid.uuid4().hex[:6]
OLD_PHONE = "0795550771"
NEW_PHONE = "0795550772"
OTHER_PHONE = "0795550773"
GUEST_PHONE = "0795550774"


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _login(pw: str) -> dict:
    r = requests.post(f"{API}/auth/staff/login", json={"password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _order_doc(phone: str, user_id, status: str, typ: str = "delivery", created=None, number=None):
    now = datetime.now(timezone.utc)
    return {
        "order_number": number or 900000 + int(uuid.uuid4().int % 90000), "type": typ, "source": "telephone", "status": status,
        "items": [{"product_id": "x", "name": {"fr": f"Test {TAG}", "de": "Test"}, "unit_price": 10.0, "quantity": 1, "options": [], "removed_ingredients": [], "extras": [], "line_total": 10.0}],
        "customer": {"first_name": "Avant", "last_name": TAG, "phone": phone, "email": None},
        "address": {"street": "Ancienne rue", "number": "1", "npa": "1700", "city": "Fribourg", "instructions": "Sonnette A"} if typ == "delivery" else None,
        "requested_time": "asap", "payment_method": "cash", "language": "fr", "age_confirmed": True, "user_id": user_id,
        "subtotal": 10.0, "extras_total": 0.0, "delivery_fee": 0.0, "total": 10.0, "created_at": created or now, "test_tag": TAG,
        "notifications": [], "status_history": [{"status": status, "at": now}],
    }


@pytest.fixture(scope="module")
def ctx():
    mgr = _login(MANAGER_PW)
    # staff-created customer (phone order) with one saved address
    r = requests.post(f"{API}/customers", json={"first_name": "Avant", "last_name": TAG, "phone": OLD_PHONE, "email": "avant@test.ch",
                                                 "address": {"label": "", "street": "Rue du Test", "number": "5", "npa": "1700", "city": "Fribourg", "instructions": "2e étage"}},
                      headers=mgr, timeout=15)
    assert r.status_code == 201, r.text
    cust = r.json()
    cid = cust["id"]
    other = requests.post(f"{API}/customers", json={"first_name": "Autre", "last_name": TAG, "phone": OTHER_PHONE}, headers=mgr, timeout=15).json()
    old = datetime.now(timezone.utc) - timedelta(days=30)
    ids = _run(_insert_orders(cid, old))
    _run(db.loyalty.update_one({"_id": cid}, {"$set": {"stamps": 3, "rewards": 1, "reserved": 0, "lifetime_pizzas": 13}}, upsert=True))
    _run(db.marketing_consents.update_one({"phone": OLD_PHONE}, {"$set": {"phone": OLD_PHONE, "consent": True, "at": datetime.now(timezone.utc), "source": "staff"}}, upsert=True))
    data = {"mgr": mgr, "cid": cid, "cust": cust, "other_id": other["id"], **ids}
    yield data
    _run(_cleanup([cid, other["id"]]))


async def _insert_orders(cid: str, old: datetime) -> dict:
    guest = await db.orders.insert_one(_order_doc(OLD_PHONE, None, "completed", created=old))          # guest order with the OLD number, before the file existed
    active = await db.orders.insert_one(_order_doc(OLD_PHONE, cid, "accepted"))                        # in progress, linked
    done = await db.orders.insert_one(_order_doc(OLD_PHONE, cid, "completed"))                         # finished, linked
    pickup = await db.orders.insert_one(_order_doc(OLD_PHONE, cid, "accepted", typ="pickup"))          # pickup in progress
    pure_guest = await db.orders.insert_one(_order_doc(GUEST_PHONE, None, "completed", created=old))   # guest row candidate
    return {"guest": str(guest.inserted_id), "active": str(active.inserted_id), "done": str(done.inserted_id), "pickup": str(pickup.inserted_id), "pure_guest": str(pure_guest.inserted_id)}


async def _cleanup(user_ids):
    await db.orders.delete_many({"test_tag": TAG})
    for uid in user_ids:
        await db.loyalty.delete_one({"_id": uid})
        await db.customer_audit.delete_many({"user_id": uid})
    created = [u["_id"] async for u in db.users.find({"last_name": TAG}, {"_id": 1})]
    for _id in created:
        await db.loyalty.delete_one({"_id": str(_id)})
        await db.customer_audit.delete_many({"user_id": str(_id)})
    await db.users.delete_many({"last_name": TAG})
    await db.marketing_consents.delete_many({"phone": {"$in": [OLD_PHONE, NEW_PHONE, OTHER_PHONE, GUEST_PHONE]}})


def test_requires_profile_exposes_editable_data(ctx):
    r = requests.get(f"{API}/customers/{ctx['cid']}/profile", headers=ctx["mgr"], timeout=15)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["kind"] == "staff"
    assert len(p["saved_addresses"]) == 1 and p["saved_addresses"][0]["id"] == ctx["cust"]["addresses"][0]["id"]
    assert p["changes_audit"] == []
    numbers = {o["id"] for o in p["orders"]}
    assert {ctx["guest"], ctx["active"], ctx["done"], ctx["pickup"]} <= numbers


def test_requires_update_identity_and_phone_keeps_history_and_loyalty(ctx):
    body = {"first_name": "Après", "last_name": TAG, "phone": "079 555 07 72", "email": "apres@test.ch"}
    r = requests.put(f"{API}/customers/{ctx['cid']}", json=body, headers=ctx["mgr"], timeout=15)
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["id"] == ctx["cid"] and u["first_name"] == "Après" and u["phone"] == NEW_PHONE and u["email"] == "apres@test.ch"
    doc = _run(db.users.find_one({"_id": ObjectId(ctx["cid"])}))
    assert doc["previous_phones"] == [OLD_PHONE]
    # marketing consent followed the number
    assert _run(db.marketing_consents.find_one({"phone": OLD_PHONE})) is None
    assert _run(db.marketing_consents.find_one({"phone": NEW_PHONE}))["consent"] is True
    # Carte Fidélité untouched (keyed by the account id)
    assert _run(db.loyalty.find_one({"_id": ctx["cid"]}))["stamps"] == 3
    # journal
    audit = _run(db.customer_audit.find({"user_id": ctx["cid"]}).to_list(10))
    assert len(audit) == 1
    fields = {c["field"]: (c["previous"], c["new"]) for c in audit[0]["changes"]}
    assert fields["phone"] == (OLD_PHONE, NEW_PHONE) and fields["first_name"] == ("Avant", "Après") and fields["email"] == ("avant@test.ch", "apres@test.ch")
    assert "last_name" not in fields
    # profile: history complete (guest order with the OLD number still attached), loyalty + audit visible
    p = requests.get(f"{API}/customers/{ctx['cid']}/profile", headers=ctx["mgr"], timeout=15).json()
    assert p["phone"] == NEW_PHONE and p["first_name"] == "Après"
    assert {ctx["guest"], ctx["active"], ctx["done"], ctx["pickup"]} <= {o["id"] for o in p["orders"]}
    assert p["loyalty"]["stamps"] == 3 and len(p["changes_audit"]) == 1
    assert p["marketing"]["consent"] is True
    # past orders keep their snapshot
    for oid in (ctx["guest"], ctx["done"]):
        o = _run(db.orders.find_one({"_id": ObjectId(oid)}))
        assert o["customer"]["first_name"] == "Avant" and o["customer"]["phone"] == OLD_PHONE
    # the list also shows the corrected number and merges everything in one row
    rows = requests.get(f"{API}/customers?q={TAG}", headers=ctx["mgr"], timeout=15).json()["customers"]
    me = next(x for x in rows if x["key"] == ctx["cid"])
    assert me["orders_count"] == 4 and me["phone"] == NEW_PHONE
    assert not any(x["key"] == f"guest:{OLD_PHONE}" for x in rows)


def test_requires_phone_collision_and_validation(ctx):
    r = requests.put(f"{API}/customers/{ctx['cid']}", json={"first_name": "Après", "last_name": TAG, "phone": OTHER_PHONE}, headers=ctx["mgr"], timeout=15)
    assert r.status_code == 409
    r = requests.put(f"{API}/customers/{ctx['cid']}", json={"first_name": "Après", "last_name": TAG, "phone": "12 34 5"}, headers=ctx["mgr"], timeout=15)
    assert r.status_code == 400
    r = requests.put(f"{API}/customers/guest:{GUEST_PHONE}", json={"first_name": "X", "phone": GUEST_PHONE}, headers=ctx["mgr"], timeout=15)
    assert r.status_code == 404
    # no-op (same values) -> 200 and no extra journal entry
    r = requests.put(f"{API}/customers/{ctx['cid']}", json={"first_name": "Après", "last_name": TAG, "phone": NEW_PHONE, "email": "apres@test.ch"}, headers=ctx["mgr"], timeout=15)
    assert r.status_code == 200
    assert _run(db.customer_audit.count_documents({"user_id": ctx["cid"]})) == 1


def test_requires_saved_address_edit_add_delete(ctx):
    aid = ctx["cust"]["addresses"][0]["id"]
    body = {"label": "", "street": "Rue Corrigée", "number": "7", "npa": "1700", "city": "Fribourg", "instructions": "Code 1234"}
    r = requests.put(f"{API}/customers/{ctx['cid']}/addresses/{aid}", json=body, headers=ctx["mgr"], timeout=15)
    assert r.status_code == 200, r.text
    a = r.json()["addresses"]
    assert len(a) == 1 and a[0]["id"] == aid and a[0]["street"] == "Rue Corrigée" and a[0]["instructions"] == "Code 1234"
    assert requests.put(f"{API}/customers/{ctx['cid']}/addresses/nope", json=body, headers=ctx["mgr"], timeout=15).status_code == 404
    r = requests.post(f"{API}/customers/{ctx['cid']}/addresses", json={**body, "street": "Deuxième rue"}, headers=ctx["mgr"], timeout=15)
    assert r.status_code == 200 and len(r.json()["addresses"]) == 2
    second = next(x for x in r.json()["addresses"] if x["street"] == "Deuxième rue")
    r = requests.delete(f"{API}/customers/{ctx['cid']}/addresses/{second['id']}", headers=ctx["mgr"], timeout=15)
    assert r.status_code == 200 and [x["id"] for x in r.json()["addresses"]] == [aid]
    assert requests.delete(f"{API}/customers/{ctx['cid']}/addresses/{second['id']}", headers=ctx["mgr"], timeout=15).status_code == 404
    audit = _run(db.customer_audit.find({"user_id": ctx["cid"], "changes.field": "address"}).to_list(10))
    assert len(audit) == 2  # edit + delete (add goes through the existing endpoint)


def test_requires_in_progress_order_address_only(ctx):
    body = {"street": "Nouvelle rue", "number": "9", "npa": "1700", "city": "Fribourg", "instructions": "Porte bleue"}
    r = requests.put(f"{API}/orders/{ctx['active']}/address", json=body, headers=ctx["mgr"], timeout=15)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["address"]["street"] == "Nouvelle rue" and o["address"]["instructions"] == "Porte bleue" and o["address_updated_at"]
    assert o["customer"]["first_name"] == "Avant" and o["total"] == 10.0  # snapshot + totals untouched
    doc = _run(db.orders.find_one({"_id": ObjectId(ctx["active"])}))
    assert doc["address_history"][0]["street"] == "Ancienne rue"
    assert requests.put(f"{API}/orders/{ctx['done']}/address", json=body, headers=ctx["mgr"], timeout=15).status_code == 409
    assert requests.put(f"{API}/orders/{ctx['pickup']}/address", json=body, headers=ctx["mgr"], timeout=15).status_code == 400
    assert requests.put(f"{API}/orders/{ctx['active']}/address", json={**body, "street": " "}, headers=ctx["mgr"], timeout=15).status_code == 400
    zones = requests.get(f"{API}/settings", headers=ctx["mgr"], timeout=15).json().get("delivery_zones") or []
    if zones:
        assert requests.put(f"{API}/orders/{ctx['active']}/address", json={**body, "npa": "9999"}, headers=ctx["mgr"], timeout=15).status_code == 400
    assert _run(db.orders.find_one({"_id": ObjectId(ctx["done"])}))["address"]["street"] == "Ancienne rue"


def test_requires_roles(ctx):
    phone = _login(PHONE_PW)
    r = requests.put(f"{API}/customers/{ctx['cid']}", json={"first_name": "Après", "last_name": TAG, "phone": NEW_PHONE, "email": "tel@test.ch"}, headers=phone, timeout=15)
    assert r.status_code == 200, r.text
    assert requests.put(f"{API}/orders/{ctx['active']}/address", json={"street": "Rue Tel", "number": "", "npa": "1700", "city": "Fribourg"}, headers=phone, timeout=15).status_code == 200
    kitchen = _login(KITCHEN_PW)
    assert requests.put(f"{API}/customers/{ctx['cid']}", json={"first_name": "K", "last_name": TAG, "phone": NEW_PHONE}, headers=kitchen, timeout=15).status_code == 403
    assert requests.put(f"{API}/customers/{ctx['cid']}", json={"first_name": "K", "last_name": TAG, "phone": NEW_PHONE}, timeout=15).status_code == 401
    last = _run(db.customer_audit.find({"user_id": ctx["cid"]}).sort("at", -1).to_list(1))[0]
    assert last["role"] == "phone"


def test_requires_guest_to_customer_file(ctx):
    rows = requests.get(f"{API}/customers?q={GUEST_PHONE}", headers=ctx["mgr"], timeout=15).json()["customers"]
    guest = next(x for x in rows if x["key"] == f"guest:{GUEST_PHONE}")
    assert guest["kind"] == "guest" and guest["orders_count"] == 1
    p = requests.get(f"{API}/customers/guest:{GUEST_PHONE}/profile", headers=ctx["mgr"], timeout=15).json()
    assert p["saved_addresses"] == [] and p["changes_audit"] == [] and p["orders"][0]["address"]["street"] == "Ancienne rue"
    r = requests.post(f"{API}/customers", json={"first_name": "Invité", "last_name": TAG, "phone": GUEST_PHONE,
                                                 "address": {"label": "", "street": "Ancienne rue", "number": "1", "npa": "1700", "city": "Fribourg", "instructions": None}}, headers=ctx["mgr"], timeout=15)
    assert r.status_code == 201, r.text
    nid = r.json()["id"]
    p = requests.get(f"{API}/customers/{nid}/profile", headers=ctx["mgr"], timeout=15).json()
    assert p["kind"] == "staff" and p["orders_count"] == 1 and p["orders"][0]["id"] == ctx["pure_guest"] and len(p["saved_addresses"]) == 1
    rows = requests.get(f"{API}/customers?q={GUEST_PHONE}", headers=ctx["mgr"], timeout=15).json()["customers"]
    assert not any(x["key"] == f"guest:{GUEST_PHONE}" for x in rows)

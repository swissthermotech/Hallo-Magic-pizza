"""Duplicate-order protection on the public customer endpoint POST /api/orders (idempotency key + 3-min fallback).
Runs against the local sandbox API; every order it creates is deleted at the end (pending orders only – nothing is
accepted, so no PrintNode job, no review, no Fidélité finalisation). Test names contain "requires" (conftest)."""
import asyncio
import concurrent.futures as cf
import os
import sys
import uuid

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from server import db  # noqa: E402

def _run(coro):
    """Run a coroutine on the module's event loop (each test file is run on its own: pytest tests/<file> -n 0)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


API = "http://localhost:8001/api"
PHONE = "079 555 01 06"



def _marg():
    return next(p for p in requests.get(f"{API}/products", timeout=15).json() if p["name"]["fr"] == "Margherita")


def _body(cid=None, qty=1, requested_time="asap", **kw):
    b = {"type": "pickup", "source": "web", "payment_method": "cash", "requested_time": requested_time, "age_confirmed": True, "language": "fr",
         "items": [{"product_id": _marg()["id"], "quantity": qty, "size_key": "32"}],
         "customer": {"first_name": "Dup", "last_name": "Test", "phone": PHONE, "email": "dup.test@example.com"}}
    if cid:
        b["client_order_id"] = cid
    b.update(kw)
    return b


def _post(body):
    r = requests.post(f"{API}/orders", json=body, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _count():
    return _run(db.orders.count_documents({"customer.phone": {"$in": [PHONE, "0795550106"]}}))


def _seq():
    return 100 + _run(db.counters.find_one({"_id": "orders"}))["seq"]


@pytest.fixture(autouse=True)
def _cleanup():
    _run(db.orders.delete_many({"customer.phone": {"$in": [PHONE, "0795550106"]}}))
    yield
    _run(db.orders.delete_many({"customer.phone": {"$in": [PHONE, "0795550106"]}}))
    _run(db.checkout_claims.delete_many({}))


def test_requires_single_submit_creates_exactly_one_order():
    seq0 = _seq()
    o = _post(_body(cid=str(uuid.uuid4())))
    assert o["order_number"] == seq0 + 1 and o["status"] == "pending"
    assert _count() == 1 and _seq() == seq0 + 1


def test_requires_same_client_order_id_three_times_returns_same_order():
    cid = str(uuid.uuid4())
    seq0 = _seq()
    a, b, c = _post(_body(cid=cid)), _post(_body(cid=cid)), _post(_body(cid=cid))
    assert a["id"] == b["id"] == c["id"] and a["order_number"] == b["order_number"] == c["order_number"]
    assert _count() == 1, "one order only"
    assert _seq() == seq0 + 1, "one order number only"


def test_requires_double_tap_concurrent_same_key_one_order():
    cid = str(uuid.uuid4())
    seq0 = _seq()
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(_post, [_body(cid=cid)] * 4))
    assert len({r["id"] for r in res}) == 1 and len({r["order_number"] for r in res}) == 1
    assert _count() == 1 and _seq() == seq0 + 1


def test_requires_lost_response_then_retry_recovers_existing_order():
    cid = str(uuid.uuid4())
    first = _post(_body(cid=cid))          # server created it, imagine the client never saw this response
    retry = _post(_body(cid=cid))          # client retries the SAME checkout attempt
    assert retry["id"] == first["id"] and retry["order_number"] == first["order_number"]
    assert _count() == 1
    # refresh: the confirmation/status stays reachable by id
    assert requests.get(f"{API}/orders/{first['id']}", timeout=15).json()["order_number"] == first["order_number"]


def test_requires_fallback_without_key_exact_repeat_within_3_minutes_no_duplicate():
    seq0 = _seq()
    a = _post(_body())                      # old client, no client_order_id
    b = _post(_body())                      # identical repeat 1 s later (double tap / blank screen retry)
    assert a["id"] == b["id"] and _count() == 1 and _seq() == seq0 + 1
    # any real difference = a different checkout -> allowed
    c = _post(_body(qty=2))                 # other quantity
    slot = requests.get(f"{API}/settings/ordering", timeout=15).json()["pickup_slots"]
    d = _post(_body(requested_time=slot[-1])) if slot else _post(_body(general_note="autre"))  # other requested time (or note)
    e = _post(_body(payment_method="terminal"))  # other payment method
    assert len({a["id"], c["id"], d["id"], e["id"]}) == 4 and _count() == 4


def test_requires_fallback_ignores_orders_older_than_window():
    a = _post(_body())
    _run(db.orders.update_one({"_id": __import__("bson").ObjectId(a["id"])}, {"$set": {"created_at": __import__("datetime").datetime.utcnow() - __import__("datetime").timedelta(minutes=4)}}))
    b = _post(_body())                      # same pizzas again 4 minutes later = intentional new order
    assert b["id"] != a["id"] and _count() == 2


def test_requires_new_checkout_new_key_is_a_new_order():
    a = _post(_body(cid=str(uuid.uuid4())))
    b = _post(_body(cid=str(uuid.uuid4())))  # the customer really orders a second time (new checkout attempt)
    assert a["id"] != b["id"] and b["order_number"] == a["order_number"] + 1 and _count() == 2


def test_requires_no_duplicate_side_effects_and_fidelity_hold_once():
    """Logged-in customer with 9 stamps: the first POST applies the -50 % reward and holds it (reserved 1); the
    duplicate POSTs (same key, then fallback) must NOT hold it again. No print job, no review entry is created."""
    st, login = requests.post(f"{API}/auth/login", json={"phone": "079 555 01 99", "password": "Fidelity2026!"}, timeout=15), None
    assert st.status_code == 200, st.text
    tok = st.json()["access_token"]
    uid = str(_run(db.users.find_one({"phone": "0795550199"}))["_id"])
    saved = _run(db.loyalty.find_one({"_id": uid}))
    prints0 = _run(db.print_jobs.count_documents({}))
    reviews0 = _run(db.review_customers.count_documents({}))
    hdr = {"Authorization": f"Bearer {tok}"}
    try:
        _run(db.loyalty.update_one({"_id": uid}, {"$set": {"stamps": 9, "rewards": 0, "reserved": 0}}))
        cid = str(uuid.uuid4())
        body = _body(cid=cid, customer={"first_name": "Fidel", "last_name": "Test", "phone": "079 555 01 99", "email": "fidel.test@example.com"})
        a = requests.post(f"{API}/orders", json=body, headers=hdr, timeout=30).json()
        assert a["loyalty"]["rewards_applied"] == 1 and a["total"] == 7.0
        assert _run(db.loyalty.find_one({"_id": uid}))["reserved"] == 1
        b = requests.post(f"{API}/orders", json=body, headers=hdr, timeout=30).json()          # same key
        body.pop("client_order_id")
        c = requests.post(f"{API}/orders", json=body, headers=hdr, timeout=30).json()          # fallback path
        assert a["id"] == b["id"] == c["id"]
        assert _run(db.loyalty.find_one({"_id": uid}))["reserved"] == 1, "reward held exactly once"
        assert _run(db.orders.count_documents({"customer.phone": {"$in": ["079 555 01 99", "0795550199"]}, "_id": __import__("bson").ObjectId(a["id"])})) == 1
        assert _run(db.print_jobs.count_documents({})) == prints0 and _run(db.review_customers.count_documents({})) == reviews0
    finally:
        _run(db.orders.delete_many({"customer.phone": {"$in": ["079 555 01 99", "0795550199"]}, "status": "pending", "customer.first_name": "Fidel"}))
        _run(db.loyalty.replace_one({"_id": uid}, saved))

"""Iteration 10 review – PrintNode backend hardening focused tests.

Scope (matches review_request):
- Fresh web POST /api/orders is PENDING -> /print returns 409 ('not accepted yet').
- Accept -> exactly ONE 'kitchen' print job with status 'simulated'.
- Second non-force /print -> 409.
- Force reprint -> 200 (+ new 'reprint' job).

Run: pytest /app/backend/tests/test_iter10_print_hardening.py -n 0 -v
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def H():
    r = requests.post(f"{API}/auth/staff/login", json={"pin": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def menu():
    r = requests.get(f"{API}/menu")
    assert r.status_code == 200
    m = r.json()
    return {p["name"]["fr"]: p for p in m["products"]}


@pytest.fixture(scope="module")
def ordering():
    return requests.get(f"{API}/settings/ordering").json()


def _fresh_web_order(menu, ordering):
    """Create a fresh CUSTOMER web order that is PENDING (staff has not accepted it)."""
    body = {
        "type": "pickup",
        "items": [{"product_id": menu["Margherita"]["id"], "quantity": 1, "size_key": "32"}],
        "customer": {"first_name": "TEST_Print", "phone": "0790000123"},
        "requested_time": "asap",
        "payment_method": "pay_at_pickup",
    }
    r = requests.post(f"{API}/orders", json=body)
    if r.status_code != 200:
        # pickup closed -> try the first slot; if still closed -> skip
        if ordering.get("pickup_slots"):
            body["requested_time"] = ordering["pickup_slots"][0]
            r = requests.post(f"{API}/orders", json=body)
        if r.status_code != 200:
            pytest.skip(f"cannot create fresh web pickup order right now ({r.status_code}: {r.text})")
    o = r.json()
    assert o["status"] == "pending", f"expected pending, got {o['status']}"
    assert o["printed"] is False
    return o


def test_print_on_pending_order_returns_409(H, menu, ordering):
    o = _fresh_web_order(menu, ordering)
    r = requests.post(f"{API}/orders/{o['id']}/print", json={}, headers=H)
    assert r.status_code == 409, r.text
    assert "not accepted" in r.text.lower()
    # cleanup: reject
    requests.post(f"{API}/orders/{o['id']}/reject", json={"reason": "TEST cleanup"}, headers=H)


def test_accept_creates_exactly_one_kitchen_print_job_simulated(H, menu, ordering):
    o = _fresh_web_order(menu, ordering)

    jobs_before = requests.get(f"{API}/print-jobs?limit=1000", headers=H).json()
    n_before = sum(1 for j in jobs_before if j["order_id"] == o["id"])
    assert n_before == 0

    # Accept: choose a quick time (20 min)
    acc = requests.post(f"{API}/orders/{o['id']}/accept", json={"minutes": 20}, headers=H)
    assert acc.status_code == 200, acc.text
    accepted = acc.json()
    assert accepted["status"] == "accepted"
    assert accepted["printed"] is True
    assert accepted["print_status"] == "simulated"
    assert accepted["print_attempts"] == 1

    jobs = [j for j in requests.get(f"{API}/print-jobs?limit=1000", headers=H).json() if j["order_id"] == o["id"]]
    assert len(jobs) == 1, f"expected exactly one job, got {jobs}"
    assert jobs[0]["kind"] == "kitchen"
    assert jobs[0]["status"] == "simulated"

    # Second non-force print -> 409
    r2 = requests.post(f"{API}/orders/{o['id']}/print", json={}, headers=H)
    assert r2.status_code == 409, r2.text

    # Force reprint -> 200 and a new 'reprint' job
    r3 = requests.post(f"{API}/orders/{o['id']}/print", json={"force": True}, headers=H)
    assert r3.status_code == 200, r3.text
    body3 = r3.json()
    assert body3["ok"] is True
    assert body3["print_status"] == "simulated"
    assert body3["print_attempts"] == 2
    assert "REIMPRESSION" in body3["text"]

    jobs2 = [j for j in requests.get(f"{API}/print-jobs?limit=1000", headers=H).json() if j["order_id"] == o["id"]]
    kinds = sorted(j["kind"] for j in jobs2)
    assert kinds == ["kitchen", "reprint"], f"unexpected job kinds: {kinds}"
    assert all(j["status"] == "simulated" for j in jobs2)

    # cleanup: cancel via reject after accept? use status transition to completed to remove from active list
    # Simpler: reject-after-accept is not allowed; leave the order (no side effects, it's TEST_ prefixed).

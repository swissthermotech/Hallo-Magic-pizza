"""Iteration 9 – operational refinements only. Run: pytest tests/test_refinements_iter9.py -n 0"""
import os
import pytest
import requests

API = os.environ.get("API_URL", "http://localhost:8001/api")


def login(pin):
    r = requests.post(f"{API}/auth/staff/login", json={"pin": pin})
    return r


@pytest.fixture(scope="module")
def H():
    m = login("1234").json()["access_token"]
    return {"Authorization": f"Bearer {m}"}


@pytest.fixture(scope="module")
def menu():
    m = requests.get(f"{API}/menu").json()
    return {p["name"]["fr"]: p for p in m["products"]}


def customer(H):
    return requests.get(f"{API}/customers/search?phone=0791751450", headers=H).json()["accounts"][0]


def test_phone_order_below_minimum_allowed_web_blocked(H, menu):
    c = customer(H)
    body = {"type": "delivery", "station": 1, "payment_method": "cash", "customer_id": c["id"],
            "items": [{"product_id": menu["Margherita"]["id"], "quantity": 1, "size_key": "32"}],  # CHF 14 < 25 minimum
            "customer": {"first_name": c["first_name"], "phone": c["phone"]}, "address": c["addresses"][0], "requested_time": "asap"}
    r = requests.post(f"{API}/phone-orders", json=body, headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["total"] < 25
    web = {k: v for k, v in body.items() if k not in ("station", "payment_method", "customer_id")}
    assert requests.post(f"{API}/orders", json=web).status_code == 400  # customer rule unchanged


def test_driver_flow_no_pickup_step_and_auto_complete(H, menu):
    c = customer(H)
    body = {"type": "delivery", "station": 2, "payment_method": "terminal", "customer_id": c["id"],
            "items": [{"product_id": menu["Margherita"]["id"], "quantity": 2, "size_key": "32"}],
            "customer": {"first_name": c["first_name"], "phone": c["phone"]}, "address": c["addresses"][0], "requested_time": "asap"}
    o = requests.post(f"{API}/phone-orders", json=body, headers=H).json()
    assert requests.post(f"{API}/orders/{o['id']}/assign", json={"driver": "Livreur 1"}, headers=H).status_code == 200
    d1 = {"Authorization": f"Bearer {login('1111').json()['access_token']}"}
    mine = requests.get(f"{API}/driver/orders", headers=d1).json()
    assert any(x["id"] == o["id"] for x in mine)
    # assigned -> directly PARTI (no pickup call)
    r = requests.post(f"{API}/driver/orders/{o['id']}/depart", headers=d1).json()
    assert r["status"] == "delivering" and r["picked_up_at"] and r["out_for_delivery_at"]
    r = requests.post(f"{API}/driver/orders/{o['id']}/collect", json={"method": "terminal"}, headers=d1).json()
    assert r["payment_collected"] is True
    r = requests.post(f"{API}/driver/orders/{o['id']}/delivered", headers=d1).json()
    assert r["status"] == "completed" and r["delivered_at"] and r["completed_at"]
    assert [e["status"] for e in r["status_history"]][-2:] == ["delivered", "completed"]
    active = requests.get(f"{API}/orders?active=true", headers=H).json()
    assert all(not (x["id"] == o["id"] and x["status"] not in ("completed", "cancelled")) for x in active)
    # still in today's driver list under "done today"
    assert any(x["id"] == o["id"] and x["status"] == "completed" for x in requests.get(f"{API}/driver/orders", headers=d1).json())


def test_driver_sees_only_today(H):
    d2 = {"Authorization": f"Bearer {login('2222').json()['access_token']}"}
    from datetime import datetime, timezone, timedelta
    start_utc = datetime.now(timezone.utc) - timedelta(hours=26)
    for o in requests.get(f"{API}/driver/orders", headers=d2).json():
        stamp = o["delivered_at"] if o["status"] in ("delivered", "completed") else (o["assigned_at"] or o["estimated_ready_at"])
        assert stamp is not None
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        assert dt >= start_utc, o["order_number"]


def test_pickup_retiree_auto_completes(H, menu):
    pk = {"type": "pickup", "items": [{"product_id": menu["Tiramisu"]["id"], "quantity": 1}], "customer": {"first_name": "P", "phone": "0790000003"}, "requested_time": "asap"}
    o = requests.post(f"{API}/orders", json=pk).json()
    requests.post(f"{API}/orders/{o['id']}/accept", json={"minutes": 10}, headers=H)
    for st in ("preparing", "ready", "picked_up"):
        r = requests.post(f"{API}/orders/{o['id']}/status", json={"status": st}, headers=H)
        assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
    assert [e["status"] for e in r.json()["status_history"]][-2:] == ["picked_up", "completed"]


def test_inactive_driver_position_cannot_login(H):
    try:
        assert requests.put(f"{API}/auth/staff/drivers/driver3/active", json={"active": False}, headers=H).status_code == 200
        r = login("3333")
        assert r.status_code == 403 and "INACTIF" in r.text
        # kitchen (non-driver) unaffected, cannot toggle
        assert requests.put(f"{API}/auth/staff/drivers/driver3/active", json={"active": True}, headers={"Authorization": f"Bearer {login('2345').json()['access_token']}"}).status_code == 403
    finally:
        requests.put(f"{API}/auth/staff/drivers/driver3/active", json={"active": True}, headers=H)
    r = login("3333")
    assert r.status_code == 200 and r.json()["role"] == "driver3"


def test_deactivation_cuts_existing_session_and_session_expires_end_of_day(H):
    import jwt
    from datetime import datetime, timezone, timedelta
    tok = login("3333").json()["access_token"]
    exp = datetime.fromtimestamp(jwt.decode(tok, options={"verify_signature": False})["exp"], tz=timezone.utc)
    assert exp <= datetime.now(timezone.utc) + timedelta(hours=27)  # ends at 03:00 Zurich at the latest
    d3 = {"Authorization": f"Bearer {tok}"}
    assert requests.get(f"{API}/driver/orders", headers=d3).status_code == 200
    try:
        requests.put(f"{API}/auth/staff/drivers/driver3/active", json={"active": False}, headers=H)
        assert requests.get(f"{API}/driver/orders", headers=d3).status_code == 403
    finally:
        requests.put(f"{API}/auth/staff/drivers/driver3/active", json={"active": True}, headers=H)

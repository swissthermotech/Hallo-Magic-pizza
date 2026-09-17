"""Iteration 10 – print safety, driver shifts, ordering hours, half/half, shift accounting. Run: pytest tests/test_final_iter10.py -n 0"""
import os
import pytest
import requests

API = os.environ.get("API_URL", "http://localhost:8001/api")


@pytest.fixture(scope="module")
def H():
    return {"Authorization": f"Bearer {requests.post(f'{API}/auth/staff/login', json={'pin': '1234'}).json()['access_token']}"}


@pytest.fixture(scope="module")
def menu():
    m = requests.get(f"{API}/menu").json()
    return {p["name"]["fr"]: p for p in m["products"]}


def cust(H):
    return requests.get(f"{API}/customers/search?phone=0791751450", headers=H).json()["accounts"][0]


def phone_order(H, menu, items, driver_ok=True):
    c = cust(H)
    body = {"type": "delivery", "station": 1, "payment_method": "cash", "customer_id": c["id"], "items": items,
            "customer": {"first_name": c["first_name"], "phone": c["phone"]}, "address": c["addresses"][0], "requested_time": "asap"}
    r = requests.post(f"{API}/phone-orders", json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def test_printer_configured_but_simulated_without_key(H, menu):
    o = phone_order(H, menu, [{"product_id": menu["Margherita"]["id"], "quantity": 2, "size_key": "32"}])
    t = requests.get(f"{API}/orders/{o['id']}/ticket", headers=H).json()
    assert t["printer_configured"] is False  # API key empty -> simulated; printer id is set in .env
    assert o["printed"] is True and o["print_status"] == "simulated" and o["print_attempts"] == 1


def test_auto_print_idempotent_and_reprint_marked(H, menu):
    o = phone_order(H, menu, [{"product_id": menu["Margherita"]["id"], "quantity": 2, "size_key": "32"}])
    assert requests.post(f"{API}/orders/{o['id']}/print", json={}, headers=H).status_code == 409  # no second automatic print
    r = requests.post(f"{API}/orders/{o['id']}/print", json={"force": True}, headers=H).json()
    assert "REIMPRESSION" in r["text"] and r["print_attempts"] == 2
    o2 = requests.get(f"{API}/orders/{o['id']}", headers=H).json()
    assert o2["reprint_count"] == 1
    jobs = [j for j in requests.get(f"{API}/print-jobs?limit=500", headers=H).json() if j["order_id"] == o["id"]]
    assert sorted(j["kind"] for j in jobs) == ["kitchen", "reprint"]


def test_dashboard_polling_never_prints(H):
    before = len(requests.get(f"{API}/print-jobs?limit=1000", headers=H).json())
    for _ in range(3):
        requests.get(f"{API}/orders?active=true", headers=H)
        requests.get(f"{API}/settings")
    assert len(requests.get(f"{API}/print-jobs?limit=1000", headers=H).json()) == before


def test_shift_pin_lifecycle(H, menu):
    assert requests.post(f"{API}/auth/staff/login", json={"pin": "1111"}).status_code == 401  # permanent driver PINs retired
    sh = requests.post(f"{API}/auth/staff/shifts/driver1/open", json={"name": "Marco"}, headers=H).json()
    assert len(sh["pin"]) == 6
    d = requests.post(f"{API}/auth/staff/login", json={"pin": sh["pin"]}).json()
    assert d["role"] == "driver1" and d["label"] == "Livreur 1 — Marco"
    h1 = {"Authorization": f"Bearer {d['access_token']}"}
    assert requests.get(f"{API}/driver/orders", headers=h1).status_code == 200
    # second device takes over -> first device out
    d2 = requests.post(f"{API}/auth/staff/login", json={"pin": sh["pin"]}).json()
    h2 = {"Authorization": f"Bearer {d2['access_token']}"}
    assert requests.get(f"{API}/driver/orders", headers=h1).status_code == 403
    assert requests.get(f"{API}/driver/orders", headers=h2).status_code == 200
    # reset session -> phone must log in again with same pin
    requests.post(f"{API}/auth/staff/shifts/driver1/reset-session", headers=H)
    assert requests.get(f"{API}/driver/orders", headers=h2).status_code == 403
    d3 = requests.post(f"{API}/auth/staff/login", json={"pin": sh["pin"]}).json()
    h3 = {"Authorization": f"Bearer {d3['access_token']}"}
    # assignment records the shift name permanently
    o = phone_order(H, menu, [{"product_id": menu["Margherita"]["id"], "quantity": 2, "size_key": "32"}])
    a = requests.post(f"{API}/orders/{o['id']}/assign", json={"driver": "Livreur 1"}, headers=H).json()
    assert a["driver_name"] == "Marco"
    assert "MARCO" in requests.get(f"{API}/orders/{o['id']}/ticket", headers=H).json()["text"]
    requests.post(f"{API}/driver/orders/{o['id']}/depart", headers=h3)
    requests.post(f"{API}/driver/orders/{o['id']}/delivered", headers=h3)
    rep = requests.get(f"{API}/reports/closing", headers=H).json()["drivers"]
    assert any(d["driver"] == "Livreur 1" and d["driver_name"] == "Marco" and d["deliveries"] >= 1 for d in rep)
    # reopen with another name -> old pin dead, history keeps Marco
    sh2 = requests.post(f"{API}/auth/staff/shifts/driver1/open", json={"name": "Luca"}, headers=H).json()
    assert requests.post(f"{API}/auth/staff/login", json={"pin": sh["pin"]}).status_code == 401
    assert requests.get(f"{API}/driver/orders", headers=h3).status_code == 403
    assert requests.get(f"{API}/orders/{o['id']}", headers=H).json()["driver_name"] == "Marco"
    requests.post(f"{API}/auth/staff/shifts/driver1/close", headers=H)
    assert requests.post(f"{API}/auth/staff/login", json={"pin": sh2["pin"]}).status_code == 401
    assert requests.post(f"{API}/orders/{o['id']}/assign", json={"driver": "Livreur 3"}, headers=H).status_code in (400, 409)  # no open shift


def test_ordering_hours_status_and_validation(menu):
    st = requests.get(f"{API}/settings/ordering").json()
    assert set(st) >= {"pickup_open", "delivery_open", "pickup_slots", "delivery_slots", "next_open"}
    body = {"type": "pickup", "items": [{"product_id": menu["Tiramisu"]["id"], "quantity": 1}], "customer": {"first_name": "H", "phone": "0790000004"}, "requested_time": "asap"}
    r = requests.post(f"{API}/orders", json=body)
    assert (r.status_code == 200) == st["pickup_open"], r.text
    if not st["pickup_open"]:
        assert "Restaurant fermé" in r.text
    body["requested_time"] = "03:07"  # never a valid slot
    assert requests.post(f"{API}/orders", json=body).status_code == 400
    if st["pickup_slots"]:
        body["requested_time"] = st["pickup_slots"][0]
        assert requests.post(f"{API}/orders", json=body).status_code == 200
    settings = requests.get(f"{API}/settings").json()
    assert settings["opening_hours"]["mon"] == "" and settings["opening_hours"]["tue"] == "17:00-22:00"
    assert settings["delivery_cutoff_minutes"] == 15


def test_first_delivery_manager_control_requires_manager(H):
    r = requests.put(f"{API}/settings/first-delivery", json={"lunch": "11:30"}, headers=H)
    assert r.status_code == 200 and r.json()["first_delivery"]["lunch"] == "11:30"
    assert requests.put(f"{API}/settings/first-delivery", json={"lunch": ""}, headers=H).status_code == 200
    assert requests.put(f"{API}/settings/first-delivery", json={"lunch": ""}).status_code == 401


def test_half_half_phone_only_and_pricing(H, menu):
    a, b = menu["Margherita"], menu["Diavola"]
    pa = next(s["price"] for s in a["sizes"] if s["key"] == "40")
    pb = next(s["price"] for s in b["sizes"] if s["key"] == "40")
    o = phone_order(H, menu, [{"product_id": a["id"], "quantity": 1, "size_key": "40", "half_product_id": b["id"], "half_removed_ingredient_ids": ["oignons"], "half_note": "bien cuite"}])
    assert o["items"][0]["unit_price"] == max(pa, pb) and o["items"][0]["half"]["name"]["fr"] == "Diavola"
    t = requests.get(f"{API}/orders/{o['id']}/ticket", headers=H).json()["text"]
    assert "MOITIE / MOITIE" in t and "1/2 MARGHERITA" in t and "1/2 DIAVOLA" in t and "- SANS OIGNONS" in t and "NOTE: BIEN CUITE" in t
    c = cust(H)
    web = {"type": "pickup", "items": [{"product_id": a["id"], "quantity": 1, "size_key": "40", "half_product_id": b["id"]}], "customer": {"first_name": c["first_name"], "phone": c["phone"]}, "requested_time": "asap"}
    r = requests.post(f"{API}/orders", json=web)
    assert r.status_code == 400  # never for customers (either hours or half rule)


def test_secrets_not_exposed(H):
    for j in requests.get(f"{API}/print-jobs?limit=20", headers=H).json():
        assert "api_key" not in str(j).lower()
    import subprocess
    out = subprocess.run(["grep", "-rl", "--exclude-dir=node_modules", "PRINTNODE", "/app/frontend/app", "/app/frontend/src"], capture_output=True, text=True).stdout
    assert out.strip() == ""

"""Security regression: every staff/admin/driver endpoint requires a server-side JWT (401) and the right role (403).
Run: pytest tests/test_security_iter8.py -n 0"""
import os
import pytest
import requests

API = os.environ.get("API_URL", "http://localhost:8001/api")
PINS = {"manager": "1234", "kitchen": "2345", "phone": "3456", "driver1": "1111", "driver2": "2222", "driver3": "3333"}


@pytest.fixture(scope="module")
def tok():
    out = {}
    for role, pin in PINS.items():
        r = requests.post(f"{API}/auth/staff/login", json={"pin": pin})
        assert r.status_code == 200, r.text
        assert r.json()["role"] == role
        out[role] = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return out


@pytest.fixture(scope="module")
def order(tok):
    menu = requests.get(f"{API}/menu").json()
    marg = next(p for p in menu["products"] if p["name"]["fr"] == "Margherita")
    body = {"type": "delivery", "items": [{"product_id": marg["id"], "quantity": 2, "size_key": "32"}],
            "customer": {"first_name": "Sec", "phone": "0790009999"}, "address": {"street": "Rue Test", "number": "1", "npa": "1723", "city": "Marly"},
            "requested_time": "asap"}
    r = requests.post(f"{API}/orders", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# (method, path, json, roles allowed)
def matrix(oid):
    return [
        ("GET", "/orders", None, {"manager", "kitchen"}),
        ("POST", f"/orders/{oid}/accept", {"minutes": 20}, {"manager", "kitchen"}),
        ("POST", f"/orders/{oid}/delay", {"minutes": 5}, {"manager", "kitchen"}),
        ("POST", f"/orders/{oid}/status", {"status": "preparing"}, {"manager", "kitchen"}),
        ("POST", f"/orders/{oid}/assign", {"driver": "Livreur 1"}, {"manager", "kitchen"}),
        ("POST", f"/orders/{oid}/print", {"force": True}, {"manager", "kitchen"}),
        ("GET", f"/orders/{oid}/receipt", None, {"manager", "kitchen"}),
        ("POST", f"/orders/{oid}/receipt/print", {"force": True}, {"manager", "kitchen"}),
        ("GET", "/print-jobs", None, {"manager", "kitchen"}),
        ("GET", f"/orders/{oid}/ticket", None, {"manager", "kitchen", "phone"}),
        ("GET", "/customers/search?phone=079", None, {"manager", "phone"}),
        ("POST", "/customers", {"first_name": "X", "phone": "0000000"}, {"manager", "phone"}),
        ("POST", "/customers/000000000000000000000000/addresses", {"street": "a", "npa": "1", "city": "b"}, {"manager", "phone"}),
        ("POST", "/phone-orders", {"type": "pickup", "items": [], "customer": {"first_name": "X", "phone": "0"}}, {"manager", "phone"}),
        ("PUT", "/settings", {"delivery_fee": "not-a-number"}, {"manager"}),  # 422 for manager, never overwrites settings
        ("POST", "/products", {}, {"manager"}),
        ("PATCH", "/products/000000000000000000000000", {"available": True}, {"manager"}),
        ("DELETE", "/products/000000000000000000000000", None, {"manager"}),
        ("POST", "/extras", {}, {"manager"}),
        ("POST", "/categories", {}, {"manager"}),
        ("POST", "/uploads/product-photo", None, {"manager"}),
        ("GET", "/reports/closing", None, {"manager"}),
        ("POST", "/reports/closing", {"date": "2026-01-01", "driver": "Livreur 1"}, {"manager"}),
        ("GET", "/reports/sources", None, {"manager"}),
        ("GET", "/auth/staff/roles", None, {"manager"}),
        ("PUT", "/auth/staff/pins", {"role": "nope", "pin": "0000"}, {"manager"}),  # 400 for manager, no PIN changed
        ("GET", "/driver/orders", None, {"driver1", "driver2", "driver3"}),
    ]


def call(method, path, json=None, headers=None):
    return requests.request(method, f"{API}{path}", json=json, headers=headers or {})


def test_unauthenticated_requests_return_401(order):
    for method, path, body, _ in matrix(order["id"]) + [("POST", f"/driver/orders/{order['id']}/depart", None, set())]:
        r = call(method, path, body)
        assert r.status_code == 401, f"{method} {path} -> {r.status_code}"
    bad = {"Authorization": "Bearer not.a.jwt"}
    assert call("GET", "/orders", headers=bad).status_code == 401


def test_wrong_roles_return_403(order, tok):
    for method, path, body, allowed in matrix(order["id"]):
        for role in PINS:
            if role in allowed:
                continue
            r = call(method, path, body, tok[role])
            assert r.status_code == 403, f"{role} {method} {path} -> {r.status_code} {r.text[:80]}"


def test_allowed_roles_pass_auth_layer(order, tok):
    """Allowed roles must never get 401/403 (business validation errors like 400/404/409/422 are fine)."""
    for method, path, body, allowed in matrix(order["id"]):
        for role in allowed:
            r = call(method, path, body, tok[role])
            assert r.status_code not in (401, 403), f"{role} {method} {path} -> {r.status_code}"


def test_customer_token_is_not_a_staff_token(order):
    r = requests.post(f"{API}/auth/register", json={"first_name": "Cust", "phone": "0790008888", "password": "secret123"})
    if r.status_code == 409:
        r = requests.post(f"{API}/auth/login", json={"phone": "0790008888", "password": "secret123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert call("GET", "/orders", headers=h).status_code == 401
    assert call("GET", "/reports/closing", headers=h).status_code == 401


def test_customer_facing_endpoints_stay_public(order):
    assert requests.get(f"{API}/menu").status_code == 200
    assert requests.get(f"{API}/settings").status_code == 200
    assert requests.get(f"{API}/orders/{order['id']}").status_code == 200
    r = requests.get(f"{API}/orders?ids={order['id']}")
    assert r.status_code == 200 and len(r.json()) == 1


def test_driver_sees_only_own_orders(order, tok):
    requests.post(f"{API}/orders/{order['id']}/accept", json={"minutes": 20}, headers=tok["manager"])
    r = requests.post(f"{API}/orders/{order['id']}/assign", json={"driver": "Livreur 1"}, headers=tok["manager"])
    assert r.status_code == 200, r.text
    mine = requests.get(f"{API}/driver/orders", headers=tok["driver1"]).json()
    others = requests.get(f"{API}/driver/orders", headers=tok["driver2"]).json()
    assert any(o["id"] == order["id"] for o in mine)
    assert all(o["id"] != order["id"] for o in others)
    assert all(o["driver"] == "Livreur 2" for o in others)
    assert requests.post(f"{API}/driver/orders/{order['id']}/depart", headers=tok["driver2"]).status_code == 403
    assert requests.post(f"{API}/driver/orders/{order['id']}/collect", headers=tok["driver3"]).status_code == 403


def test_no_secrets_in_frontend_source():
    import subprocess
    root = "/app/frontend"
    for needle in ("EXPO_PUBLIC_STAFF_PIN", "PRINTNODE", "JWT_SECRET", "EMERGENT_LLM_KEY"):
        out = subprocess.run(["grep", "-rl", "--exclude-dir=node_modules", "--exclude-dir=.expo", needle, f"{root}/app", f"{root}/src", f"{root}/.env"], capture_output=True, text=True).stdout
        assert out.strip() == "", f"{needle} found in frontend: {out}"

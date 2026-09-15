"""
Iter 8 security spot-checks (fast smoke).
Full coverage lives in test_security_iter8.py (110 tests).
"""
import os
import requests
import pytest

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
if BASE:
    BASE = BASE.rstrip("/")


@pytest.fixture(scope="module")
def base():
    assert BASE, "EXPO_PUBLIC_BACKEND_URL not set"
    return BASE


def _login(base, pin):
    r = requests.post(f"{base}/api/auth/staff/login", json={"pin": pin}, timeout=10)
    assert r.status_code == 200, f"login failed for pin {pin}: {r.status_code} {r.text}"
    return r.json()["access_token"]


# public menu still works
def test_public_menu(base):
    r = requests.get(f"{base}/api/menu", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "categories" in d and "products" in d


# /orders unauth -> 401
def test_orders_requires_auth(base):
    r = requests.get(f"{base}/api/orders", timeout=10)
    assert r.status_code == 401


# /orders with kitchen -> 200
def test_orders_kitchen_allowed(base):
    tok = _login(base, "2345")
    r = requests.get(f"{base}/api/orders", headers={"Authorization": f"Bearer {tok}"}, timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# /reports/closing kitchen -> 403
def test_closing_kitchen_forbidden(base):
    tok = _login(base, "2345")
    r = requests.get(f"{base}/api/reports/closing", headers={"Authorization": f"Bearer {tok}"}, timeout=10)
    assert r.status_code == 403


# /reports/closing manager -> 200
def test_closing_manager_allowed(base):
    tok = _login(base, "1234")
    r = requests.get(f"{base}/api/reports/closing", headers={"Authorization": f"Bearer {tok}"}, timeout=10)
    assert r.status_code == 200

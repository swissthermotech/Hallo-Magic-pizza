"""Shared test helper: driver PINs are temporary shift PINs since iteration 10."""
import os
import requests

API = os.environ.get("API_URL", "http://localhost:8001/api")
_CACHE = {}


def driver_pin(role: str) -> str:
    """Opens (once per test session) a shift for the driver role and returns its 6-digit PIN."""
    if role in _CACHE and requests.post(f"{API}/auth/staff/login", json={"pin": _CACHE[role]}).status_code != 200:
        del _CACHE[role]  # shift was closed/reopened by another test -> open a fresh one
    if role not in _CACHE:
        mgr = requests.post(f"{API}/auth/staff/login", json={"pin": "1234"}).json()["access_token"]
        r = requests.post(f"{API}/auth/staff/shifts/{role}/open", json={"name": f"Test {role[-1]}"}, headers={"Authorization": f"Bearer {mgr}"})
        _CACHE[role] = r.json()["pin"]
    return _CACHE[role]

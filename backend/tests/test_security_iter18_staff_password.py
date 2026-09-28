"""Iteration 18 – Staff password auth (PIN → password) preview tests.
Runs read-only checks against the PREVIEW sandbox backend using python requests.
Does NOT create/print orders, does NOT change any settings/products/customers.
Cleans staff_login_attempts before AND after to keep UI unblocked.
"""
import os
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"] if "EXPO_PUBLIC_BACKEND_URL" in os.environ else None
# Fallback to frontend/.env
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"')
                break
BASE_URL = BASE_URL.rstrip("/") + "/api"
assert "emergent.host" not in BASE_URL, "refusing to run against production"

MGR_PWD = "Preview-Manager-2026!"
KITCHEN_PWD = "Preview-Cuisine-2026!"
PHONE_PWD = "Preview-Phone-2026!"


@pytest.fixture(scope="module")
def mongo():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module", autouse=True)
def clear_locks(mongo):
    mongo.staff_login_attempts.delete_many({})
    yield
    mongo.staff_login_attempts.delete_many({})


@pytest.fixture(scope="module")
def s():
    return requests.Session()


def login(s, secret):
    return s.post(f"{BASE_URL}/auth/staff/login", json={"password": secret}, timeout=15)


# ── 1. legacy PIN rejected now that role has password_hash ──────────────────
def test_legacy_pin_rejected(s, mongo):
    mongo.staff_login_attempts.delete_many({})
    r = login(s, "1234")
    assert r.status_code == 401, r.text


# ── 2. brute force -> 429 after 5th, correct password also blocked ──────────
def test_lockout_after_5_failures(s, mongo):
    mongo.staff_login_attempts.delete_many({})
    codes = [login(s, f"wrong-{i}").status_code for i in range(4)]
    assert codes == [401, 401, 401, 401], codes
    r = login(s, "wrong-final")
    assert r.status_code == 429, r.text
    # Even correct password is blocked while locked
    r = login(s, MGR_PWD)
    assert r.status_code == 429, r.text
    # Confirm lockout doc persisted
    doc = mongo.staff_login_attempts.find_one({})
    assert doc is not None
    assert doc.get("locked_until") is not None
    # Clear lock and confirm login works again
    mongo.staff_login_attempts.delete_many({})
    r = login(s, MGR_PWD)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "manager"


# ── 3. manager token (obtained fresh) ───────────────────────────────────────
@pytest.fixture(scope="module")
def manager_token(s, mongo):
    mongo.staff_login_attempts.delete_many({})
    r = login(s, MGR_PWD)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def kitchen_token(s, mongo):
    mongo.staff_login_attempts.delete_many({})
    r = login(s, KITCHEN_PWD)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ── 4. weak password refused (400) ──────────────────────────────────────────
def test_weak_password_refused(s, manager_token):
    H = {"Authorization": f"Bearer {manager_token}"}
    for weak in ["short1!", "onlyletters!!", "NoSpecial123", "1234567890!"]:
        r = s.put(f"{BASE_URL}/auth/staff/password", json={"role": "phone", "password": weak}, headers=H, timeout=15)
        assert r.status_code == 400, f"{weak!r} -> {r.status_code}: {r.text[:150]}"


# ── 5. driver role rejected for password (400) ──────────────────────────────
def test_driver_role_rejected(s, manager_token):
    H = {"Authorization": f"Bearer {manager_token}"}
    r = s.put(f"{BASE_URL}/auth/staff/password", json={"role": "driver1", "password": MGR_PWD}, headers=H, timeout=15)
    assert r.status_code == 400, r.text


# ── 6. kitchen token cannot set passwords (403) ─────────────────────────────
def test_kitchen_cannot_manage_passwords(s, kitchen_token):
    H = {"Authorization": f"Bearer {kitchen_token}"}
    r = s.put(f"{BASE_URL}/auth/staff/password", json={"role": "phone", "password": "AnyStrongPwd-9!"}, headers=H, timeout=15)
    assert r.status_code == 403, r.text


# ── 7. GET /auth/staff/roles shows credential=password for the three ────────
def test_roles_credential_kinds(s, manager_token):
    H = {"Authorization": f"Bearer {manager_token}"}
    r = s.get(f"{BASE_URL}/auth/staff/roles", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    creds = {x["role"]: x["credential"] for x in r.json()}
    assert creds.get("manager") == "password", creds
    assert creds.get("kitchen") == "password", creds
    assert creds.get("phone") == "password", creds


# ── 8. kitchen and phone passwords log in with correct role ────────────────
def test_kitchen_login(s, mongo):
    mongo.staff_login_attempts.delete_many({})
    r = login(s, KITCHEN_PWD)
    assert r.status_code == 200
    assert r.json()["role"] == "kitchen"


def test_phone_login(s, mongo):
    mongo.staff_login_attempts.delete_many({})
    r = login(s, PHONE_PWD)
    assert r.status_code == 200
    assert r.json()["role"] == "phone"

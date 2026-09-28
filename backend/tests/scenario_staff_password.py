"""Staff password authentication scenario – runs against the PREVIEW backend only (sandbox DB).
Never run against production. Creates no order, prints nothing, sends no e-mail.

Checks: legacy PIN still works (migration safety) -> lockout after 5 failures (429) even with the right secret ->
lock cleared -> manager sets its own password (fresh token returned, old token revoked) -> weak passwords rejected ->
old PIN rejected -> new password works -> kitchen password set -> duplicate password refused -> /roles credential flags.
"""
import os
import sys
import time

import httpx
from pymongo import MongoClient

BASE = os.environ.get("BASE", "http://localhost:8001/api")
assert "emergent.host" not in BASE, "refusing to run against production"
MANAGER_OLD = os.environ.get("MANAGER_OLD", "1234")
MANAGER_NEW = os.environ.get("MANAGER_NEW", "Preview-Manager-2026!")
KITCHEN_NEW = os.environ.get("KITCHEN_NEW", "Preview-Cuisine-2026!")

mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
c = httpx.Client(base_url=BASE, timeout=30)
ok = 0


def check(name, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond:
        sys.exit(1)
    ok += 1


def login(secret):
    return c.post("/auth/staff/login", json={"password": secret})


mongo.staff_login_attempts.delete_many({})  # clean slate (sandbox)

# 1. legacy PIN still valid before migration
r = login(MANAGER_OLD)
check("legacy manager PIN accepted", r.status_code == 200 and r.json()["role"] == "manager", r.text[:120])
old_token = r.json()["access_token"]
check("token has expires_at", bool(r.json().get("expires_at")))

# 2. brute force: 4 failures -> 401 with attempts left, 5th -> 429, then even the right secret is blocked
codes = [login("wrong-%d" % i).status_code for i in range(4)]
check("first 4 failures are 401", codes == [401] * 4, str(codes))
r = login("wrong-5")
check("5th failure -> 429 locked", r.status_code == 429, r.text[:120])
r = login(MANAGER_OLD)
check("correct secret blocked while locked (429)", r.status_code == 429, r.text[:120])
doc = mongo.staff_login_attempts.find_one({})
check("lockout persisted server-side with locked_until", doc is not None and doc.get("locked_until") is not None and len(doc["_id"]) == 64)
mongo.staff_login_attempts.delete_many({})  # simulate the 15 minutes elapsing
r = login(MANAGER_OLD)
check("login works again after lock cleared", r.status_code == 200)
old_token = r.json()["access_token"]
H = {"Authorization": f"Bearer {old_token}"}

# 3. weak passwords refused (server-side)
for weak in ["short1!", "onlyletters!!", "NoSpecial123", "1234567890!", " Space-Start1!"]:
    r = c.put("/auth/staff/password", json={"role": "manager", "password": weak}, headers=H)
    check(f"weak password refused: {weak!r}", r.status_code == 400, r.text[:100])
r = c.put("/auth/staff/password", json={"role": "driver1", "password": MANAGER_NEW}, headers=H)
check("driver roles cannot get a password (shift codes)", r.status_code == 400)

# 4. manager sets own password -> fresh token, old token revoked, old PIN dead
r = c.put("/auth/staff/password", json={"role": "manager", "password": MANAGER_NEW}, headers=H)
check("manager password set", r.status_code == 200 and r.json().get("access_token"), r.text[:120])
new_token = r.json()["access_token"]
time.sleep(1.1)
r = c.get("/auth/staff/me", headers=H)
check("old manager token revoked after password change (401)", r.status_code == 401, r.text[:100])
r = c.get("/auth/staff/me", headers={"Authorization": f"Bearer {new_token}"})
check("fresh token still valid", r.status_code == 200 and r.json()["role"] == "manager")
doc = mongo.staff_auth.find_one({"_id": "manager"})
check("legacy pin_hash removed, password_hash stored as argon2", "pin_hash" not in doc and doc["password_hash"].startswith("$argon2"))
check("plaintext never stored", MANAGER_NEW not in str(doc))
r = login(MANAGER_OLD)
check("old PIN rejected", r.status_code == 401)
r = login(MANAGER_NEW)
check("new password logs in as manager", r.status_code == 200 and r.json()["role"] == "manager")
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

# 5. other roles: kitchen password, duplicate refused, roles listing
r = c.put("/auth/staff/password", json={"role": "kitchen", "password": MANAGER_NEW}, headers=H)
check("same password for two roles refused (409)", r.status_code == 409)
r = c.put("/auth/staff/password", json={"role": "kitchen", "password": KITCHEN_NEW}, headers=H)
check("kitchen password set (no token returned for other role)", r.status_code == 200 and not r.json().get("access_token"))
r = login(KITCHEN_NEW)
check("kitchen password logs in as kitchen", r.status_code == 200 and r.json()["role"] == "kitchen")
r = login("2345")
check("kitchen legacy PIN rejected", r.status_code == 401)
r = c.get("/auth/staff/roles", headers=H)
creds = {x["role"]: x["credential"] for x in r.json()}
check("roles report credential kinds", creds["manager"] == "password" and creds["kitchen"] == "password" and creds["phone"] in ("pin", "password"), str(creds))
r = c.get("/auth/staff/roles", headers={"Authorization": f"Bearer {login(KITCHEN_NEW).json()['access_token']}"})
check("kitchen cannot manage passwords (403)", r.status_code == 403)
mongo.staff_login_attempts.delete_many({})
print(f"\nALL {ok} CHECKS PASSED")

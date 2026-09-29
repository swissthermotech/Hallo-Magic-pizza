"""Customer account deletion (right to erasure) – PREVIEW sandbox only. Never run against production.
Creates a throwaway customer + one order directly in the sandbox DB (no API order creation -> nothing is printed),
then exercises DELETE /api/auth/me and verifies anonymisation, token invalidation and the untouched staff auth."""
import os
import sys
from datetime import datetime, timezone

import httpx
from bson import ObjectId
from pymongo import MongoClient

BASE = os.environ.get("BASE", "http://localhost:8001/api")
assert "emergent.host" not in BASE, "refusing to run against production"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
c = httpx.Client(base_url=BASE, timeout=30)
ok = 0


def check(name, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond:
        sys.exit(1)
    ok += 1


PHONE = "079 000 99 77"
db.users.delete_many({"phone": {"$in": ["0790009977", PHONE]}})
r = c.post("/auth/register", json={"first_name": "Erasure", "last_name": "Test", "phone": PHONE, "email": "erasure@example.com", "password": "Erase-Me-2026!"})
check("register throwaway customer", r.status_code == 201, r.text[:120])
tok = r.json()["access_token"]
uid = r.json()["user"]["id"]
H = {"Authorization": f"Bearer {tok}"}

# one historical (completed) order + one active order inserted directly (nothing is printed)
now = datetime.now(timezone.utc)
base = {"order_number": 999901, "type": "delivery", "source": "web", "items": [{"name": "Test", "qty": 1, "unit_price": 20.0, "total": 20.0}],
        "subtotal": 20.0, "delivery_fee": 0.0, "total": 20.0, "created_at": now, "status_history": [], "user_id": uid, "legacy": True,
        "customer": {"first_name": "Erasure", "last_name": "Test", "phone": "0790009977", "email": "erasure@example.com"},
        "address": {"street": "Rue Secrète", "number": "7", "npa": "1723", "city": "Marly", "instructions": "code 1234"}, "general_note": "sonnez 2x"}
done_id = db.orders.insert_one({**base, "status": "completed"}).inserted_id
active_id = db.orders.insert_one({**base, "order_number": 999902, "status": "accepted", "user_id": None, "customer": {**base["customer"]}}).inserted_id
db.print_jobs.insert_one({"order_id": str(done_id), "order_number": 999901, "kind": "kitchen", "status": "simulated", "content": "CLIENT: ERASURE TEST TEL: 0790009977", "created_at": now})

r = c.request("DELETE", "/auth/me", json={"password": "wrong-password"}, headers=H)
check("wrong password -> 403, nothing deleted", r.status_code == 403 and db.users.find_one({"_id": ObjectId(uid)}) is not None)
r = c.request("DELETE", "/auth/me", json={"password": "Erase-Me-2026!"}, headers=H)
check("active order (matched by phone) blocks deletion -> 409", r.status_code == 409, r.text[:120])
db.orders.update_one({"_id": active_id}, {"$set": {"status": "cancelled"}})
r = c.request("DELETE", "/auth/me", json={"password": "Erase-Me-2026!"}, headers=H)
check("deletion succeeds", r.status_code == 200 and r.json()["anonymised_orders"] == 2, r.text[:120])
check("user document deleted", db.users.find_one({"_id": ObjectId(uid)}) is None)
check("old token rejected (401)", c.get("/auth/me", headers=H).status_code == 401)
check("old token cannot list orders (401)", c.get("/me/orders", headers=H).status_code == 401)
o = db.orders.find_one({"_id": done_id})
check("order history kept (number/total/status/items)", o["order_number"] == 999901 and o["total"] == 20.0 and o["status"] == "completed" and len(o["items"]) == 1)
check("personal data removed", o["customer"] == {"first_name": "Client supprimé", "last_name": "", "phone": "", "email": None} and "user_id" not in o and o.get("general_note") is None)
check("address street/number/instructions removed, NPA/city kept", o["address"]["street"] == "" and o["address"]["number"] == "" and o["address"]["instructions"] is None and o["address"]["npa"] == "1723" and o["address"]["city"] == "Marly")
o2 = db.orders.find_one({"_id": active_id})
check("phone-matched guest order anonymised too", o2["customer"]["phone"] == "" and o2["customer"]["first_name"] == "Client supprimé")
pj = db.print_jobs.find_one({"order_id": str(done_id)})
check("stored ticket copy redacted", "0790009977" not in pj["content"] and pj.get("redacted_at") is not None)
check("marketing consent removed", db.marketing_consents.find_one({"phone": "0790009977"}) is None)
r = c.post("/auth/login", json={"phone": PHONE, "password": "Erase-Me-2026!"})
check("login after deletion fails", r.status_code in (401, 404), r.text[:80])
# staff auth untouched
r = c.post("/auth/staff/login", json={"password": "Preview-Manager-2026!"})
check("staff manager login still works", r.status_code == 200 and r.json()["role"] == "manager")
mt = r.json()["access_token"]
cust = c.get("/customers?q=supprim&marketing=all", headers={"Authorization": f"Bearer {mt}"}).json()
check("Manager customers view shows one aggregate 'Clients supprimés' row", any(p.get("first_name") == "Clients supprimés" for p in cust["customers"]))
# cleanup of the sandbox test orders
db.orders.delete_many({"_id": {"$in": [done_id, active_id]}})
db.print_jobs.delete_many({"order_id": {"$in": [str(done_id), str(active_id)]}})
db.staff_login_attempts.delete_many({})
print(f"\nALL {ok} CHECKS PASSED (sandbox cleaned)")

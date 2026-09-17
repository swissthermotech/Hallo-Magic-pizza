"""Manual scenario (NOT a pytest suite – never accepts orders through the API, so nothing is printed).
Driver identity: assignment snapshot, delivery attributed to the performer, closing per identity, no renaming.
Uses Livreur 3; the original open shift is restored (same PIN) and all test docs are deleted at the end."""
import asyncio
import os
import sys
from datetime import datetime, timezone

import requests
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
API = "http://localhost:8001/api"
MARK = "identity-scenario"


def login(pin):
    r = requests.post(f"{API}/auth/staff/login", json={"pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    H = login("1234")
    orig = await db.driver_shifts.find_one({"role": "driver3", "closed_at": None})
    assert orig, "Livreur 3 must have an open shift"
    tmpl = await db.orders.find_one({"type": "delivery", "status": {"$in": ["completed", "delivered"]}, "driver": {"$ne": None}})
    created = []

    async def mk(n):
        d = dict(tmpl)
        d.pop("_id")
        d.update({"order_number": 900000 + n, "status": "accepted", "driver": None, "driver_name": None, "shift_id": None, "assigned_at": None,
                  "delivered_at": None, "picked_up_at": None, "out_for_delivery_at": None, "collection_method": "cash", "payment_collected": False,
                  "created_at": datetime.now(timezone.utc), "printed": True, "print_status": "skipped_test", "client_request_id": None,
                  "status_history": [], "notifications": [], "test_marker": MARK})
        d.pop("client_request_id")
        res = await db.orders.insert_one(d)
        created.append(res.inserted_id)
        return str(res.inserted_id)

    try:
        a, b = await mk(1), await mk(2)
        # Person 1 (Marco) on Livreur 3
        s1 = requests.post(f"{API}/auth/staff/shifts/driver3/open", json={"name": "Marco"}, headers=H).json()
        assert requests.get(f"{API}/auth/staff/drivers", headers=H).json()[2]["label"] == "Livreur 3 — Marco"
        oa = requests.post(f"{API}/orders/{a}/assign", json={"driver": "Livreur 3"}, headers=H).json()
        assert oa["driver_name"] == "Marco" and oa["shift_id"], oa
        D1 = login(s1["pin"])
        requests.post(f"{API}/driver/orders/{a}/depart", headers=D1).raise_for_status()
        oa = requests.post(f"{API}/driver/orders/{a}/delivered", headers=D1).json()
        assert oa["status"] == "completed" and oa["driver_name"] == "Marco", oa
        # Slot re-opened for person 2 (Aliou-T) – order B assigned under Marco but DELIVERED by Aliou-T
        ob = requests.post(f"{API}/orders/{b}/assign", json={"driver": "Livreur 3"}, headers=H).json()
        assert ob["driver_name"] == "Marco"
        s2 = requests.post(f"{API}/auth/staff/shifts/driver3/open", json={"name": "Aliou-T"}, headers=H).json()
        assert requests.get(f"{API}/auth/staff/drivers", headers=H).json()[2]["label"] == "Livreur 3 — Aliou-T"
        D2 = login(s2["pin"])
        requests.post(f"{API}/driver/orders/{b}/depart", headers=D2).raise_for_status()
        ob = requests.post(f"{API}/driver/orders/{b}/delivered", headers=D2).json()
        assert ob["driver_name"] == "Aliou-T", ob
        oa2 = requests.get(f"{API}/orders/{a}", headers=H).json()
        assert oa2["driver_name"] == "Marco", "historical delivery must NOT be renamed"
        # Closing: one entry per identity, separate closings
        rep = requests.get(f"{API}/reports/closing", headers=H).json()["drivers"]
        l3 = [d for d in rep if d["driver"] == "Livreur 3"]
        labels = [d["label"] for d in l3]
        assert len(labels) == len(set(labels)), labels
        marco = next(d for d in l3 if d["driver_name"] == "Marco")
        aliou = next(d for d in l3 if d["driver_name"] == "Aliou-T")
        assert aliou["is_current"] and not marco["is_current"]
        assert 900001 in [o["order_number"] for o in marco["orders"]] and 900002 in [o["order_number"] for o in aliou["orders"]]
        assert 900002 not in [o["order_number"] for o in marco["orders"]]
        requests.post(f"{API}/reports/closing", json={"date": rep and marco["date"], "driver": "Livreur 3", "driver_name": "Marco", "actual_cash": 12.5}, headers=H).raise_for_status()
        rep = requests.get(f"{API}/reports/closing", headers=H).json()["drivers"]
        marco = next(d for d in rep if d["driver"] == "Livreur 3" and d["driver_name"] == "Marco")
        aliou = next(d for d in rep if d["driver"] == "Livreur 3" and d["driver_name"] == "Aliou-T")
        assert marco["actual_cash"] == 12.5 and aliou["actual_cash"] is None, (marco["actual_cash"], aliou["actual_cash"])
        # kitchen role can read the slot labels (needed on the dashboard), no PIN data
        K = login("2345")
        dr = requests.get(f"{API}/auth/staff/drivers", headers=K)
        assert dr.status_code == 200 and "pin" not in dr.text and "pin_hash" not in dr.text
        assert requests.get(f"{API}/auth/staff/shifts", headers=K).status_code == 403
        print("SCENARIO OK – labels for Livreur 3 today:", labels)
    finally:
        # Restore: delete scenario orders, closing and shifts; re-open the original shift (same PIN as before)
        await db.orders.delete_many({"test_marker": MARK})
        await db.closings.delete_many({"driver": "Livreur 3", "driver_name": {"$in": ["Marco", "Aliou-T"]}})
        await db.driver_shifts.delete_many({"role": "driver3", "opened_at": {"$gt": orig["opened_at"]}})
        await db.driver_shifts.update_one({"_id": orig["_id"]}, {"$set": {"closed_at": None}, "$unset": {"closed_reason": ""}})
        restored = await db.driver_shifts.find_one({"role": "driver3", "closed_at": None})
        assert restored and restored["_id"] == orig["_id"] and restored["name"] == orig["name"]
        print("restored Livreur 3 shift:", restored["name"], "| leftover scenario orders:", await db.orders.count_documents({"test_marker": MARK}))
        print("real print jobs sent:", await db.print_jobs.count_documents({"status": "sent"}))


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)

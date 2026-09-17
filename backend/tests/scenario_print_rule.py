"""Manual scenario (NOT pytest) – printing rule + scheduled orders. NEVER accepts a printable order:
the only accept test uses an order pre-flagged printed=True (do_print refuses, nothing reaches PrintNode).
All scenario orders are deleted at the end."""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from zoneinfo import ZoneInfo

load_dotenv("/app/backend/.env")
API = "http://localhost:8001/api"
TZ = ZoneInfo("Europe/Zurich")
MARK = "print-rule-scenario"


def login(pin):
    return {"Authorization": f"Bearer {requests.post(f'{API}/auth/staff/login', json={'pin': pin}).json()['access_token']}"}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    sent_before = await db.print_jobs.count_documents({"status": "sent"})
    H, P = login("1234"), login("3456")
    prod = requests.get(f"{API}/products").json()[0]
    item = {"product_id": prod["id"], "quantity": 1, "size_key": (prod["sizes"] or [{}])[0].get("key")}
    cust = {"first_name": "Scenario", "last_name": "Test", "phone": "0000000000"}
    created = []
    try:
        st = requests.get(f"{API}/settings/ordering").json()
        assert "days" in st and st["days"], st.keys()
        print("ordering days:", [(d["date"], d["is_today"], len(d["pickup_slots"]), len(d["delivery_slots"])) for d in st["days"]])
        # 1) Phone order -> PENDING, no accepted_at, no print job
        r = requests.post(f"{API}/phone-orders", json={"type": "pickup", "items": [item], "customer": cust, "station": 1, "payment_method": "cash", "minutes": 25}, headers=P)
        assert r.status_code == 200, r.text
        po = r.json(); created.append(po["id"])
        assert po["status"] == "pending" and not po.get("accepted_at") and not po["printed"], po["status"]
        assert po["requested_time"] and po["requested_time"] != "asap"  # "in 25 min" stored as requested time
        assert await db.print_jobs.count_documents({"order_id": po["id"]}) == 0
        # manual print on pending -> refused
        assert requests.post(f"{API}/orders/{po['id']}/print", json={}, headers=H).status_code == 409
        # 2) Scheduled web order for a future day: valid slot accepted, invalid slot / closed day / >7 days refused
        future = next(d for d in st["days"] if not d["is_today"])
        slot = future["pickup_slots"][0]
        r = requests.post(f"{API}/orders", json={"type": "pickup", "items": [item], "customer": cust, "requested_time": slot, "requested_date": future["date"]})
        assert r.status_code == 200, r.text
        so = r.json(); created.append(so["id"])
        assert so["status"] == "pending" and so["requested_date"] == future["date"] and so["scheduled_for"] and not so["printed"]
        assert await db.print_jobs.count_documents({"order_id": so["id"]}) == 0
        assert requests.post(f"{API}/orders", json={"type": "pickup", "items": [item], "customer": cust, "requested_time": "03:15", "requested_date": future["date"]}).status_code == 400
        assert requests.post(f"{API}/orders", json={"type": "pickup", "items": [item], "customer": cust, "requested_time": "asap", "requested_date": future["date"]}).status_code == 400
        far = (datetime.now(TZ) + timedelta(days=12)).date().isoformat()
        assert requests.post(f"{API}/orders", json={"type": "pickup", "items": [item], "customer": cust, "requested_time": "12:00", "requested_date": far}).status_code == 400
        assert requests.post(f"{API}/orders", json={"type": "pickup", "items": [item], "customer": cust, "requested_time": "12:00", "requested_date": "2020-01-01"}).status_code == 400
        # scheduled order visible in the staff list
        ids = [o["id"] for o in requests.get(f"{API}/orders", headers=H).json()]
        assert so["id"] in ids and po["id"] in ids
        # ticket preview for the scheduled order shows the date block (no print)
        tk = requests.get(f"{API}/orders/{so['id']}/ticket", headers=H).json()["text"]
        assert "COMMANDE PROGRAMMEE" in tk and "PAS POUR AUJOURD'HUI" in tk and future["date"][8:10] in tk, tk
        # 3) Accept idempotency WITHOUT printing: pre-flag printed=True so do_print refuses (409 swallowed)
        await db.orders.update_one({"_id": __import__("bson").ObjectId(so["id"])}, {"$set": {"printed": True, "print_status": "skipped_test", "test_marker": MARK}})
        a1 = requests.post(f"{API}/orders/{so['id']}/accept", json={"time": slot}, headers=H)
        a2 = requests.post(f"{API}/orders/{so['id']}/accept", json={"time": slot}, headers=H)
        assert a1.status_code == 200 and a2.status_code == 400, (a1.status_code, a2.status_code)
        acc = a1.json()
        ready = datetime.fromisoformat(acc["estimated_ready_at"].replace("Z", "+00:00")).astimezone(TZ)
        assert ready.date().isoformat() == future["date"] and ready.strftime("%H:%M") == slot, ready
        assert await db.print_jobs.count_documents({"order_id": so["id"]}) == 0
        print("SCENARIO OK – phone pending:", po["order_number"], "| scheduled:", so["order_number"], future["date"], slot, "-> accepted for", ready.isoformat())
    finally:
        from bson import ObjectId
        await db.orders.delete_many({"_id": {"$in": [ObjectId(i) for i in created]}})
        print("leftover scenario orders:", await db.orders.count_documents({"customer.phone": "0000000000", "customer.first_name": "Scenario"}))
        print("real print jobs before/after:", sent_before, await db.print_jobs.count_documents({"status": "sent"}))


asyncio.run(main())

"""Snapshot the full original document, flip to pending, then after test to restore."""
import os
import sys
import json
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
OID = ObjectId("6ab911a41640440ce55631b1")
SNAP = "/tmp/order_6ab911a41640440ce55631b1.bson.json"

c = MongoClient(os.environ["MONGO_URL"])
db = c[os.environ["DB_NAME"]]


def snapshot():
    doc = db.orders.find_one({"_id": OID})
    assert doc is not None, "order not found"
    # bson default -> store as extended json via bson.json_util
    from bson import json_util
    with open(SNAP, "w") as f:
        f.write(json_util.dumps(doc))
    print(f"snapshotted -> {SNAP}; status={doc['status']}")


def set_pending():
    db.orders.update_one(
        {"_id": OID},
        {"$set": {"status": "pending"}, "$unset": {"accepted_at": "", "estimated_ready_at": ""}},
    )
    print("set status=pending")


def set_accepted():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # match existing naive datetimes
    eta = now + timedelta(minutes=25)
    db.orders.update_one(
        {"_id": OID},
        {
            "$set": {"status": "accepted", "accepted_at": now, "estimated_ready_at": eta},
            "$push": {"status_history": {"status": "accepted", "at": now}},
        },
    )
    print(f"set status=accepted; eta={eta.isoformat()}")


def restore():
    from bson import json_util
    with open(SNAP, "r") as f:
        doc = json_util.loads(f.read())
    db.orders.replace_one({"_id": OID}, doc, upsert=True)
    doc = db.orders.find_one({"_id": OID})
    print(f"restored -> status={doc['status']} history_len={len(doc.get('status_history', []))}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"snapshot": snapshot, "pending": set_pending, "accept": set_accepted, "restore": restore}.get(
        cmd, lambda: print(db.orders.find_one({"_id": OID}, {"status": 1, "accepted_at": 1, "estimated_ready_at": 1}))
    )()

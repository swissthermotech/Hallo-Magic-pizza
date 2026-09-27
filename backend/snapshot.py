"""One-time snapshot import into a FRESH production database.

Why: the preview backend keeps all live data in its local MongoDB; a permanent Emergent deployment starts on an
EMPTY managed MongoDB that the startup seed fills with the default menu. This module lets the manager replace
that fresh default state with an exact copy of the preview data – and nothing else:

  * manager JWT **and** the secret X-Import-Token (SNAPSHOT_IMPORT_TOKEN in the backend env) are both required;
  * an import session can only be opened on a FRESH database (no orders, no customers, no closings);
  * every collection is replaced atomically per collection, only while a session is open (max 60 min);
  * the source (preview) database is never touched – the export is a plain read.
"""
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from bson import json_util
from fastapi import APIRouter, Body, Depends, Header, HTTPException

from database import db

router = APIRouter(prefix="/admin/snapshot")

# Everything the app persists (order matters only for readability – the import is per collection)
COLLECTIONS = ["counters", "categories", "products", "extras", "settings", "staff_auth", "users", "orders",
               "print_jobs", "closings", "driver_shifts", "marketing_consents"]
SESSION_ID = "snapshot_import"
SESSION_MAX = timedelta(minutes=60)


def _manager():
    import staff_auth
    return staff_auth.require_roles("manager")


def _token(x_import_token: str = Header(default="")):
    expected = os.environ.get("SNAPSHOT_IMPORT_TOKEN", "")
    if not expected or not x_import_token or not secrets.compare_digest(x_import_token, expected):
        raise HTTPException(403, "Import token invalid")


async def _counts() -> Dict[str, int]:
    return {c: await db[c].count_documents({}) for c in COLLECTIONS}


async def _session() -> dict | None:
    s = await db.meta.find_one({"_id": SESSION_ID})
    if not s:
        return None
    started = s["started_at"]
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - started > SESSION_MAX:
        await db.meta.delete_one({"_id": SESSION_ID})
        return None
    return s


def _fresh(counts: Dict[str, int]) -> bool:
    return counts["orders"] == 0 and counts["users"] == 0 and counts["closings"] == 0


@router.get("/status")
async def status(_: dict = Depends(_manager())):
    counts = await _counts()
    return {"counts": counts, "fresh": _fresh(counts), "session_open": (await _session()) is not None,
            "import_token_configured": bool(os.environ.get("SNAPSHOT_IMPORT_TOKEN"))}


@router.post("/begin")
async def begin(_: dict = Depends(_manager()), __: None = Depends(_token)):
    counts = await _counts()
    if not _fresh(counts) and not await _session():
        raise HTTPException(409, "Target database is not fresh (orders/customers/closings exist) – import refused")
    await db.meta.update_one({"_id": SESSION_ID}, {"$set": {"started_at": datetime.now(timezone.utc)}}, upsert=True)
    return {"ok": True, "counts": counts}


@router.post("/import")
async def import_chunk(payload: Dict[str, Any] = Body(...), _: dict = Depends(_manager()), __: None = Depends(_token)):
    """Body: {collection, docs: [Extended JSON documents], first: bool}. `first` replaces the collection content."""
    if not await _session():
        raise HTTPException(409, "No open import session – call /begin on a fresh database first")
    coll = payload.get("collection")
    if coll not in COLLECTIONS:
        raise HTTPException(400, f"Unknown collection {coll!r}")
    docs: List[dict] = json_util.loads(json.dumps(payload.get("docs") or []))
    if payload.get("first"):
        await db[coll].delete_many({})  # replaces the seeded defaults of the fresh database
    if docs:
        await db[coll].insert_many(docs, ordered=True)
    return {"collection": coll, "inserted": len(docs), "total": await db[coll].count_documents({})}


@router.post("/finish")
async def finish(_: dict = Depends(_manager()), __: None = Depends(_token)):
    await db.meta.delete_one({"_id": SESSION_ID})
    return {"ok": True, "counts": await _counts()}

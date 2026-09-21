"""Staff customer database + optional marketing consent.

ONE customer identity per phone number: registered accounts and staff-created customers live in `users`,
guests only exist through their orders. Profiles are aggregated read-only from those two sources – no order
or accounting data is ever rewritten here.

Marketing consent (optional e-mail offers) is stored per phone identity in `marketing_consents`
(consent yes/no, date/time, source: checkout | account | staff, plus a history). Nobody is opted in
automatically: the flag is only ever set to True by an explicit tick of the customer.
"""
import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from auth import normalize_phone
from database import db

router = APIRouter(prefix="/customers")

ORDER_PROJECTION = {"order_number": 1, "type": 1, "source": 1, "station": 1, "status": 1, "total": 1, "created_at": 1,
                    "customer": 1, "address": 1, "user_id": 1, "marketing_consent": 1}
NOT_SPENT = {"cancelled", "rejected"}


def _roles(*roles: str):
    import staff_auth
    return staff_auth.require_roles(*roles)


async def ensure_indexes():
    await db.marketing_consents.create_index("phone", unique=True)


# ---------------------------------------------------------------------------
# Consent store
# ---------------------------------------------------------------------------
async def set_consent(phone: str, consent: bool, source: str, email: Optional[str] = None,
                      first_name: Optional[str] = None, last_name: Optional[str] = None) -> Optional[dict]:
    digits = normalize_phone(phone)
    if len(digits) < 7:
        return None
    now = datetime.now(timezone.utc)
    upd: Dict[str, Any] = {"phone": digits, "consent": bool(consent), "at": now, "source": source}
    if email:
        upd["email"] = email.strip().lower()
    if first_name:
        upd["first_name"] = first_name.strip()
    if last_name:
        upd["last_name"] = last_name.strip()
    await db.marketing_consents.update_one({"phone": digits}, {"$set": upd, "$push": {"history": {"consent": bool(consent), "at": now, "source": source}}}, upsert=True)
    return await db.marketing_consents.find_one({"phone": digits})


async def get_consent(phone: str) -> dict:
    c = await db.marketing_consents.find_one({"phone": normalize_phone(phone)})
    return _consent_view(c)


def _consent_view(c: Optional[dict]) -> dict:
    return {"consent": bool(c and c.get("consent")), "at": c.get("at") if c else None, "source": c.get("source") if c else None}


# ---------------------------------------------------------------------------
# Profiles (aggregated, read-only)
# ---------------------------------------------------------------------------
def _addr(a: dict) -> str:
    s = f"{a.get('street', '')} {a.get('number', '')}".strip()
    return f"{s}, {a.get('npa', '')} {a.get('city', '')}".strip(", ")


def _profile(key: str, first: str, last: str, phone: str, email: Optional[str], kind: str, created_at=None) -> dict:
    return {"key": key, "first_name": first or "", "last_name": last or "", "phone": phone or "", "email": email or None, "kind": kind,
            "addresses": [], "orders_count": 0, "total_spent": 0.0, "last_order_at": None, "first_order_at": None, "created_at": created_at}


async def build_profiles() -> Dict[str, dict]:
    users = await db.users.find({}, {"password_hash": 1, "first_name": 1, "last_name": 1, "phone": 1, "email": 1, "addresses": 1, "created_at": 1}).to_list(10000)
    orders = await db.orders.find({}, ORDER_PROJECTION).sort("created_at", -1).to_list(50000)
    consents = {c["phone"]: c async for c in db.marketing_consents.find({})}
    profiles: Dict[str, dict] = {}
    by_phone: Dict[str, str] = {}
    for u in users:
        key = str(u["_id"])
        kind = "account" if u.get("password_hash") else "staff"
        p = _profile(key, u.get("first_name", ""), u.get("last_name", ""), u.get("phone", ""), u.get("email"), kind, u.get("created_at"))
        p["addresses"] = [_addr(a) for a in u.get("addresses", [])]
        profiles[key] = p
        d = normalize_phone(u.get("phone", ""))
        if d:
            by_phone[d] = key
    for o in orders:  # newest first
        cust = o.get("customer") or {}
        d = normalize_phone(cust.get("phone", ""))
        key = o.get("user_id") if o.get("user_id") in profiles else by_phone.get(d)
        if not key:
            key = f"guest:{d or str(o['_id'])}"
            if key not in profiles:
                profiles[key] = _profile(key, cust.get("first_name", ""), cust.get("last_name", ""), cust.get("phone", ""), cust.get("email"), "guest", o.get("created_at"))
                if d:
                    by_phone[d] = key
        p = profiles[key]
        p["orders_count"] += 1
        if o.get("status") not in NOT_SPENT:
            p["total_spent"] = round(p["total_spent"] + float(o.get("total") or 0), 2)
        if p["last_order_at"] is None:
            p["last_order_at"] = o.get("created_at")
        p["first_order_at"] = o.get("created_at")
        if not p["email"] and cust.get("email"):
            p["email"] = cust["email"]
        if o.get("address"):
            a = _addr(o["address"])
            if a and a.lower() not in [x.lower() for x in p["addresses"]]:
                p["addresses"].append(a)
    for p in profiles.values():
        c = consents.get(normalize_phone(p["phone"]))
        p["marketing"] = _consent_view(c)
        if not p["email"] and c and c.get("email"):
            p["email"] = c["email"]
    return profiles


def _matches(p: dict, q: str) -> bool:
    ql = q.lower().strip()
    if not ql:
        return True
    digits = normalize_phone(ql)
    name = f"{p['first_name']} {p['last_name']}".lower()
    if ql in name or (p.get("email") and ql in p["email"].lower()):
        return True
    return bool(digits) and len(digits) >= 3 and digits in normalize_phone(p["phone"])


def _sort_key(p: dict):
    ts = p["last_order_at"] or p.get("created_at") or datetime(1970, 1, 1, tzinfo=timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (-ts.timestamp(), p["last_name"].lower(), p["first_name"].lower())


@router.get("")
async def list_customers(q: str = "", marketing: str = Query("all", pattern="^(all|yes|no)$"), limit: int = 200, _: dict = Depends(_roles("manager", "phone"))):
    """Customer database: accounts + staff-created customers + guests (one row per phone identity)."""
    profiles = list((await build_profiles()).values())
    out = [p for p in profiles if _matches(p, q)]
    if marketing == "yes":
        out = [p for p in out if p["marketing"]["consent"]]
    elif marketing == "no":
        out = [p for p in out if not p["marketing"]["consent"]]
    out.sort(key=_sort_key)
    stats = {"total": len(profiles), "accounts": sum(1 for p in profiles if p["kind"] == "account"),
             "marketing_yes": sum(1 for p in profiles if p["marketing"]["consent"])}
    return {"customers": out[:limit], "count": len(out), "stats": stats}


@router.get("/marketing-export.csv")
async def export_marketing_csv(_: dict = Depends(_roles("manager"))):
    """CSV of customers who explicitly opted in (first name, last name, e-mail, phone, consent date)."""
    profiles = [p for p in (await build_profiles()).values() if p["marketing"]["consent"]]
    profiles.sort(key=lambda p: (p["last_name"].lower(), p["first_name"].lower()))
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["first_name", "last_name", "email", "phone", "consent_date"])
    for p in profiles:
        at = p["marketing"]["at"]
        w.writerow([p["first_name"], p["last_name"], p.get("email") or "", p["phone"], at.strftime("%Y-%m-%d %H:%M") if at else ""])
    name = f"marketing-optin-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return Response(content="\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _order_query(p: dict) -> dict:
    digits = normalize_phone(p["phone"])
    ors: List[dict] = []
    if p["kind"] != "guest":
        ors.append({"user_id": p["key"]})
    if digits:
        ors.append({"customer.phone": {"$regex": r"\D*".join(digits) + r"\D*$"}})
    if not ors:
        return {"_id": None}
    return {"$or": ors} if len(ors) > 1 else ors[0]


def _ser(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("/{key}/profile")
async def customer_profile(key: str, _: dict = Depends(_roles("manager", "phone"))):
    profiles = await build_profiles()
    p = profiles.get(key)
    if not p:
        raise HTTPException(404, "Client introuvable")
    docs = await db.orders.find(_order_query(p)).sort("created_at", -1).to_list(500)
    return {**p, "orders": [_ser(d) for d in docs]}


class MarketingIn(BaseModel):
    consent: bool


@router.put("/{key}/marketing")
async def staff_set_marketing(key: str, body: MarketingIn, _: dict = Depends(_roles("manager"))):
    """Manager records a consent change made on the customer's request (e.g. unsubscribe by phone)."""
    if key.startswith("guest:"):
        phone = key[6:]
        first = last = email = None
        try:
            ObjectId(phone)
            raise HTTPException(400, "Ce client n'a pas de numéro de téléphone")
        except HTTPException:
            raise
        except Exception:
            pass
    else:
        u = await db.users.find_one({"_id": ObjectId(key)}) if ObjectId.is_valid(key) else None
        if not u:
            raise HTTPException(404, "Client introuvable")
        phone, first, last, email = u.get("phone", ""), u.get("first_name"), u.get("last_name"), u.get("email")
    c = await set_consent(phone, body.consent, "staff", email=email, first_name=first, last_name=last)
    if c is None:
        raise HTTPException(400, "Numéro de téléphone invalide")
    return _consent_view(c)

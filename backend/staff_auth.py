"""Staff / driver authentication: server-side PIN verification (Argon2 hashes in Mongo), JWT with a role claim.
Roles: manager, kitchen, phone, driver1, driver2, driver3. PINs are never shipped to the frontend."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import List

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, Field

from zoneinfo import ZoneInfo

from auth import JWT_ALG, JWT_SECRET, bearer, password_hash
from database import db

TZ = ZoneInfo("Europe/Zurich")

ROLES = ["manager", "kitchen", "phone", "driver1", "driver2", "driver3"]
DRIVER_NAME = {"driver1": "Livreur 1", "driver2": "Livreur 2", "driver3": "Livreur 3"}
# Development fallback PINs (only used to seed the DB once; manager changes them in admin → Sécurité)
DEFAULT_PINS = {"manager": os.environ.get("STAFF_PIN_MANAGER", "1234"), "kitchen": "2345", "phone": "3456", "driver1": "1111", "driver2": "2222", "driver3": "3333"}

router = APIRouter(prefix="/auth/staff")


async def seed_staff_pins():
    for role in ROLES:
        if not await db.staff_auth.find_one({"_id": role}):
            await db.staff_auth.insert_one({"_id": role, "pin_hash": password_hash.hash(DEFAULT_PINS[role]), "updated_at": datetime.now(timezone.utc), "active": True})
    await db.staff_auth.update_many({"active": {"$exists": False}}, {"$set": {"active": True}})


def shift_expiry() -> datetime:
    """Driver sessions end with the working day (03:00 Europe/Zurich next morning covers late deliveries)."""
    now = datetime.now(TZ)
    end = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if now.hour >= 3:
        end += timedelta(days=1)
    return end.astimezone(timezone.utc)


class StaffLoginIn(BaseModel):
    pin: str = Field(min_length=4, max_length=12)


class StaffTokenOut(BaseModel):
    access_token: str
    role: str
    label: str


def role_label(role: str) -> str:
    return DRIVER_NAME.get(role) or {"manager": "Manager", "kitchen": "Cuisine / Staff", "phone": "Commandes téléphoniques"}[role]


async def open_shift(role: str):
    return await db.driver_shifts.find_one({"role": role, "closed_at": None, "expires_at": {"$gt": datetime.now(timezone.utc)}})


async def open_shift_for_name(driver_label: str):
    role = next((r for r, n in DRIVER_NAME.items() if n == driver_label), None)
    return await open_shift(role) if role else None


@router.post("/login", response_model=StaffTokenOut)
async def staff_login(body: StaffLoginIn):
    # Drivers: temporary 6-digit shift PIN (one open shift per position, one device per shift)
    if len(body.pin) == 6:
        async for sh in db.driver_shifts.find({"closed_at": None}):
            try:
                ok = password_hash.verify(body.pin, sh["pin_hash"])
            except Exception:
                ok = False
            if not ok:
                continue
            if sh["expires_at"].replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
                raise HTTPException(403, f"{DRIVER_NAME[sh['role']]}: service expiré – le manager doit rouvrir le service")
            sid = secrets.token_hex(8)  # new device takes over the shift session (single active device)
            await db.driver_shifts.update_one({"_id": sh["_id"]}, {"$set": {"session_id": sid, "last_login_at": datetime.now(timezone.utc)}})
            now = datetime.now(timezone.utc)
            tok = jwt.encode({"sub": sh["role"], "role": sh["role"], "typ": "staff", "sid": sid, "name": sh["name"], "iat": now, "exp": sh["expires_at"]}, JWT_SECRET, algorithm=JWT_ALG)
            return StaffTokenOut(access_token=tok, role=sh["role"], label=f"{DRIVER_NAME[sh['role']]} — {sh['name']}")
    async for doc in db.staff_auth.find({}):
        if doc["_id"] in DRIVER_NAME:
            continue  # permanent driver PINs are retired – drivers only enter with a shift PIN
        try:
            if password_hash.verify(body.pin, doc["pin_hash"]):
                if not doc.get("active", True):
                    raise HTTPException(403, f"{role_label(doc['_id'])}: poste INACTIF – demandez au manager d'activer ce poste")
                now = datetime.now(timezone.utc)
                exp = min(now + timedelta(hours=16), shift_expiry()) if doc["_id"] in DRIVER_NAME else now + timedelta(hours=16)
                tok = jwt.encode({"sub": doc["_id"], "role": doc["_id"], "typ": "staff", "iat": now, "exp": exp}, JWT_SECRET, algorithm=JWT_ALG)
                return StaffTokenOut(access_token=tok, role=doc["_id"], label=role_label(doc["_id"]))
        except HTTPException:
            raise
        except Exception:
            continue
    raise HTTPException(401, "Code d'accès incorrect")


async def staff_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not credentials:
        raise HTTPException(401, "Authentification requise")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("typ") != "staff" or payload.get("role") not in ROLES:
            raise ValueError()
    except (InvalidTokenError, KeyError, ValueError):
        raise HTTPException(401, "Session invalide ou expirée")
    if payload["role"] in DRIVER_NAME:
        sh = await open_shift(payload["role"])
        if not sh:
            raise HTTPException(403, "Service fermé – demandez au manager d'ouvrir le service")
        if payload.get("sid") != sh.get("session_id"):
            raise HTTPException(403, "Session remplacée (autre appareil) – reconnectez-vous avec le code du service")
        return {"role": payload["role"], "name": sh["name"], "shift_id": str(sh["_id"])}
    return {"role": payload["role"]}


def require_roles(*roles: str):
    async def dep(user: dict = Depends(staff_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "Accès refusé pour ce rôle")
        return user
    return dep


@router.get("/me", response_model=StaffTokenOut)
async def staff_me(user: dict = Depends(staff_user), credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    label = f"{role_label(user['role'])} — {user['name']}" if user.get("name") else role_label(user["role"])
    return StaffTokenOut(access_token=credentials.credentials, role=user["role"], label=label)


class PinChangeIn(BaseModel):
    role: str
    pin: str = Field(min_length=4, max_length=12)


@router.put("/pins")
async def change_pin(body: PinChangeIn, _: dict = Depends(require_roles("manager"))):
    if body.role not in ROLES:
        raise HTTPException(400, "Unknown role")
    if not body.pin.isdigit():
        raise HTTPException(400, "Le code doit contenir uniquement des chiffres")
    # A PIN must identify exactly one role
    async for doc in db.staff_auth.find({"_id": {"$ne": body.role}}):
        if password_hash.verify(body.pin, doc["pin_hash"]):
            raise HTTPException(409, "Ce code est déjà utilisé par un autre rôle")
    await db.staff_auth.update_one({"_id": body.role}, {"$set": {"pin_hash": password_hash.hash(body.pin), "updated_at": datetime.now(timezone.utc)}}, upsert=True)
    return {"ok": True, "role": body.role}


@router.get("/roles")
async def list_roles(_: dict = Depends(require_roles("manager"))) -> List[dict]:
    docs = {d["_id"]: d async for d in db.staff_auth.find({})}
    return [{"role": r, "label": role_label(r), "updated_at": docs.get(r, {}).get("updated_at"), "active": docs.get(r, {}).get("active", True)} for r in ROLES]


class ActiveIn(BaseModel):
    active: bool


@router.put("/drivers/{role}/active")
async def set_driver_active(role: str, body: ActiveIn, _: dict = Depends(require_roles("manager"))):
    """Manager shift control: only ACTIVE driver positions can log in (existing sessions are cut too)."""
    if role not in DRIVER_NAME:
        raise HTTPException(400, "Driver role expected")
    await db.staff_auth.update_one({"_id": role}, {"$set": {"active": body.active, "active_changed_at": datetime.now(timezone.utc)}})
    return {"role": role, "label": DRIVER_NAME[role], "active": body.active}


# ---------------------------------------------------------------------------
# Driver shifts (manager): OUVRIR LE SERVICE -> temporary 6-digit PIN, RESET SESSION, FERMER LE SERVICE
# ---------------------------------------------------------------------------
class ShiftOpenIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


def shift_view(sh: dict, pin: str = None) -> dict:
    return {"role": sh["role"], "driver": DRIVER_NAME[sh["role"]], "name": sh["name"], "opened_at": sh["opened_at"], "expires_at": sh["expires_at"],
            "closed_at": sh.get("closed_at"), "last_login_at": sh.get("last_login_at"), "connected": bool(sh.get("last_login_at")), **({"pin": pin} if pin else {})}


@router.get("/shifts")
async def list_shifts(_: dict = Depends(require_roles("manager"))):
    out = []
    for role, driver in DRIVER_NAME.items():
        sh = await open_shift(role)
        out.append(shift_view(sh) if sh else {"role": role, "driver": driver, "name": None, "opened_at": None, "expires_at": None, "connected": False})
    return out


@router.get("/drivers")
async def list_drivers(_: dict = Depends(require_roles("manager", "kitchen", "phone"))):
    """Who is on each slot right now – used for the Manager assignment buttons ("Livreur 1 — Aliou"). No PIN data."""
    out = []
    for role, driver in DRIVER_NAME.items():
        sh = await open_shift(role)
        out.append({"role": role, "driver": driver, "name": sh["name"] if sh else None, "open": bool(sh),
                    "label": f"{driver} — {sh['name']}" if sh else driver})
    return out


@router.post("/shifts/{role}/open")
async def open_shift_ep(role: str, body: ShiftOpenIn, _: dict = Depends(require_roles("manager"))):
    if role not in DRIVER_NAME:
        raise HTTPException(400, "Driver role expected")
    now = datetime.now(timezone.utc)
    await db.driver_shifts.update_many({"role": role, "closed_at": None}, {"$set": {"closed_at": now, "closed_reason": "reopened"}})  # old PIN stops working
    pin = f"{secrets.randbelow(900000) + 100000}"
    sh = {"role": role, "name": body.name.strip(), "pin_hash": password_hash.hash(pin), "opened_at": now, "expires_at": shift_expiry(), "closed_at": None, "session_id": None}
    await db.driver_shifts.insert_one(sh)
    return shift_view(sh, pin)  # the PIN is shown to the manager once – never stored in clear


@router.post("/shifts/{role}/reset-session")
async def reset_shift_session(role: str, _: dict = Depends(require_roles("manager"))):
    sh = await open_shift(role)
    if not sh:
        raise HTTPException(404, "Aucun service ouvert")
    await db.driver_shifts.update_one({"_id": sh["_id"]}, {"$set": {"session_id": None, "last_login_at": None}})  # current phone is logged out; same PIN on the new phone
    return {"ok": True}


@router.post("/shifts/{role}/close")
async def close_shift(role: str, _: dict = Depends(require_roles("manager"))):
    res = await db.driver_shifts.update_many({"role": role, "closed_at": None}, {"$set": {"closed_at": datetime.now(timezone.utc), "closed_reason": "closed"}})
    return {"ok": True, "closed": res.modified_count}

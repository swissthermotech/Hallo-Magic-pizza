"""Staff / driver authentication: server-side PIN verification (Argon2 hashes in Mongo), JWT with a role claim.
Roles: manager, kitchen, phone, driver1, driver2, driver3. PINs are never shipped to the frontend."""
import os
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


@router.post("/login", response_model=StaffTokenOut)
async def staff_login(body: StaffLoginIn):
    async for doc in db.staff_auth.find({}):
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
    if payload["role"] in DRIVER_NAME:  # deactivating a driver position ends its existing sessions immediately
        doc = await db.staff_auth.find_one({"_id": payload["role"]})
        if doc and not doc.get("active", True):
            raise HTTPException(403, "Poste livreur INACTIF")
    return {"role": payload["role"]}


def require_roles(*roles: str):
    async def dep(user: dict = Depends(staff_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "Accès refusé pour ce rôle")
        return user
    return dep


@router.get("/me", response_model=StaffTokenOut)
async def staff_me(user: dict = Depends(staff_user), credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    return StaffTokenOut(access_token=credentials.credentials, role=user["role"], label=role_label(user["role"]))


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

"""Staff / driver authentication: server-side password verification (Argon2 hashes in Mongo), JWT with a role claim.
Roles: manager, kitchen, phone, driver1, driver2, driver3. Secrets are never shipped to the frontend.

Credentials (collection `staff_auth`, one document per role):
  * `password_hash`  – real password (>= 10 chars, letters + digits + special) set by the manager in Admin → Sécurité;
  * `pin_hash`       – LEGACY numeric PIN, accepted only while the role has no `password_hash` yet (safe migration:
                       nobody is locked out; setting a password removes the legacy PIN for that role).
Drivers keep their temporary 6-digit shift codes (generated per service by the manager, expire the same night).
Brute force: 5 failed attempts from the same client => login blocked for 15 minutes (server-side, collection
`staff_login_attempts`)."""
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from zoneinfo import ZoneInfo

from auth import JWT_ALG, JWT_SECRET, bearer, password_hash
from database import db

TZ = ZoneInfo("Europe/Zurich")

ROLES = ["manager", "kitchen", "phone", "driver1", "driver2", "driver3"]
DRIVER_NAME = {"driver1": "Livreur 1", "driver2": "Livreur 2", "driver3": "Livreur 3"}
# Development fallback PINs (only used to seed a FRESH database once; the manager then sets real passwords in admin → Sécurité)
DEFAULT_PINS = {"manager": os.environ.get("STAFF_PIN_MANAGER", "1234"), "kitchen": "2345", "phone": "3456", "driver1": "1111", "driver2": "2222", "driver3": "3333"}

PASSWORD_MIN = 10
PASSWORD_MAX = 128
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
SESSION_MAX_HOURS = 16  # staff session never outlives the working day (03:00 Europe/Zurich) nor 16 h

router = APIRouter(prefix="/auth/staff")


async def seed_staff_pins():
    for role in ROLES:
        if not await db.staff_auth.find_one({"_id": role}):
            await db.staff_auth.insert_one({"_id": role, "pin_hash": password_hash.hash(DEFAULT_PINS[role]), "updated_at": datetime.now(timezone.utc), "active": True})
    await db.staff_auth.update_many({"active": {"$exists": False}}, {"$set": {"active": True}})
    await db.staff_login_attempts.create_index("last_failed_at", expireAfterSeconds=86400)  # cleanup only; locked_until is enforced at login


def validate_password(value: str) -> str:
    if len(value) < PASSWORD_MIN or len(value) > PASSWORD_MAX:
        raise ValueError(f"Le mot de passe doit contenir entre {PASSWORD_MIN} et {PASSWORD_MAX} caractères")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"[0-9]", value) or not re.search(r"[^A-Za-z0-9\s]", value):
        raise ValueError("Le mot de passe doit contenir des lettres, des chiffres et au moins un caractère spécial")
    if value != value.strip():
        raise ValueError("Le mot de passe ne peut pas commencer ou finir par un espace")
    return value


# ---- brute-force protection ------------------------------------------------------------------------------------
def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    ip = (fwd.split(",")[0].strip() if fwd else "") or (request.client.host if request.client else "unknown")
    return hashlib.sha256(f"staff-login|{ip}".encode()).hexdigest()  # raw IPs are never stored


def _lock_message(locked_until: datetime) -> str:
    mins = max(1, int((locked_until - datetime.now(timezone.utc)).total_seconds() + 59) // 60)
    return f"Trop de tentatives – accès bloqué pendant {mins} min"


async def _check_not_locked(key: str) -> None:
    row = await db.staff_login_attempts.find_one({"_id": key})
    if not row:
        return
    until = row.get("locked_until")
    if until is not None and until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        raise HTTPException(429, _lock_message(until.replace(tzinfo=timezone.utc)))
    if until is not None:  # lock expired -> fresh window
        await db.staff_login_attempts.delete_one({"_id": key, "locked_until": until})


async def _record_failure(key: str) -> None:
    now = datetime.now(timezone.utc)
    row = await db.staff_login_attempts.find_one_and_update({"_id": key}, {"$inc": {"failed_count": 1}, "$set": {"last_failed_at": now}},
                                                             upsert=True, return_document=ReturnDocument.AFTER)
    if row["failed_count"] >= MAX_FAILED_ATTEMPTS:
        until = now + timedelta(minutes=LOCKOUT_MINUTES)
        await db.staff_login_attempts.update_one({"_id": key}, {"$set": {"locked_until": until}})
        raise HTTPException(429, _lock_message(until))
    left = MAX_FAILED_ATTEMPTS - row["failed_count"]
    raise HTTPException(401, f"Mot de passe incorrect – {left} tentative{'s' if left > 1 else ''} restante{'s' if left > 1 else ''}")


async def _clear_failures(key: str) -> None:
    await db.staff_login_attempts.delete_one({"_id": key})


def shift_expiry() -> datetime:
    """Driver sessions end with the working day (03:00 Europe/Zurich next morning covers late deliveries)."""
    now = datetime.now(TZ)
    end = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if now.hour >= 3:
        end += timedelta(days=1)
    return end.astimezone(timezone.utc)


class StaffLoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


class StaffTokenOut(BaseModel):
    access_token: str
    role: str
    label: str
    expires_at: Optional[datetime] = None


def _staff_token(role: str, now: datetime, credential_version: int) -> tuple:
    """`cv` = credential version of the role: every password change bumps it, so all older sessions are revoked."""
    exp = min(now + timedelta(hours=SESSION_MAX_HOURS), shift_expiry())
    return jwt.encode({"sub": role, "role": role, "typ": "staff", "cv": credential_version, "iat": now, "exp": exp}, JWT_SECRET, algorithm=JWT_ALG), exp


def role_label(role: str) -> str:
    return DRIVER_NAME.get(role) or {"manager": "Manager", "kitchen": "Cuisine / Staff", "phone": "Commandes téléphoniques"}[role]


async def open_shift(role: str):
    return await db.driver_shifts.find_one({"role": role, "closed_at": None, "expires_at": {"$gt": datetime.now(timezone.utc)}})


async def open_shift_for_name(driver_label: str):
    role = next((r for r, n in DRIVER_NAME.items() if n == driver_label), None)
    return await open_shift(role) if role else None


@router.post("/login", response_model=StaffTokenOut)
async def staff_login(body: StaffLoginIn, request: Request):
    key = _client_key(request)
    await _check_not_locked(key)
    secret = body.password
    # Drivers: temporary 6-digit shift code (one open shift per position, one device per shift)
    if len(secret) == 6 and secret.isdigit():
        async for sh in db.driver_shifts.find({"closed_at": None}):
            try:
                ok = password_hash.verify(secret, sh["pin_hash"])
            except Exception:
                ok = False
            if not ok:
                continue
            if sh["expires_at"].replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
                raise HTTPException(403, f"{DRIVER_NAME[sh['role']]}: service expiré – le manager doit rouvrir le service")
            sid = secrets.token_hex(8)  # new device takes over the shift session (single active device)
            await db.driver_shifts.update_one({"_id": sh["_id"]}, {"$set": {"session_id": sid, "last_login_at": datetime.now(timezone.utc)}})
            await _clear_failures(key)
            now = datetime.now(timezone.utc)
            tok = jwt.encode({"sub": sh["role"], "role": sh["role"], "typ": "staff", "sid": sid, "name": sh["name"], "iat": now, "exp": sh["expires_at"]}, JWT_SECRET, algorithm=JWT_ALG)
            return StaffTokenOut(access_token=tok, role=sh["role"], label=f"{DRIVER_NAME[sh['role']]} — {sh['name']}", expires_at=sh["expires_at"])
    async for doc in db.staff_auth.find({}):
        if doc["_id"] in DRIVER_NAME:
            continue  # permanent driver PINs are retired – drivers only enter with a shift code
        stored = doc.get("password_hash") or doc.get("pin_hash")  # legacy PIN only until a password exists
        if not stored:
            continue
        try:
            ok = password_hash.verify(secret, stored)
        except Exception:
            ok = False
        if not ok:
            continue
        if not doc.get("active", True):
            raise HTTPException(403, f"{role_label(doc['_id'])}: poste INACTIF – demandez au manager d'activer ce poste")
        await _clear_failures(key)
        tok, exp = _staff_token(doc["_id"], datetime.now(timezone.utc), int(doc.get("credential_version", 0)))
        return StaffTokenOut(access_token=tok, role=doc["_id"], label=role_label(doc["_id"]), expires_at=exp)
    await _record_failure(key)  # raises 401 (attempts left) or 429 (locked)
    raise HTTPException(401, "Mot de passe incorrect")


async def staff_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not credentials:
        raise HTTPException(401, "Authentification requise")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALG], options={"require": ["exp", "iat", "role"]})
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
    # Sessions issued before the role's password was (re)set are revoked: changing a password logs every device out
    doc = await db.staff_auth.find_one({"_id": payload["role"]}, {"credential_version": 1})
    if int((doc or {}).get("credential_version", 0)) != int(payload.get("cv", 0)):
        raise HTTPException(401, "Mot de passe modifié – veuillez vous reconnecter")
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


class PasswordChangeIn(BaseModel):
    role: str
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


@router.put("/password")
async def change_password(body: PasswordChangeIn, user: dict = Depends(require_roles("manager"))):
    """Manager sets the password of a staff role. Replaces the legacy PIN of that role; every existing session of the
    role is revoked (except the manager's current device, which receives a fresh token when changing its own role)."""
    if body.role not in ROLES or body.role in DRIVER_NAME:
        raise HTTPException(400, "Rôle inconnu (les livreurs utilisent le code du service)")
    try:
        validate_password(body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # A password identifies exactly one role
    async for doc in db.staff_auth.find({"_id": {"$ne": body.role}}):
        stored = doc.get("password_hash") or doc.get("pin_hash")
        try:
            if stored and password_hash.verify(body.password, stored):
                raise HTTPException(409, "Ce mot de passe est déjà utilisé par un autre rôle")
        except HTTPException:
            raise
        except Exception:
            continue
    now = datetime.now(timezone.utc)
    doc = await db.staff_auth.find_one_and_update({"_id": body.role},
                                                  {"$set": {"password_hash": password_hash.hash(body.password), "password_set_at": now, "updated_at": now},
                                                   "$unset": {"pin_hash": ""}, "$inc": {"credential_version": 1}},
                                                  upsert=True, return_document=ReturnDocument.AFTER)
    out = {"ok": True, "role": body.role}
    if body.role == user["role"]:
        tok, exp = _staff_token(body.role, now, int(doc["credential_version"]))  # this device stays logged in
        out.update({"access_token": tok, "expires_at": exp})
    return out


@router.get("/roles")
async def list_roles(_: dict = Depends(require_roles("manager"))) -> List[dict]:
    docs = {d["_id"]: d async for d in db.staff_auth.find({})}
    return [{"role": r, "label": role_label(r), "updated_at": docs.get(r, {}).get("updated_at"), "active": docs.get(r, {}).get("active", True),
             "credential": "password" if docs.get(r, {}).get("password_hash") else ("pin" if docs.get(r, {}).get("pin_hash") else "none")}
            for r in ROLES]


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

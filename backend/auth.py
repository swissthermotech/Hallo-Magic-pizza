"""Optional customer accounts (JWT + Argon2). Guest checkout stays fully available – every endpoint that
accepts a token also works without one."""
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel, Field

from database import db

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_DAYS = 30  # prototype: long-lived session, no refresh tokens yet

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/auth")


def normalize_phone(value: str) -> str:
    """'+41 79 123 45 67' / '0041791234567' / '079 123 45 67' -> '0791234567'."""
    digits = re.sub(r"[^\d]", "", value or "")
    if digits.startswith("0041"):
        digits = "0" + digits[4:]
    elif digits.startswith("41") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class SavedAddress(BaseModel):
    id: str = ""
    label: str = ""
    street: str
    number: str = ""
    npa: str
    city: str
    instructions: Optional[str] = None


class RegisterIn(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = ""
    phone: str = Field(min_length=7)
    email: Optional[str] = None
    password: str = Field(min_length=6, max_length=128)
    marketing_consent: bool = False  # optional e-mail offers – unchecked by default, never required


class LoginIn(BaseModel):
    phone: str
    password: str


class ProfileIn(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = ""
    phone: str = Field(min_length=7)
    email: Optional[str] = None


class UserOut(BaseModel):
    id: str
    first_name: str
    last_name: str = ""
    phone: str
    email: Optional[str] = None
    addresses: List[SavedAddress] = []
    created_at: datetime
    marketing_consent: Optional[bool] = None  # current opt-in state (filled by the account endpoints)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def user_out(doc: dict) -> UserOut:
    return UserOut(id=str(doc["_id"]), first_name=doc["first_name"], last_name=doc.get("last_name", ""), phone=doc["phone"],
                   email=doc.get("email"), addresses=[SavedAddress(**a) for a in doc.get("addresses", [])], created_at=doc["created_at"])


async def user_out_full(doc: dict) -> UserOut:
    """Profile + current marketing consent (stored per phone identity, see customers.py)."""
    import customers
    out = user_out(doc)
    out.marketing_consent = (await customers.get_consent(doc["phone"]))["consent"]
    return out


def make_token(user_id: ObjectId) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(days=JWT_DAYS), "typ": "access"}, JWT_SECRET, algorithm=JWT_ALG)


async def optional_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> Optional[dict]:
    """Returns the user document for a valid token, None for guests (no / invalid token never blocks checkout)."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("typ") != "access":
            return None
        return await db.users.find_one({"_id": ObjectId(payload["sub"])})
    except (InvalidTokenError, KeyError, ValueError):
        return None


async def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not credentials:
        raise HTTPException(401, "Authentication required")
    user = await optional_user(credentials)
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    return user


async def ensure_indexes():
    await db.users.create_index("phone", unique=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn):
    phone = normalize_phone(body.phone)
    if len(phone) < 7:
        raise HTTPException(400, "Numéro de téléphone invalide")
    existing = await db.users.find_one({"phone": phone})
    if existing and existing.get("password_hash"):
        raise HTTPException(409, "Un compte existe déjà avec ce numéro")
    if existing:
        # Customer created by staff from a phone order (no password yet) -> the caller claims the account
        await db.users.update_one({"_id": existing["_id"]}, {"$set": {"password_hash": password_hash.hash(body.password), "first_name": body.first_name.strip(),
                                                                       "last_name": body.last_name.strip() or existing.get("last_name", ""), "email": (body.email or "").strip().lower() or existing.get("email")}})
        existing = await db.users.find_one({"_id": existing["_id"]})
        if body.marketing_consent:
            await _consent(existing, True, "account")
        return TokenOut(access_token=make_token(existing["_id"]), user=await user_out_full(existing))
    doc = {"first_name": body.first_name.strip(), "last_name": body.last_name.strip(), "phone": phone,
           "email": (body.email or "").strip().lower() or None, "password_hash": password_hash.hash(body.password),
           "addresses": [], "created_at": datetime.now(timezone.utc)}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    if body.marketing_consent:  # explicit opt-in only
        await _consent(doc, True, "account")
    return TokenOut(access_token=make_token(res.inserted_id), user=await user_out_full(doc))


async def _consent(user: dict, consent: bool, source: str):
    import customers
    await customers.set_consent(user["phone"], consent, source, email=user.get("email"), first_name=user.get("first_name"), last_name=user.get("last_name"))


class MarketingIn(BaseModel):
    consent: bool


@router.put("/me/marketing", response_model=UserOut)
async def update_marketing(body: MarketingIn, user=Depends(current_user)):
    """Account holders opt in / withdraw at any time from their profile."""
    await _consent(user, body.consent, "account")
    return await user_out_full(user)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn):
    user = await db.users.find_one({"phone": normalize_phone(body.phone)})
    dummy = "$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy"
    try:
        valid = password_hash.verify(body.password, user["password_hash"] if user and user.get("password_hash") else dummy)
    except Exception:
        valid = False
    if not user or not user.get("password_hash") or not valid:
        raise HTTPException(401, "Téléphone ou mot de passe incorrect")
    return TokenOut(access_token=make_token(user["_id"]), user=await user_out_full(user))


@router.get("/me", response_model=UserOut)
async def me(user=Depends(current_user)):
    return await user_out_full(user)


class DeleteMeIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


ACTIVE_ORDER_STATUSES = ["pending", "accepted", "preparing", "ready", "assigned", "delivering", "picked_up", "delivered"]
ANONYMISED_NAME = "Client supprimé"


@router.delete("/me")
async def delete_me(body: DeleteMeIn, user=Depends(current_user)):
    """Customer right to erasure (App Store 5.1.1(v) / nFADP): the customer re-enters the password, then
    1. every order of this person (linked by account id or by the account phone number) keeps its number, items, totals,
       statuses and timestamps but loses name / phone / e-mail / street / instructions (statistics + history stay intact);
    2. the ticket copies stored in print_jobs for those orders are redacted;
    3. the marketing-consent record of the phone number and the Google-review request state of this person are removed;
    4. the account document is deleted -> every JWT of this customer is rejected from now on (current_user looks the
       user up on each request), so no server-side token store is needed.
    Refused while an order is still in progress (staff and drivers need the contact data to fulfil it)."""
    try:
        ok = password_hash.verify(body.password, user["password_hash"])
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(403, "Mot de passe incorrect")
    uid = str(user["_id"])
    digits = normalize_phone(user.get("phone", ""))
    scope = {"$or": [{"user_id": uid}] + ([{"customer.phone": {"$regex": re.escape(digits[-9:]) + "$"}}] if len(digits) >= 9 else [])}
    active = await db.orders.count_documents({**scope, "status": {"$in": ACTIVE_ORDER_STATUSES}})
    if active:
        raise HTTPException(409, "Une commande est encore en cours – la suppression sera possible une fois la commande terminée")
    now = datetime.now(timezone.utc)
    order_ids = [o["_id"] async for o in db.orders.find(scope, {"_id": 1})]
    if order_ids:
        await db.orders.update_many(
            {"_id": {"$in": order_ids}},
            {"$set": {"customer.first_name": ANONYMISED_NAME, "customer.last_name": "", "customer.phone": "", "customer.email": None,
                      "general_note": None, "anonymised_at": now},
             "$unset": {"user_id": "", "marketing_consent": ""}})
        # delivery orders: keep NPA/city (zone statistics), drop street/number/instructions (ticket layout still renders)
        await db.orders.update_many({"_id": {"$in": order_ids}, "address": {"$type": "object"}},
                                    {"$set": {"address.street": "", "address.number": "", "address.instructions": None}})
        await db.print_jobs.update_many({"order_id": {"$in": [str(i) for i in order_ids]}},
                                        {"$set": {"content": "[contenu supprimé – compte client effacé]", "redacted_at": now}})
    if digits:
        await db.marketing_consents.delete_one({"phone": digits})
    # Google-review request state of this person (account id / e-mail / phone) is personal data too
    erase = [{"user_id": uid}] + ([{"email": user["email"].strip().lower()}] if user.get("email") else []) + ([{"phone": digits}] if digits else [])
    await db.review_customers.delete_many({"$or": erase})
    await db.users.delete_one({"_id": user["_id"]})
    return {"ok": True, "anonymised_orders": len(order_ids)}


@router.put("/me", response_model=UserOut)
async def update_me(body: ProfileIn, user=Depends(current_user)):
    phone = normalize_phone(body.phone)
    other = await db.users.find_one({"phone": phone, "_id": {"$ne": user["_id"]}})
    if other:
        raise HTTPException(409, "Ce numéro est déjà utilisé par un autre compte")
    upd = {"first_name": body.first_name.strip(), "last_name": body.last_name.strip(), "phone": phone, "email": (body.email or "").strip().lower() or None}
    await db.users.update_one({"_id": user["_id"]}, {"$set": upd})
    return user_out(await db.users.find_one({"_id": user["_id"]}))


@router.post("/me/addresses", response_model=UserOut)
async def add_address(body: SavedAddress, user=Depends(current_user)):
    addr = body.model_dump()
    addr["id"] = str(ObjectId())
    await db.users.update_one({"_id": user["_id"]}, {"$push": {"addresses": addr}})
    return user_out(await db.users.find_one({"_id": user["_id"]}))


@router.put("/me/addresses/{addr_id}", response_model=UserOut)
async def update_address(addr_id: str, body: SavedAddress, user=Depends(current_user)):
    addr = body.model_dump()
    addr["id"] = addr_id
    res = await db.users.update_one({"_id": user["_id"], "addresses.id": addr_id}, {"$set": {"addresses.$": addr}})
    if res.matched_count == 0:
        raise HTTPException(404, "Address not found")
    return user_out(await db.users.find_one({"_id": user["_id"]}))


@router.delete("/me/addresses/{addr_id}", response_model=UserOut)
async def delete_address(addr_id: str, user=Depends(current_user)):
    await db.users.update_one({"_id": user["_id"]}, {"$pull": {"addresses": {"id": addr_id}}})
    return user_out(await db.users.find_one({"_id": user["_id"]}))


async def save_address_for_user(user: dict, address: dict):
    """Called from checkout when the customer ticks 'save this address'. Skips exact duplicates."""
    key = lambda a: (a["street"].strip().lower(), a.get("number", "").strip().lower(), a["npa"].strip(), a["city"].strip().lower())  # noqa: E731
    if any(key(a) == key(address) for a in user.get("addresses", [])):
        return
    addr = {"id": str(ObjectId()), "label": "", "street": address["street"], "number": address.get("number", ""), "npa": address["npa"],
            "city": address["city"], "instructions": address.get("instructions")}
    await db.users.update_one({"_id": user["_id"]}, {"$push": {"addresses": addr}})


# ---------------------------------------------------------------------------
# Staff-side customers (phone orders) – same collection as customer accounts, no password until the customer registers
# ---------------------------------------------------------------------------
customers_router = APIRouter(prefix="/customers")


class CustomerIn(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = ""
    phone: str = Field(min_length=7)
    email: Optional[str] = None
    address: Optional[SavedAddress] = None


def _phone_roles():
    import staff_auth
    return staff_auth.require_roles("manager", "phone")


@customers_router.post("", response_model=UserOut, status_code=201)
async def create_customer(body: CustomerIn, _: dict = Depends(_phone_roles())):
    phone = normalize_phone(body.phone)
    if len(phone) < 7:
        raise HTTPException(400, "Numéro de téléphone invalide")
    if await db.users.find_one({"phone": phone}):
        raise HTTPException(409, "Un client existe déjà avec ce numéro")
    addresses = []
    if body.address:
        a = body.address.model_dump()
        a["id"] = str(ObjectId())
        addresses.append(a)
    doc = {"first_name": body.first_name.strip(), "last_name": body.last_name.strip(), "phone": phone, "email": (body.email or "").strip().lower() or None,
           "password_hash": None, "addresses": addresses, "created_at": datetime.now(timezone.utc), "created_by": "staff"}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return user_out(doc)


@customers_router.post("/{customer_id}/addresses", response_model=UserOut)
async def staff_add_address(customer_id: str, body: SavedAddress, _: dict = Depends(_phone_roles())):
    try:
        cid = ObjectId(customer_id)
    except Exception:
        raise HTTPException(404, "Customer not found")
    user = await db.users.find_one({"_id": cid})
    if not user:
        raise HTTPException(404, "Customer not found")
    await save_address_for_user(user, body.model_dump())
    return user_out(await db.users.find_one({"_id": cid}))

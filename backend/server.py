from fastapi import FastAPI, APIRouter, HTTPException, Query, Request, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from bson import ObjectId
from pydantic import BaseModel, Field, BeforeValidator, ConfigDict, AliasChoices
from typing import List, Optional, Dict, Any, Annotated, Literal
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pymongo import ReturnDocument
import os
import logging
from pathlib import Path

from seed_data import CATEGORIES, EXTRAS, PRODUCTS, DEFAULT_SETTINGS
from database import client, db
import auth as auth_mod
import photos as photos_mod

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Zurich")

app = FastAPI(title="Hallo Magic Pizza API")
api = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Mongo helpers
# ---------------------------------------------------------------------------
def _to_str(v):
    return str(v) if isinstance(v, ObjectId) else v


PyObjectId = Annotated[str, BeforeValidator(_to_str)]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, validation_alias=AliasChoices("_id", "id"))

    def to_mongo(self) -> dict:
        data = self.model_dump(exclude_none=True)
        data.pop("id", None)
        return data

    @classmethod
    def from_mongo(cls, doc: dict):
        if doc is None:
            return None
        doc = dict(doc)
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return cls(**doc)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class I18n(BaseModel):
    fr: str = ""
    de: str = ""


class Ingredient(BaseModel):
    id: str
    fr: str
    de: str


class Category(BaseDocument):
    slug: str
    name: I18n
    sort: int = 0
    image_url: Optional[str] = None
    active: bool = True
    filter: Optional[str] = None  # e.g. "gluten_free" -> virtual category built from product options


class Extra(BaseDocument):
    key: str
    name: I18n
    price: float
    available: bool = True
    max_quantity: int = 1
    vat_rate: Optional[float] = None  # % – None -> settings standard rate


class WineInfo(BaseModel):
    type: Optional[str] = None
    origin: Optional[str] = None
    bottle_size: Optional[str] = None


class SizeOption(BaseModel):
    key: str
    label: str
    price: float


class ProductOption(BaseModel):
    """Dough / base options (classic, gluten-free, lactose-free...)."""
    key: str
    group: str = "dough"
    name: I18n
    price: float = 0.0
    price_by_size: Dict[str, float] = {}
    only_sizes: List[str] = []
    default: bool = False


class Product(BaseDocument):
    category_id: str
    name: I18n
    description: I18n = I18n()
    price: float
    sizes: List[SizeOption] = []
    options: List[ProductOption] = []
    image_url: Optional[str] = None
    ingredients: List[Ingredient] = []
    allowed_extra_ids: List[str] = []
    customizable: bool = False
    allergens: I18n = I18n()
    available: bool = True
    is_alcohol: bool = False
    alcohol_type: Optional[str] = None  # "fermented" (beer, wine, prosecco -> 16+) | "spirits" (distilled -> 18+)
    images: List[str] = []  # additional photos (API urls); image_url is the main photo
    wine: Optional[WineInfo] = None
    sort: int = 0
    vat_rate: Optional[float] = None  # % – None -> derived from settings (alcohol vs standard)
    deleted_at: Optional[datetime] = None


class ProductIn(BaseModel):
    category_id: str
    name: I18n
    description: I18n = I18n()
    price: float
    sizes: List[SizeOption] = []
    options: List[ProductOption] = []
    image_url: Optional[str] = None
    ingredients: List[Ingredient] = []
    allowed_extra_ids: List[str] = []
    customizable: bool = False
    allergens: I18n = I18n()
    available: bool = True
    is_alcohol: bool = False
    alcohol_type: Optional[str] = None
    images: List[str] = []
    wine: Optional[WineInfo] = None
    sort: int = 0
    vat_rate: Optional[float] = None


class ProductPatch(BaseModel):
    vat_rate: Optional[float] = None
    category_id: Optional[str] = None
    name: Optional[I18n] = None
    description: Optional[I18n] = None
    price: Optional[float] = None
    sizes: Optional[List[SizeOption]] = None
    options: Optional[List[ProductOption]] = None
    image_url: Optional[str] = None
    ingredients: Optional[List[Ingredient]] = None
    allowed_extra_ids: Optional[List[str]] = None
    customizable: Optional[bool] = None
    allergens: Optional[I18n] = None
    available: Optional[bool] = None
    is_alcohol: Optional[bool] = None
    alcohol_type: Optional[str] = None
    images: Optional[List[str]] = None
    wine: Optional[WineInfo] = None
    sort: Optional[int] = None


class ExtraIn(BaseModel):
    key: str
    name: I18n
    price: float
    available: bool = True
    max_quantity: int = 1
    vat_rate: Optional[float] = None


class CategoryIn(BaseModel):
    slug: str
    name: I18n
    sort: int = 0
    image_url: Optional[str] = None
    active: bool = True
    filter: Optional[str] = None


class DeliveryZone(BaseModel):
    npa: str
    city: str
    minimum_order: float = 0


class Settings(BaseModel):
    restaurant_name: str = "Hallo Magic Pizza"
    # Fiscal / business identity (editable in admin)
    business_name: str = "Hallo Magic Pizza"
    street: str = "Route de Chésalles 19"
    postal_code: str = "1723"
    city: str = "Marly"
    vat_number: str = "CHE-156.631.035 TVA"
    vat_rate_standard: float = 2.6   # food & non-alcoholic drinks
    vat_rate_alcohol: float = 8.1    # beer, wine, spirits
    delivery_fee_vat_rate: float = 2.6
    phone: str = ""
    address: str = ""
    opening_hours: Dict[str, str] = {}
    temporarily_closed: bool = False
    closed_message: I18n = I18n()
    delivery_enabled: bool = True
    pickup_enabled: bool = True
    minimum_order: float = 0
    delivery_fee: float = 0
    free_delivery_from: Optional[float] = None
    delivery_zones: List[DeliveryZone] = []


# ----- Orders -----
OrderType = Literal["pickup", "delivery"]
PICKUP_FLOW = ["pending", "accepted", "preparing", "ready", "picked_up", "completed"]
DELIVERY_FLOW = ["pending", "accepted", "preparing", "ready", "assigned", "delivering", "delivered", "completed"]
TERMINAL = {"completed", "cancelled"}

NOTIF_TEXT = {
    "order_received": {"fr": "Commande reçue", "de": "Bestellung erhalten",
                        "body_fr": "Votre commande #{n} a bien été reçue. En attente de confirmation.",
                        "body_de": "Ihre Bestellung #{n} ist eingegangen. Warten auf Bestätigung."},
    "order_accepted": {"fr": "Commande acceptée", "de": "Bestellung angenommen",
                        "body_fr": "Commande acceptée – prête vers {t}.", "body_de": "Bestellung angenommen – bereit gegen {t}."},
    "preparing": {"fr": "En préparation", "de": "In Zubereitung",
                  "body_fr": "Votre commande #{n} est en préparation.", "body_de": "Ihre Bestellung #{n} wird zubereitet."},
    "ready": {"fr": "Prête à retirer", "de": "Abholbereit",
              "body_fr": "Votre commande #{n} est prête à être retirée.", "body_de": "Ihre Bestellung #{n} ist abholbereit."},
    "ready_delivery": {"fr": "Prête pour livraison", "de": "Bereit zur Lieferung",
                       "body_fr": "Votre commande #{n} est prête et part bientôt.", "body_de": "Ihre Bestellung #{n} ist bereit und geht bald raus."},
    "assigned": {"fr": "Attribuée au livreur", "de": "Kurier zugewiesen",
                 "body_fr": "Un livreur a pris en charge votre commande #{n}.", "body_de": "Ein Kurier hat Ihre Bestellung #{n} übernommen."},
    "delivering": {"fr": "En livraison", "de": "Unterwegs",
                   "body_fr": "Votre commande #{n} est en route.", "body_de": "Ihre Bestellung #{n} ist unterwegs."},
    "delivered": {"fr": "Livrée", "de": "Geliefert",
                  "body_fr": "Votre commande #{n} a été livrée. Bon appétit!", "body_de": "Ihre Bestellung #{n} wurde geliefert. En Guete!"},
    "picked_up": {"fr": "Retirée", "de": "Abgeholt",
                  "body_fr": "Merci et bon appétit!", "body_de": "Danke und en Guete!"},
    "completed": {"fr": "Terminée", "de": "Abgeschlossen",
                  "body_fr": "Commande #{n} terminée. Merci!", "body_de": "Bestellung #{n} abgeschlossen. Danke!"},
    "cancelled": {"fr": "Commande annulée", "de": "Bestellung storniert",
                  "body_fr": "Votre commande #{n} a été annulée. {r}", "body_de": "Ihre Bestellung #{n} wurde storniert. {r}"},
    "delay": {"fr": "Retard estimé", "de": "Verspätung",
              "body_fr": "Votre commande aura environ {d} minutes de retard. Nouvelle heure estimée: {t}.",
              "body_de": "Ihre Bestellung verspätet sich um ca. {d} Minuten. Neue geschätzte Zeit: {t}."},
}


class OrderExtraIn(BaseModel):
    extra_id: str
    quantity: int = 1


class OrderItemIn(BaseModel):
    product_id: str
    quantity: int = 1
    size_key: Optional[str] = None
    option_keys: List[str] = []
    removed_ingredient_ids: List[str] = []
    extras: List[OrderExtraIn] = []
    note: Optional[str] = None


class CustomerIn(BaseModel):
    first_name: str
    last_name: str = ""
    phone: str
    email: Optional[str] = None


class AddressIn(BaseModel):
    street: str
    number: str = ""
    npa: str
    city: str
    instructions: Optional[str] = None


class OrderIn(BaseModel):
    type: OrderType
    source: str = "web"
    items: List[OrderItemIn]
    customer: CustomerIn
    address: Optional[AddressIn] = None
    requested_time: Optional[str] = None  # "asap" or "HH:MM"
    general_note: Optional[str] = None
    age_confirmed: bool = False
    save_address: bool = False  # logged-in customers: store the delivery address in the profile
    language: str = "fr"


PAYMENT_METHODS = {
    "pay_at_pickup": ("PAIEMENT AU RETRAIT", "Paiement au retrait"),
    "pay_at_delivery": ("PAIEMENT A LA LIVRAISON", "Paiement à la livraison"),
    "cash": ("ESPECES", "Espèces"),
    "terminal": ("TERMINAL (CARTE)", "Terminal (carte)"),
}


def payment_label(o: dict, upper: bool) -> str:
    pm = o.get("payment_method") or ("pay_at_pickup" if o["type"] == "pickup" else "pay_at_delivery")
    return PAYMENT_METHODS.get(pm, PAYMENT_METHODS["pay_at_pickup"])[0 if upper else 1]


class PhoneOrderIn(OrderIn):
    """Order entered by restaurant staff on an iPad ("Poste 1" / "Poste 2") while the customer is on the phone."""
    station: int = 1
    payment_method: str = "pay_at_pickup"
    customer_id: Optional[str] = None  # customers collection (= users) – links the order to the caller
    minutes: Optional[int] = None      # preparation estimate when requested_time is "asap" (default 30)


class OrderExtra(BaseModel):
    extra_id: str
    name: I18n
    unit_price: float
    quantity: int
    # VAT snapshot at order time (for the whole extra line = unit_price * quantity * item quantity)
    vat_rate: float = 0.0
    gross_amount: float = 0.0
    net_amount: float = 0.0
    vat_amount: float = 0.0


class OrderItemOption(BaseModel):
    key: str
    name: I18n
    price: float


class VatGroup(BaseModel):
    rate: float
    gross: float
    net: float
    vat: float


class OrderItem(BaseModel):
    product_id: str
    name: I18n
    unit_price: float
    quantity: int
    size: Optional[SizeOption] = None
    options: List[OrderItemOption] = []
    removed_ingredients: List[Ingredient] = []
    extras: List[OrderExtra] = []
    note: Optional[str] = None
    line_total: float
    # VAT snapshot at order time (product part = unit_price * quantity, extras carry their own snapshot)
    vat_rate: float = 0.0
    gross_amount: float = 0.0
    net_amount: float = 0.0
    vat_amount: float = 0.0


class Notification(BaseModel):
    event: str
    title: I18n
    body: I18n
    created_at: datetime
    push_sent: bool = False


class StatusEvent(BaseModel):
    status: str
    at: datetime


class Order(BaseDocument):
    order_number: int
    type: OrderType
    source: str
    status: str
    items: List[OrderItem]
    customer: CustomerIn
    address: Optional[AddressIn] = None
    requested_time: Optional[str] = None
    general_note: Optional[str] = None
    payment_method: str
    language: str = "fr"
    age_confirmed: bool = False
    age_required: Optional[int] = None  # 16 (beer/wine) or 18 (spirits) – staff/driver must check ID at handover
    user_id: Optional[str] = None       # customer account (None = guest)
    station: Optional[int] = None       # phone orders: iPad "Poste 1" / "Poste 2"
    driver: Optional[str] = None        # delivery: "Livreur 1" / "Livreur 2" / "Livreur 3"
    subtotal: float
    extras_total: float
    delivery_fee: float
    total: float
    # Fiscal snapshot (all amounts gross = VAT included, CHF)
    subtotal_gross: float = 0.0
    delivery_fee_gross: float = 0.0
    delivery_fee_vat_rate: float = 0.0
    discount_gross: float = 0.0
    total_gross: float = 0.0
    vat_breakdown: List[VatGroup] = []
    total_vat: float = 0.0
    total_net: float = 0.0
    paid: bool = False
    receipt_printed: bool = False
    receipt_printed_at: Optional[datetime] = None
    receipt_print_attempts: int = 0
    created_at: datetime
    accepted_at: Optional[datetime] = None
    estimated_minutes: Optional[int] = None
    estimated_ready_at: Optional[datetime] = None
    time_changed: bool = False  # staff changed the customer's requested time
    delay_minutes_total: int = 0
    reject_reason: Optional[str] = None
    printed: bool = False
    printed_at: Optional[datetime] = None
    print_attempts: int = 0
    print_status: Optional[str] = None  # simulated | sent | failed
    notifications: List[Notification] = []
    status_history: List[StatusEvent] = []


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
async def seed():
    if await db.categories.count_documents({}) == 0:
        await db.categories.insert_many([Category(**c).to_mongo() for c in CATEGORIES])
    if await db.extras.count_documents({}) == 0:
        await db.extras.insert_many([
            Extra(key=k, name=I18n(fr=fr, de=de), price=p, max_quantity=mq).to_mongo() for k, fr, de, p, mq in EXTRAS
        ])
    if await db.products.count_documents({}) == 0:
        cats = {c["slug"]: str(c["_id"]) async for c in db.categories.find({})}
        docs = []
        for i, p in enumerate(PRODUCTS):
            p = dict(p)
            slug = p.pop("category_slug")
            docs.append(Product(category_id=cats[slug], sort=i, **p).to_mongo())
        await db.products.insert_many(docs)
    if await db.settings.count_documents({"_id": "main"}) == 0:
        await db.settings.insert_one({"_id": "main", **Settings(**DEFAULT_SETTINGS).model_dump()})
    else:
        # One-time fiscal migration for settings created before VAT support
        sdoc = await db.settings.find_one({"_id": "main"})
        if "vat_number" not in sdoc:
            fiscal = {k: DEFAULT_SETTINGS[k] for k in ("business_name", "street", "postal_code", "city", "vat_number",
                                                      "vat_rate_standard", "vat_rate_alcohol", "delivery_fee_vat_rate", "phone", "address")}
            await db.settings.update_one({"_id": "main"}, {"$set": fiscal})
    # Give every product / extra an explicit, editable VAT rate (defaults: alcohol 8.1%, everything else 2.6%)
    s = await get_settings()
    await db.products.update_many({"vat_rate": None, "is_alcohol": True}, {"$set": {"vat_rate": s.vat_rate_alcohol}})
    await db.products.update_many({"vat_rate": None}, {"$set": {"vat_rate": s.vat_rate_standard}})
    await db.extras.update_many({"vat_rate": None}, {"$set": {"vat_rate": s.vat_rate_standard}})
    # Alcohol group for age check: existing alcoholic products (beer, wine) are fermented -> 16+
    await db.products.update_many({"is_alcohol": True, "alcohol_type": None}, {"$set": {"alcohol_type": "fermented"}})
    await auth_mod.ensure_indexes()
    try:
        photos_mod.init_storage()
    except Exception as e:  # storage unavailable -> uploads will retry lazily
        logger.warning("Object storage init failed: %s", e)
    logger.info("Seed check complete")


@app.on_event("startup")
async def on_startup():
    await seed()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# ---------------------------------------------------------------------------
# Menu / catalog
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"app": "Hallo Magic Pizza API", "status": "ok"}


@api.get("/menu")
async def get_menu(include_unavailable: bool = False):
    cats = [Category.from_mongo(c) async for c in db.categories.find({"active": True}).sort("sort", 1)]
    q: Dict[str, Any] = {"deleted_at": None}
    products = [Product.from_mongo(p) async for p in db.products.find(q).sort("sort", 1)]
    if not include_unavailable:
        # Sold-out items are still returned but flagged, so clients can render "unavailable"
        pass
    extras = [Extra.from_mongo(e) async for e in db.extras.find({}).sort("price", 1)]
    settings = await get_settings()
    return {"categories": cats, "products": products, "extras": extras, "settings": settings}


@api.get("/categories", response_model=List[Category])
async def list_categories():
    return [Category.from_mongo(c) async for c in db.categories.find({}).sort("sort", 1)]


@api.post("/categories", response_model=Category)
async def create_category(body: CategoryIn):
    res = await db.categories.insert_one(Category(**body.model_dump()).to_mongo())
    return Category.from_mongo(await db.categories.find_one({"_id": res.inserted_id}))


@api.put("/categories/{cat_id}", response_model=Category)
async def update_category(cat_id: str, body: CategoryIn):
    doc = await db.categories.find_one_and_update({"_id": oid(cat_id)}, {"$set": body.model_dump()}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(404, "Category not found")
    return Category.from_mongo(doc)


@api.get("/products", response_model=List[Product])
async def list_products(category_id: Optional[str] = None):
    q: Dict[str, Any] = {"deleted_at": None}
    if category_id:
        q["category_id"] = category_id
    return [Product.from_mongo(p) async for p in db.products.find(q).sort("sort", 1)]


@api.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    doc = await db.products.find_one({"_id": oid(product_id), "deleted_at": None})
    if not doc:
        raise HTTPException(404, "Product not found")
    return Product.from_mongo(doc)


@api.post("/products", response_model=Product)
async def create_product(body: ProductIn):
    res = await db.products.insert_one(Product(**body.model_dump()).to_mongo())
    return Product.from_mongo(await db.products.find_one({"_id": res.inserted_id}))


@api.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, body: ProductIn):
    doc = await db.products.find_one_and_update({"_id": oid(product_id)}, {"$set": body.model_dump()}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(404, "Product not found")
    return Product.from_mongo(doc)


@api.patch("/products/{product_id}", response_model=Product)
async def patch_product(product_id: str, body: ProductPatch):
    update = body.model_dump(exclude_unset=True)
    if not update:
        raise HTTPException(400, "Nothing to update")
    doc = await db.products.find_one_and_update({"_id": oid(product_id)}, {"$set": update}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(404, "Product not found")
    return Product.from_mongo(doc)


@api.delete("/products/{product_id}")
async def delete_product(product_id: str):
    res = await db.products.update_one({"_id": oid(product_id)}, {"$set": {"deleted_at": now_utc(), "available": False}})
    if res.matched_count == 0:
        raise HTTPException(404, "Product not found")
    return {"ok": True}


@api.get("/extras", response_model=List[Extra])
async def list_extras():
    return [Extra.from_mongo(e) async for e in db.extras.find({}).sort("price", 1)]


@api.post("/extras", response_model=Extra)
async def create_extra(body: ExtraIn):
    if await db.extras.find_one({"key": body.key}):
        raise HTTPException(400, "Extra key already exists")
    res = await db.extras.insert_one(Extra(**body.model_dump()).to_mongo())
    return Extra.from_mongo(await db.extras.find_one({"_id": res.inserted_id}))


@api.put("/extras/{extra_id}", response_model=Extra)
async def update_extra(extra_id: str, body: ExtraIn):
    doc = await db.extras.find_one_and_update({"_id": oid(extra_id)}, {"$set": body.model_dump()}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(404, "Extra not found")
    return Extra.from_mongo(doc)


@api.delete("/extras/{extra_id}")
async def delete_extra(extra_id: str):
    res = await db.extras.delete_one({"_id": oid(extra_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Extra not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@api.get("/settings", response_model=Settings)
async def get_settings():
    doc = await db.settings.find_one({"_id": "main"})
    if not doc:
        return Settings(**DEFAULT_SETTINGS)
    doc.pop("_id", None)
    return Settings(**doc)


@api.put("/settings", response_model=Settings)
async def update_settings(body: Settings):
    await db.settings.update_one({"_id": "main"}, {"$set": body.model_dump()}, upsert=True)
    return body


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
def fmt_time(dt: Optional[datetime]) -> str:
    if not dt:
        return "--:--"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ).strftime("%H:%M")


def make_notification(event: str, n: int, t: str = "", d: int = 0, r: str = "") -> dict:
    tx = NOTIF_TEXT[event]
    return Notification(
        event=event,
        title=I18n(fr=tx["fr"], de=tx["de"]),
        body=I18n(fr=tx["body_fr"].format(n=n, t=t, d=d, r=r).strip(), de=tx["body_de"].format(n=n, t=t, d=d, r=r).strip()),
        created_at=now_utc(),
    ).model_dump()


def split_vat(gross: float, rate: float):
    """VAT-inclusive split: net = gross / (1 + rate), vat = gross - net. Rounded to 0.01, always reconciling."""
    gross = round(gross, 2)
    net = round(gross / (1 + rate / 100.0), 2)
    return gross, net, round(gross - net, 2)


def vat_breakdown(groups: Dict[float, float], discount: float = 0.0) -> List[VatGroup]:
    """Group gross amounts per rate. A (future) discount is allocated proportionally to each rate group so
    net + vat always equals the customer total."""
    total = sum(groups.values())
    out: List[VatGroup] = []
    allocated = 0.0
    rates = sorted(groups)
    for i, rate in enumerate(rates):
        gross = groups[rate]
        if discount and total:
            share = round(discount * gross / total, 2) if i < len(rates) - 1 else round(discount - allocated, 2)
            allocated += share
            gross -= share
        if round(gross, 2) == 0:
            continue
        g, n, v = split_vat(gross, rate)
        out.append(VatGroup(rate=rate, gross=g, net=n, vat=v))
    return out


async def next_order_number() -> int:
    doc = await db.counters.find_one_and_update(
        {"_id": "orders"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return 100 + doc["seq"]


async def load_order(order_id: str) -> dict:
    doc = await db.orders.find_one({"_id": oid(order_id)})
    if not doc:
        raise HTTPException(404, "Order not found")
    return doc


def required_age(products: List[dict]) -> Optional[int]:
    """16+ for fermented drinks (beer, wine, prosecco), 18+ for spirits. Mixed cart -> 18+."""
    ages = [18 if p.get("alcohol_type") == "spirits" else 16 for p in products if p.get("is_alcohol")]
    return max(ages) if ages else None


async def compute_order(body: OrderIn, user: Optional[dict]) -> Order:
    """Validates the cart against the live catalog and builds the full Order (prices + frozen VAT snapshot).
    Shared by customer checkout (/orders) and staff phone orders (/phone-orders)."""
    settings = await get_settings()
    if settings.temporarily_closed:
        raise HTTPException(400, "Restaurant temporarily closed")
    if body.type == "delivery" and not settings.delivery_enabled:
        raise HTTPException(400, "Delivery disabled")
    if body.type == "pickup" and not settings.pickup_enabled:
        raise HTTPException(400, "Pickup disabled")
    if body.type == "delivery" and not body.address:
        raise HTTPException(400, "Address required for delivery")
    if not body.items:
        raise HTTPException(400, "Empty order")

    extras_by_id = {str(e["_id"]): e for e in await db.extras.find({}).to_list(500)}
    items: List[OrderItem] = []
    subtotal = 0.0
    extras_total = 0.0
    alcohol_products: List[dict] = []
    vat_groups: Dict[float, float] = {}
    for it in body.items:
        pdoc = await db.products.find_one({"_id": oid(it.product_id), "deleted_at": None})
        if not pdoc:
            raise HTTPException(400, f"Product {it.product_id} not found")
        if not pdoc.get("available", True):
            raise HTTPException(400, f"{pdoc['name']['fr']} n'est plus disponible")
        if pdoc.get("is_alcohol"):
            alcohol_products.append(pdoc)
        prod_rate = pdoc.get("vat_rate")
        if prod_rate is None:
            prod_rate = settings.vat_rate_alcohol if pdoc.get("is_alcohol") else settings.vat_rate_standard
        qty = max(1, it.quantity)
        allowed = set(pdoc.get("allowed_extra_ids", []))
        ex_list: List[OrderExtra] = []
        ex_sum = 0.0
        for ex in it.extras:
            edoc = extras_by_id.get(ex.extra_id)
            if not edoc or (edoc["key"] not in allowed and ex.extra_id not in allowed):
                raise HTTPException(400, "Extra not allowed for this product")
            eqty = max(1, min(ex.quantity, edoc.get("max_quantity", 1)))
            ex_rate = edoc.get("vat_rate")
            if ex_rate is None:
                ex_rate = settings.vat_rate_standard
            eg, en, ev = split_vat(edoc["price"] * eqty * qty, ex_rate)
            vat_groups[ex_rate] = vat_groups.get(ex_rate, 0.0) + eg
            ex_list.append(OrderExtra(extra_id=ex.extra_id, name=I18n(**edoc["name"]), unit_price=edoc["price"], quantity=eqty,
                                      vat_rate=ex_rate, gross_amount=eg, net_amount=en, vat_amount=ev))
            ex_sum += edoc["price"] * eqty
        removed = [Ingredient(**i) for i in pdoc.get("ingredients", []) if i["id"] in set(it.removed_ingredient_ids)]
        # Size
        size: Optional[SizeOption] = None
        base_price = pdoc["price"]
        sizes = pdoc.get("sizes") or []
        if sizes:
            sdoc = next((s for s in sizes if s["key"] == it.size_key), None) or sizes[0]
            size = SizeOption(**sdoc)
            base_price = sdoc["price"]
        # Options (dough, lactose-free...)
        opts: List[OrderItemOption] = []
        opt_sum = 0.0
        for odoc in pdoc.get("options") or []:
            if odoc["key"] in set(it.option_keys) and not odoc.get("default"):
                if odoc.get("only_sizes") and size and size.key not in odoc["only_sizes"]:
                    raise HTTPException(400, f"Option {odoc['name']['fr']} non disponible pour {size.label}")
                p = odoc.get("price_by_size", {}).get(size.key if size else "", odoc.get("price", 0.0))
                opts.append(OrderItemOption(key=odoc["key"], name=I18n(**odoc["name"]), price=p))
                opt_sum += p
        qty = max(1, it.quantity)
        unit = base_price + opt_sum
        line_total = round((unit + ex_sum) * qty, 2)
        subtotal += unit * qty
        extras_total += ex_sum * qty
        pg, pn, pv = split_vat(unit * qty, prod_rate)
        vat_groups[prod_rate] = vat_groups.get(prod_rate, 0.0) + pg
        items.append(OrderItem(
            product_id=it.product_id, name=I18n(**pdoc["name"]), unit_price=unit, quantity=qty, size=size, options=opts,
            removed_ingredients=removed, extras=ex_list, note=(it.note or None), line_total=line_total,
            vat_rate=prod_rate, gross_amount=pg, net_amount=pn, vat_amount=pv,
        ))
    age_req = required_age(alcohol_products)
    if age_req and not body.age_confirmed:
        raise HTTPException(400, f"Confirmation d'âge requise ({age_req}+) pour les boissons alcoolisées")

    goods = round(subtotal + extras_total, 2)
    delivery_fee = 0.0
    if body.type == "delivery":
        zone = next((z for z in settings.delivery_zones if z.npa == (body.address.npa if body.address else "")), None)
        if settings.delivery_zones and not zone:
            raise HTTPException(400, "Zone de livraison non desservie")
        minimum = zone.minimum_order if zone and zone.minimum_order else settings.minimum_order
        if goods < minimum:
            raise HTTPException(400, f"Minimum de commande CHF {minimum:.2f} pour la livraison à {zone.city if zone else ''}")
        delivery_fee = settings.delivery_fee
        if settings.free_delivery_from and goods >= settings.free_delivery_from:
            delivery_fee = 0.0
    total = round(goods + delivery_fee, 2)
    if delivery_fee > 0:
        vat_groups[settings.delivery_fee_vat_rate] = vat_groups.get(settings.delivery_fee_vat_rate, 0.0) + round(delivery_fee, 2)
    discount = 0.0  # promotions not implemented yet – allocation across VAT groups is handled in vat_breakdown()
    breakdown = vat_breakdown(vat_groups, discount)
    total_net = round(sum(g.net for g in breakdown), 2)
    total_vat = round(sum(g.vat for g in breakdown), 2)

    number = await next_order_number()
    ts = now_utc()
    return Order(
        order_number=number, type=body.type, source=body.source, status="pending", items=items,
        customer=body.customer, address=body.address if body.type == "delivery" else None,
        requested_time=body.requested_time, general_note=body.general_note or None,
        payment_method="pay_at_delivery" if body.type == "delivery" else "pay_at_pickup",
        language=body.language, age_confirmed=bool(age_req) and body.age_confirmed, age_required=age_req,
        user_id=str(user["_id"]) if user else None,
        subtotal=round(subtotal, 2), extras_total=round(extras_total, 2), delivery_fee=delivery_fee, total=total,
        subtotal_gross=goods, delivery_fee_gross=round(delivery_fee, 2), delivery_fee_vat_rate=settings.delivery_fee_vat_rate if delivery_fee > 0 else 0.0,
        discount_gross=discount, total_gross=total, vat_breakdown=breakdown, total_vat=total_vat, total_net=total_net,
        created_at=ts, status_history=[StatusEvent(status="pending", at=ts)],
        notifications=[Notification(**make_notification("order_received", number))],
    )


@api.post("/orders", response_model=Order)
async def create_order(body: OrderIn, user: Optional[dict] = Depends(auth_mod.optional_user)):
    order = await compute_order(body, user)
    res = await db.orders.insert_one(order.to_mongo())
    if user and body.save_address and body.type == "delivery" and body.address:
        await auth_mod.save_address_for_user(user, body.address.model_dump())
    return Order.from_mongo(await db.orders.find_one({"_id": res.inserted_id}))


@api.post("/phone-orders", response_model=Order)
async def create_phone_order(body: PhoneOrderIn):
    """Staff-entered phone order: same catalog, prices, VAT snapshot, ticket and receipt as any other order.
    Created directly as ACCEPTED (staff confirmed it on the phone) and printed once immediately."""
    if body.station not in (1, 2):
        raise HTTPException(400, "station must be 1 or 2")
    if body.payment_method not in PAYMENT_METHODS:
        raise HTTPException(400, "Invalid payment method")
    customer = await db.users.find_one({"_id": oid(body.customer_id)}) if body.customer_id else None
    body.source = "telephone"
    body.age_confirmed = True  # staff informs the caller; the 16+/18+ ID check happens at handover (ticket + dashboard warning)
    order = await compute_order(body, customer)
    ts = now_utc()
    if body.requested_time and body.requested_time != "asap":
        ready = parse_local_time(body.requested_time)
        minutes = max(0, int((ready - ts).total_seconds() // 60))
    else:
        minutes = body.minutes if body.minutes is not None else 30
        ready = ts + timedelta(minutes=minutes)
    doc = order.to_mongo()
    doc.update({
        "status": "accepted", "station": body.station, "payment_method": body.payment_method, "accepted_at": ts,
        "estimated_minutes": minutes, "estimated_ready_at": ready, "time_changed": False,
        "status_history": [StatusEvent(status="pending", at=ts).model_dump(), StatusEvent(status="accepted", at=ts).model_dump()],
        "notifications": [make_notification("order_received", order.order_number), make_notification("order_accepted", order.order_number, t=fmt_time(ready))],
    })
    res = await db.orders.insert_one(doc)
    if customer and body.save_address and body.type == "delivery" and body.address:
        await auth_mod.save_address_for_user(customer, body.address.model_dump())
    # One kitchen print job (same pipeline / duplicate guard as the dashboard "accept")
    try:
        await do_print(await load_order(str(res.inserted_id)), force=False)
    except HTTPException:
        pass
    return Order.from_mongo(await load_order(str(res.inserted_id)))


class AssignIn(BaseModel):
    driver: str  # "Livreur 1" | "Livreur 2" | "Livreur 3"


@api.post("/orders/{order_id}/assign", response_model=Order)
async def assign_driver(order_id: str, body: AssignIn):
    doc = await load_order(order_id)
    if doc["type"] != "delivery":
        raise HTTPException(400, "Only delivery orders can be assigned")
    if doc["status"] not in ("accepted", "preparing", "ready", "assigned"):
        raise HTTPException(400, "Order cannot be assigned in its current status")
    if doc["status"] in ("ready", "assigned"):
        notif = make_notification("assigned", doc["order_number"]) if doc["status"] == "ready" else None
        return await push_status(doc, "assigned", notif, {"driver": body.driver})
    new = await db.orders.find_one_and_update({"_id": doc["_id"]}, {"$set": {"driver": body.driver}}, return_document=ReturnDocument.AFTER)
    return Order.from_mongo(new)


@api.get("/me/orders", response_model=List[Order])
async def my_orders(user: dict = Depends(auth_mod.current_user), limit: int = 50):
    docs = await db.orders.find({"user_id": str(user["_id"])}).sort("created_at", -1).to_list(limit)
    return [Order.from_mongo(d) for d in docs]


@api.get("/customers/search")
async def search_customers(phone: str = Query(min_length=3), limit: int = 20):
    """Staff / phone-order lookup: accounts + past orders matching a phone number (accounts and guests)."""
    digits = auth_mod.normalize_phone(phone)
    if len(digits) < 3:
        raise HTTPException(400, "Numéro trop court")
    accounts = [auth_mod.user_out(u).model_dump() async for u in db.users.find({"phone": {"$regex": digits}}).limit(limit)]
    # Guest orders store the phone as typed -> compare on digits only
    pattern = r"\D*".join(digits)
    docs = await db.orders.find({"customer.phone": {"$regex": pattern}}).sort("created_at", -1).to_list(limit)
    return {"accounts": accounts, "orders": [Order.from_mongo(d).model_dump() for d in docs]}


@api.get("/orders", response_model=List[Order])
async def list_orders(active: bool = True, ids: Optional[str] = None, limit: int = 100):
    q: Dict[str, Any] = {}
    if ids:
        q["_id"] = {"$in": [oid(i) for i in ids.split(",") if i]}
    elif active:
        q["$or"] = [
            {"status": {"$nin": list(TERMINAL)}},
            {"status": {"$in": list(TERMINAL)}, "created_at": {"$gte": now_utc() - timedelta(hours=3)}},
        ]
    docs = await db.orders.find(q).sort("created_at", -1).to_list(limit)
    return [Order.from_mongo(d) for d in docs]


@api.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    return Order.from_mongo(await load_order(order_id))


class AcceptIn(BaseModel):
    minutes: Optional[int] = None  # estimated preparation time
    time: Optional[str] = None     # exact "HH:MM" (confirm or change the requested time)


class RejectIn(BaseModel):
    reason: Optional[str] = None


class DelayIn(BaseModel):
    minutes: Optional[int] = None
    time: Optional[str] = None


class StatusIn(BaseModel):
    status: str


def parse_local_time(hhmm: str) -> datetime:
    try:
        h, m = [int(x) for x in hhmm.strip().split(":")]
    except Exception:
        raise HTTPException(400, "Invalid time, expected HH:MM")
    local_now = datetime.now(TZ)
    target = local_now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target < local_now - timedelta(hours=2):
        target += timedelta(days=1)
    return target.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Printing (PrintNode architecture – disabled until credentials are configured)
# ---------------------------------------------------------------------------
PRINTNODE_API_KEY = os.environ.get("PRINTNODE_API_KEY", "")
PRINTNODE_PRINTER_ID = os.environ.get("PRINTNODE_PRINTER_ID", "")


async def send_to_printer(order_doc: dict, text: str, kind: str = "kitchen") -> str:
    """Create a print job. Returns status: 'sent' | 'failed' | 'simulated'.
    With PrintNode credentials configured, this posts a raw job to the Epson TM-T70II via PrintNode.
    Without credentials the job is only recorded (simulated) – nothing touches the existing installation."""
    job = {
        "order_id": str(order_doc["_id"]), "order_number": order_doc["order_number"], "provider": "printnode", "kind": kind,
        "printer_id": PRINTNODE_PRINTER_ID or None, "content": text, "created_at": now_utc(), "status": "queued",
    }
    if not PRINTNODE_API_KEY or not PRINTNODE_PRINTER_ID:
        job["status"] = "simulated"
        await db.print_jobs.insert_one(job)
        return "simulated"
    try:
        import base64
        import requests  # PrintNode REST API
        esc = "\x1b@" + text + "\n\n\n\n\x1dV\x00"  # ESC/POS init + cut
        payload = {"printerId": int(PRINTNODE_PRINTER_ID), "title": f"Commande #{order_doc['order_number']}",
                   "contentType": "raw_base64", "content": base64.b64encode(esc.encode("cp1252", "replace")).decode(),
                   "source": "Hallo Magic Pizza"}
        r = requests.post("https://api.printnode.com/printjobs", json=payload, auth=(PRINTNODE_API_KEY, ""), timeout=10)
        job["status"] = "sent" if r.ok else "failed"
        job["provider_response"] = r.text[:500]
    except Exception as e:  # network / config error
        job["status"] = "failed"
        job["error"] = str(e)
    await db.print_jobs.insert_one(job)
    return job["status"]


async def do_print(doc: dict, force: bool) -> dict:
    if doc.get("printed") and not force:
        raise HTTPException(409, "Ticket already printed")
    # Guard against accidental double taps: refuse a second job within 10 seconds
    last = doc.get("printed_at")
    if last and not force:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now_utc() - last < timedelta(seconds=10):
            raise HTTPException(409, "Print job already in progress")
    settings = await get_settings()
    text = build_ticket(doc, settings)
    status = await send_to_printer(doc, text)
    new = await db.orders.find_one_and_update(
        {"_id": doc["_id"]},
        {"$set": {"printed": True, "printed_at": now_utc(), "print_status": status}, "$inc": {"print_attempts": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return {"ok": True, "printed": True, "printed_at": new["printed_at"], "print_attempts": new["print_attempts"],
            "print_status": status, "text": text}


async def push_status(doc: dict, status: str, notif: Optional[dict], extra_set: Optional[dict] = None) -> Order:
    update: Dict[str, Any] = {"$set": {"status": status, **(extra_set or {})},
                              "$push": {"status_history": StatusEvent(status=status, at=now_utc()).model_dump()}}
    if notif:
        update["$push"]["notifications"] = notif
    new = await db.orders.find_one_and_update({"_id": doc["_id"]}, update, return_document=ReturnDocument.AFTER)
    return Order.from_mongo(new)


@api.post("/orders/{order_id}/accept", response_model=Order)
async def accept_order(order_id: str, body: AcceptIn):
    doc = await load_order(order_id)
    if doc["status"] != "pending":
        raise HTTPException(400, "Order is not pending")
    ts = now_utc()
    if body.time:
        ready = parse_local_time(body.time)
        minutes = max(0, int((ready - ts).total_seconds() // 60))
    elif body.minutes is not None:
        minutes = body.minutes
        ready = ts + timedelta(minutes=minutes)
    else:
        raise HTTPException(400, "minutes or time required")
    requested = doc.get("requested_time")
    changed = bool(requested and requested != "asap" and fmt_time(ready) != requested)
    notif = make_notification("order_accepted", doc["order_number"], t=fmt_time(ready))
    order = await push_status(doc, "accepted", notif, {"accepted_at": ts, "estimated_minutes": minutes, "estimated_ready_at": ready, "time_changed": changed})
    # Automatic kitchen print on acceptance (idempotent: skipped if already printed)
    try:
        fresh = await load_order(order_id)
        if not fresh.get("printed"):
            await do_print(fresh, force=False)
            order = Order.from_mongo(await load_order(order_id))
    except HTTPException:
        pass
    return order


@api.post("/orders/{order_id}/reject", response_model=Order)
async def reject_order(order_id: str, body: RejectIn):
    doc = await load_order(order_id)
    if doc["status"] in TERMINAL:
        raise HTTPException(400, "Order already closed")
    notif = make_notification("cancelled", doc["order_number"], r=body.reason or "")
    return await push_status(doc, "cancelled", notif, {"reject_reason": body.reason})


@api.post("/orders/{order_id}/delay", response_model=Order)
async def delay_order(order_id: str, body: DelayIn):
    """Add +N minutes or set a new exact time. Customer is notified immediately."""
    doc = await load_order(order_id)
    if doc["status"] in TERMINAL or doc["status"] == "pending":
        raise HTTPException(400, "Order must be accepted first")
    base = doc.get("estimated_ready_at") or now_utc()
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    if body.time:
        new_ready = parse_local_time(body.time)
        delta = int(round((new_ready - base).total_seconds() / 60))
    elif body.minutes is not None:
        delta = body.minutes
        new_ready = base + timedelta(minutes=delta)
    else:
        raise HTTPException(400, "minutes or time required")
    notif = make_notification("delay", doc["order_number"], t=fmt_time(new_ready), d=abs(delta))
    new = await db.orders.find_one_and_update(
        {"_id": doc["_id"]},
        {"$set": {"estimated_ready_at": new_ready, "time_changed": True},
         "$inc": {"delay_minutes_total": delta, "estimated_minutes": delta},
         "$push": {"notifications": notif}},
        return_document=ReturnDocument.AFTER,
    )
    return Order.from_mongo(new)


STATUS_EVENT = {
    "preparing": "preparing", "ready": None, "assigned": "assigned", "delivering": "delivering",
    "delivered": "delivered", "picked_up": "picked_up", "completed": "completed", "cancelled": "cancelled",
}


@api.post("/orders/{order_id}/status", response_model=Order)
async def set_status(order_id: str, body: StatusIn):
    doc = await load_order(order_id)
    flow = PICKUP_FLOW if doc["type"] == "pickup" else DELIVERY_FLOW
    if body.status not in flow and body.status != "cancelled":
        raise HTTPException(400, f"Invalid status for {doc['type']}")
    if doc["status"] in TERMINAL:
        raise HTTPException(400, "Order already closed")
    if doc["status"] == "pending" and body.status not in ("cancelled",):
        raise HTTPException(400, "Accept the order first")
    n = doc["order_number"]
    if body.status == "ready":
        ev = "ready" if doc["type"] == "pickup" else "ready_delivery"
    else:
        ev = STATUS_EVENT.get(body.status)
    notif = make_notification(ev, n) if ev else None
    return await push_status(doc, body.status, notif)


# ---------------------------------------------------------------------------
# 80mm ticket
# ---------------------------------------------------------------------------
def build_ticket(o: dict, settings: Settings) -> str:
    W = 32  # 80mm at font A ~ 32 chars for large text
    lines: List[str] = []
    c = lambda s: s.center(W)  # noqa: E731
    lines += [c(settings.restaurant_name.upper()), "", c(f"COMMANDE #{o['order_number']}"), "=" * W]
    lines.append("RETRAIT" if o["type"] == "pickup" else "LIVRAISON")
    if o.get("source") == "telephone":
        lines.append(f"TELEPHONE - POSTE {o.get('station') or 1}")
    if o.get("requested_time") and o["requested_time"] != "asap":
        lines.append("SOUHAITE: " + o["requested_time"])
    if o.get("estimated_ready_at"):
        lines.append(("PRET VERS " if o["type"] == "pickup" else "LIVRAISON VERS ") + fmt_time(o["estimated_ready_at"]))
    lines.append("Recue: " + fmt_time(o["created_at"]))
    if o.get("age_required"):
        lines += ["", "!" * W, c(f"ALCOOL - CONTROLE AGE {o['age_required']}+"), c("VERIFIER LA PIECE D'IDENTITE"), "!" * W]
    lines += ["-" * W]
    for it in o["items"]:
        size = f" {it['size']['label'].upper()}" if it.get("size") else ""
        lines.append(f"{it['quantity']}x {it['name']['fr'].upper()}{size}")
        for op in it.get("options", []):
            lines.append(f"   * {op['name']['fr'].upper()}")
        for r in it.get("removed_ingredients", []):
            lines.append(f"   - SANS {r['fr'].upper()}")
        for e in it.get("extras", []):
            q = f"{e['quantity']}x " if e["quantity"] > 1 else ""
            lines.append(f"   + {q}{e['name']['fr'].upper()}")
        if it.get("note"):
            lines.append(f"   NOTE: {it['note'].upper()}")
        lines.append("")
    if o.get("general_note"):
        lines += ["NOTE COMMANDE:", o["general_note"].upper(), ""]
    lines += ["-" * W, "CLIENT:", f"{o['customer']['first_name']} {o['customer'].get('last_name', '')}".strip(), o["customer"]["phone"]]
    if o["type"] == "delivery" and o.get("address"):
        a = o["address"]
        lines += ["", "ADRESSE:", f"{a['street']} {a.get('number', '')}".strip(), f"{a['npa']} {a['city']}"]
        if a.get("instructions"):
            lines.append("INFO: " + a["instructions"])
    lines += ["-" * W]
    if o.get("delivery_fee"):
        lines.append(f"{'Livraison':<{W-10}}{('CHF %.2f' % o['delivery_fee']):>10}")
    lines.append(f"{'TOTAL:':<{W-12}}{('CHF %.2f' % o['total']):>12}")
    if o.get("driver"):
        lines.append(f"LIVREUR: {o['driver'].upper()}")
    lines += ["", c(payment_label(o, True)), "", c("Merci / Danke!"), ""]
    return "\n".join(lines)


@api.get("/orders/{order_id}/ticket")
async def get_ticket(order_id: str):
    doc = await load_order(order_id)
    settings = await get_settings()
    return {"order_id": order_id, "order_number": doc["order_number"], "text": build_ticket(doc, settings),
            "printed": doc.get("printed", False), "printed_at": doc.get("printed_at"), "print_attempts": doc.get("print_attempts", 0),
            "print_status": doc.get("print_status"), "printer_configured": bool(PRINTNODE_API_KEY and PRINTNODE_PRINTER_ID)}


class PrintIn(BaseModel):
    force: bool = False


@api.post("/orders/{order_id}/print")
async def print_ticket(order_id: str, body: PrintIn = PrintIn()):
    """Print (first time) or re-print (force=true) the 80mm kitchen ticket."""
    doc = await load_order(order_id)
    return await do_print(doc, body.force)


@api.get("/print-jobs")
async def list_print_jobs(limit: int = 50):
    docs = await db.print_jobs.find({}).sort("created_at", -1).to_list(limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


# ---------------------------------------------------------------------------
# Customer receipt (fiscal, VAT included) – separate from the kitchen ticket
# ---------------------------------------------------------------------------
def money(v: float) -> str:
    return f"CHF {v:.2f}"


def build_receipt(o: dict, s: Settings) -> str:
    W = 42  # 80mm, font B ~ 42 chars
    c = lambda t: t.center(W)  # noqa: E731
    row = lambda label, amount: f"{label[:W - 12]:<{W - 12}}{amount:>12}"  # noqa: E731
    created = o["created_at"] if o["created_at"].tzinfo else o["created_at"].replace(tzinfo=timezone.utc)
    local = created.astimezone(TZ)
    lines: List[str] = [
        c(s.business_name.upper()), c(s.street), c(f"{s.postal_code} {s.city}"), c(f"Tél. {s.phone}"), c(s.vat_number), "",
        c("REÇU / QUITTANCE"), "=" * W,
        f"Commande n° {o['order_number']}",
        f"Date: {local.strftime('%d.%m.%Y')}    Heure: {local.strftime('%H:%M')}",
        "RETRAIT" if o["type"] == "pickup" else "LIVRAISON",
    ]
    if o.get("estimated_ready_at"):
        lines.append(("Retrait confirmé: " if o["type"] == "pickup" else "Livraison confirmée: ") + fmt_time(o["estimated_ready_at"]))
    cust = o["customer"]
    lines += ["-" * W, f"Client: {cust['first_name']} {cust.get('last_name', '')}".strip(), f"Tél: {cust['phone']}"]
    if o["type"] == "delivery" and o.get("address"):
        a = o["address"]
        lines.append(f"Adresse: {a['street']} {a.get('number', '')}".strip() + f", {a['npa']} {a['city']}")
    lines += ["-" * W]
    for it in o["items"]:
        size = f" {it['size']['label']}" if it.get("size") else ""
        lines.append(row(f"{it['quantity']}x {it['name']['fr']}{size}", money(it["unit_price"] * it["quantity"])))
        if it["quantity"] > 1:
            lines.append(f"   ({money(it['unit_price'])} / pce)")
        for op in it.get("options", []):
            if op.get("price"):
                lines.append(f"   * {op['name']['fr']}")
        for e in it.get("extras", []):
            q = f"{e['quantity']}x " if e["quantity"] > 1 else ""
            lines.append(row(f"   + {q}{e['name']['fr']}", money(e["unit_price"] * e["quantity"] * it["quantity"])))
        for r in it.get("removed_ingredients", []):
            lines.append(row(f"   - sans {r['fr']}", money(0)))
        if it.get("extras") or it["quantity"] > 1:
            lines.append(row("   Total ligne", money(it["line_total"])))
    lines += ["-" * W, row("Sous-total", money(o.get("subtotal_gross", o["total"] - o.get("delivery_fee", 0))))]
    if o.get("delivery_fee"):
        lines.append(row("Frais de livraison", money(o["delivery_fee"])))
    if o.get("discount_gross"):
        lines.append(row("Remise", f"-{money(o['discount_gross'])}"))
    lines += ["=" * W, row("TOTAL", money(o["total"])), "=" * W,
              payment_label(o, False),
              "Statut: " + ("PAYÉ" if o.get("paid") else "à payer"), "", "TVA INCLUSE"]
    for g in o.get("vat_breakdown", []):
        lines += [f"TVA {g['rate']:.1f}%", row("  Base HT", money(g["net"])), row("  TVA", money(g["vat"]))]
    if o.get("vat_breakdown"):
        lines += [row("Total HT", money(o["total_net"])), row("Total TVA", money(o["total_vat"]))]
    lines += ["", c(s.vat_number), c("Merci de votre visite / Danke!"), ""]
    return "\n".join(lines)


@api.get("/orders/{order_id}/receipt")
async def get_receipt(order_id: str):
    doc = await load_order(order_id)
    s = await get_settings()
    return {"order_id": order_id, "order_number": doc["order_number"], "text": build_receipt(doc, s),
            "printed": doc.get("receipt_printed", False), "printed_at": doc.get("receipt_printed_at"),
            "print_attempts": doc.get("receipt_print_attempts", 0), "vat_breakdown": doc.get("vat_breakdown", []),
            "total_net": doc.get("total_net"), "total_vat": doc.get("total_vat"), "total": doc["total"]}


@api.post("/orders/{order_id}/receipt/print")
async def print_receipt(order_id: str, body: PrintIn = PrintIn()):
    """Print / re-print the customer receipt (same simulated PrintNode pipeline as the kitchen ticket)."""
    doc = await load_order(order_id)
    if doc.get("receipt_printed") and not body.force:
        raise HTTPException(409, "Receipt already printed")
    s = await get_settings()
    text = build_receipt(doc, s)
    status = await send_to_printer(doc, text, kind="receipt")
    new = await db.orders.find_one_and_update(
        {"_id": doc["_id"]},
        {"$set": {"receipt_printed": True, "receipt_printed_at": now_utc()}, "$inc": {"receipt_print_attempts": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return {"ok": True, "printed": True, "printed_at": new["receipt_printed_at"], "print_attempts": new["receipt_print_attempts"],
            "print_status": status, "text": text}


api.include_router(auth_mod.router)
api.include_router(auth_mod.customers_router)
api.include_router(photos_mod.router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

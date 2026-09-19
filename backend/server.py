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
import asyncio
import re
import logging
from pathlib import Path

from seed_data import CATEGORIES, EXTRAS, PRODUCTS, DEFAULT_SETTINGS
from database import client, db
import auth as auth_mod
import photos as photos_mod
import staff_auth as staff_mod
import review_email as review_mod
from fastapi.responses import RedirectResponse
import hours as hours_mod
from fastapi.security import HTTPAuthorizationCredentials

# Role guards (server-side JWT). Customer-facing endpoints (menu, settings, POST /orders, GET /orders/{id}, GET /orders?ids=) stay public.
MANAGER = staff_mod.require_roles("manager")
STAFF = staff_mod.require_roles("manager", "kitchen")
PHONE = staff_mod.require_roles("manager", "phone")
TICKET = staff_mod.require_roles("manager", "kitchen", "phone")

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
    price: float                          # default / fallback price
    price_by_size: Dict[str, float] = {}  # per pizza size key ("32" / "40" / "50") – empty = use `price`
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
    origin: I18n = I18n()   # meat / fish origin for this product (admin-maintained, empty = not configured)
    available: bool = True
    is_alcohol: bool = False
    alcohol_type: Optional[str] = None  # "fermented" (beer, wine, prosecco -> 16+) | "spirits" (distilled -> 18+)
    images: List[str] = []  # additional photos (API urls); image_url is the main photo
    wine: Optional[WineInfo] = None
    sort: int = 0
    vat_rate: Optional[float] = None  # % – None -> derived from settings (alcohol vs standard)
    highlight: Optional[str] = None   # "moment" (Pizza du mois – listed first) | "custom" (Créez votre pizza – second) | None
    available_from: Optional[str] = None   # "YYYY-MM-DD" – optional window (e.g. Pizza du moment); empty = no limit
    available_until: Optional[str] = None
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
    origin: I18n = I18n()
    available: bool = True
    is_alcohol: bool = False
    alcohol_type: Optional[str] = None
    images: List[str] = []
    wine: Optional[WineInfo] = None
    sort: int = 0
    vat_rate: Optional[float] = None
    highlight: Optional[str] = None
    available_from: Optional[str] = None
    available_until: Optional[str] = None


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
    origin: Optional[I18n] = None
    available: Optional[bool] = None
    is_alcohol: Optional[bool] = None
    alcohol_type: Optional[str] = None
    images: Optional[List[str]] = None
    wine: Optional[WineInfo] = None
    sort: Optional[int] = None
    highlight: Optional[str] = None
    available_from: Optional[str] = None
    available_until: Optional[str] = None


class ExtraIn(BaseModel):
    key: str
    name: I18n
    price: float
    price_by_size: Dict[str, float] = {}
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
    delivery_cutoff_minutes: int = 15          # last delivery order before window end (13:45 / 21:45)
    first_delivery: Dict[str, str] = {}        # {"lunch": "11:30", "evening": "17:00" | "closed"} – manager quick control
    meat_fish_origin: I18n = I18n()            # "Origine des viandes et poissons" – free text maintained by admin
    printing_enabled_at: Optional[datetime] = None
    hero_images: List[str] = []              # homepage carousel (admin-managed, API urls)
    public_url: str = ""                     # public site url (https://…) used in customer e-mails
    review_enabled: bool = False             # Google review request e-mail after a completed order
    google_review_url: str = ""              # entered by the restaurant in Administration
    # Public legal pages (Confidentialité / CGV / Mentions légales) – text entered by the restaurant, empty = placeholder
    legal_privacy: I18n = I18n(fr="", de="")
    legal_terms: I18n = I18n(fr="", de="")
    legal_imprint: I18n = I18n(fr="", de="")
    review_delay_minutes: int = 90           # sent this long after completion  # orders created before this moment can never auto-print
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
                   "body_fr": "Votre commande est en livraison.", "body_de": "Ihre Bestellung ist unterwegs."},
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
    # MOITIÉ / MOITIÉ (staff phone orders only): second pizza for the other half
    half_product_id: Optional[str] = None
    half_removed_ingredient_ids: List[str] = []
    half_note: Optional[str] = None


class HalfInfo(BaseModel):
    product_id: str
    name: I18n
    removed_ingredients: List[Ingredient] = []
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
    requested_date: Optional[str] = None  # "YYYY-MM-DD" (Europe/Zurich) – omitted/today = same-day order; future = scheduled order
    general_note: Optional[str] = None
    age_confirmed: bool = False
    save_address: bool = False  # logged-in customers: store the delivery address in the profile
    language: str = "fr"
    payment_method: str = "cash"  # how the customer will pay at handover: "cash" (ESPÈCES) | "terminal" (CARTE) – no online payment


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
    client_request_id: Optional[str] = None  # generated by the iPad per order attempt -> duplicate taps return the same order


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
    half: Optional[HalfInfo] = None  # second half (price = the more expensive pizza of the two)
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
    requested_date: Optional[str] = None   # "YYYY-MM-DD" local; set only for orders placed for a future day
    scheduled_for: Optional[datetime] = None  # requested date + time (UTC) – sorting / "Programmées" section
    general_note: Optional[str] = None
    payment_method: str
    language: str = "fr"
    age_confirmed: bool = False
    age_required: Optional[int] = None  # 16 (beer/wine) or 18 (spirits) – staff/driver must check ID at handover
    user_id: Optional[str] = None       # customer account (None = guest)
    station: Optional[int] = None       # phone orders: iPad "Poste 1" / "Poste 2"
    driver: Optional[str] = None        # delivery: "Livreur 1" / "Livreur 2" / "Livreur 3"
    driver_name: Optional[str] = None   # person who did the delivery (snapshot; updated to the performer on "livrée") – kept in history
    shift_id: Optional[str] = None      # driver_shifts id of that person's service (stable identity for reports)
    legacy: bool = False                # computed: created before the printer went live (development/test data) – never prints
    reprint_count: int = 0
    assigned_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    out_for_delivery_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    collection_method: Optional[str] = None  # cash | terminal | none (already paid / nothing to collect)
    amount_due: float = 0.0
    payment_collected: bool = False
    collected_at: Optional[datetime] = None
    printnode_job_id: Optional[str] = None
    last_print_error: Optional[str] = None
    client_request_id: Optional[str] = None  # idempotency key (phone orders double-tap)
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
    # Final menu structure: "Entrées" is a normal category; the virtual "Pizza sans gluten" tab is gone
    # (gluten-free stays available as the gluten_free dough option on each pizza).
    await db.categories.delete_many({"filter": "gluten_free"})
    if not await db.categories.find_one({"slug": "entrees"}):
        await db.categories.update_many({}, {"$inc": {"sort": 1}})
        await db.categories.insert_one(Category(slug="entrees", name=I18n(fr="Entrées", de="Vorspeisen"), sort=1).to_mongo())
    if not await db.categories.find_one({"slug": "salades"}):
        await db.categories.update_many({"sort": {"$gte": 2}}, {"$inc": {"sort": 1}})
        await db.categories.insert_one(Category(slug="salades", name=I18n(fr="Salades", de="Salate"), sort=2).to_mongo())
    # Final public labels (only if still the seed defaults – restaurant edits win)
    await db.categories.update_one({"slug": "pizza", "name.fr": "Pizza"}, {"$set": {"name": {"fr": "Pizzas", "de": "Pizzas"}}})
    await db.categories.update_one({"slug": "dessert", "name.fr": "Dessert"}, {"$set": {"name": {"fr": "Desserts", "de": "Desserts"}}})
    await auth_mod.ensure_indexes()
    await staff_mod.seed_staff_pins()
    cur = await db.settings.find_one({"_id": "main"})
    if cur is not None and cur.get("opening_hours"):
        # Backward-compatible migration: canonicalise hours typed by hand (e.g. 'tue': '17.00-22' was unparseable -> Tuesday closed)
        fixed = {}
        for d, v in cur["opening_hours"].items():
            try:
                fixed[d] = normalize_hours(v or "")
            except HTTPException:
                fixed[d] = DEFAULT_SETTINGS["opening_hours"].get(d, "")
                logger.warning("opening_hours[%s]=%r invalid – reset to default %r", d, v, fixed[d])
        if fixed != cur["opening_hours"]:
            await db.settings.update_one({"_id": "main"}, {"$set": {"opening_hours": fixed}})
            logger.info("opening_hours normalised: %s", fixed)
    if PRINTNODE_API_KEY and PRINTNODE_PRINTER_ID:
        cur = await db.settings.find_one({})
        if cur is not None and not cur.get("printing_enabled_at"):
            # Real printer just configured: everything created before now is historical and can never auto-print
            await db.settings.update_one({"_id": cur["_id"]}, {"$set": {"printing_enabled_at": now_utc()}})
            logger.info("PrintNode enabled – auto-print only for orders created from now on")
    # Idempotency key for phone orders: unique only when present (documents without a key never collide)
    try:
        await db.orders.drop_index("client_request_id_1")
    except Exception:
        pass
    await db.orders.create_index("client_request_id", unique=True, partialFilterExpression={"client_request_id": {"$type": "string"}})
    try:
        photos_mod.init_storage()
    except Exception as e:  # storage unavailable -> uploads will retry lazily
        logger.warning("Object storage init failed: %s", e)
    # Google review e-mails: isolated background loop (never in the order/print request path)
    asyncio.create_task(review_mod.review_loop(db, get_settings, now_utc))
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
    today = datetime.now(TZ).date().isoformat()
    if not include_unavailable:
        # Sold-out items are still returned but flagged; products outside their date window are hidden
        products = [p for p in products if (not p.available_from or p.available_from <= today) and (not p.available_until or p.available_until >= today)]
    rank = {"moment": 0, "custom": 1}
    products.sort(key=lambda p: (rank.get(p.highlight or "", 2), p.sort))
    extras = [Extra.from_mongo(e) async for e in db.extras.find({}).sort("price", 1)]
    settings = await get_settings()
    return {"categories": cats, "products": products, "extras": extras, "settings": settings}


@api.get("/categories", response_model=List[Category])
async def list_categories():
    return [Category.from_mongo(c) async for c in db.categories.find({}).sort("sort", 1)]


@api.post("/categories", response_model=Category)
async def create_category(body: CategoryIn, _: dict = Depends(MANAGER)):
    res = await db.categories.insert_one(Category(**body.model_dump()).to_mongo())
    return Category.from_mongo(await db.categories.find_one({"_id": res.inserted_id}))


@api.put("/categories/{cat_id}", response_model=Category)
async def update_category(cat_id: str, body: CategoryIn, _: dict = Depends(MANAGER)):
    doc = await db.categories.find_one_and_update({"_id": oid(cat_id)}, {"$set": body.model_dump()}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(404, "Category not found")
    return Category.from_mongo(doc)


@api.delete("/categories/{cat_id}")
async def delete_category(cat_id: str, _: dict = Depends(MANAGER)):
    """Only empty categories can be deleted – move or delete its products first."""
    if await db.products.count_documents({"category_id": cat_id, "deleted_at": None}) > 0:
        raise HTTPException(400, "La catégorie contient encore des produits")
    res = await db.categories.delete_one({"_id": oid(cat_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Category not found")
    return {"ok": True}


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
async def create_product(body: ProductIn, _: dict = Depends(MANAGER)):
    if body.highlight == "moment":  # only ONE Pizza du mois at a time
        await db.products.update_many({"highlight": "moment"}, {"$set": {"highlight": None}})
    res = await db.products.insert_one(Product(**body.model_dump()).to_mongo())
    return Product.from_mongo(await db.products.find_one({"_id": res.inserted_id}))


@api.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, body: ProductIn, _: dict = Depends(MANAGER)):
    if body.highlight == "moment":  # only ONE Pizza du mois at a time
        await db.products.update_many({"highlight": "moment", "_id": {"$ne": oid(product_id)}}, {"$set": {"highlight": None}})
    doc = await db.products.find_one_and_update({"_id": oid(product_id)}, {"$set": body.model_dump()}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(404, "Product not found")
    return Product.from_mongo(doc)


@api.patch("/products/{product_id}", response_model=Product)
async def patch_product(product_id: str, body: ProductPatch, _: dict = Depends(MANAGER)):
    update = body.model_dump(exclude_unset=True)
    if not update:
        raise HTTPException(400, "Nothing to update")
    doc = await db.products.find_one_and_update({"_id": oid(product_id)}, {"$set": update}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(404, "Product not found")
    return Product.from_mongo(doc)


@api.delete("/products/{product_id}")
async def delete_product(product_id: str, _: dict = Depends(MANAGER)):
    res = await db.products.update_one({"_id": oid(product_id)}, {"$set": {"deleted_at": now_utc(), "available": False}})
    if res.matched_count == 0:
        raise HTTPException(404, "Product not found")
    return {"ok": True}


@api.get("/extras", response_model=List[Extra])
async def list_extras():
    return [Extra.from_mongo(e) async for e in db.extras.find({}).sort("price", 1)]


@api.post("/extras", response_model=Extra)
async def create_extra(body: ExtraIn, _: dict = Depends(MANAGER)):
    if await db.extras.find_one({"key": body.key}):
        raise HTTPException(400, "Extra key already exists")
    res = await db.extras.insert_one(Extra(**body.model_dump()).to_mongo())
    return Extra.from_mongo(await db.extras.find_one({"_id": res.inserted_id}))


@api.put("/extras/{extra_id}", response_model=Extra)
async def update_extra(extra_id: str, body: ExtraIn, _: dict = Depends(MANAGER)):
    doc = await db.extras.find_one_and_update({"_id": oid(extra_id)}, {"$set": body.model_dump()}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(404, "Extra not found")
    return Extra.from_mongo(doc)


@api.delete("/extras/{extra_id}")
async def delete_extra(extra_id: str, _: dict = Depends(MANAGER)):
    res = await db.extras.delete_one({"_id": oid(extra_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Extra not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@api.get("/settings/ordering")
async def get_ordering_status():
    """Customer ordering status for now (Europe/Zurich): open flags, next opening, valid pickup/delivery slots."""
    return hours_mod.ordering_status(await get_settings(), datetime.now(TZ))


class FirstDeliveryIn(BaseModel):
    lunch: Optional[str] = None    # "11:30" | "closed" | "" (= opening time)
    evening: Optional[str] = None


@api.put("/settings/first-delivery")
async def set_first_delivery(body: FirstDeliveryIn, _: dict = Depends(staff_mod.require_roles("manager"))):
    """Manager quick control: 'Première livraison disponible' per service, without touching other settings."""
    cur = await get_settings()
    fd = dict(cur.first_delivery or {})
    for k in ("lunch", "evening"):
        v = getattr(body, k)
        if v is not None:
            fd[k] = v.strip()
    await db.settings.update_one({}, {"$set": {"first_delivery": fd}}, upsert=True)
    return {"first_delivery": fd, "ordering": hours_mod.ordering_status(await get_settings(), datetime.now(TZ))}


@api.get("/settings", response_model=Settings)
async def get_settings():
    doc = await db.settings.find_one({"_id": "main"})
    if not doc:
        return Settings(**DEFAULT_SETTINGS)
    doc.pop("_id", None)
    return Settings(**doc)


def normalize_hours(value: str) -> str:
    """Accept sloppy admin input ("17.00-22", "11h-14h, 17:00 - 22:00") -> canonical "HH:MM-HH:MM, HH:MM-HH:MM"; "" = closed."""
    out = []
    for part in [p for p in value.replace(";", ",").split(",") if p.strip()]:
        m = re.match(r"^\s*(\d{1,2})(?:[:.hH](\d{0,2}))?\s*-\s*(\d{1,2})(?:[:.hH](\d{0,2}))?\s*$", part)
        if not m:
            raise HTTPException(400, f"Horaire invalide: '{part.strip()}' (format 11:00-14:00)")
        h1, m1, h2, m2 = int(m.group(1)), int(m.group(2) or 0), int(m.group(3)), int(m.group(4) or 0)
        if not (0 <= h1 <= 23 and 0 <= h2 <= 24 and 0 <= m1 < 60 and 0 <= m2 < 60) or (h1 * 60 + m1) >= (h2 * 60 + m2):
            raise HTTPException(400, f"Horaire invalide: '{part.strip()}'")
        out.append(f"{h1:02d}:{m1:02d}-{h2:02d}:{m2:02d}")
    return ", ".join(out)


@api.put("/settings", response_model=Settings)
async def update_settings(body: Settings, _: dict = Depends(MANAGER)):
    body.opening_hours = {d: normalize_hours(v or "") for d, v in body.opening_hours.items()}
    if body.google_review_url and not body.google_review_url.startswith("https://"):
        raise HTTPException(400, "Le lien Google doit commencer par https://")
    await db.settings.update_one({"_id": "main"}, {"$set": body.model_dump()}, upsert=True)
    return body


@api.get("/review/{order_id}/go")
async def review_redirect(order_id: str):
    """Link used in the review e-mail: our own domain -> the Google review URL configured in Administration."""
    s = await get_settings()
    if not s.google_review_url.startswith("https://"):
        raise HTTPException(404, "Lien d'avis non configuré")
    try:
        await db.orders.update_one({"_id": oid(order_id)}, {"$set": {"review_clicked_at": now_utc()}})
    except Exception:
        pass
    return RedirectResponse(s.google_review_url, status_code=302)


@api.get("/admin/export")
async def export_menu(_: dict = Depends(MANAGER)):
    """Backup of the whole restaurant configuration (categories, products, extras, settings) as JSON."""
    def clean(d):
        d = dict(d); d["id"] = str(d.pop("_id")); return d
    return {
        "exported_at": now_utc().isoformat(), "app": "hallo-magic-pizza",
        "categories": [clean(c) async for c in db.categories.find({})],
        "products": [clean(p) async for p in db.products.find({})],
        "extras": [clean(e) async for e in db.extras.find({})],
        "settings": (await get_settings()).model_dump(),
    }


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


def extra_price(edoc: dict, size_key: Optional[str]) -> float:
    """Supplement price for a pizza size (32/40/50) – falls back to the flat price."""
    pbs = edoc.get("price_by_size") or {}
    if size_key and size_key in pbs and pbs[size_key] is not None:
        return float(pbs[size_key])
    return float(edoc["price"])


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


def collection_fields(payment_method: str, total: float) -> dict:
    """What the driver / counter must collect at handover. Online payment does not exist -> everything is collected
    unless explicitly marked paid."""
    method = "terminal" if payment_method == "terminal" else "cash"
    return {"collection_method": method, "amount_due": round(total, 2), "payment_collected": False}


async def compute_order(body: OrderIn, user: Optional[dict], enforce_minimum: bool = True, allow_half: bool = False, enforce_hours: bool = True) -> Order:
    """Validates the cart against the live catalog and builds the full Order (prices + frozen VAT snapshot).
    Shared by customer checkout (/orders) and staff phone orders (/phone-orders)."""
    settings = await get_settings()
    local_now = datetime.now(TZ)
    # Scheduled (future-day) order? Validate the date/time against the opening hours of THAT day.
    sched_date = None
    if body.requested_date:
        try:
            sched_date = datetime.strptime(body.requested_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Date invalide")
        if sched_date < local_now.date():
            raise HTTPException(400, "Date passée")
        if sched_date == local_now.date():
            sched_date = None  # same-day order: normal rules below
    if sched_date:
        if (sched_date - local_now.date()).days > 7:
            raise HTTPException(400, "Commande possible au maximum 7 jours à l'avance")
        if not body.requested_time or body.requested_time == "asap":
            raise HTTPException(400, "Choisissez une heure pour une commande programmée")
        p_slots, d_slots = hours_mod.slots_for_day(settings, sched_date, local_now)
        if body.requested_time.strip() not in (p_slots if body.type == "pickup" else d_slots):
            raise HTTPException(400, "Créneau non disponible ce jour-là – choisissez un créneau proposé")
    elif enforce_hours:
        st = hours_mod.ordering_status(settings, local_now)
        if not body.requested_time or body.requested_time == "asap":
            # ASAP is allowed while open AND before an opening later today (= first available time after opening)
            if body.type == "pickup" and not st["asap_pickup"]:
                raise HTTPException(400, f"Restaurant fermé – prochaine ouverture {st['next_open'] or '–'}")
            if body.type == "delivery" and not st["asap_delivery"]:
                raise HTTPException(400, "Livraison indisponible pour le moment – le retrait reste possible jusqu'à la fermeture" if st["asap_pickup"] else f"Restaurant fermé – prochaine ouverture {st['next_open'] or '–'}")
        else:
            slots = st["pickup_slots"] if body.type == "pickup" else st["delivery_slots"]
            if body.requested_time.strip() not in slots:
                raise HTTPException(400, "Heure non disponible – choisissez un créneau proposé")
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
        # Size chosen for this line (same rule as below: unknown/missing key -> first size); drives per-size supplement prices
        _sizes = pdoc.get("sizes") or []
        size_key = (next((sd for sd in _sizes if sd["key"] == it.size_key), None) or _sizes[0])["key"] if _sizes else None
        for ex in it.extras:
            edoc = extras_by_id.get(ex.extra_id)
            if not edoc or (edoc["key"] not in allowed and ex.extra_id not in allowed):
                raise HTTPException(400, "Extra not allowed for this product")
            eqty = max(1, min(ex.quantity, edoc.get("max_quantity", 1)))
            ex_rate = edoc.get("vat_rate")
            if ex_rate is None:
                ex_rate = settings.vat_rate_standard
            ex_price = extra_price(edoc, size_key)
            eg, en, ev = split_vat(ex_price * eqty * qty, ex_rate)
            vat_groups[ex_rate] = vat_groups.get(ex_rate, 0.0) + eg
            ex_list.append(OrderExtra(extra_id=ex.extra_id, name=I18n(**edoc["name"]), unit_price=ex_price, quantity=eqty,
                                      vat_rate=ex_rate, gross_amount=eg, net_amount=en, vat_amount=ev))
            ex_sum += ex_price * eqty
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
        half: Optional[HalfInfo] = None
        if it.half_product_id:
            if not allow_half:
                raise HTTPException(400, "Pizza moitié/moitié disponible uniquement par téléphone")
            hdoc = await db.products.find_one({"_id": oid(it.half_product_id), "deleted_at": None})
            if not hdoc:
                raise HTTPException(400, "Second half not found")
            hsizes = hdoc.get("sizes") or []
            hs = next((x for x in hsizes if size and x["key"] == size.key), None)
            h_price = hs["price"] if hs else hdoc["price"]
            base_price = max(base_price, h_price)  # business rule: price of the more expensive pizza
            h_removed = [Ingredient(**ing) for ing in (hdoc.get("ingredients") or []) if ing["id"] in set(it.half_removed_ingredient_ids)]
            half = HalfInfo(product_id=it.half_product_id, name=I18n(**hdoc["name"]), removed_ingredients=h_removed, note=it.half_note or None)
        qty = max(1, it.quantity)
        unit = base_price + opt_sum
        line_total = round((unit + ex_sum) * qty, 2)
        subtotal += unit * qty
        extras_total += ex_sum * qty
        pg, pn, pv = split_vat(unit * qty, prod_rate)
        vat_groups[prod_rate] = vat_groups.get(prod_rate, 0.0) + pg
        items.append(OrderItem(
            product_id=it.product_id, name=I18n(**pdoc["name"]), unit_price=unit, quantity=qty, size=size, options=opts,
            removed_ingredients=removed, extras=ex_list, note=(it.note or None), half=half, line_total=line_total,
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
        if enforce_minimum and goods < minimum:
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
    scheduled_for = None
    if sched_date:
        h, m = [int(x) for x in body.requested_time.strip().split(":")]
        scheduled_for = datetime(sched_date.year, sched_date.month, sched_date.day, h, m, tzinfo=TZ).astimezone(timezone.utc)
    return Order(
        order_number=number, type=body.type, source=body.source, status="pending", items=items,
        customer=body.customer, address=body.address if body.type == "delivery" else None,
        requested_time=body.requested_time, requested_date=sched_date.isoformat() if sched_date else None, scheduled_for=scheduled_for,
        general_note=body.general_note or None,
        payment_method="pay_at_delivery" if body.type == "delivery" else "pay_at_pickup",
        language=body.language, age_confirmed=bool(age_req) and body.age_confirmed, age_required=age_req,
        user_id=str(user["_id"]) if user else None,
        subtotal=round(subtotal, 2), extras_total=round(extras_total, 2), delivery_fee=delivery_fee, total=total,
        subtotal_gross=goods, delivery_fee_gross=round(delivery_fee, 2), delivery_fee_vat_rate=settings.delivery_fee_vat_rate if delivery_fee > 0 else 0.0,
        discount_gross=discount, total_gross=total, vat_breakdown=breakdown, total_vat=total_vat, total_net=total_net,
        created_at=ts, status_history=[StatusEvent(status="pending", at=ts)],
        notifications=[Notification(**make_notification("order_received", number))],
    )


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


@api.post("/orders", response_model=Order)
async def create_order(body: OrderIn, user: Optional[dict] = Depends(auth_mod.optional_user)):
    # Customer Web/App checkout: e-mail is mandatory (order follow-up + review request); phone orders (staff) are not affected
    email = (body.customer.email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Adresse e-mail invalide / Ungültige E-Mail-Adresse")
    body.customer.email = email
    if body.payment_method not in ("cash", "terminal", "pay_at_pickup", "pay_at_delivery"):
        raise HTTPException(400, "Invalid payment method")
    order = await compute_order(body, user)
    if body.payment_method in ("cash", "terminal"):
        order.payment_method = body.payment_method  # drives ticket "A ENCAISSER · ESPECES/TERMINAL", driver screen and Clôture buckets
    doc = order.to_mongo()
    doc.update(collection_fields(order.payment_method, order.total))
    res = await db.orders.insert_one(doc)
    if user and body.save_address and body.type == "delivery" and body.address:
        await auth_mod.save_address_for_user(user, body.address.model_dump())
    return Order.from_mongo(await db.orders.find_one({"_id": res.inserted_id}))


@api.post("/phone-orders", response_model=Order)
async def create_phone_order(body: PhoneOrderIn, staff: dict = Depends(PHONE)):
    """Staff-entered phone order: same catalog, prices, VAT snapshot, ticket and receipt as any other order.
    The time was agreed with the caller on the phone, so the order is ACCEPTED immediately with that time
    (ASAP -> now + N min, default 30; "in N min" -> that time; exact HH:MM -> confirmed as is) and goes straight
    to EN COURS. Acceptance goes through the SAME accept_order path as every other order -> exactly ONE kitchen
    ticket, same duplicate-print protection. The Manager can still refuse/cancel it afterwards from the card."""
    if body.station not in (1, 2):
        raise HTTPException(400, "station must be 1 or 2")
    if body.client_request_id:
        dup = await db.orders.find_one({"client_request_id": body.client_request_id})
        if dup:
            return Order.from_mongo(dup)  # idempotent: double tap returns the existing order
    if body.payment_method not in PAYMENT_METHODS:
        raise HTTPException(400, "Invalid payment method")
    customer = await db.users.find_one({"_id": oid(body.customer_id)}) if body.customer_id else None
    body.source = "telephone"
    body.age_confirmed = True  # staff informs the caller; the 16+/18+ ID check happens at handover (ticket + dashboard warning)
    if (not body.requested_time or body.requested_time == "asap") and body.minutes is not None and not body.requested_date:
        # "in N minutes" agreed on the phone -> stored as the requested time (printed as LIVRAISON DEMANDÉE / RETRAIT À)
        body.requested_time = fmt_time(now_utc() + timedelta(minutes=body.minutes))
    order = await compute_order(body, customer, enforce_minimum=False, allow_half=True, enforce_hours=False)  # staff overrides: minimum, hours, half/half
    doc = order.to_mongo()
    doc.update({"station": body.station, "payment_method": body.payment_method, "client_request_id": body.client_request_id,
                **collection_fields(body.payment_method, order.total)})
    res = await db.orders.insert_one(doc)
    if customer and body.save_address and body.type == "delivery" and body.address:
        await auth_mod.save_address_for_user(customer, body.address.model_dump())
    # Immediate acceptance = the agreed time becomes the confirmed time and the ticket is printed (once) right now
    agreed = AcceptIn(time=body.requested_time) if body.requested_time not in (None, "", "asap") else AcceptIn(minutes=30)
    return await accept_order(str(res.inserted_id), agreed, staff)


class AssignIn(BaseModel):
    driver: str  # "Livreur 1" | "Livreur 2" | "Livreur 3"


@api.post("/orders/{order_id}/assign", response_model=Order)
async def assign_driver(order_id: str, body: AssignIn, _: dict = Depends(STAFF)):
    doc = await load_order(order_id)
    if doc["type"] != "delivery":
        raise HTTPException(400, "Only delivery orders can be assigned")
    if doc["status"] not in ("accepted", "preparing", "ready", "assigned"):
        raise HTTPException(400, "Order cannot be assigned in its current status")
    if body.driver not in staff_mod.DRIVER_NAME.values():
        raise HTTPException(400, "Unknown driver")
    if doc.get("driver") and doc["driver"] != body.driver and doc.get("picked_up_at"):
        raise HTTPException(409, f"Commande déjà prise en charge par {doc['driver']}")
    shift = await staff_mod.open_shift_for_name(body.driver)
    if not shift:
        raise HTTPException(409, f"Aucun service ouvert pour {body.driver} – ouvrez le service (Admin → Sécurité)")
    # Identity snapshot: the PERSON currently on this slot (name + shift id). Re-opening the slot with another
    # person later never renames this order – historical deliveries keep the driver who did them.
    fields = {"driver": body.driver, "driver_name": shift["name"], "shift_id": str(shift["_id"]), "assigned_at": now_utc()}
    if doc["status"] in ("ready", "assigned"):
        notif = make_notification("assigned", doc["order_number"]) if doc["status"] == "ready" else None
        return await push_status(doc, "assigned", notif, fields)
    new = await db.orders.find_one_and_update({"_id": doc["_id"]}, {"$set": fields}, return_document=ReturnDocument.AFTER)
    return Order.from_mongo(new)


# ---------------------------------------------------------------------------
# Driver screen (role driverN sees only "Livreur N" orders)
# ---------------------------------------------------------------------------
def driver_of(user: dict) -> str:
    name = staff_mod.DRIVER_NAME.get(user["role"])
    if not name:
        raise HTTPException(403, "Compte livreur requis")
    return name


async def driver_order(order_id: str, user: dict) -> dict:
    doc = await load_order(order_id)
    if doc.get("driver") != driver_of(user):
        raise HTTPException(403, "Cette livraison n'est pas attribuée à votre poste")
    return doc


@api.get("/driver/orders", response_model=List[Order])
async def driver_orders(user: dict = Depends(staff_mod.staff_user)):
    """Operational list for the person on shift: ONLY deliveries assigned to this identity (slot + name / shift),
    active first (sorted by promised time), plus today's own delivered ones for the collapsed history.
    Deliveries made by another person on the same slot and pre-go-live test data never appear."""
    name = driver_of(user)
    _, start, end = day_range(None)
    settings = await get_settings()
    active = {"$in": ["accepted", "preparing", "ready", "assigned", "delivering"]}
    mine = {"driver": name, "type": "delivery", "status": {"$nin": ["cancelled"]},
            "$or": [{"driver_name": user.get("name")}, {"shift_id": user.get("shift_id")}]}
    if settings.printing_enabled_at:
        mine["created_at"] = {"$gte": settings.printing_enabled_at}
    docs = await db.orders.find({**mine, "$and": [{"$or": [{"status": active},
                                                           {"status": {"$in": ["delivered", "completed"]}, "delivered_at": {"$gte": start}}]}]}).to_list(200)
    def key(d):
        when = d.get("estimated_ready_at") or d.get("scheduled_for") or d.get("created_at")
        return (0 if d["status"] in active["$in"] else 1, when.replace(tzinfo=None) if when else datetime.max)
    return [Order.from_mongo(d) for d in sorted(docs, key=key)]


@api.post("/driver/orders/{order_id}/pickup", response_model=Order)
async def driver_pickup(order_id: str, user: dict = Depends(staff_mod.staff_user)):
    doc = await driver_order(order_id, user)
    if doc.get("picked_up_at"):
        return Order.from_mongo(doc)
    if doc["status"] in ("accepted", "preparing", "ready", "assigned"):
        extra = {"picked_up_at": now_utc(), **({"ready_at": now_utc()} if not doc.get("ready_at") else {})}
        if doc["status"] == "assigned":
            return Order.from_mongo(await db.orders.find_one_and_update({"_id": doc["_id"]}, {"$set": extra}, return_document=ReturnDocument.AFTER))
        return await push_status(doc, "assigned", None, extra)
    raise HTTPException(409, f"Statut actuel: {doc['status']}")


@api.post("/driver/orders/{order_id}/depart", response_model=Order)
async def driver_depart(order_id: str, user: dict = Depends(staff_mod.staff_user)):
    doc = await driver_order(order_id, user)
    if doc["status"] == "delivering":
        return Order.from_mongo(doc)
    if doc["status"] not in ("accepted", "preparing", "ready", "assigned"):
        raise HTTPException(409, f"Statut actuel: {doc['status']}")
    extra = {"out_for_delivery_at": now_utc()}
    if not doc.get("picked_up_at"):
        extra["picked_up_at"] = now_utc()
    if not doc.get("ready_at"):
        extra["ready_at"] = now_utc()
    return await push_status(doc, "delivering", make_notification("delivering", doc["order_number"]), extra)


@api.post("/driver/orders/{order_id}/delivered", response_model=Order)
async def driver_delivered(order_id: str, user: dict = Depends(staff_mod.staff_user)):
    doc = await driver_order(order_id, user)
    if doc["status"] in ("delivered", "completed"):
        return Order.from_mongo(doc)
    if doc["status"] != "delivering":
        raise HTTPException(409, "Appuyez d'abord sur PARTI / EN LIVRAISON")
    # The delivery is attributed to the person who actually performed it (current shift on this slot),
    # e.g. slot re-opened for Aliou after Marco was assigned -> the delivery is Aliou's.
    extra = {"delivered_at": now_utc()}
    if user.get("name"):
        extra.update({"driver_name": user["name"], "shift_id": user.get("shift_id")})
    return await finish_order(doc, "delivered", make_notification("delivered", doc["order_number"]), extra)


class CollectIn(BaseModel):
    method: Optional[str] = None  # cash | terminal | none


@api.post("/driver/orders/{order_id}/collect", response_model=Order)
async def driver_collect(order_id: str, body: CollectIn = CollectIn(), user: dict = Depends(staff_mod.staff_user)):
    """Explicit confirmation that the amount was collected (never automatic on delivery)."""
    doc = await driver_order(order_id, user)
    upd = {"payment_collected": True, "collected_at": now_utc(), "paid": True}
    if body.method in ("cash", "terminal", "none"):
        upd["collection_method"] = body.method
    new = await db.orders.find_one_and_update({"_id": doc["_id"]}, {"$set": upd}, return_document=ReturnDocument.AFTER)
    return Order.from_mongo(new)


# ---------------------------------------------------------------------------
# Manager reports: end-of-day driver closing + totals by source
# ---------------------------------------------------------------------------
def day_range(date: Optional[str]):
    d = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now(TZ).date()
    start = datetime(d.year, d.month, d.day, tzinfo=TZ)
    return d.isoformat(), start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


LEGACY_DRIVER_LABEL = "Non identifié"  # deliveries recorded before named shifts existed (no person attached)


def slug(text: str) -> str:
    import unicodedata
    base = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return "-".join(part for part in "".join(ch if ch.isalnum() else " " for ch in base).split()) or "x"


async def resolve_driver_identity(o: dict, shifts: List[dict]) -> Optional[str]:
    """Person behind a delivery. Snapshot `driver_name` wins; older orders (no snapshot) are matched to the shift
    that was open on that slot when the order was assigned. Nothing is written back – historical data is untouched."""
    if o.get("driver_name"):
        return o["driver_name"]
    role = next((r for r, n in staff_mod.DRIVER_NAME.items() if n == o.get("driver")), None)
    at = o.get("assigned_at") or o.get("delivered_at") or o.get("created_at")
    if not role or not at:
        return None
    at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    for sh in shifts:
        if sh["role"] != role:
            continue
        opened = sh["opened_at"].replace(tzinfo=timezone.utc)
        closed = (sh.get("closed_at") or sh["expires_at"]).replace(tzinfo=timezone.utc)
        if opened <= at <= closed:
            return sh["name"]
    return None


@api.get("/reports/closing")
async def closing_report(date: Optional[str] = None, _: dict = Depends(staff_mod.require_roles("manager"))):
    """One closing entry per real driver identity (slot + person), never per generic slot alone.
    Re-opening a slot for another person creates a new identity; earlier deliveries stay with the earlier person."""
    day, start, end = day_range(date)
    docs = await db.orders.find({"type": "delivery", "driver": {"$ne": None}, "created_at": {"$gte": start, "$lt": end}}).to_list(2000)
    shifts = await db.driver_shifts.find({"opened_at": {"$lt": end}}, {"pin_hash": 0, "session_id": 0}).to_list(5000)
    closings: Dict[tuple, dict] = {(c["driver"], c.get("driver_name")): c async for c in db.closings.find({"date": day})}
    current = {sh["role"]: sh for sh in [await staff_mod.open_shift(r) for r in staff_mod.DRIVER_NAME] if sh} if day == day_range(None)[0] else {}
    by_identity: Dict[tuple, List[dict]] = {}
    for o in docs:
        by_identity.setdefault((o["driver"], await resolve_driver_identity(o, shifts)), []).append(o)
    out = []
    for role, slot in staff_mod.DRIVER_NAME.items():
        cur = current.get(role)
        names = {k[1] for k in by_identity if k[0] == slot}
        if cur:
            names.add(cur["name"])  # person on duty today is always listed, even before the first delivery
        if not names:
            names.add(None)  # nothing today on this slot -> single empty entry
        slot_groups = len(names)
        ordered = sorted(names, key=lambda n: (n is None, not (cur and n == cur["name"]), (n or "").lower()))
        for name in ordered:
            mine = by_identity.get((slot, name), [])
            delivered = [o for o in mine if o["status"] in ("delivered", "completed")]
            cancelled = [o for o in mine if o["status"] == "cancelled"]
            cash = round(sum(o["total"] for o in delivered if (o.get("collection_method") or "cash") == "cash"), 2)
            terminal = round(sum(o["total"] for o in delivered if o.get("collection_method") == "terminal"), 2)
            paid = round(sum(o["total"] for o in delivered if o.get("collection_method") == "none"), 2)
            # Closing record per identity; a legacy slot-only record still applies when the slot has a single identity
            c = closings.get((slot, name)) or (closings.get((slot, None)) if (name is None or slot_groups == 1) else None)
            out.append({
                "driver": slot, "driver_name": name, "label": f"{slot} — {name or LEGACY_DRIVER_LABEL}",
                "identity_key": f"{slug(slot)}__{slug(name) if name else 'legacy'}", "legacy": name is None,
                "is_current": bool(cur and name == cur["name"]),
                "date": day, "deliveries": len(delivered), "cancelled": len(cancelled),
                "orders": [{"id": str(o["_id"]), "order_number": o["order_number"], "total": o["total"], "collection_method": o.get("collection_method") or "cash",
                            "payment_collected": o.get("payment_collected", False), "delivered_at": o.get("delivered_at"), "status": o["status"],
                            "city": (o.get("address") or {}).get("city", "")} for o in sorted(mine, key=lambda x: x["created_at"])],
                "cash_expected": cash, "terminal_expected": terminal, "paid_no_collection": paid, "total": round(cash + terminal + paid, 2),
                "actual_cash": c.get("actual_cash") if c else None, "actual_terminal": c.get("actual_terminal") if c else None,
                "cash_difference": round(c["actual_cash"] - cash, 2) if c and c.get("actual_cash") is not None else None,
                "terminal_difference": round(c["actual_terminal"] - terminal, 2) if c and c.get("actual_terminal") is not None else None,
                "closed_at": c.get("closed_at") if c else None,
            })
    return {"date": day, "drivers": out}


class ClosingIn(BaseModel):
    date: str
    driver: str
    driver_name: Optional[str] = None  # identity (person) – None only for legacy unnamed deliveries
    actual_cash: Optional[float] = None
    actual_terminal: Optional[float] = None
    note: Optional[str] = None


@api.post("/reports/closing")
async def save_closing(body: ClosingIn, _: dict = Depends(staff_mod.require_roles("manager"))):
    if body.driver not in staff_mod.DRIVER_NAME.values():
        raise HTTPException(400, "Unknown driver")
    name = (body.driver_name or "").strip() or None
    await db.closings.update_one({"date": body.date, "driver": body.driver, "driver_name": name},
                                 {"$set": {"actual_cash": body.actual_cash, "actual_terminal": body.actual_terminal, "note": body.note, "closed_at": now_utc()}}, upsert=True)
    return {"ok": True}


@api.get("/reports/sources")
async def sources_report(date: Optional[str] = None, _: dict = Depends(staff_mod.require_roles("manager"))):
    day, start, end = day_range(date)
    docs = await db.orders.find({"created_at": {"$gte": start, "$lt": end}, "status": {"$ne": "cancelled"}}).to_list(5000)
    buckets: Dict[str, Dict[str, float]] = {}
    for o in docs:
        key = f"TÉLÉPHONE · POSTE {o.get('station') or 1}" if o["source"] == "telephone" else ("WEB" if o["source"] == "web" else "APP")
        b = buckets.setdefault(key, {"count": 0, "total": 0.0})
        b["count"] += 1
        b["total"] = round(b["total"] + o["total"], 2)
    order = ["WEB", "APP", "TÉLÉPHONE · POSTE 1", "TÉLÉPHONE · POSTE 2"]
    return {"date": day, "sources": [{"source": k, **buckets.get(k, {"count": 0, "total": 0.0})} for k in order],
            "total_count": sum(b["count"] for b in buckets.values()), "total": round(sum(b["total"] for b in buckets.values()), 2)}


@api.get("/me/orders", response_model=List[Order])
async def my_orders(user: dict = Depends(auth_mod.current_user), limit: int = 50):
    docs = await db.orders.find({"user_id": str(user["_id"])}).sort("created_at", -1).to_list(limit)
    return [Order.from_mongo(d) for d in docs]


@api.get("/customers/search")
async def search_customers(phone: str = Query(min_length=3), limit: int = 20, _: dict = Depends(PHONE)):
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
async def list_orders(active: bool = True, ids: Optional[str] = None, limit: int = 400, credentials: HTTPAuthorizationCredentials = Depends(auth_mod.bearer)):
    """`ids=` -> the customer's own orders (device-stored ids, no auth). Without ids -> full staff list (manager/kitchen only)."""
    q: Dict[str, Any] = {}
    if ids:
        q["_id"] = {"$in": [oid(i) for i in ids.split(",") if i]}
    else:
        user = await staff_mod.staff_user(credentials)
        if user["role"] not in ("manager", "kitchen"):
            raise HTTPException(403, "Accès refusé pour ce rôle")
    if not ids and active:
        q["$or"] = [
            {"status": {"$nin": list(TERMINAL)}},
            {"status": {"$in": list(TERMINAL)}, "created_at": {"$gte": now_utc() - timedelta(hours=3)}},
        ]
    docs = await db.orders.find(q).sort("created_at", -1).to_list(limit)
    settings = await get_settings()
    for d in docs:
        d["legacy"] = is_historical(d, settings)  # dashboards move these out of the operational lists
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


def parse_local_time(hhmm: str, on_date: Optional[str] = None) -> datetime:
    try:
        h, m = [int(x) for x in hhmm.strip().split(":")]
    except Exception:
        raise HTTPException(400, "Invalid time, expected HH:MM")
    local_now = datetime.now(TZ)
    if on_date:  # scheduled order: the time belongs to its requested day
        d = datetime.strptime(on_date, "%Y-%m-%d").date()
        return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ).astimezone(timezone.utc)
    target = local_now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target < local_now - timedelta(hours=2):
        target += timedelta(days=1)
    return target.astimezone(timezone.utc)


def fmt_date(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(TZ)
    return f"{hours_mod.DAY_FR[hours_mod.DAYS[local.weekday()]]} {local.strftime('%d.%m.%Y')}"


# ---------------------------------------------------------------------------
# Printing (PrintNode architecture – disabled until credentials are configured)
# ---------------------------------------------------------------------------
PRINTNODE_API_KEY = os.environ.get("PRINTNODE_API_KEY", "").strip()
PRINTNODE_PRINTER_ID = os.environ.get("PRINTNODE_PRINTER_ID", "").strip()
if PRINTNODE_API_KEY and PRINTNODE_PRINTER_ID:
    logger.info("PrintNode configured – printer %s", PRINTNODE_PRINTER_ID)
else:
    logger.warning("PrintNode NOT configured (PRINTNODE_API_KEY=%s, PRINTNODE_PRINTER_ID=%s) – print jobs will only be SIMULATED",
                   "set" if PRINTNODE_API_KEY else "EMPTY", PRINTNODE_PRINTER_ID or "EMPTY")


def is_historical(doc: dict, settings: Settings) -> bool:
    """True for orders created before the real printer was enabled: they must never reach the printer
    (no auto-print, no manual reprint, no receipt) – protects against replaying test/old orders."""
    if not settings.printing_enabled_at:
        return False
    created = doc["created_at"] if doc["created_at"].tzinfo else doc["created_at"].replace(tzinfo=timezone.utc)
    enabled = settings.printing_enabled_at.replace(tzinfo=settings.printing_enabled_at.tzinfo or timezone.utc)
    return created < enabled


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
        logger.warning("Print job for order #%s only SIMULATED – PrintNode credentials missing", order_doc["order_number"])
        await db.print_jobs.insert_one(job)
        return "simulated"
    try:
        import base64
        import requests  # PrintNode REST API
        # ESC @ init, ESC t 16 = code page WPC1252 (accents É È À Ô print correctly), text encoded in cp1252, then cut.
        esc = "\x1b@\x1bt\x10" + text + "\n\n\n\n\x1dV\x00"
        payload = {"printerId": int(PRINTNODE_PRINTER_ID), "title": f"Commande #{order_doc['order_number']}",
                   "contentType": "raw_base64", "content": base64.b64encode(esc.encode("cp1252", "replace")).decode(),
                   "source": "Hallo Magic Pizza"}
        r = requests.post("https://api.printnode.com/printjobs", json=payload, auth=(PRINTNODE_API_KEY, ""), timeout=10)
        job["status"] = "sent" if r.ok else "failed"
        job["provider_response"] = r.text[:500]
        if r.ok:
            job["printnode_job_id"] = r.text.strip().strip('"')
            logger.info("PrintNode job %s sent for order #%s (%s)", job["printnode_job_id"], order_doc["order_number"], kind)
        else:
            job["error"] = f"PrintNode HTTP {r.status_code}: {r.text[:200]}"
            logger.error("PrintNode rejected job for order #%s: %s", order_doc["order_number"], job["error"])
    except Exception as e:  # network / config error
        job["status"] = "failed"
        job["error"] = str(e)
        logger.error("PrintNode request failed for order #%s: %s", order_doc["order_number"], e)
    await db.print_jobs.insert_one(job)
    return job["status"]


def escpos_qr(data: str) -> str:
    """ESC/POS QR (model 2, size 6, EC level M) – Epson TM-T70II. Payload is an internal driver URL only."""
    payload = data.encode("ascii", "replace")
    n = len(payload) + 3
    pl, ph = n % 256, n // 256
    cmd = "\x1b\x61\x01"  # center
    cmd += "\x1d\x28\x6b\x04\x00\x31\x41\x32\x00"  # model 2
    cmd += "\x1d\x28\x6b\x03\x00\x31\x43\x06"       # module size 6
    cmd += "\x1d\x28\x6b\x03\x00\x31\x45\x31"       # EC level M
    cmd += f"\x1d\x28\x6b{chr(pl)}{chr(ph)}\x31\x50\x30" + payload.decode("ascii")  # store
    cmd += "\x1d\x28\x6b\x03\x00\x31\x51\x30"       # print
    cmd += "\x1b\x61\x00"
    return cmd


async def do_print(doc: dict, force: bool) -> dict:
    if doc.get("status") == "pending":
        raise HTTPException(409, "Order not accepted yet – the ticket prints on acceptance")
    if doc.get("printed") and not force:
        raise HTTPException(409, "Ticket already printed")
    if doc.get("print_status") == "failed" and not force:
        force = True  # RETRY after a failure is always allowed (job preserved in print_jobs)
    settings = await get_settings()
    if is_historical(doc, settings):
        # Historical / test order (created before the real printer was enabled): never sent to the printer,
        # neither automatically nor by a manual reprint.
        if force:
            raise HTTPException(409, "Historical order – printing disabled")
        await db.print_jobs.insert_one({"order_id": str(doc["_id"]), "order_number": doc["order_number"], "kind": "kitchen", "status": "skipped_historical", "created_at": now_utc()})
        await db.orders.update_one({"_id": doc["_id"]}, {"$set": {"printed": True, "printed_at": now_utc(), "print_status": "skipped_historical"}})
        return {"ok": True, "printed": True, "print_status": "skipped_historical", "print_attempts": doc.get("print_attempts", 0), "text": ""}
    if not force:
        # Durable idempotency: exactly one automatic print per order, across devices/retries/restarts
        locked = await db.orders.find_one_and_update({"_id": doc["_id"], "printed": {"$ne": True}, "print_lock": {"$exists": False}},
                                                     {"$set": {"print_lock": now_utc()}})
        if not locked:
            raise HTTPException(409, "Ticket already printed")
    last = doc.get("printed_at")
    if last and not force:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now_utc() - last < timedelta(seconds=10):
            raise HTTPException(409, "Print job already in progress")
    is_reprint = bool(force and doc.get("printed") and doc.get("print_status") in ("sent", "simulated"))
    text = build_ticket(doc, settings, reprint=is_reprint)
    status = await send_to_printer(doc, text, kind="reprint" if is_reprint else "kitchen")
    job = await db.print_jobs.find_one({"order_id": str(doc["_id"])}, sort=[("created_at", -1)])
    ok = status in ("sent", "simulated")
    upd = {"printed": ok or bool(doc.get("printed")), "printed_at": now_utc(), "print_status": status, "last_print_error": (job or {}).get("error") if not ok else None,
           "printnode_job_id": (job or {}).get("printnode_job_id")}
    inc = {"print_attempts": 1, **({"reprint_count": 1} if is_reprint else {})}
    new = await db.orders.find_one_and_update({"_id": doc["_id"]}, {"$set": upd, "$unset": {"print_lock": ""}, "$inc": inc}, return_document=ReturnDocument.AFTER)
    return {"ok": ok, "printed": ok, "printed_at": new["printed_at"], "print_attempts": new["print_attempts"],
            "print_status": status, "last_print_error": upd["last_print_error"], "printnode_job_id": upd["printnode_job_id"], "text": strip_escpos(text)}


async def push_status(doc: dict, status: str, notif: Optional[dict], extra_set: Optional[dict] = None) -> Order:
    update: Dict[str, Any] = {"$set": {"status": status, **(extra_set or {})},
                              "$push": {"status_history": StatusEvent(status=status, at=now_utc()).model_dump()}}
    if notif:
        update["$push"]["notifications"] = notif
    new = await db.orders.find_one_and_update({"_id": doc["_id"]}, update, return_document=ReturnDocument.AFTER)
    return Order.from_mongo(new)


async def finish_order(doc: dict, status: str, notif: Optional[dict], extra_set: Optional[dict] = None) -> Order:
    """'picked_up' / 'delivered' close the order: the final status is recorded, then TERMINÉE automatically
    (no extra manager tap). Both events stay in status_history."""
    await push_status(doc, status, notif, extra_set)
    return await push_status(doc, "completed", None, {"completed_at": now_utc()})


@api.post("/orders/{order_id}/accept", response_model=Order)
async def accept_order(order_id: str, body: AcceptIn, _: dict = Depends(STAFF)):
    """THE ONLY place that produces the initial kitchen ticket. Atomic pending->accepted transition: a second
    tap / retry / other device gets 400 (not pending) and can never create a second job."""
    doc = await load_order(order_id)
    if doc["status"] != "pending":
        raise HTTPException(400, "Order is not pending")
    ts = now_utc()
    sched = doc.get("scheduled_for")
    if sched and sched.tzinfo is None:
        sched = sched.replace(tzinfo=timezone.utc)
    if body.time:
        ready = parse_local_time(body.time, on_date=doc.get("requested_date"))
        minutes = max(0, int((ready - ts).total_seconds() // 60))
    elif body.minutes is not None:
        minutes = body.minutes
        base = ts
        requested_dt = sched
        if not requested_dt and doc.get("requested_time") not in (None, "", "asap"):
            requested_dt = parse_local_time(doc["requested_time"])  # same-day scheduled order (e.g. 13:45)
        if requested_dt and requested_dt > ts:
            base = requested_dt  # scheduled: "+30 min" is relative to the requested slot, never to the acceptance time
        else:
            st = hours_mod.ordering_status(await get_settings(), datetime.now(TZ))
            if st.get("asap_from") and not st["pickup_open"]:
                base = parse_local_time(st["asap_from"])  # accepted before opening: "15 min" = 15 min after opening
        ready = base + timedelta(minutes=minutes)
    else:
        raise HTTPException(400, "minutes or time required")
    requested = doc.get("requested_time")
    changed = bool(requested and requested != "asap" and fmt_time(ready) != requested)
    notif = make_notification("order_accepted", doc["order_number"], t=(fmt_date(ready) + " " if doc.get("requested_date") else "") + fmt_time(ready))
    # Atomic claim: only the request that flips pending -> accepted continues (and prints)
    claimed = await db.orders.find_one_and_update(
        {"_id": doc["_id"], "status": "pending"},
        {"$set": {"status": "accepted", "accepted_at": ts, "estimated_minutes": minutes, "estimated_ready_at": ready, "time_changed": changed},
         "$push": {"status_history": StatusEvent(status="accepted", at=ts).model_dump(), "notifications": notif}},
        return_document=ReturnDocument.AFTER)
    if not claimed:
        raise HTTPException(400, "Order is not pending")
    order = Order.from_mongo(claimed)
    # Automatic kitchen print on acceptance (idempotent: skipped if already printed)
    try:
        if not claimed.get("printed"):
            await do_print(claimed, force=False)
            order = Order.from_mongo(await load_order(order_id))
    except HTTPException:
        pass
    return order


@api.post("/orders/{order_id}/reject", response_model=Order)
async def reject_order(order_id: str, body: RejectIn, _: dict = Depends(STAFF)):
    doc = await load_order(order_id)
    if doc["status"] in TERMINAL:
        raise HTTPException(400, "Order already closed")
    notif = make_notification("cancelled", doc["order_number"], r=body.reason or "")
    return await push_status(doc, "cancelled", notif, {"reject_reason": body.reason})


@api.post("/orders/{order_id}/delay", response_model=Order)
async def delay_order(order_id: str, body: DelayIn, _: dict = Depends(STAFF)):
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
async def set_status(order_id: str, body: StatusIn, _: dict = Depends(STAFF)):
    doc = await load_order(order_id)
    flow = PICKUP_FLOW if doc["type"] == "pickup" else DELIVERY_FLOW
    if body.status not in flow and body.status != "cancelled":
        raise HTTPException(400, f"Invalid status for {doc['type']}")
    if doc["status"] in TERMINAL:
        raise HTTPException(409, "Order already closed")
    if doc["status"] == "pending" and body.status not in ("cancelled",):
        raise HTTPException(400, "Accept the order first")
    if body.status != "cancelled" and flow.index(body.status) <= flow.index(doc["status"]):
        raise HTTPException(409, f"Statut déjà {doc['status']} – mise à jour obsolète ignorée")
    n = doc["order_number"]
    if body.status == "ready":
        ev = "ready" if doc["type"] == "pickup" else "ready_delivery"
    else:
        ev = STATUS_EVENT.get(body.status)
    notif = make_notification(ev, n) if ev else None
    stamps = {"ready": "ready_at", "delivering": "out_for_delivery_at", "delivered": "delivered_at"}
    extra = {stamps[body.status]: now_utc()} if body.status in stamps else None
    if body.status in ("picked_up", "delivered"):
        return await finish_order(doc, body.status, notif, extra)
    return await push_status(doc, body.status, notif, extra)


# ---------------------------------------------------------------------------
# 80mm ticket
# ---------------------------------------------------------------------------
ESC_RESET = "\x1d!\x00\x1bE\x00\x1ba\x00"  # normal size, bold off, left align


def escpos_big(text: str, scale: int = 3, w: Optional[int] = None, h: Optional[int] = None, reverse: bool = False) -> str:
    """One centered BOLD line at w×h character size (Epson GS ! n, 1..8). reverse = white on black (GS B)."""
    w, h = w or scale, h or scale
    n = ((w - 1) << 4) | (h - 1)
    rev_on, rev_off = ("\x1dB\x01", "\x1dB\x00") if reverse else ("", "")
    return f"\x1ba\x01\x1bE\x01{rev_on}\x1d!{chr(n)}{text}\x1d!\x00{rev_off}\x1bE\x00\x1ba\x00"


def escpos_item(qty_size: str, name: str) -> List[str]:
    """Pizza line, always BOLD and on ONE line whenever it fits the 80 mm paper:
    - ≤ 21 chars → 2× width + height ('1x 50 CM FORESTIÈRE')
    - ≤ 42 chars → double height, normal width ('1x 50 CM QUATTRO FORMAGGI SPECIALE')
    - longer      → '1x 50 CM' (2×) then the name on the next double-height line (printer wraps beyond 42 cols)."""
    full = f"{qty_size} {name}".strip()
    if len(full) <= 21:
        return [f"\x1bE\x01\x1d!\x11{full}{ESC_RESET}"]
    if len(full) <= 42:
        return [f"\x1bE\x01\x1d!\x01{full}{ESC_RESET}"]
    return [f"\x1bE\x01\x1d!\x11{qty_size}{ESC_RESET}", f"\x1bE\x01\x1d!\x01 {name}{ESC_RESET}"]


def strip_escpos(text: str) -> str:
    """Plain-text version of a ticket (app preview / logs): removes ESC/POS control sequences, keeps the words."""
    text = re.sub(r"\x1d[!B].", "", text)
    text = re.sub(r"\x1b[aEt].", "", text)
    return text


def build_ticket(o: dict, settings: Settings, reprint: bool = False) -> str:
    """OPERATIONAL kitchen / delivery ticket (80 mm). Real ESC/POS sizes: 3x for LIVRAISON/RETRAIT, #, times;
    2x for labels, payment and pizza sizes. Not a fiscal receipt (see build_receipt)."""
    W = 42  # Epson TM-T70 80 mm, font A
    c = lambda t: t.center(W)  # noqa: E731
    huge = lambda t, rev=False: escpos_big(t, 4, reverse=rev)  # noqa: E731  (4x – 10 chars max)
    big = lambda t: escpos_big(t, 3)  # noqa: E731  (3x – 14 chars max)
    mid = lambda t: escpos_big(t, 2)  # noqa: E731  (2x – 21 chars max)
    tall = lambda t: escpos_big(t, 1, w=1, h=2)  # noqa: E731  (double height, 42 chars)
    delivery = o["type"] == "delivery"
    lines: List[str] = [c(settings.restaurant_name.upper())]
    if reprint:
        lines += [c("*** REIMPRESSION ***")]
    # ---- 1. Order number, then LIVRAISON / RETRAIT (biggest text, slightly lower so it shows in the ticket holder);
    #         delivery = white-on-black band, pickup = starred frame --------------------------------------------
    lines += [mid(f"#{o['order_number']}")]
    if delivery:
        lines += ["#" * W, huge("LIVRAISON", True), "#" * W]
    else:
        lines += ["*" * W, huge("RETRAIT"), "*" * W]
    requested = o.get("requested_time") if o.get("requested_time") not in (None, "", "asap") else None
    confirmed = fmt_time(o["estimated_ready_at"]) if o.get("estimated_ready_at") else None
    ready_dt = o.get("estimated_ready_at") or o.get("scheduled_for")
    if ready_dt and ready_dt.tzinfo is None:
        ready_dt = ready_dt.replace(tzinfo=timezone.utc)
    scheduled = bool(ready_dt) and ready_dt.astimezone(TZ).date() != datetime.now(TZ).date()
    # ---- 2. WHEN – the very large (4x) time is ALWAYS the effective ready/delivery time (never accepted_at) ----
    when_label = "LIVRAISON DEMANDÉE" if delivery else "RETRAIT À"  # customer-requested time (delivery: 18 cols at 2x)
    lines += ["-" * W]
    if scheduled:
        # Future-day order: the DATE is the first thing the kitchen must see – never confused with today's tickets
        lines += [mid("COMMANDE PROGRAMMEE"), mid("PAS POUR AUJOURD'HUI"), mid(fmt_date(ready_dt).upper())]
        if requested and confirmed and confirmed != requested:
            lines += [mid(f"DEMANDÉE {requested}"), mid(f"CONFIRMÉE {confirmed}")]
        else:
            lines += [mid(when_label)]
        lines += [huge(confirmed or requested or "--:--")]
    elif requested:
        if confirmed and confirmed != requested:
            # Staff changed the requested time: show both, the large one is the confirmed operational time
            lines += [mid(f"DEMANDÉE {requested}"), mid(f"CONFIRMÉE {confirmed}"), huge(confirmed)]
        else:
            lines += [mid(when_label), huge(requested)]
    else:
        lines += [mid("DÈS QUE POSSIBLE")]
        if confirmed:
            lines += [huge(confirmed)]
    lines += ["=" * W]
    # ---- 2. SOURCE --------------------------------------------------------------------------------------------
    src = f"TELEPHONE - POSTE {o.get('station') or 1}" if o.get("source") == "telephone" else {"web": "WEB", "ios": "APP IPHONE", "android": "APP ANDROID"}.get(o.get("source", "web"), o.get("source", "web").upper())
    lines += [c(src), "=" * W]
    if o.get("driver"):
        lines += [tall(f"{o['driver'].upper()}{(' - ' + o['driver_name'].upper()) if o.get('driver_name') else ''}")]
    if o.get("age_required"):
        lines += ["!" * W, c(f"ALCOOL - CONTROLE AGE {o['age_required']}+"), c("VERIFIER LA PIECE D'IDENTITE"), "!" * W]
    # ---- 3. PAYMENT – immediately visible --------------------------------------------------------------------
    method = o.get("collection_method") or ("terminal" if o.get("payment_method") == "terminal" else "cash")
    amount = "CHF %.2f" % o.get("amount_due", o["total"])
    lines += ["-" * W]
    if o.get("payment_collected") or method == "none":
        lines += [tall("DEJA PAYE")]
    else:
        lines += [tall(f"À ENCAISSER · {'TERMINAL' if method == 'terminal' else 'ESPÈCES'} · {amount}")]  # one bold line
    # ---- 4. ITEMS – "1x 50 CM  NOM" whole line bold 2x (one line when it fits); supplements smaller, indented -----
    def size_txt(it):
        return it["size"]["label"].upper().replace("CM", "").strip() + " CM" if it.get("size") else ""
    def item_line(it, name):
        return escpos_item(f"{it['quantity']}x {size_txt(it)}".strip(), name)
    lines += ["-" * W]
    for it in o["items"]:
        if it.get("half"):
            lines += item_line(it, "MOITIE / MOITIE")
            lines.append(f"   1/2 {it['name']['fr'].upper()}")
            for r in it.get("removed_ingredients", []):
                lines.append(f"       - SANS {r['fr'].upper()}")
            if it.get("note"):
                lines.append(f"       NOTE: {it['note'].upper()}")
            lines.append(f"   1/2 {it['half']['name']['fr'].upper()}")
            for r in it["half"].get("removed_ingredients", []):
                lines.append(f"       - SANS {r['fr'].upper()}")
            if it["half"].get("note"):
                lines.append(f"       NOTE: {it['half']['note'].upper()}")
        else:
            lines += item_line(it, it["name"]["fr"].upper())
            for op in it.get("options", []):
                lines.append(f"   * {op['name']['fr'].upper()}")
            for r in it.get("removed_ingredients", []):
                lines.append(f"   - SANS {r['fr'].upper()}")
        for e in it.get("extras", []):
            q = f"{e['quantity']}x " if e["quantity"] > 1 else ""
            lines.append(f"   + {q}{e['name']['fr'].upper()}")
        if not it.get("half") and it.get("note"):
            lines.append(f"   NOTE: {it['note'].upper()}")
        lines.append("")
    if o.get("general_note"):
        lines += ["NOTE COMMANDE:", o["general_note"].upper(), ""]
    lines += ["-" * W, "CLIENT:", f"{o['customer']['first_name']} {o['customer'].get('last_name', '')}".strip().upper(), f"TEL: {o['customer']['phone']}"]
    if o["type"] == "delivery" and o.get("address"):
        a = o["address"]
        lines += ["", "ADRESSE:", f"{a['street']} {a.get('number', '')}".strip().upper(), f"{a['npa']} {a['city'].upper()}"]
        if a.get("instructions"):
            lines.append(f"INFO: {a['instructions'].upper()}")
    lines += ["-" * W]
    if o.get("delivery_fee"):
        lines.append(f"{'Livraison':<{W-10}}{('CHF %.2f' % o['delivery_fee']):>10}")
    lines.append(f"{'TOTAL:':<{W-12}}{('CHF %.2f' % o['total']):>12}")
    # Operational timestamps
    stamps = [("Recue", o.get("created_at")), ("Acceptee", o.get("accepted_at")), ("Prete", o.get("ready_at")), ("Partie", o.get("out_for_delivery_at")), ("Livree", o.get("delivered_at"))]
    lines += ["-" * W] + [f"{k + ':':<10}{fmt_time(v)}" for k, v in stamps if v]
    lines += ["", c("Ticket operationnel - pas un recu fiscal"), ""]
    return "\n".join(lines)


@api.get("/orders/{order_id}/ticket")
async def get_ticket(order_id: str, _: dict = Depends(TICKET)):
    doc = await load_order(order_id)
    settings = await get_settings()
    return {"order_id": order_id, "order_number": doc["order_number"], "text": strip_escpos(build_ticket(doc, settings)),
            "printed": doc.get("printed", False), "printed_at": doc.get("printed_at"), "print_attempts": doc.get("print_attempts", 0),
            "print_status": doc.get("print_status"), "printer_configured": bool(PRINTNODE_API_KEY and PRINTNODE_PRINTER_ID),
            "last_print_error": doc.get("last_print_error"), "printnode_job_id": doc.get("printnode_job_id"),
            "qr": f"/driver?o={order_id}" if doc["type"] == "delivery" else None}


class PrintIn(BaseModel):
    force: bool = False


@api.post("/orders/{order_id}/print")
async def print_ticket(order_id: str, body: PrintIn = PrintIn(), _: dict = Depends(STAFF)):
    """Print (first time) or re-print (force=true) the 80mm kitchen ticket."""
    doc = await load_order(order_id)
    return await do_print(doc, body.force)


@api.get("/print-jobs")
async def list_print_jobs(limit: int = 50, _: dict = Depends(STAFF)):
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
async def get_receipt(order_id: str, _: dict = Depends(STAFF)):
    doc = await load_order(order_id)
    s = await get_settings()
    return {"order_id": order_id, "order_number": doc["order_number"], "text": build_receipt(doc, s),
            "printed": doc.get("receipt_printed", False), "printed_at": doc.get("receipt_printed_at"),
            "print_attempts": doc.get("receipt_print_attempts", 0), "vat_breakdown": doc.get("vat_breakdown", []),
            "total_net": doc.get("total_net"), "total_vat": doc.get("total_vat"), "total": doc["total"]}


@api.post("/orders/{order_id}/receipt/print")
async def print_receipt(order_id: str, body: PrintIn = PrintIn(), _: dict = Depends(STAFF)):
    """Print / re-print the customer receipt (same simulated PrintNode pipeline as the kitchen ticket)."""
    doc = await load_order(order_id)
    if doc.get("receipt_printed") and not body.force:
        raise HTTPException(409, "Receipt already printed")
    s = await get_settings()
    if is_historical(doc, s):
        raise HTTPException(409, "Historical order – printing disabled")
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
api.include_router(staff_mod.router)
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

from fastapi import FastAPI, APIRouter, HTTPException, Query, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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
    wine: Optional[WineInfo] = None
    sort: int = 0
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
    wine: Optional[WineInfo] = None
    sort: int = 0


class ProductPatch(BaseModel):
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
    wine: Optional[WineInfo] = None
    sort: Optional[int] = None


class ExtraIn(BaseModel):
    key: str
    name: I18n
    price: float
    available: bool = True
    max_quantity: int = 1


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
    language: str = "fr"


class OrderExtra(BaseModel):
    extra_id: str
    name: I18n
    unit_price: float
    quantity: int


class OrderItemOption(BaseModel):
    key: str
    name: I18n
    price: float


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
    subtotal: float
    extras_total: float
    delivery_fee: float
    total: float
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


@api.post("/orders", response_model=Order)
async def create_order(body: OrderIn, request: Request):
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
    has_alcohol = False
    for it in body.items:
        pdoc = await db.products.find_one({"_id": oid(it.product_id), "deleted_at": None})
        if not pdoc:
            raise HTTPException(400, f"Product {it.product_id} not found")
        if not pdoc.get("available", True):
            raise HTTPException(400, f"{pdoc['name']['fr']} n'est plus disponible")
        if pdoc.get("is_alcohol"):
            has_alcohol = True
        allowed = set(pdoc.get("allowed_extra_ids", []))
        ex_list: List[OrderExtra] = []
        ex_sum = 0.0
        for ex in it.extras:
            edoc = extras_by_id.get(ex.extra_id)
            if not edoc or (edoc["key"] not in allowed and ex.extra_id not in allowed):
                raise HTTPException(400, "Extra not allowed for this product")
            qty = max(1, min(ex.quantity, edoc.get("max_quantity", 1)))
            ex_list.append(OrderExtra(extra_id=ex.extra_id, name=I18n(**edoc["name"]), unit_price=edoc["price"], quantity=qty))
            ex_sum += edoc["price"] * qty
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
        items.append(OrderItem(
            product_id=it.product_id, name=I18n(**pdoc["name"]), unit_price=unit, quantity=qty, size=size, options=opts,
            removed_ingredients=removed, extras=ex_list, note=(it.note or None), line_total=line_total,
        ))
    if has_alcohol and not body.age_confirmed:
        raise HTTPException(400, "Age confirmation required for alcoholic drinks")

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

    number = await next_order_number()
    ts = now_utc()
    order = Order(
        order_number=number, type=body.type, source=body.source, status="pending", items=items,
        customer=body.customer, address=body.address if body.type == "delivery" else None,
        requested_time=body.requested_time, general_note=body.general_note or None,
        payment_method="pay_at_delivery" if body.type == "delivery" else "pay_at_pickup",
        language=body.language, age_confirmed=body.age_confirmed,
        subtotal=round(subtotal, 2), extras_total=round(extras_total, 2), delivery_fee=delivery_fee, total=total,
        created_at=ts, status_history=[StatusEvent(status="pending", at=ts)],
        notifications=[Notification(**make_notification("order_received", number))],
    )
    res = await db.orders.insert_one(order.to_mongo())
    return Order.from_mongo(await db.orders.find_one({"_id": res.inserted_id}))


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


async def send_to_printer(order_doc: dict, text: str) -> str:
    """Create a print job. Returns status: 'sent' | 'failed' | 'simulated'.
    With PrintNode credentials configured, this posts a raw job to the Epson TM-T70II via PrintNode.
    Without credentials the job is only recorded (simulated) – nothing touches the existing installation."""
    job = {
        "order_id": str(order_doc["_id"]), "order_number": order_doc["order_number"], "provider": "printnode",
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
    if o.get("requested_time") and o["requested_time"] != "asap":
        lines.append("SOUHAITE: " + o["requested_time"])
    if o.get("estimated_ready_at"):
        lines.append(("PRET VERS " if o["type"] == "pickup" else "LIVRAISON VERS ") + fmt_time(o["estimated_ready_at"]))
    lines.append("Recue: " + fmt_time(o["created_at"]))
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
    lines += ["", c("PAIEMENT AU RETRAIT" if o["type"] == "pickup" else "PAIEMENT A LA LIVRAISON"), "", c("Merci / Danke!"), ""]
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


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

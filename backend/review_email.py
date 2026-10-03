"""Google review request e-mail – sent ONCE per eligible COMPLETED order, through Emergent's managed e-mail proxy.
Rules: never on creation / acceptance / cancellation; never twice (atomic claim on the order document); a failure never
touches order, payment or printing flows (runs in a background loop, fully isolated). Recipients and content come from
server-side records/templates only. The link in the e-mail points to OUR site (/api/review/{id}/go) which redirects to the
Google review URL entered by the restaurant in Administration."""
import asyncio
import ipaddress
import logging
import os
import re
from datetime import timedelta
from html import escape
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from pymongo import ReturnDocument

from auth import normalize_phone

load_dotenv()
logger = logging.getLogger(__name__)

EMAIL_BASE_URL = "https://integrations.emergentagent.com"  # constant on purpose (survives deployment)
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Hallo Magic Pizza")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")
EMAIL_DRY_RUN = os.environ.get("EMAIL_DRY_RUN", "0") == "1"  # tests / preview: log instead of sending

# ---- guardrail gate (G2 + G3) -------------------------------------------------------------------------------
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv", "send us your password",
             "enter your password below", "confirm your card number", "your full card number", "seed phrase",
             "recovery phrase", "verify your card", "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> str:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if EMAIL_REPLY_TO:
        payload["contact_email"] = EMAIL_REPLY_TO
    if EMAIL_DRY_RUN:
        logger.info("[EMAIL DRY RUN] to=%s subject=%r", to, subject)
        return "dry-run"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": EMAIL_KEY}, json=payload)
    resp.raise_for_status()
    return resp.json().get("id", "")


# ---- template ---------------------------------------------------------------------------------------------------
TEXT = {
    "fr": {"subject": "Merci pour votre commande #{n} – votre avis compte", "hi": "Bonjour {name},",
           "body": "Merci d'avoir commandé chez {brand}. Nous espérons que vous vous êtes régalé(e) !",
           "ask": "Un petit avis Google nous aide énormément – cela ne prend qu'une minute :",
           "cta": "Laisser un avis", "foot": "E-mail envoyé une seule fois par {brand} suite à votre commande #{n}. Nous ne demandons jamais de mot de passe ni de données bancaires par e-mail."},
    "de": {"subject": "Danke für Ihre Bestellung #{n} – Ihre Meinung zählt", "hi": "Guten Tag {name},",
           "body": "Vielen Dank für Ihre Bestellung bei {brand}. Wir hoffen, es hat geschmeckt!",
           "ask": "Eine kurze Google-Bewertung hilft uns sehr – es dauert nur eine Minute:",
           "cta": "Bewertung abgeben", "foot": "Diese E-Mail wird von {brand} nur einmal nach Ihrer Bestellung #{n} gesendet. Wir fragen nie per E-Mail nach Passwörtern oder Bankdaten."},
}


def build_review_email(lang: str, first_name: str, order_number: int, link: str) -> tuple:
    t = TEXT["de" if (lang or "fr").startswith("de") else "fr"]
    brand = escape(EMAIL_FROM_NAME)
    n = str(order_number)
    subject = t["subject"].format(n=n)
    html = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:24px;font-family:Arial,Helvetica,sans-serif;color:#2B2521;font-size:15px;line-height:22px">'
        f'<p style="font-size:20px;font-weight:bold;margin:0 0 16px">{brand}</p>'
        f'<p>{escape(t["hi"].format(name=first_name or ""))}</p>'
        f'<p>{escape(t["body"].format(brand=EMAIL_FROM_NAME))}</p>'
        f'<p>{escape(t["ask"])}</p>'
        f'<p style="margin:24px 0"><a href="{escape(link)}" style="background:#C8332B;color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:bold;display:inline-block">{escape(t["cta"])}</a></p>'
        f'<p style="font-size:12px;color:#888">{escape(t["foot"].format(brand=EMAIL_FROM_NAME, n=n))}</p>'
        '</td></tr></table>'
    )
    return subject, html


# ---- per-customer state: never ask again after a click, and pause 3 completed orders after an unanswered request ---
PAUSE_ORDERS = 3  # after a request that was NOT clicked, the next N completed orders get no e-mail


def customer_keys(order: dict) -> dict:
    """Identity of the customer behind an order: account id (logged-in) + e-mail + phone digits (guests)."""
    c = order.get("customer") or {}
    return {"user_id": order.get("user_id") or None,
            "email": (c.get("email") or "").strip().lower() or None,
            "phone": normalize_phone(c.get("phone") or "") or None}


def _state_query(keys: dict) -> Optional[dict]:
    ors = [{k: v} for k, v in keys.items() if v]
    return {"$or": ors} if ors else None


def _orders_query(keys: dict) -> Optional[dict]:
    """Same identity, expressed on order documents (e-mail case-insensitive, phone by digits like Clients search)."""
    ors = []
    if keys["user_id"]:
        ors.append({"user_id": keys["user_id"]})
    if keys["email"]:
        ors.append({"customer.email": {"$regex": f"^{re.escape(keys['email'])}$", "$options": "i"}})
    if keys["phone"]:
        ors.append({"customer.phone": {"$regex": r"\D*".join(keys["phone"]) + r"\D*$"}})
    return {"$or": ors} if ors else None


async def review_decision(db, order: dict) -> str:
    """'send' | 'skipped_clicked' (customer already clicked a review link – never again)
    | 'skipped_recent' (asked recently and fewer than PAUSE_ORDERS orders completed since)."""
    keys = customer_keys(order)
    sq = _state_query(keys)
    if not sq:
        return "send"
    states = await db.review_customers.find(sq).to_list(20)
    if any(s.get("clicked_at") for s in states):
        return "skipped_clicked"
    asked = [s["asked_at"] for s in states if s.get("asked_at")]
    if not asked:
        return "send"
    since = max(asked)
    # orders of this person completed AFTER the last request and BEFORE this one (processing order independent)
    q = {**_orders_query(keys), "status": "completed", "completed_at": {"$gt": since, "$lt": order["completed_at"]}, "_id": {"$ne": order["_id"]}}
    completed_since = await db.orders.count_documents(q)
    return "send" if completed_since >= PAUSE_ORDERS else "skipped_recent"


async def remember_customer(db, order: dict, field: str, when) -> None:
    """Upsert the customer's review state (one document per customer; account id, e-mail and phone are all kept
    so a guest order and a later account login resolve to the same person)."""
    keys = customer_keys(order)
    sq = _state_query(keys)
    if not sq:
        return
    existing = await db.review_customers.find_one(sq)
    sets = {k: v for k, v in keys.items() if v}
    sets[field] = when
    if field == "asked_at":
        sets["asked_order_id"] = str(order["_id"])
    if existing:
        await db.review_customers.update_one({"_id": existing["_id"]}, {"$set": sets})
    else:
        await db.review_customers.insert_one(sets)


async def backfill_review_customers(db) -> int:
    """One-time (runs only while the collection is empty): derive the per-customer state from what already happened –
    orders whose review e-mail was sent (asked_at) and orders whose link was clicked (clicked_at) – so customers who
    clicked before this rule existed are never asked again. Returns the number of orders processed."""
    if await db.review_customers.estimated_document_count() > 0:
        return 0
    n = 0
    async for o in db.orders.find({"review_status": "sent", "review_sent_at": {"$exists": True}}).sort("review_sent_at", 1):
        await remember_customer(db, o, "asked_at", o["review_sent_at"])
        n += 1
    async for o in db.orders.find({"review_clicked_at": {"$exists": True}}):
        await remember_customer(db, o, "clicked_at", o["review_clicked_at"])
        n += 1
    if n:
        logger.info("Review state backfilled from %d orders", n)
    return n


# ---- background loop --------------------------------------------------------------------------------------------
async def process_due_reviews(db, settings, now) -> int:
    """One pass: claim + send for every eligible completed order. Returns the number of e-mails sent."""
    if not settings.review_enabled or not settings.google_review_url or not settings.public_url or not EMAIL_KEY:
        return 0
    if not settings.public_url.startswith("https://"):
        return 0
    due = now - timedelta(minutes=max(0, int(settings.review_delay_minutes or 0)))
    q = {"status": "completed", "completed_at": {"$lte": due}, "review_status": {"$exists": False},
         "customer.email": {"$type": "string", "$ne": ""}}
    if not EMAIL_DRY_RUN and not settings.reviews_live_since:
        return 0  # real mode without a go-live moment (set at startup) – never mail historical orders
    cutoffs = [c.replace(tzinfo=None) for c in (settings.printing_enabled_at, settings.reviews_live_since) if c]  # Mongo datetimes are naive UTC
    if cutoffs:
        q["created_at"] = {"$gte": max(cutoffs)}  # never mail customers of development/test/historical orders
    sent = 0
    async for o in db.orders.find(q).sort("completed_at", 1).limit(20):
        # Atomic claim: whichever worker flips review_status first owns the send – no duplicates, ever
        claimed = await db.orders.find_one_and_update({"_id": o["_id"], "review_status": {"$exists": False}},
                                                      {"$set": {"review_status": "sending"}}, return_document=ReturnDocument.AFTER)
        if not claimed:
            continue
        try:
            decision = await review_decision(db, o)
            if decision != "send":
                await db.orders.update_one({"_id": o["_id"]}, {"$set": {"review_status": decision, "review_decided_at": now}})
                continue
            link = f"{settings.public_url.rstrip('/')}/api/review/{o['_id']}/go"
            subject, html = build_review_email(o.get("language", "fr"), o["customer"].get("first_name", ""), o["order_number"], link)
            email_id = await send_email(to=o["customer"]["email"], subject=subject, html=html)
            await db.orders.update_one({"_id": o["_id"]}, {"$set": {"review_status": "sent", "review_sent_at": now, "review_email_id": email_id}})
            await remember_customer(db, o, "asked_at", now)
            sent += 1
        except Exception as e:  # isolated: the order/payment flow is never affected
            logger.error("Review e-mail failed for order #%s: %s", o.get("order_number"), e)
            await db.orders.update_one({"_id": o["_id"]}, {"$set": {"review_status": "failed", "review_error": str(e)[:300]}})
    return sent


async def review_loop(db, get_settings, now_utc):
    await asyncio.sleep(20)
    while True:
        try:
            await process_due_reviews(db, await get_settings(), now_utc())
        except Exception as e:
            logger.error("review loop error: %s", e)
        await asyncio.sleep(60)

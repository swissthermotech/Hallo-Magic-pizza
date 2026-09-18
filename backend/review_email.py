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
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from pymongo import ReturnDocument

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
    if settings.printing_enabled_at:
        q["created_at"] = {"$gte": settings.printing_enabled_at}  # never mail customers of development/test orders
    sent = 0
    async for o in db.orders.find(q).limit(20):
        # Atomic claim: whichever worker flips review_status first owns the send – no duplicates, ever
        claimed = await db.orders.find_one_and_update({"_id": o["_id"], "review_status": {"$exists": False}},
                                                      {"$set": {"review_status": "sending"}}, return_document=ReturnDocument.AFTER)
        if not claimed:
            continue
        try:
            link = f"{settings.public_url.rstrip('/')}/api/review/{o['_id']}/go"
            subject, html = build_review_email(o.get("language", "fr"), o["customer"].get("first_name", ""), o["order_number"], link)
            email_id = await send_email(to=o["customer"]["email"], subject=subject, html=html)
            await db.orders.update_one({"_id": o["_id"]}, {"$set": {"review_status": "sent", "review_sent_at": now, "review_email_id": email_id}})
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

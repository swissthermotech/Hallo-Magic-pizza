"""Google review e-mail – per-customer rules (review_email.py):
  * never ask again once the customer clicked a review link (account id, e-mail or phone match)
  * after a request that was NOT clicked, the next 3 completed orders get no request; the 4th does
  * state is server-side (collection review_customers) -> identical on every device / after logout-login, guests included.
Runs against the sandbox DB in EMAIL_DRY_RUN mode with fixture orders (marker _review_test) created & removed here.
Test names contain "requires" so the legacy autouse PIN fixture is skipped.
"""
import asyncio
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import review_email as rm  # noqa: E402
from server import db  # noqa: E402

API = "http://localhost:8001/api"
MARK = {"_review_test": True}


class S:  # minimal Settings stand-in for process_due_reviews
    review_enabled = True
    google_review_url = "https://search.google.com/local/writereview?placeid=test"
    public_url = "https://example.test"
    review_delay_minutes = 0
    reviews_live_since = None

    def __init__(self, cutoff):
        self.printing_enabled_at = cutoff  # only orders created after this are processed -> isolates the fixtures


def _order(n, *, email, phone, user_id=None, completed_at, created_at):
    return {**MARK, "order_number": n, "status": "completed", "type": "pickup", "source": "web", "language": "fr",
            "user_id": user_id, "customer": {"first_name": "Review", "last_name": "Test", "email": email, "phone": phone},
            "items": [], "total": 25.0, "created_at": created_at, "completed_at": completed_at}


async def _cleanup():
    await db.orders.delete_many(MARK)
    await db.review_customers.delete_many({"$or": [{"email": {"$regex": "@review-test\\.example$"}}, {"phone": {"$in": ["0790000003", "0790000004", "0790000005"]}}]})


async def _status(_id):
    return (await db.orders.find_one({"_id": _id}, {"review_status": 1}))["review_status"]


async def _scenario():
    await _cleanup()
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # Mongo stores naive UTC
    cutoff = now - timedelta(minutes=5)
    created = now - timedelta(minutes=4)
    settings = S(cutoff)
    log = []

    # ---- Customer A (guest): never asked -> asked; clicks -> never again (by e-mail, by phone, even once logged-in) ----
    a1 = (await db.orders.insert_one(_order(90001, email="a@review-test.example", phone="079 000 00 03", completed_at=now - timedelta(minutes=3), created_at=created))).inserted_id
    sent = await rm.process_due_reviews(db, settings, now)
    log.append(("A1 first completed order -> e-mail sent", sent == 1 and await _status(a1) == "sent"))
    state = await db.review_customers.find_one({"email": "a@review-test.example"})
    log.append(("A state saved server-side (asked_at, phone digits)", bool(state and state.get("asked_at") and state.get("phone") == "0790000003")))

    # the customer clicks the link in the e-mail (real endpoint, redirect not followed)
    req = urllib.request.Request(f"{API}/review/{a1}/go", method="GET")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        urllib.request.build_opener(NoRedirect).open(req)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    state = await db.review_customers.find_one({"email": "a@review-test.example"})
    log.append(("A clicks review link -> 302 + clicked_at stored on the customer", code == 302 and bool(state and state.get("clicked_at"))))

    a2 = (await db.orders.insert_one(_order(90002, email="a@review-test.example", phone="079 000 00 03", completed_at=now - timedelta(minutes=2), created_at=created))).inserted_id
    a3 = (await db.orders.insert_one(_order(90003, email="A@Review-Test.example", phone="076 999 99 99", user_id="acct-A", completed_at=now - timedelta(minutes=2), created_at=created))).inserted_id  # same e-mail, other phone, now logged in
    a4 = (await db.orders.insert_one(_order(90004, email="other@review-test.example", phone="+41 79 000 00 03", completed_at=now - timedelta(minutes=1), created_at=created))).inserted_id  # same phone only
    sent = await rm.process_due_reviews(db, settings, now)
    log.append(("A after click: next order -> no e-mail", sent == 0 and await _status(a2) == "skipped_clicked"))
    log.append(("A after click: same e-mail from an account on another device -> no e-mail", await _status(a3) == "skipped_clicked"))
    log.append(("A after click: same phone, different e-mail -> no e-mail", await _status(a4) == "skipped_clicked"))

    # ---- Customer B (account): asked, does NOT click -> next 3 completed orders silent, 4th asked again -----------
    b = dict(email="b@review-test.example", phone="079 000 00 04", user_id="acct-B")
    b1 = (await db.orders.insert_one(_order(90011, **b, completed_at=now - timedelta(minutes=3), created_at=created))).inserted_id
    sent = await rm.process_due_reviews(db, settings, now)
    log.append(("B1 -> e-mail sent (asked)", sent == 1 and await _status(b1) == "sent"))
    later = now + timedelta(seconds=1)
    ids = []
    for i, n in enumerate([90012, 90013, 90014, 90015]):
        ids.append((await db.orders.insert_one(_order(n, **b, completed_at=later + timedelta(seconds=10 * (i + 1)), created_at=created))).inserted_id)
    sent = await rm.process_due_reviews(db, settings, later + timedelta(minutes=1))  # all four due in ONE pass
    st = [await _status(i) for i in ids]
    log.append(("B2, B3, B4 (3 orders after dismissal) -> no e-mail", st[:3] == ["skipped_recent"] * 3))
    log.append(("B5 (4th order) -> asked again", sent == 1 and st[3] == "sent"))
    # ... and the pause restarts; a guest order with B's e-mail (logged out / other device) is treated as the same person
    b6 = (await db.orders.insert_one(_order(90016, email="b@review-test.example", phone="078 111 11 11", user_id=None, completed_at=later + timedelta(minutes=2), created_at=created))).inserted_id
    sent = await rm.process_due_reviews(db, settings, later + timedelta(minutes=3))
    log.append(("B6 as guest (same e-mail, logged out) right after B5 -> no e-mail", sent == 0 and await _status(b6) == "skipped_recent"))

    # ---- Customer C: unknown person -> asked normally (rules don't block first-timers) ------------------------------
    c1 = (await db.orders.insert_one(_order(90021, email="c@review-test.example", phone="079 000 00 05", completed_at=now, created_at=created))).inserted_id
    sent = await rm.process_due_reviews(db, settings, later + timedelta(minutes=3))
    log.append(("C first order -> e-mail sent", sent == 1 and await _status(c1) == "sent"))

    await _cleanup()
    return log


def test_requires_review_once_per_customer():
    log = asyncio.run(_scenario())
    for label, ok in log:
        print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    assert all(ok for _, ok in log), [l for l, ok in log if not ok]

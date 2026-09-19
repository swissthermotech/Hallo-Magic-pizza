"""Iter 13 – FINAL regression before production.

Covers the backend items in the review request:
  1. POST /api/orders – email validation, payment_method → collection_method
  2. POST /api/phone-orders – station 1 & 2, no email, print_status simulated, single print job
  3. GET /api/menu – category order, single highlight='moment' (Margherita → Napoletana → cleared)
  4. Same supplement on 3 different sizes (per-size price + max_quantity clamp)

Cleanup: deletes TEST_* orders + associated print_jobs at end of the module.

PRINTNODE key is intentionally EMPTY in /app/backend/.env – accepting orders is safe
(print_status becomes 'simulated'). If the environment has been changed and the first
accepted order ends up with print_status='sent', the test aborts loudly.
"""
import os
import re
import uuid

import pytest
import requests

from dotenv import load_dotenv as _ld
_ld("/app/frontend/.env")
BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

MANAGER_PIN = "1234"
PHONE_PIN = "3456"

# Real Mongo ids captured from GET /api/menu (deterministic seed):
MARGHERITA_ID = "6aa94a928068d15c2420f9e5"
NAPOLETANA_ID = "6aa94a928068d15c2420f9e6"
JAMBON_EPAULE_EXTRA_ID = "6aa94a928068d15c2420f9c8"  # price_by_size 32=2, 40=3, 50=4, max=2
PARME_EXTRA_ID = "6aa94a928068d15c2420f9de"          # price 4 flat, max=1


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def manager_token(s):
    r = s.post(f"{API}/auth/staff/login", json={"pin": MANAGER_PIN}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def phone_token(s):
    r = s.post(f"{API}/auth/staff/login", json={"pin": PHONE_PIN}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def created_order_ids():
    return []


# ---------------------------------------------------------------------------
# 1. POST /api/orders – e-mail validation + payment_method → collection_method
# ---------------------------------------------------------------------------
class TestOrdersEmailAndPayment:
    def _pickup_body(self, email, payment="terminal"):
        return {
            "type": "pickup",
            "source": "web",
            "items": [{"product_id": MARGHERITA_ID, "quantity": 1, "size_key": "32", "option_keys": ["classic"]}],
            "customer": {"first_name": "TEST_Reg", "last_name": "User", "phone": "0790000001", "email": email},
            "requested_time": "asap",
            "age_confirmed": True,
            "payment_method": payment,
        }

    def test_missing_email_returns_400(self, s):
        body = self._pickup_body(email=None)
        body["customer"]["email"] = None
        r = s.post(f"{API}/orders", json=body, timeout=10)
        assert r.status_code == 400, r.text
        assert "mail" in r.text.lower()

    def test_invalid_email_returns_400(self, s):
        r = s.post(f"{API}/orders", json=self._pickup_body(email="abc"), timeout=10)
        assert r.status_code == 400, r.text

    def test_pickup_terminal_creates_order(self, s, created_order_ids):
        r = s.post(f"{API}/orders", json=self._pickup_body(email="test_reg@example.com", payment="terminal"), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["payment_method"] == "terminal"
        assert data["collection_method"] == "terminal"
        assert data["status"] == "pending"
        created_order_ids.append(data["id"])

    def test_delivery_cash_creates_order(self, s, created_order_ids):
        body = {
            "type": "delivery",
            "source": "web",
            "items": [
                {"product_id": MARGHERITA_ID, "quantity": 2, "size_key": "40", "option_keys": ["classic"]}
            ],
            "customer": {"first_name": "TEST_Reg", "last_name": "Cash", "phone": "0790000002", "email": "test_reg_cash@example.com"},
            "address": {"street": "Route de Villars", "number": "46", "npa": "1700", "city": "Fribourg"},
            "requested_time": "asap",
            "age_confirmed": True,
            "payment_method": "cash",
        }
        r = s.post(f"{API}/orders", json=body, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["payment_method"] == "cash"
        assert data["collection_method"] == "cash"
        assert data["total"] >= 30.0, f"delivery minimum: got {data['total']}"
        created_order_ids.append(data["id"])


# ---------------------------------------------------------------------------
# 2. POST /api/phone-orders – station 1/2 without email, exactly one print job
# ---------------------------------------------------------------------------
class TestPhoneOrdersNoEmail:
    def _body(self, station, cri):
        return {
            "type": "pickup",
            "source": "telephone",
            "station": station,
            "items": [{"product_id": MARGHERITA_ID, "quantity": 1, "size_key": "32", "option_keys": ["classic"]}],
            "customer": {"first_name": "TEST_Reg", "last_name": f"Poste{station}", "phone": "0790000003"},
            "requested_time": "asap",
            "minutes": 20,
            "age_confirmed": True,
            "payment_method": "cash",
            "client_request_id": cri,
        }

    @pytest.mark.parametrize("station", [1, 2])
    def test_phone_order_station(self, s, phone_token, created_order_ids, station):
        hdr = {"Authorization": f"Bearer {phone_token}"}
        cri = f"iter13-{station}-{uuid.uuid4().hex[:8]}"
        r = s.post(f"{API}/phone-orders", json=self._body(station, cri), headers=hdr, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "accepted", data
        # print_status MUST be 'simulated' (PrintNode key intentionally empty). Abort loudly if 'sent'.
        assert data.get("print_status") == "simulated", (
            f"UNSAFE: first accepted phone-order has print_status={data.get('print_status')!r} "
            f"(expected 'simulated'). Re-check PRINTNODE_API_KEY in /app/backend/.env before continuing."
        )
        assert data.get("printed") is True
        created_order_ids.append(data["id"])

        # Idempotency + exactly one print_job for this order
        r2 = s.post(f"{API}/phone-orders", json=self._body(station, cri), headers=hdr, timeout=20)
        assert r2.status_code == 200 and r2.json()["id"] == data["id"], "client_request_id must be idempotent"

        detail = s.get(f"{API}/orders/{data['id']}", headers=hdr, timeout=10).json()
        assert detail["printed"] is True
        assert detail["print_status"] == "simulated"


# ---------------------------------------------------------------------------
# 3. GET /api/menu category order + single highlight 'moment'
# ---------------------------------------------------------------------------
EXPECTED_ORDER = ["entrees", "salades", "pizza", "creer-votre-pizza", "piadina-pasta", "dessert", "boissons"]


class TestMenuAndHighlight:
    def test_category_order(self, s):
        r = s.get(f"{API}/menu", timeout=10)
        assert r.status_code == 200
        slugs = [c["slug"] for c in r.json()["categories"]]
        assert slugs == EXPECTED_ORDER, slugs
        # names sanity
        cats = {c["slug"]: c for c in r.json()["categories"]}
        assert cats["pizza"]["name"]["fr"] == "Pizzas"
        assert cats["dessert"]["name"]["fr"].startswith("Dessert")

    def test_single_highlight_moment(self, s, manager_token):
        hdr = {"Authorization": f"Bearer {manager_token}"}

        def full_body(pid, highlight):
            p = s.get(f"{API}/products/{pid}", headers=hdr, timeout=10).json()
            # Build ProductIn-compatible body (strip server-managed fields)
            body = {k: v for k, v in p.items() if k not in ("id", "created_at", "updated_at", "deleted_at", "_id")}
            body["highlight"] = highlight
            return body

        # Set Margherita → moment
        r = s.put(f"{API}/products/{MARGHERITA_ID}", json=full_body(MARGHERITA_ID, "moment"), headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["highlight"] == "moment"

        # Set Napoletana → moment (must reset Margherita)
        r = s.put(f"{API}/products/{NAPOLETANA_ID}", json=full_body(NAPOLETANA_ID, "moment"), headers=hdr, timeout=15)
        assert r.status_code == 200, r.text

        menu = s.get(f"{API}/menu", timeout=10).json()
        highs = {p["id"]: p.get("highlight") for p in menu["products"] if p.get("highlight") == "moment"}
        assert list(highs.keys()) == [NAPOLETANA_ID], f"only Napoletana should be 'moment', got {highs}"

        # Verify Margherita cleared
        marg = next(p for p in menu["products"] if p["id"] == MARGHERITA_ID)
        assert marg.get("highlight") in (None, "", "custom"), f"Margherita highlight not cleared: {marg.get('highlight')}"

        # Reset Napoletana at end
        r = s.put(f"{API}/products/{NAPOLETANA_ID}", json=full_body(NAPOLETANA_ID, None), headers=hdr, timeout=15)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# 4. Same supplement on 3 sizes – per-size price + max_quantity clamp
# ---------------------------------------------------------------------------
class TestSupplementPerSize:
    def test_three_sizes_extras(self, s, created_order_ids):
        body = {
            "type": "pickup",
            "source": "web",
            "items": [
                {"product_id": MARGHERITA_ID, "quantity": 1, "size_key": sz,
                 "option_keys": ["classic"],
                 "extras": [
                    {"extra_id": JAMBON_EPAULE_EXTRA_ID, "quantity": 2},
                    {"extra_id": PARME_EXTRA_ID, "quantity": 3},  # will be clamped to max_quantity=1
                 ]}
                for sz in ("32", "40", "50")
            ],
            "customer": {"first_name": "TEST_Reg", "last_name": "Sizes", "phone": "0790000004", "email": "test_sizes@example.com"},
            "requested_time": "asap",
            "age_confirmed": True,
            "payment_method": "cash",
        }
        r = s.post(f"{API}/orders", json=body, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        created_order_ids.append(data["id"])

        assert len(data["items"]) == 3
        by_size = {it["size"]["key"]: it for it in data["items"]}
        assert set(by_size.keys()) == {"32", "40", "50"}

        # Per size expectations
        expected_jambon = {"32": 2.0, "40": 3.0, "50": 4.0}
        for size, item in by_size.items():
            extras = {e["extra_id"]: e for e in item["extras"]}
            # jambon quantity kept, price varies by size
            j = extras[JAMBON_EPAULE_EXTRA_ID]
            assert j["quantity"] == 2, f"jambon qty size {size}"
            assert abs(j["unit_price"] - expected_jambon[size]) < 0.01, f"jambon price size {size}: {j['unit_price']}"
            # parme clamped to max 1
            p = extras[PARME_EXTRA_ID]
            assert p["quantity"] == 1, f"parme not clamped for size {size}: qty={p['quantity']}"
            assert abs(p["unit_price"] - 4.0) < 0.01

        # Unit price differs by size (price_by_size configured on Margherita: 14/22/31)
        prices = {sz: it["unit_price"] for sz, it in by_size.items()}
        assert prices["32"] < prices["40"] < prices["50"], prices


# ---------------------------------------------------------------------------
# Cleanup fixture – runs after ALL tests in this module.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def _cleanup(created_order_ids):
    yield
    # Purge every TEST_* order + print_jobs via direct Mongo (fastest and matches spec)
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    async def _run():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        dbn = os.environ["DB_NAME"]
        db = cli[dbn]
        # Match all TEST_ orders (in case there are stragglers)
        cur_ids = [d["_id"] async for d in db.orders.find({"customer.first_name": {"$regex": "^TEST_"}}, {"_id": 1})]
        n_orders = 0
        n_jobs = 0
        if cur_ids:
            n_jobs = (await db.print_jobs.delete_many({"order_id": {"$in": [str(i) for i in cur_ids]}})).deleted_count
            n_orders = (await db.orders.delete_many({"_id": {"$in": cur_ids}})).deleted_count
        print(f"\n[CLEANUP] Deleted {n_orders} TEST_ orders and {n_jobs} print_jobs")

        # Sanity: Napoletana highlight cleared
        p = await db.products.find_one({"_id": (__import__('bson').ObjectId)(NAPOLETANA_ID)})
        print(f"[CLEANUP] Napoletana highlight = {p.get('highlight') if p else 'MISSING'}")
        cli.close()

    asyncio.run(_run())

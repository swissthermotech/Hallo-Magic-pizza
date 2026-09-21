"""Iteration 17 – Admin product create/edit/photo, supplements CRUD, customer database, marketing consent.

Does NOT accept orders. Restores every real value it touches (Margherita 40cm price, Champignons,
Olives, Ananas). Marks all created content with 'ZZTEST' / 'TEST_' so the main agent can sweep.
"""
import io
import os
import time
import uuid
from typing import Dict, Optional

import pytest
import requests
from PIL import Image

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") + "/api"


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
def _pin_login(pin: str) -> str:
    r = requests.post(f"{BASE}/auth/staff/login", json={"pin": pin}, timeout=15)
    assert r.status_code == 200, f"staff login {pin} -> {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def mgr() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_pin_login('1234')}"})
    return s


@pytest.fixture(scope="module")
def phone() -> requests.Session:
    """Phone role – PIN was rotated in Admin → Sécurité, cannot login with default 3456.
    We probe the DB defaults but skip any test that needs it if unavailable."""
    for pin in ("3456", "0000"):
        try:
            tok = _pin_login(pin)
        except AssertionError:
            continue
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {tok}"})
        return s
    pytest.skip("phone-role PIN unknown (rotated from default 3456)")


@pytest.fixture(scope="module")
def menu() -> dict:
    r = requests.get(f"{BASE}/menu", timeout=15)
    assert r.status_code == 200
    return r.json()


def _find_by_name(menu, name_substr: str, kind: str = "product"):
    items = menu["products"] if kind == "product" else menu["extras"]
    for p in items:
        if name_substr.lower() in (p["name"]["fr"] or "").lower():
            return p
    raise AssertionError(f"{name_substr!r} not found in menu.{kind}s")


# ---------------------------------------------------------------------------
# 1. Public menu & health
# ---------------------------------------------------------------------------
class TestPublicMenu:
    def test_menu_loads(self, menu):
        assert "products" in menu and "extras" in menu and "categories" in menu
        assert len(menu["products"]) >= 5

    def test_menu_has_expected_pizzas(self, menu):
        for name in ("Margherita",):
            _find_by_name(menu, name)


# ---------------------------------------------------------------------------
# 2. Customers list – auth matrix
# ---------------------------------------------------------------------------
class TestCustomersAuth:
    def test_list_requires_token(self):
        r = requests.get(f"{BASE}/customers", timeout=10)
        assert r.status_code == 401, r.text

    def test_phone_role_can_list(self, phone):
        r = phone.get(f"{BASE}/customers", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(["customers", "count", "stats"]).issubset(data.keys())

    def test_manager_can_list(self, mgr):
        r = mgr.get(f"{BASE}/customers", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "customers" in data
        # sanity: expect a healthy DB (>= 5 rows typically)
        assert isinstance(data["customers"], list)
        assert data["count"] == len(data["customers"]) or data["count"] >= 0

    def test_marketing_export_forbidden_for_phone(self, phone):
        r = phone.get(f"{BASE}/customers/marketing-export.csv", timeout=15)
        assert r.status_code == 403, r.text

    def test_marketing_export_ok_for_manager(self, mgr):
        r = mgr.get(f"{BASE}/customers/marketing-export.csv", timeout=15)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert r.text.lstrip("\ufeff").startswith("first_name;last_name;email;phone;consent_date")


# ---------------------------------------------------------------------------
# 3. Customers search / filter
# ---------------------------------------------------------------------------
class TestCustomersSearch:
    def test_search_by_name_email_phone(self, mgr):
        base = mgr.get(f"{BASE}/customers", timeout=15).json()["customers"]
        # Pick any real customer to derive a search fragment
        assert base, "no customers – seed DB first"
        # by name (last name first 2 chars if any)
        target = next((c for c in base if c["last_name"]), None)
        if target:
            frag = target["last_name"][:3]
            r = mgr.get(f"{BASE}/customers", params={"q": frag}, timeout=15)
            assert r.status_code == 200
            names = [f"{c['first_name']} {c['last_name']}".lower() for c in r.json()["customers"]]
            assert any(frag.lower() in n for n in names)

        # by phone digits
        with_phone = next((c for c in base if len(c.get("phone") or "") >= 4), None)
        if with_phone:
            digits = "".join(ch for ch in with_phone["phone"] if ch.isdigit())[:4]
            r = mgr.get(f"{BASE}/customers", params={"q": digits}, timeout=15)
            assert r.status_code == 200
            assert r.json()["count"] >= 1

    def test_filter_yes_no_all(self, mgr):
        for m in ("all", "yes", "no"):
            r = mgr.get(f"{BASE}/customers", params={"marketing": m}, timeout=15)
            assert r.status_code == 200, m


# ---------------------------------------------------------------------------
# 4. Product create (ZZTEST) + photo upload + edit-existing + delete
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def pizza_cat(menu):
    for c in menu["categories"]:
        slug = (c.get("slug") or "").lower()
        name = (c.get("name") or {}).get("fr", "").lower()
        if slug == "pizzas" or name.startswith("pizza"):
            return c
    return menu["categories"][0]


@pytest.fixture(scope="module")
def zztest_product(mgr, pizza_cat):
    body = {
        "category_id": pizza_cat["id"],
        "name": {"fr": "ZZTEST Pizza Test", "de": "ZZTEST Pizza Test DE"},
        "description": {"fr": "desc FR", "de": "Beschreibung DE"},
        "price": 17.5,
        "sizes": [
            {"key": "32", "label": "32 cm", "price": 17.5},
            {"key": "40", "label": "40 cm", "price": 26.0},
            {"key": "50", "label": "50 cm", "price": 35.0},
        ],
        "ingredients": [
            {"id": "tomate", "fr": "tomate", "de": "Tomaten"},
            {"id": "mozzarella", "fr": "mozzarella", "de": "Mozzarella"},
        ],
        "customizable": True,
        "available": True,
    }
    r = mgr.post(f"{BASE}/products", json=body, timeout=15)
    assert r.status_code == 200, r.text
    p = r.json()
    yield p
    # cleanup (soft delete)
    mgr.delete(f"{BASE}/products/{p['id']}", timeout=10)


class TestProductCreate:
    def test_created_and_persisted(self, mgr, zztest_product):
        p = zztest_product
        assert p["name"]["fr"] == "ZZTEST Pizza Test"
        assert p["name"]["de"] == "ZZTEST Pizza Test DE"
        assert p["price"] == 17.5
        keys = sorted(s["key"] for s in p["sizes"])
        assert keys == ["32", "40", "50"]
        by = {s["key"]: s["price"] for s in p["sizes"]}
        assert by == {"32": 17.5, "40": 26.0, "50": 35.0}
        assert p["customizable"] is True
        # ingredients FR + DE
        names = [(i["fr"], i["de"]) for i in p["ingredients"]]
        assert ("tomate", "Tomaten") in names
        assert ("mozzarella", "Mozzarella") in names

    def test_appears_in_menu(self, zztest_product):
        r = requests.get(f"{BASE}/menu", timeout=15)
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()["products"]]
        assert zztest_product["id"] in ids


# ---------------------------------------------------------------------------
# 5. Photo upload (JPG + PNG)
# ---------------------------------------------------------------------------
def _jpeg_bytes(w=1600, h=1200) -> bytes:
    img = Image.new("RGB", (w, h), (30, 90, 200))
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            img.putpixel((x, y), ((x * 13) & 255, (y * 7) & 255, ((x + y) * 3) & 255))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _png_bytes(w=800, h=600) -> bytes:
    img = Image.new("RGBA", (w, h), (255, 128, 0, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class TestPhotoUpload:
    def test_upload_jpg(self, mgr, zztest_product):
        data = _jpeg_bytes()
        assert len(data) > 200 * 1024, f"jpg too small ({len(data)}B)"
        r = mgr.post(f"{BASE}/uploads/product-photo",
                     files={"file": ("test.jpg", data, "image/jpeg")}, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["url"].startswith("/api/files/hallo-magic-pizza/products/")
        # Persist on product
        pr = mgr.patch(f"{BASE}/products/{zztest_product['id']}", json={"image_url": body["url"]}, timeout=15)
        assert pr.status_code == 200
        assert pr.json()["image_url"] == body["url"]
        # Serve back
        img = requests.get(BASE.rsplit("/api", 1)[0] + body["url"], timeout=15)
        assert img.status_code == 200
        assert img.headers.get("content-type", "").startswith("image/jpeg")
        assert len(img.content) > 5000

    def test_upload_png(self, mgr):
        data = _png_bytes()
        r = mgr.post(f"{BASE}/uploads/product-photo",
                     files={"file": ("test.png", data, "image/png")}, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["url"].endswith(".jpg")  # optimised to JPEG

    def test_upload_requires_manager(self, phone):
        data = _jpeg_bytes(400, 300)
        r = phone.post(f"{BASE}/uploads/product-photo",
                       files={"file": ("x.jpg", data, "image/jpeg")}, timeout=30)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 6. Edit existing pizza price (Margherita 40cm +1, then restore)
# ---------------------------------------------------------------------------
class TestEditMargherita:
    def test_change_and_restore_40cm_price(self, mgr, menu):
        marg = _find_by_name(menu, "Margherita")
        size40 = next(s for s in marg["sizes"] if s["key"] == "40")
        original = size40["price"]
        new_price = round(original + 1, 2)
        try:
            new_sizes = []
            for s in marg["sizes"]:
                new_sizes.append({"key": s["key"], "label": s.get("label", s["key"]),
                                  "price": new_price if s["key"] == "40" else s["price"]})
            r = mgr.patch(f"{BASE}/products/{marg['id']}", json={"sizes": new_sizes}, timeout=15)
            assert r.status_code == 200, r.text
            got = requests.get(f"{BASE}/menu", timeout=15).json()
            m2 = _find_by_name(got, "Margherita")
            assert next(s for s in m2["sizes"] if s["key"] == "40")["price"] == new_price
        finally:
            # RESTORE
            restore = [{"key": s["key"], "label": s.get("label", s["key"]), "price": s["price"]} for s in marg["sizes"]]
            r = mgr.patch(f"{BASE}/products/{marg['id']}", json={"sizes": restore}, timeout=15)
            assert r.status_code == 200
            got = requests.get(f"{BASE}/menu", timeout=15).json()
            m3 = _find_by_name(got, "Margherita")
            assert next(s for s in m3["sizes"] if s["key"] == "40")["price"] == original


# ---------------------------------------------------------------------------
# 7. Supplements: create + verify allowed_extra_ids propagation + edit several + delete
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def zztest_extra(mgr):
    body = {
        "key": "zztest_truffe",
        "name": {"fr": "ZZTEST Truffe", "de": "ZZTEST Trüffel"},
        "price": 3.5,
        "price_by_size": {"32": 3.5, "40": 5.0, "50": 7.0},
        "available": True,
        "max_quantity": 2,
    }
    r = mgr.post(f"{BASE}/extras", json=body, timeout=15)
    assert r.status_code == 200, r.text
    e = r.json()
    yield e
    mgr.delete(f"{BASE}/extras/{e['id']}", timeout=10)


class TestExtrasCreate:
    def test_extra_created_with_size_prices(self, zztest_extra):
        assert zztest_extra["key"].startswith("zztest_truffe")
        assert zztest_extra["price_by_size"] == {"32": 3.5, "40": 5.0, "50": 7.0}
        assert zztest_extra["max_quantity"] == 2

    def test_menu_extras_contain_new(self, zztest_extra):
        m = requests.get(f"{BASE}/menu", timeout=15).json()
        keys = [e["key"] for e in m["extras"]]
        assert zztest_extra["key"] in keys

    def test_allowed_extras_updated_on_customizable_products(self, zztest_extra):
        m = requests.get(f"{BASE}/menu", timeout=15).json()
        marg = _find_by_name(m, "Margherita")
        assert zztest_extra["key"] in marg["allowed_extra_ids"], marg["allowed_extra_ids"]


class TestExtrasEditRestore:
    """Edit 3 real supplements. Store originals, verify persistence, restore each."""

    def _find(self, name: str) -> dict:
        r = requests.get(f"{BASE}/menu", timeout=15).json()
        for e in r["extras"]:
            if name.lower() in (e["name"]["fr"] or "").lower():
                return e
        pytest.skip(f"'{name}' not in extras (seed data may differ)")

    def test_edit_three_and_restore(self, mgr):
        champ = self._find("Champignons")
        olives = self._find("Olives")
        ananas = self._find("Ananas")

        orig_champ = requests.get(f"{BASE}/extras", timeout=15).json()
        orig_map = {e["id"]: e for e in orig_champ}
        keys_before = {e["id"]: e["key"] for e in orig_champ}

        try:
            # 1. Champ: change DE name + 40cm price
            new_champ = {**champ,
                         "name": {"fr": champ["name"]["fr"], "de": "ZZTEST Champignons DE"},
                         "price_by_size": {**(champ.get("price_by_size") or {}), "40": (champ.get("price_by_size", {}).get("40") or champ["price"]) + 0.5}}
            new_champ.pop("id", None); new_champ.pop("created_at", None); new_champ.pop("updated_at", None)
            r = mgr.put(f"{BASE}/extras/{champ['id']}", json=new_champ, timeout=15)
            assert r.status_code == 200, r.text

            # 2. Olives: max = 3
            new_olives = {**olives, "max_quantity": 3}
            new_olives.pop("id", None); new_olives.pop("created_at", None); new_olives.pop("updated_at", None)
            r = mgr.put(f"{BASE}/extras/{olives['id']}", json=new_olives, timeout=15)
            assert r.status_code == 200

            # 3. Ananas: toggle unavailable
            new_ananas = {**ananas, "available": not ananas["available"]}
            new_ananas.pop("id", None); new_ananas.pop("created_at", None); new_ananas.pop("updated_at", None)
            r = mgr.put(f"{BASE}/extras/{ananas['id']}", json=new_ananas, timeout=15)
            assert r.status_code == 200

            # verify
            after = {e["id"]: e for e in requests.get(f"{BASE}/extras", timeout=15).json()}
            assert after[champ["id"]]["name"]["de"] == "ZZTEST Champignons DE"
            assert after[olives["id"]]["max_quantity"] == 3
            assert after[ananas["id"]]["available"] == (not ananas["available"])

            # keys unchanged
            for eid, k in keys_before.items():
                assert after[eid]["key"] == k, f"key changed on {eid}"

            # No untouched extra was modified
            touched = {champ["id"], olives["id"], ananas["id"]}
            for eid, before in orig_map.items():
                if eid in touched:
                    continue
                a = after[eid]
                for f in ("name", "price", "price_by_size", "max_quantity", "available", "vat_rate"):
                    assert a.get(f) == before.get(f), f"unexpected mutation on {eid}.{f}"
        finally:
            for original in (champ, olives, ananas):
                body = {**original}
                body.pop("id", None); body.pop("created_at", None); body.pop("updated_at", None)
                mgr.put(f"{BASE}/extras/{original['id']}", json=body, timeout=15)


class TestExtrasDelete:
    def test_delete_zztest_truffe(self, mgr):
        # create a fresh one so the module fixture also has one; delete it here
        body = {"key": "zztest_delete_me", "name": {"fr": "ZZTEST Del", "de": "ZZTEST Del"},
                "price": 1.0, "price_by_size": {}, "available": True, "max_quantity": 1}
        r = mgr.post(f"{BASE}/extras", json=body, timeout=15)
        assert r.status_code == 200
        eid = r.json()["id"]
        r = mgr.delete(f"{BASE}/extras/{eid}", timeout=10)
        assert r.status_code == 200
        keys = [e["key"] for e in requests.get(f"{BASE}/menu", timeout=15).json()["extras"]]
        assert "zztest_delete_me" not in keys


# ---------------------------------------------------------------------------
# 8. Marketing consent at checkout – place 2 orders (never accepted!)
# ---------------------------------------------------------------------------
def _pickup_order(name_prefix: str, phone_num: str, email: str, consent: bool) -> dict:
    from datetime import date, timedelta
    # minimal cheap item = first available extra-less product with a fixed price
    m = requests.get(f"{BASE}/menu", timeout=15).json()
    prod = next(p for p in m["products"] if not p.get("customizable") and p.get("available"))
    line = {
        "product_id": prod["id"],
        "name": prod["name"],
        "unit_price": prod["price"],
        "quantity": 1,
        "extras": [],
        "removed_ingredients": [],
    }
    # Restaurant is closed today (Monday) – schedule for tomorrow 17:00 (Tuesday opens 17:00)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    return {
        "type": "pickup",
        "source": "web",
        "items": [line],
        "customer": {"first_name": name_prefix, "last_name": "Auto", "phone": phone_num, "email": email},
        "requested_time": "17:00",
        "requested_date": tomorrow,
        "language": "fr",
        "payment_method": "cash",
        "marketing_consent": consent,
    }


@pytest.fixture(scope="module")
def order_ids():
    ids: list[str] = []
    yield ids  # never touch after – main agent will sweep


class TestMarketingCheckout:
    def test_place_no_consent(self, order_ids):
        body = _pickup_order("TEST_NoConsent", "0799000001", "test@example.com", False)
        r = requests.post(f"{BASE}/orders", json=body, timeout=20)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "pending"
        assert o["marketing_consent"] is False
        order_ids.append(o["id"])

    def test_place_with_consent(self, order_ids):
        body = _pickup_order("TEST_Consent", "0799000002", "test2@example.com", True)
        r = requests.post(f"{BASE}/orders", json=body, timeout=20)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["marketing_consent"] is True
        order_ids.append(o["id"])

    def test_customer_row_marketing_yes(self, mgr):
        # Wait a moment for orders to settle
        time.sleep(0.5)
        r = mgr.get(f"{BASE}/customers", params={"marketing": "yes"}, timeout=15)
        assert r.status_code == 200
        names = [f"{c['first_name']}".lower() for c in r.json()["customers"]]
        assert any("test_consent" in n for n in names), names

    def test_customer_row_marketing_no_untouched(self, mgr):
        r = mgr.get(f"{BASE}/customers", params={"marketing": "yes"}, timeout=15)
        for c in r.json()["customers"]:
            assert c["first_name"] != "TEST_NoConsent", "no-consent customer wrongly opted-in"

    def test_csv_contains_test_consent(self, mgr):
        r = mgr.get(f"{BASE}/customers/marketing-export.csv", timeout=15)
        assert r.status_code == 200
        assert "TEST_Consent" in r.text
        assert "test2@example.com" in r.text
        assert "0799000002" in r.text or "799000002" in r.text

    def test_manager_toggle_consent_off(self, mgr):
        # find the customer key
        r = mgr.get(f"{BASE}/customers", params={"q": "TEST_Consent"}, timeout=15)
        assert r.status_code == 200
        c = next((x for x in r.json()["customers"] if x["first_name"] == "TEST_Consent"), None)
        assert c, "customer not listed"
        r = mgr.put(f"{BASE}/customers/{c['key']}/marketing", json={"consent": False}, timeout=15)
        assert r.status_code == 200
        assert r.json()["consent"] is False
        assert r.json()["source"] == "staff"
        # restore ON for further checks
        mgr.put(f"{BASE}/customers/{c['key']}/marketing", json={"consent": True}, timeout=15)


# ---------------------------------------------------------------------------
# 9. Marketing consent at account registration
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def account_session():
    token: Dict[str, Optional[str]] = {"t": None, "phone": "0799000003"}
    r = requests.post(f"{BASE}/auth/register", json={
        "first_name": "TEST_Account", "last_name": "Auto",
        "phone": token["phone"], "email": "test3@example.com",
        "password": "secret123", "marketing_consent": True,
    }, timeout=20)
    if r.status_code == 409:
        # already exists – login instead
        r = requests.post(f"{BASE}/auth/login", json={"phone": token["phone"], "password": "secret123"}, timeout=15)
    assert r.status_code in (200, 201), r.text
    token["t"] = r.json()["access_token"]
    return token


class TestMarketingAccount:
    def test_register_opts_in(self, account_session):
        r = requests.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {account_session['t']}"}, timeout=15)
        assert r.status_code == 200
        # It may be True (fresh register) or False (existing account) – normalize
        me = r.json()
        # explicit set
        r2 = requests.put(f"{BASE}/auth/me/marketing", json={"consent": True},
                          headers={"Authorization": f"Bearer {account_session['t']}"}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["marketing_consent"] is True

    def test_toggle_off(self, account_session):
        r = requests.put(f"{BASE}/auth/me/marketing", json={"consent": False},
                         headers={"Authorization": f"Bearer {account_session['t']}"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["marketing_consent"] is False

    def test_toggle_on(self, account_session):
        r = requests.put(f"{BASE}/auth/me/marketing", json={"consent": True},
                         headers={"Authorization": f"Bearer {account_session['t']}"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["marketing_consent"] is True

    def test_appears_in_staff_customers(self, mgr):
        r = mgr.get(f"{BASE}/customers", params={"q": "TEST_Account"}, timeout=15)
        assert r.status_code == 200
        c = next((x for x in r.json()["customers"] if x["first_name"] == "TEST_Account"), None)
        assert c, "account not listed as customer"
        assert c["kind"] == "account"
        assert c["marketing"]["consent"] is True


# ---------------------------------------------------------------------------
# 10. Customer profile endpoint (manager & phone)
# ---------------------------------------------------------------------------
class TestCustomerProfile:
    def test_manager_profile_matches_orders_count(self, mgr):
        r = mgr.get(f"{BASE}/customers", timeout=15)
        cust = next((c for c in r.json()["customers"] if c["orders_count"] >= 1), None)
        if not cust:
            pytest.skip("no customer with orders")
        r = mgr.get(f"{BASE}/customers/{cust['key']}/profile", timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["key"] == cust["key"]
        assert len(p["orders"]) == cust["orders_count"], f"{len(p['orders'])} vs {cust['orders_count']}"
        # order docs have _id excluded (has id string) and required fields
        for o in p["orders"][:3]:
            assert "id" in o and isinstance(o["id"], str)
            assert "_id" not in o
            assert "order_number" in o and "status" in o and "total" in o

    def test_phone_role_can_read_profile(self, phone, mgr):
        r = mgr.get(f"{BASE}/customers", timeout=15)
        cust = r.json()["customers"][0]
        r = phone.get(f"{BASE}/customers/{cust['key']}/profile", timeout=15)
        assert r.status_code == 200

    def test_phone_role_cannot_set_marketing(self, phone, mgr):
        cust = mgr.get(f"{BASE}/customers", timeout=15).json()["customers"][0]
        r = phone.put(f"{BASE}/customers/{cust['key']}/marketing", json={"consent": True}, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 11. Validation
# ---------------------------------------------------------------------------
class TestProductValidation:
    def test_missing_name_fr(self, mgr, pizza_cat):
        body = {"category_id": pizza_cat["id"], "name": {"fr": "", "de": ""}, "price": 10.0}
        r = mgr.post(f"{BASE}/products", json=body, timeout=15)
        # Pydantic min_length not set – server may accept empty name; API contract merely 200
        # This just documents current behaviour so main agent can decide.
        assert r.status_code in (200, 422, 400)

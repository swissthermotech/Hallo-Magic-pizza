"""Iteration 5 backend suite: customer accounts (auth), dynamic alcohol age (16/18+),
customer search, product photo upload/serving, order.user_id + saved address."""
import io
import os
import random
import string
import time

import pytest
import requests
from PIL import Image

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://hallo-magic-test.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

STATE: dict = {}


def _rand_phone() -> str:
    # keep 079 55X XX XX shape so /staff/customers can match a substring
    return "079 555 " + "".join(random.choices(string.digits, k=2)) + " " + "".join(random.choices(string.digits, k=2))


def _digits(v: str) -> str:
    return "".join(ch for ch in v if ch.isdigit())


# ------------------------------------------------------------------
# Menu bootstrap – get product ids we need
# ------------------------------------------------------------------
class TestBootstrap:
    def test_menu(self):
        r = requests.get(f"{API}/menu", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        STATE["products"] = d["products"]
        STATE["margherita"] = next(p for p in d["products"] if p["name"]["fr"] == "Margherita")
        STATE["heineken"] = next(p for p in d["products"] if "Heineken" in p["name"]["fr"])
        assert STATE["heineken"]["is_alcohol"] is True
        assert STATE["heineken"]["alcohol_type"] == "fermented"


# ------------------------------------------------------------------
# Auth: register / login / profile / addresses
# ------------------------------------------------------------------
class TestAuth:
    def test_register_and_phone_normalisation(self):
        raw = "+41 79 111 " + "".join(random.choices(string.digits, k=2)) + " " + "".join(random.choices(string.digits, k=2))
        STATE["raw_phone"] = raw
        STATE["norm_phone"] = "0" + _digits(raw)[2:] if _digits(raw).startswith("41") and len(_digits(raw)) == 11 else _digits(raw)
        body = {"first_name": "TEST_Ada", "last_name": "Auth", "phone": raw, "password": "secret123"}
        r = requests.post(f"{API}/auth/register", json=body, timeout=30)
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["token_type"] == "bearer"
        assert d["user"]["phone"] == STATE["norm_phone"], f"expected normalised {STATE['norm_phone']}, got {d['user']['phone']}"
        assert d["user"]["first_name"] == "TEST_Ada"
        STATE["token"] = d["access_token"]
        STATE["user_id"] = d["user"]["id"]

    def test_register_duplicate_conflict(self):
        body = {"first_name": "TEST_Dup", "phone": STATE["raw_phone"], "password": "secret123"}
        r = requests.post(f"{API}/auth/register", json=body, timeout=30)
        assert r.status_code == 409, r.text

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"phone": STATE["raw_phone"], "password": "WRONG"}, timeout=30)
        assert r.status_code == 401, r.text

    def test_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"phone": STATE["raw_phone"], "password": "secret123"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["user"]["id"] == STATE["user_id"]

    def test_me_requires_token(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code in (401, 403), r.text

    def test_me_with_token(self):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {STATE['token']}"}, timeout=30)
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["id"] == STATE["user_id"]
        assert u["phone"] == STATE["norm_phone"]

    def test_update_profile(self):
        body = {"first_name": "TEST_Ada2", "last_name": "AuthX", "phone": STATE["raw_phone"], "email": "ada@test.local"}
        r = requests.put(f"{API}/auth/me", json=body, headers={"Authorization": f"Bearer {STATE['token']}"}, timeout=30)
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["first_name"] == "TEST_Ada2"
        assert u["email"] == "ada@test.local"

    def test_add_edit_delete_address(self):
        h = {"Authorization": f"Bearer {STATE['token']}"}
        # add
        body = {"label": "Maison", "street": "Rue Test", "number": "1", "npa": "1723", "city": "Marly"}
        r = requests.post(f"{API}/auth/me/addresses", json=body, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        addrs = r.json()["addresses"]
        assert len(addrs) == 1
        aid = addrs[0]["id"]
        assert addrs[0]["street"] == "Rue Test"
        # edit
        body_upd = {**body, "street": "Rue Modifiée", "number": "2"}
        r2 = requests.put(f"{API}/auth/me/addresses/{aid}", json=body_upd, headers=h, timeout=30)
        assert r2.status_code == 200, r2.text
        assert r2.json()["addresses"][0]["street"] == "Rue Modifiée"
        # delete
        r3 = requests.delete(f"{API}/auth/me/addresses/{aid}", headers=h, timeout=30)
        assert r3.status_code == 200, r3.text
        assert r3.json()["addresses"] == []


# ------------------------------------------------------------------
# Alcohol dynamic age (16 fermented / 18 spirits) + guest orders
# ------------------------------------------------------------------
class TestAlcoholAgeAndUserBinding:
    def _order_payload(self, extra_items=None, **kw):
        items = [{"product_id": STATE["margherita"]["id"], "quantity": 1, "size_key": "40"}]
        if extra_items:
            items += extra_items
        payload = {
            "type": "pickup",
            "items": items,
            "customer": {"first_name": "TEST_Age", "phone": "+41 79 555 44 33"},
            "requested_time": "asap",
            "language": "fr",
        }
        payload.update(kw)
        return payload

    def test_beer_without_age_confirm_400_16plus(self):
        p = self._order_payload(extra_items=[{"product_id": STATE["heineken"]["id"], "quantity": 1}])
        r = requests.post(f"{API}/orders", json=p, timeout=30)
        assert r.status_code == 400, r.text
        assert "16" in r.text, f"expected 16+ in message, got: {r.text}"

    def test_beer_with_age_confirm_ok_and_age_required_16(self):
        p = self._order_payload(extra_items=[{"product_id": STATE["heineken"]["id"], "quantity": 1}], age_confirmed=True)
        r = requests.post(f"{API}/orders", json=p, timeout=30)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["age_required"] == 16, o
        assert o["age_confirmed"] is True
        assert o["user_id"] is None, "guest order must have user_id=None"
        STATE["alcohol_order_id"] = o["id"]

    def test_ticket_contains_age_16_control(self):
        r = requests.get(f"{API}/orders/{STATE['alcohol_order_id']}/ticket", timeout=30)
        assert r.status_code == 200, r.text
        txt = r.json()["text"]
        assert "CONTROLE AGE 16+" in txt, txt

    def test_patch_to_spirits_makes_age_18(self):
        pid = STATE["heineken"]["id"]
        try:
            up = requests.patch(f"{API}/products/{pid}", json={"alcohol_type": "spirits"}, timeout=30)
            assert up.status_code == 200, up.text
            assert up.json()["alcohol_type"] == "spirits"

            p = self._order_payload(extra_items=[{"product_id": pid, "quantity": 1}], age_confirmed=True)
            r = requests.post(f"{API}/orders", json=p, timeout=30)
            assert r.status_code == 200, r.text
            assert r.json()["age_required"] == 18
        finally:
            # restore
            requests.patch(f"{API}/products/{pid}", json={"alcohol_type": "fermented"}, timeout=30)
            after = requests.get(f"{API}/menu", timeout=30).json()
            hein = next(p for p in after["products"] if p["id"] == pid)
            assert hein["alcohol_type"] == "fermented"

    def test_order_without_alcohol_age_required_null(self):
        p = self._order_payload()
        r = requests.post(f"{API}/orders", json=p, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["age_required"] is None

    def test_logged_in_order_binds_user_id_and_saves_address(self):
        h = {"Authorization": f"Bearer {STATE['token']}"}
        addr = {"street": "Route Saved", "number": "5", "npa": "1723", "city": "Marly"}
        payload = {
            "type": "delivery",
            "items": [{"product_id": STATE["margherita"]["id"], "quantity": 1, "size_key": "50"}],  # 40 CHF > min 25
            "customer": {"first_name": "TEST_LoggedIn", "phone": STATE["raw_phone"]},
            "address": addr,
            "requested_time": "asap",
            "save_address": True,
        }
        r = requests.post(f"{API}/orders", json=payload, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["user_id"] == STATE["user_id"], o
        STATE["user_order_id"] = o["id"]

        # profile now contains the saved address
        me = requests.get(f"{API}/auth/me", headers=h, timeout=30).json()
        assert any(a["street"] == "Route Saved" and a["npa"] == "1723" for a in me["addresses"]), me["addresses"]

    def test_my_orders_returns_user_orders(self):
        h = {"Authorization": f"Bearer {STATE['token']}"}
        r = requests.get(f"{API}/me/orders", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        ids = {o["id"] for o in r.json()}
        assert STATE["user_order_id"] in ids


# ------------------------------------------------------------------
# Customer search (staff/customers)
# ------------------------------------------------------------------
class TestCustomerSearch:
    def test_search_by_phone_digits(self):
        # search using 5 digits from the registered phone
        sub = _digits(STATE["raw_phone"])[3:8]
        r = requests.get(f"{API}/customers/search", params={"phone": sub}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "accounts" in d and "orders" in d
        assert any(a["id"] == STATE["user_id"] for a in d["accounts"]), d["accounts"]

    def test_short_phone_rejected(self):
        r = requests.get(f"{API}/customers/search", params={"phone": "79"}, timeout=30)
        # min_length=3 on Query -> FastAPI returns 422 (validation)
        assert r.status_code in (400, 422), r.text


# ------------------------------------------------------------------
# Product photo upload / serve / persist
# ------------------------------------------------------------------
class TestPhotos:
    def test_upload_optimise_and_get(self):
        # 3000x2000 RGB test image
        img = Image.new("RGB", (3000, 2000), color=(220, 40, 40))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        files = {"file": ("test.png", buf.getvalue(), "image/png")}
        r = requests.post(f"{API}/uploads/product-photo", files=files, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["url"].startswith("/api/files/hallo-magic-pizza/products/"), d
        assert d["url"].endswith(".jpg")
        STATE["photo_url"] = d["url"]

        # GET the URL
        r2 = requests.get(BASE + d["url"], timeout=60)
        assert r2.status_code == 200, r2.status_code
        assert r2.headers.get("Content-Type", "").startswith("image/jpeg"), r2.headers
        # Verify long edge <= 1600
        served = Image.open(io.BytesIO(r2.content))
        assert max(served.size) <= 1600, served.size

    def test_patch_product_with_images_persists_in_menu(self):
        pid = STATE["margherita"]["id"]
        # save original
        original = requests.get(f"{API}/products/{pid}", timeout=30).json()
        try:
            body = {"images": [STATE["photo_url"]], "image_url": STATE["photo_url"]}
            r = requests.patch(f"{API}/products/{pid}", json=body, timeout=30)
            assert r.status_code == 200, r.text
            got = r.json()
            assert got["image_url"] == STATE["photo_url"]
            assert STATE["photo_url"] in (got.get("images") or [])

            menu = requests.get(f"{API}/menu", timeout=30).json()
            marg = next(p for p in menu["products"] if p["id"] == pid)
            assert marg["image_url"] == STATE["photo_url"]
            assert STATE["photo_url"] in (marg.get("images") or [])
        finally:
            # restore original image_url and images (if any)
            requests.patch(f"{API}/products/{pid}", json={
                "image_url": original.get("image_url"),
                "images": original.get("images") or [],
            }, timeout=30)


# ------------------------------------------------------------------
# Regression: guest checkout unchanged (no token, no alcohol)
# ------------------------------------------------------------------
class TestGuestRegression:
    def test_guest_order_still_works(self):
        payload = {
            "type": "pickup",
            "items": [{"product_id": STATE["margherita"]["id"], "quantity": 1, "size_key": "32"}],
            "customer": {"first_name": "TEST_Guest", "phone": "+41 79 000 00 00"},
        }
        r = requests.post(f"{API}/orders", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["user_id"] is None
        assert o["age_required"] is None

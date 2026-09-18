"""Iter 11 – Final polish backend verification.

Covers ONLY what the review request lists:
- GET /api/menu category order + no gluten_free filter + Entrées/Vorspeisen present
- DELETE /api/categories/{id} auth + business rules (400 when has products, 200 when empty)
- POST/PATCH/DELETE /api/products with gluten_free option persisted
- Full CRUD on /api/extras with price_by_size

Runs against the public preview URL. Manager JWT is fetched via POST /api/auth/staff/login {pin:1234}.
Cleans up every artifact it creates.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "https://hallo-magic-test.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def manager_token():
    r = requests.post(f"{API}/auth/staff/login", json={"pin": "1234"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth(manager_token):
    return {"Authorization": f"Bearer {manager_token}"}


# ---------------------------------------------------------------------------
# 1. GET /api/menu – category order + no gluten_free + entrees fr/de
# ---------------------------------------------------------------------------
class TestMenu:
    def test_menu_categories_order_and_no_gluten_free(self):
        r = requests.get(f"{API}/menu", timeout=30)
        assert r.status_code == 200
        data = r.json()
        cats = data["categories"]
        slugs = [c["slug"] for c in cats]
        assert slugs == [
            "entrees",
            "pizza",
            "creer-votre-pizza",
            "piadina-pasta",
            "dessert",
            "boissons",
        ], f"Unexpected order: {slugs}"

        # No category should carry filter='gluten_free'
        assert all(c.get("filter") != "gluten_free" for c in cats)
        # No 'Pizza sans gluten' by name either
        assert not any("sans gluten" in (c["name"].get("fr") or "").lower() for c in cats)

    def test_entrees_names(self):
        r = requests.get(f"{API}/menu", timeout=30)
        entrees = next(c for c in r.json()["categories"] if c["slug"] == "entrees")
        assert entrees["name"]["fr"] == "Entrées"
        assert entrees["name"]["de"] == "Vorspeisen"


# ---------------------------------------------------------------------------
# 2. DELETE /api/categories/{id}
# ---------------------------------------------------------------------------
class TestCategoryDelete:
    def test_delete_pizza_category_400_when_has_products(self, auth):
        r = requests.get(f"{API}/menu", timeout=30)
        pizza = next(c for c in r.json()["categories"] if c["slug"] == "pizza")
        resp = requests.delete(f"{API}/categories/{pizza['id']}", headers=auth, timeout=30)
        assert resp.status_code == 400, resp.text
        assert "produit" in resp.json().get("detail", "").lower()

    def test_delete_requires_auth_unauthenticated_forbidden(self):
        r = requests.get(f"{API}/menu", timeout=30)
        pizza = next(c for c in r.json()["categories"] if c["slug"] == "pizza")
        resp = requests.delete(f"{API}/categories/{pizza['id']}", timeout=30)
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_create_temp_category_then_delete_it(self, auth):
        slug = f"test-tmp-{uuid.uuid4().hex[:8]}"
        payload = {
            "slug": slug,
            "name": {"fr": "TEST temp", "de": "TEST temp"},
            "sort": 99,
            "active": True,
        }
        create = requests.post(f"{API}/categories", json=payload, headers=auth, timeout=30)
        assert create.status_code == 200, create.text
        cat = create.json()
        assert cat["slug"] == slug
        cat_id = cat["id"]

        # DELETE (empty category) -> 200 {ok:true}
        delete = requests.delete(f"{API}/categories/{cat_id}", headers=auth, timeout=30)
        assert delete.status_code == 200, delete.text
        assert delete.json() == {"ok": True}

        # Ensure it's really gone
        listing = requests.get(f"{API}/categories", timeout=30)
        assert not any(c["id"] == cat_id for c in listing.json())


# ---------------------------------------------------------------------------
# 3. POST/PATCH/DELETE /api/products with gluten_free option
# ---------------------------------------------------------------------------
class TestProductGlutenFreeOption:
    def test_product_options_persist_and_patch(self, auth):
        # Find pizza category
        r = requests.get(f"{API}/menu", timeout=30)
        pizza_cat = next(c for c in r.json()["categories"] if c["slug"] == "pizza")

        payload = {
            "category_id": pizza_cat["id"],
            "name": {"fr": "TEST_Final Pizza", "de": "TEST_Final Pizza"},
            "description": {"fr": "", "de": ""},
            "price": 14.0,
            "sizes": [
                {"key": "32", "label": "32 cm", "price": 14.0},
                {"key": "40", "label": "40 cm", "price": 20.0},
                {"key": "50", "label": "50 cm", "price": 26.0},
            ],
            "options": [
                {
                    "key": "classic",
                    "group": "dough",
                    "name": {"fr": "Classique", "de": "Klassisch"},
                    "price": 0,
                    "default": True,
                },
                {
                    "key": "gluten_free",
                    "group": "dough",
                    "name": {"fr": "Sans gluten", "de": "Glutenfrei"},
                    "price": 4.0,
                    "only_sizes": ["32"],
                    "default": False,
                },
            ],
            "customizable": True,
            "available": True,
        }
        created = requests.post(f"{API}/products", json=payload, headers=auth, timeout=30)
        assert created.status_code == 200, created.text
        prod = created.json()
        pid = prod["id"]

        try:
            # Verify options persisted
            fetched = requests.get(f"{API}/products/{pid}", timeout=30).json()
            keys = [o["key"] for o in fetched["options"]]
            assert keys == ["classic", "gluten_free"]
            gf = next(o for o in fetched["options"] if o["key"] == "gluten_free")
            assert gf["price"] == 4.0
            assert gf["only_sizes"] == ["32"]
            assert gf["default"] is False

            # PATCH options: change gluten_free price to 5 and sizes to ["32","40"]
            new_options = [
                {
                    "key": "classic",
                    "group": "dough",
                    "name": {"fr": "Classique", "de": "Klassisch"},
                    "price": 0,
                    "default": True,
                },
                {
                    "key": "gluten_free",
                    "group": "dough",
                    "name": {"fr": "Sans gluten", "de": "Glutenfrei"},
                    "price": 5.0,
                    "only_sizes": ["32", "40"],
                    "default": False,
                },
            ]
            patched = requests.patch(
                f"{API}/products/{pid}",
                json={"options": new_options},
                headers=auth,
                timeout=30,
            )
            assert patched.status_code == 200, patched.text
            gf2 = next(o for o in patched.json()["options"] if o["key"] == "gluten_free")
            assert gf2["price"] == 5.0
            assert gf2["only_sizes"] == ["32", "40"]

            # Re-fetch verifies persistence
            re = requests.get(f"{API}/products/{pid}", timeout=30).json()
            gf3 = next(o for o in re["options"] if o["key"] == "gluten_free")
            assert gf3["price"] == 5.0
            assert gf3["only_sizes"] == ["32", "40"]
        finally:
            # Cleanup
            requests.delete(f"{API}/products/{pid}", headers=auth, timeout=30)


# ---------------------------------------------------------------------------
# 4. Extras CRUD with price_by_size and max_quantity
# ---------------------------------------------------------------------------
class TestExtrasCRUD:
    def test_full_lifecycle(self, auth):
        key = f"test_extra_{uuid.uuid4().hex[:8]}"
        payload = {
            "key": key,
            "name": {"fr": "TEST Supp", "de": "TEST Zutat"},
            "price": 2.0,
            "price_by_size": {"32": 2.0, "40": 3.0, "50": 4.0},
            "available": True,
            "max_quantity": 2,
        }
        create = requests.post(f"{API}/extras", json=payload, headers=auth, timeout=30)
        assert create.status_code == 200, create.text
        extra = create.json()
        ex_id = extra["id"]
        try:
            assert extra["key"] == key
            assert extra["price_by_size"] == {"32": 2.0, "40": 3.0, "50": 4.0}
            assert extra["max_quantity"] == 2

            # PUT update
            payload["price"] = 2.5
            payload["price_by_size"] = {"32": 2.5, "40": 3.5, "50": 4.5}
            payload["max_quantity"] = 3
            put = requests.put(f"{API}/extras/{ex_id}", json=payload, headers=auth, timeout=30)
            assert put.status_code == 200, put.text
            up = put.json()
            assert up["price"] == 2.5
            assert up["price_by_size"] == {"32": 2.5, "40": 3.5, "50": 4.5}
            assert up["max_quantity"] == 3

            # verify via list
            listing = requests.get(f"{API}/extras", timeout=30).json()
            fresh = next(e for e in listing if e["id"] == ex_id)
            assert fresh["price"] == 2.5
        finally:
            delete = requests.delete(f"{API}/extras/{ex_id}", headers=auth, timeout=30)
            assert delete.status_code == 200
            assert delete.json() == {"ok": True}

            # verify actually removed
            listing = requests.get(f"{API}/extras", timeout=30).json()
            assert not any(e["id"] == ex_id for e in listing)

    def test_extras_requires_auth_unauthenticated_denied(self):
        payload = {
            "key": f"noauth_{uuid.uuid4().hex[:6]}",
            "name": {"fr": "x", "de": "x"},
            "price": 1.0,
        }
        r = requests.post(f"{API}/extras", json=payload, timeout=30)
        assert r.status_code in (401, 403)

"""Iteration 22 — Live verification of the Carte Fidélité HTTP surface against the preview backend."""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
PHONE = "079 555 01 99"
PWD = "Fidelity2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"phone": PHONE, "password": PWD})
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    assert tok
    return tok


# ---------- GET /api/me/loyalty ----------

def test_me_loyalty_requires_auth(session):
    r = session.get(f"{BASE_URL}/api/me/loyalty")
    assert r.status_code == 401


def test_me_loyalty_requires_customer_seeded_values(session, token):
    r = session.get(f"{BASE_URL}/api/me/loyalty", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["stamps"] == 9
    assert data["rewards_available"] == 0
    assert data["block"] == 10


def test_second_login_requires_identical_state(session, token):
    r2 = session.post(f"{BASE_URL}/api/auth/login", json={"phone": PHONE, "password": PWD})
    assert r2.status_code == 200
    tok2 = r2.json()["access_token"]
    a = session.get(f"{BASE_URL}/api/me/loyalty", headers={"Authorization": f"Bearer {token}"}).json()
    b = session.get(f"{BASE_URL}/api/me/loyalty", headers={"Authorization": f"Bearer {tok2}"}).json()
    assert a["stamps"] == b["stamps"] == 9
    assert a["rewards_available"] == b["rewards_available"] == 0
    assert a["rewards_reserved"] == b["rewards_reserved"] == 0


# ---------- POST /api/loyalty/quote ----------

def _menu(session):
    r = session.get(f"{BASE_URL}/api/menu")
    assert r.status_code == 200
    return r.json()


def _find(menu, name):
    for p in menu.get("products", []):
        pn = p.get("name", "")
        if isinstance(pn, dict):
            pn = pn.get("fr") or pn.get("de") or ""
        if name.lower() in pn.lower():
            return p
    return None


def test_quote_requires_margherita_half_off(session, token):
    menu = _menu(session)
    marg = _find(menu, "Margherita")
    assert marg is not None, "Margherita not found in /api/menu"
    r = session.post(
        f"{BASE_URL}/api/loyalty/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={"type": "pickup", "items": [{"product_id": marg["id"], "quantity": 1, "size_key": "32"}]},
    )
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["rewards_applied"] == 1
    assert q["discount"] == 7.00
    assert q["total"] == 7.00
    # quote should not reserve
    me = session.get(f"{BASE_URL}/api/me/loyalty", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["rewards_reserved"] == 0


def test_quote_requires_drink_only_zero_discount(session, token):
    menu = _menu(session)
    # find a product in category boissons
    drink = None
    cats = {c["id"]: c for c in menu.get("categories", [])}
    for p in menu.get("products", []):
        cat = cats.get(p.get("category_id"))
        if cat and cat.get("slug") == "boissons":
            drink = p
            break
    assert drink is not None, "No boissons product found"
    body = {"type": "pickup", "items": [{"product_id": drink["id"], "quantity": 1}]}
    # include size if required
    sizes = drink.get("sizes") or []
    if sizes:
        body["items"][0]["size_key"] = sizes[0].get("key")
    r = session.post(
        f"{BASE_URL}/api/loyalty/quote",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["pizzas"] == 0
    assert q["discount"] == 0

"""VAT / TVA + receipt endpoint tests against the public backend URL.

Reads EXPO_PUBLIC_BACKEND_URL from /app/frontend/.env (as user faces it),
runs the 7 VAT scenarios, verifies historical snapshot integrity,
receipt text content and print/reprint flow (409 without force).

All temporary settings and product mutations are restored at teardown.
"""
import os
import re
import pytest
import requests

# ---- Config ---------------------------------------------------------------
def _read_env(key: str) -> str:
    path = "/app/frontend/.env"
    with open(path) as f:
        for line in f:
            if line.strip().startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError(f"{key} not found in {path}")

BASE = _read_env("EXPO_PUBLIC_BACKEND_URL").rstrip("/") + "/api"

# Product IDs (from GET /api/menu, stable seed)
P = {
    "diavola": "6aa94a928068d15c2420f9ea",
    "coca":    "6aa94a928068d15c2420fa0c",
    "beer":    "6aa94a928068d15c2420fa18",  # Bière Moretti (8.1)
    "wine":    "6aa94a928068d15c2420fa19",  # Nero d'Avola (8.1)
    "tiramisu":"6aa94a928068d15c2420fa08",
    "profit":  "6aa94a928068d15c2420fa09",  # Profiteroles 8.50
    "ex_moz":  "6aa94a928068d15c2420f9e1",
    "ex_champ":"6aa94a928068d15c2420f9ca",
}
CUST = {"first_name": "TEST", "last_name": "TVA", "phone": "026 430 00 96"}


# ---- Fixtures -------------------------------------------------------------
@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="session")
def original_settings(s):
    r = s.get(f"{BASE}/settings", timeout=10)
    assert r.status_code == 200, r.text
    orig = r.json()
    yield orig
    # restore original settings (drop keys backend may reject)
    s.put(f"{BASE}/settings", json=orig, timeout=10)


# ---- Helpers --------------------------------------------------------------
def _order(s, items, typ="pickup", address=None, age=False):
    body = {"type": typ, "source": "web", "items": items, "customer": CUST,
            "requested_time": "asap", "age_confirmed": age}
    if address:
        body["address"] = address
    r = s.post(f"{BASE}/orders", json=body, timeout=15)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _reconcile(o):
    tot = round(o["total"], 2)
    net = round(o["total_net"], 2)
    vat = round(o["total_vat"], 2)
    assert abs((net + vat) - tot) < 0.011, f"net+vat!=total: {net}+{vat}!={tot}"
    for g in o["vat_breakdown"]:
        assert g["gross"] > 0, f"empty group {g}"
        assert abs((round(g["net"], 2) + round(g["vat"], 2)) - round(g["gross"], 2)) < 0.011, g
    assert abs(sum(g["gross"] for g in o["vat_breakdown"]) - tot) < 0.011
    lines_total = sum(i["line_total"] for i in o["items"]) + o.get("delivery_fee", 0) - o.get("discount", 0)
    assert abs(round(lines_total, 2) - tot) < 0.011, f"lines+fee!=total: {lines_total} vs {tot}"


# ---- 1. Settings ----------------------------------------------------------
def test_settings_has_fiscal_fields(s, original_settings):
    o = original_settings
    for k in ["business_name", "street", "postal_code", "city", "vat_number",
              "vat_rate_standard", "vat_rate_alcohol", "delivery_fee_vat_rate"]:
        assert k in o, f"missing settings field {k}"
    assert "HALLO MAGIC PIZZA" in o["business_name"].upper() or "MAGIC" in o["business_name"].upper()
    assert "Chésalles" in o["street"] and "19" in o["street"]
    assert str(o["postal_code"]) == "1723"
    assert o["city"] == "Marly"
    assert "156.631.035" in o["vat_number"]
    assert float(o["vat_rate_standard"]) == 2.6
    assert float(o["vat_rate_alcohol"]) == 8.1


def test_settings_roundtrip(s, original_settings):
    payload = {**original_settings, "delivery_fee_vat_rate": 8.1}
    r = s.put(f"{BASE}/settings", json=payload, timeout=10)
    assert r.ok, r.text
    got = s.get(f"{BASE}/settings").json()
    assert float(got["delivery_fee_vat_rate"]) == 8.1
    # restore
    s.put(f"{BASE}/settings", json=original_settings)
    got2 = s.get(f"{BASE}/settings").json()
    assert float(got2["delivery_fee_vat_rate"]) == float(original_settings["delivery_fee_vat_rate"])


# ---- 2. Menu VAT rates ----------------------------------------------------
def test_menu_vat_rates(s):
    m = s.get(f"{BASE}/menu", timeout=10).json()
    by_id = {p["id"]: p for p in m["products"]}
    assert by_id[P["diavola"]]["vat_rate"] == 2.6
    assert by_id[P["coca"]]["vat_rate"] == 2.6
    assert by_id[P["beer"]]["vat_rate"] == 8.1
    assert by_id[P["wine"]]["vat_rate"] == 8.1
    for e in m["extras"]:
        assert e["vat_rate"] == 2.6, f"extra {e['id']} vat != 2.6"


# ---- 3. VAT scenarios -----------------------------------------------------
def test_v1_food_only(s):
    o = _order(s, [{"product_id": P["diavola"], "quantity": 1, "size_key": "32"}])
    _reconcile(o)
    assert [g["rate"] for g in o["vat_breakdown"]] == [2.6]
    assert o["items"][0]["vat_rate"] == 2.6


def test_v2_food_plus_coca(s):
    o = _order(s, [
        {"product_id": P["diavola"], "quantity": 1, "size_key": "32"},
        {"product_id": P["coca"],    "quantity": 2},
    ])
    _reconcile(o)
    assert [g["rate"] for g in o["vat_breakdown"]] == [2.6]


def test_v3_food_plus_beer(s):
    o = _order(s, [
        {"product_id": P["diavola"], "quantity": 1, "size_key": "32"},
        {"product_id": P["beer"],    "quantity": 1},
    ], age=True)
    _reconcile(o)
    rates = sorted(g["rate"] for g in o["vat_breakdown"])
    assert rates == [2.6, 8.1]
    beer = next(i for i in o["items"] if i["product_id"] == P["beer"])
    diav = next(i for i in o["items"] if i["product_id"] == P["diavola"])
    assert beer["vat_rate"] == 8.1
    assert diav["vat_rate"] == 2.6


def test_v4_food_extras_wine(s):
    o = _order(s, [
        {"product_id": P["diavola"], "quantity": 1, "size_key": "40",
         "extras": [{"extra_id": P["ex_moz"], "quantity": 1},
                    {"extra_id": P["ex_champ"], "quantity": 1}]},
        {"product_id": P["wine"], "quantity": 1},
    ], age=True)
    _reconcile(o)
    ex = o["items"][0]["extras"]
    assert len(ex) == 2
    for e in ex:
        assert e["vat_rate"] == 2.6
        assert abs(round(e["net_amount"] + e["vat_amount"], 2) - round(e["gross_amount"], 2)) < 0.011


def test_v5_delivery_fee_vat(s, original_settings):
    payload = {**original_settings, "delivery_fee": 5.0, "delivery_fee_vat_rate": 8.1}
    s.put(f"{BASE}/settings", json=payload, timeout=10)
    try:
        o = _order(s, [{"product_id": P["diavola"], "quantity": 2, "size_key": "32"}],
                   typ="delivery",
                   address={"street": "Route de Chésalles", "number": "19",
                            "npa": "1723", "city": "Marly"})
        _reconcile(o)
        assert abs(o["delivery_fee_gross"] - 5.0) < 0.011
        assert float(o["delivery_fee_vat_rate"]) == 8.1
        rates = [g["rate"] for g in o["vat_breakdown"]]
        assert 8.1 in rates and 2.6 in rates
    finally:
        s.put(f"{BASE}/settings", json=original_settings)


def test_v6_quantity_seven_coca(s):
    o = _order(s, [{"product_id": P["coca"], "quantity": 7}])
    _reconcile(o)
    item = o["items"][0]
    assert abs(item["gross_amount"] - 24.5) < 0.011, f"gross={item['gross_amount']}"


def test_v7_decimal_prices(s):
    o = _order(s, [{"product_id": P["profit"], "quantity": 3},
                   {"product_id": P["tiramisu"], "quantity": 1}])
    _reconcile(o)


# ---- 4. Historical snapshot ----------------------------------------------
def test_historical_snapshot(s):
    o = _order(s, [{"product_id": P["diavola"], "quantity": 1, "size_key": "32"}])
    old_id = o["id"]
    old_breakdown = o["vat_breakdown"]
    r = s.patch(f"{BASE}/products/{P['diavola']}", json={"vat_rate": 8.1})
    assert r.ok, r.text
    try:
        again = s.get(f"{BASE}/orders/{old_id}").json()
        assert again["items"][0]["vat_rate"] == 2.6, "old order item vat mutated!"
        assert again["vat_breakdown"] == old_breakdown, "old order breakdown mutated!"
    finally:
        s.patch(f"{BASE}/products/{P['diavola']}", json={"vat_rate": 2.6})


# ---- 5. Receipt endpoints -------------------------------------------------
def test_receipt_text_food_only(s):
    o = _order(s, [{"product_id": P["diavola"], "quantity": 1, "size_key": "32"}])
    r = s.get(f"{BASE}/orders/{o['id']}/receipt")
    assert r.ok, r.text
    txt = r.json()["text"]
    assert "HALLO MAGIC PIZZA" in txt.upper()
    assert "Route de Chésalles 19" in txt
    assert "1723" in txt and "Marly" in txt
    assert "026 430 00 96" in txt
    assert "CHE-156.631.035" in txt
    assert re.search(r"Commande n[°º]", txt), "'Commande n°' missing"
    assert "TOTAL" in txt.upper()
    assert "TVA INCLUSE" in txt.upper()
    assert "TVA 2.6%" in txt
    assert "TVA 8.1%" not in txt, "food-only receipt should not have TVA 8.1%"


def test_receipt_text_mixed(s):
    o = _order(s, [
        {"product_id": P["diavola"], "quantity": 1, "size_key": "32"},
        {"product_id": P["beer"], "quantity": 1},
    ], age=True)
    txt = s.get(f"{BASE}/orders/{o['id']}/receipt").json()["text"]
    assert "TVA 2.6%" in txt and "TVA 8.1%" in txt


def test_receipt_print_and_409(s):
    o = _order(s, [{"product_id": P["diavola"], "quantity": 1, "size_key": "32"}])
    oid = o["id"]
    r1 = s.post(f"{BASE}/orders/{oid}/receipt/print", json={})
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1.get("printed") is True
    assert (d1.get("attempts") or d1.get("print_attempts")) == 1

    r2 = s.post(f"{BASE}/orders/{oid}/receipt/print", json={})
    assert r2.status_code == 409, f"expected 409 without force, got {r2.status_code}: {r2.text}"

    r3 = s.post(f"{BASE}/orders/{oid}/receipt/print", json={"force": True})
    assert r3.status_code == 200, r3.text
    d3 = r3.json()
    assert (d3.get("attempts") or d3.get("print_attempts")) == 2


def test_ticket_has_no_tva_incluse(s):
    o = _order(s, [{"product_id": P["diavola"], "quantity": 1, "size_key": "32"}])
    r = s.get(f"{BASE}/orders/{o['id']}/ticket")
    assert r.ok, r.text
    txt = r.json().get("text", "")
    assert "TVA INCLUSE" not in txt.upper()

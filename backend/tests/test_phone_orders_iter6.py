"""Iteration 6: staff phone-orders (Poste 1 / Poste 2) + /api/customers + /api/orders/{id}/assign.

Run:
  pytest backend/tests/test_phone_orders_iter6.py -n 0 -v
The suite shares module-level STATE, so it must run sequentially.
"""
import os
import random
import time
import pytest
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://hallo-magic-test.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

STATE: dict = {}


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


def _menu(s):
    if "menu" in STATE:
        return STATE["menu"]
    r = s.get(f"{API}/menu")
    r.raise_for_status()
    STATE["menu"] = r.json()
    return STATE["menu"]


def _pick(name, m):
    return next(p for p in m["products"] if p["name"]["fr"].lower() == name.lower())


def _pick_contains(sub, m):
    return next(p for p in m["products"] if sub.lower() in p["name"]["fr"].lower())


def _extra(key, m):
    return next(e for e in m["extras"] if e["key"] == key)


# ---------------- Customers / phone-order creation ----------------
class TestPhoneOrderCreate:
    def test_create_customer_with_address(self, s):
        # Unique phone starting 079 6xx xx xx
        rand = random.randint(1000000, 9999999)
        phone = f"0796{rand}"
        assert len(phone) == 11
        payload = {
            "first_name": "TEST_Anna",
            "last_name": "Rossi",
            "phone": phone,
            "address": {
                "street": "Rue du Centre",
                "number": "5",
                "npa": "1723",
                "city": "Marly",
                "instructions": "Sonnette Rossi",
            },
        }
        r = s.post(f"{API}/customers", json=payload)
        assert r.status_code == 201, r.text
        u = r.json()
        assert u["first_name"] == "TEST_Anna"
        assert u["phone"] == phone
        assert len(u["addresses"]) == 1
        assert u["addresses"][0]["npa"] == "1723"
        STATE["cust_id"] = u["id"]
        STATE["cust_phone"] = phone
        STATE["cust_addr"] = u["addresses"][0]

    def test_phone_order_delivery_cash_station1(self, s):
        m = _menu(s)
        marg = _pick("Margherita", m)
        a = STATE["cust_addr"]
        payload = {
            "type": "delivery",
            "station": 1,
            "payment_method": "cash",
            "customer_id": STATE["cust_id"],
            # Margherita 50cm (CHF 31) to clear Marly's CHF 25 delivery minimum
            "items": [{"product_id": marg["id"], "quantity": 1, "size_key": "50"}],
            "customer": {"first_name": "TEST_Anna", "last_name": "Rossi", "phone": STATE["cust_phone"]},
            "address": {"street": a["street"], "number": a["number"], "npa": a["npa"], "city": a["city"]},
            "requested_time": "asap",
            "language": "fr",
        }
        r = s.post(f"{API}/phone-orders", json=payload)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "accepted"
        assert o["source"] == "telephone"
        assert o["station"] == 1
        assert o["payment_method"] == "cash"
        assert o["user_id"] == STATE["cust_id"]
        assert o["printed"] is True
        assert o["print_attempts"] == 1
        assert o["estimated_minutes"] == 30
        STATE["order_delivery_id"] = o["id"]
        STATE["order_delivery_num"] = o["order_number"]

    def test_customers_search_returns_account_and_order(self, s):
        digits = STATE["cust_phone"]
        # last 7 digits should still match via regex
        r = s.get(f"{API}/customers/search", params={"phone": digits[-7:]})
        assert r.status_code == 200, r.text
        d = r.json()
        # accounts contains our customer
        accs = [a for a in d["accounts"] if a["id"] == STATE["cust_id"]]
        assert accs, f"customer {STATE['cust_id']} not in search accounts"
        acc = accs[0]
        assert any(ad.get("npa") == "1723" for ad in acc["addresses"])
        # orders contain our phone order
        assert any(o["id"] == STATE["order_delivery_id"] for o in d["orders"])

    def test_phone_order_pickup_terminal_station2(self, s):
        m = _menu(s)
        marg = _pick("Margherita", m)
        payload = {
            "type": "pickup",
            "station": 2,
            "payment_method": "terminal",
            "items": [{"product_id": marg["id"], "quantity": 1, "size_key": "32"}],
            "customer": {"first_name": "TEST_Guest", "phone": "0791750000"},
            "requested_time": "asap",
        }
        r = s.post(f"{API}/phone-orders", json=payload)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["station"] == 2
        assert o["source"] == "telephone"
        assert o["payment_method"] == "terminal"
        assert o["type"] == "pickup"
        assert o["status"] == "accepted"
        assert o["order_number"] != STATE["order_delivery_num"]
        STATE["order_pickup_id"] = o["id"]

    def test_both_orders_active(self, s):
        r = s.get(f"{API}/orders", params={"active": "true", "limit": 200})
        assert r.status_code == 200
        ids = {o["id"] for o in r.json()}
        assert STATE["order_delivery_id"] in ids
        assert STATE["order_pickup_id"] in ids

    def test_pickup_pay_at_pickup_and_ticket(self, s):
        m = _menu(s)
        marg = _pick("Margherita", m)
        payload = {
            "type": "pickup",
            "station": 1,
            "payment_method": "pay_at_pickup",
            "items": [{"product_id": marg["id"], "quantity": 1, "size_key": "32"}],
            "customer": {"first_name": "TEST_G2", "phone": "0791751111"},
            "requested_time": "asap",
        }
        r = s.post(f"{API}/phone-orders", json=payload)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["estimated_minutes"] == 30
        # ticket contents
        t = s.get(f"{API}/orders/{o['id']}/ticket").json()["text"]
        assert "R E T R A I T" in t
        assert "TELEPHONE - POSTE" in t
        assert "A ENCAISSER" in t
        STATE["pickup_paypickup_id"] = o["id"]

    def test_delivery_exact_time_1945(self, s):
        m = _menu(s)
        marg = _pick("Margherita", m)
        a = STATE["cust_addr"]
        payload = {
            "type": "delivery",
            "station": 1,
            "payment_method": "pay_at_delivery",
            "customer_id": STATE["cust_id"],
            "items": [{"product_id": marg["id"], "quantity": 1, "size_key": "50"}],
            "customer": {"first_name": "TEST_Anna", "phone": STATE["cust_phone"]},
            "address": {"street": a["street"], "number": a["number"], "npa": a["npa"], "city": a["city"]},
            "requested_time": "19:45",
        }
        r = s.post(f"{API}/phone-orders", json=payload)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["requested_time"] == "19:45"
        t = s.get(f"{API}/orders/{o['id']}/ticket").json()["text"]
        assert "LIVRAISON 19:45" in t, t
        assert "Souhaite: 19:45" in t, t

    def test_pizza_extras_removed_note(self, s):
        m = _menu(s)
        diavola = _pick("Diavola", m)
        lard = _extra("lard", m)
        payload = {
            "type": "pickup",
            "station": 1,
            "payment_method": "cash",
            "items": [{
                "product_id": diavola["id"],
                "quantity": 1,
                "size_key": "32",
                "extras": [{"extra_id": lard["id"], "quantity": 1}],
                "removed_ingredient_ids": ["oignons"],
                "note": "bien cuite",
            }],
            "customer": {"first_name": "TEST_Ext", "phone": "0791752222"},
            "requested_time": "asap",
        }
        r = s.post(f"{API}/phone-orders", json=payload)
        assert r.status_code == 200, r.text
        o = r.json()
        it = o["items"][0]
        assert any(e["name"]["fr"].lower() == "lard" for e in it["extras"])
        assert any(r_["id"] == "oignons" for r_ in it["removed_ingredients"])
        assert it["note"] == "bien cuite"
        t = s.get(f"{API}/orders/{o['id']}/ticket").json()["text"]
        assert "- SANS OIGNONS" in t
        assert "+ LARD" in t
        assert "NOTE: BIEN CUITE" in t

    def test_mixed_vat_alcohol_age16(self, s):
        m = _menu(s)
        marg = _pick("Margherita", m)
        # Bière Moretti (fermented alcohol)
        moretti = _pick_contains("moretti", m)
        payload = {
            "type": "pickup",
            "station": 1,
            "payment_method": "cash",
            "items": [
                {"product_id": marg["id"], "quantity": 1, "size_key": "32"},
                {"product_id": moretti["id"], "quantity": 1},
            ],
            "customer": {"first_name": "TEST_Mix", "phone": "0791753333"},
            "requested_time": "asap",
        }
        r = s.post(f"{API}/phone-orders", json=payload)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["age_required"] == 16
        assert o["age_confirmed"] is True
        rates = {round(g["rate"], 1) for g in o["vat_breakdown"]}
        assert 2.6 in rates and 8.1 in rates, o["vat_breakdown"]
        # ticket
        t = s.get(f"{API}/orders/{o['id']}/ticket").json()["text"]
        assert "CONTROLE AGE 16+" in t
        # receipt
        rec = s.get(f"{API}/orders/{o['id']}/receipt").json()["text"]
        assert "TVA 2.6%" in rec
        assert "TVA 8.1%" in rec
        assert "CHE-156.631.035 TVA" in rec
        # net+vat totals sum to total (2dp)
        total_net = round(sum(g["net"] for g in o["vat_breakdown"]), 2)
        total_vat = round(sum(g["vat"] for g in o["vat_breakdown"]), 2)
        assert round(total_net + total_vat, 2) == round(o["total"], 2), (total_net, total_vat, o["total"])

    def test_print_jobs_single_kitchen_per_phone_order(self, s):
        r = s.get(f"{API}/print-jobs", params={"limit": 500})
        assert r.status_code == 200
        jobs = r.json()
        kitchen_for_order = [
            j for j in jobs
            if j.get("order_id") == STATE["order_delivery_id"] and j.get("kind") == "kitchen"
        ]
        assert len(kitchen_for_order) == 1, kitchen_for_order

    def test_reprint_conflict_and_force(self, s):
        oid = STATE["order_delivery_id"]
        r1 = s.post(f"{API}/orders/{oid}/print", json={"force": False})
        assert r1.status_code == 409, r1.text
        r2 = s.post(f"{API}/orders/{oid}/print", json={"force": True})
        assert r2.status_code == 200, r2.text
        assert r2.json()["print_attempts"] >= 2


# ---------------- Assign driver ----------------
class TestAssignDriver:
    def test_assign_delivery_ok(self, s):
        r = s.post(f"{API}/orders/{STATE['order_delivery_id']}/assign", json={"driver": "Livreur 2"})
        assert r.status_code == 200, r.text
        assert r.json()["driver"] == "Livreur 2"

    def test_assign_pickup_400(self, s):
        r = s.post(f"{API}/orders/{STATE['order_pickup_id']}/assign", json={"driver": "Livreur 1"})
        assert r.status_code == 400, r.text


# ---------------- Validation ----------------
class TestPhoneOrderValidation:
    def test_invalid_station(self, s):
        m = _menu(s)
        marg = _pick("Margherita", m)
        r = s.post(f"{API}/phone-orders", json={
            "type": "pickup", "station": 3, "payment_method": "cash",
            "items": [{"product_id": marg["id"], "quantity": 1, "size_key": "32"}],
            "customer": {"first_name": "TEST_v", "phone": "0791754444"},
        })
        assert r.status_code == 400

    def test_invalid_payment_method(self, s):
        m = _menu(s)
        marg = _pick("Margherita", m)
        r = s.post(f"{API}/phone-orders", json={
            "type": "pickup", "station": 1, "payment_method": "bitcoin",
            "items": [{"product_id": marg["id"], "quantity": 1, "size_key": "32"}],
            "customer": {"first_name": "TEST_v", "phone": "0791755555"},
        })
        assert r.status_code == 400


# ---------------- Regression ----------------
class TestRegression:
    def test_normal_order_still_pending(self, s):
        m = _menu(s)
        marg = _pick("Margherita", m)
        r = s.post(f"{API}/orders", json={
            "type": "pickup",
            "items": [{"product_id": marg["id"], "quantity": 1, "size_key": "32"}],
            "customer": {"first_name": "TEST_Reg", "phone": "0791756666"},
            "requested_time": "asap",
        })
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "pending"
        assert o["printed"] is False

    def test_menu_still_ok(self, s):
        r = s.get(f"{API}/menu")
        assert r.status_code == 200
        d = r.json()
        assert len(d["products"]) >= 50

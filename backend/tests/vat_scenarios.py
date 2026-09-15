"""VAT / TVA scenario tests (run against the live backend). python3 /app/backend/tests/vat_scenarios.py"""
import json
import os
import sys
import requests

BASE = os.environ.get("API", "http://localhost:8001/api")
ids = json.load(open("/tmp/ids.json"))
cust = {"first_name": "Test", "last_name": "TVA", "phone": "026 430 00 96"}


def order(items, typ="pickup", address=None, age=False):
    body = {"type": typ, "source": "web", "items": items, "customer": cust, "requested_time": "asap", "age_confirmed": age}
    if address:
        body["address"] = address
    r = requests.post(f"{BASE}/orders", json=body)
    assert r.ok, r.text
    return r.json()


def check(o, label):
    tot = o["total"]
    net = o["total_net"]
    vat = o["total_vat"]
    groups = {g["rate"]: g for g in o["vat_breakdown"]}
    ok_sum = abs(round(net + vat, 2) - tot) < 0.005
    ok_groups = all(abs(round(g["net"] + g["vat"], 2) - g["gross"]) < 0.005 for g in groups.values())
    ok_gross = abs(round(sum(g["gross"] for g in groups.values()), 2) - tot) < 0.005
    lines_ok = abs(round(sum(i["line_total"] for i in o["items"]), 2) + o["delivery_fee"] - tot) < 0.005
    print(f"\n{label}: order #{o['order_number']} total {tot:.2f} | net {net:.2f} + vat {vat:.2f} | groups {[(g['rate'], g['gross'], g['net'], g['vat']) for g in o['vat_breakdown']]}")
    print("  net+vat=total:", ok_sum, "| groups reconcile:", ok_groups, "| gross groups=total:", ok_gross, "| lines=total:", lines_ok)
    assert ok_sum and ok_groups and ok_gross and lines_ok, "RECONCILIATION FAILED"
    rec = requests.get(f"{BASE}/orders/{o['id']}/receipt").json()
    assert f"TOTAL{'':>{42 - 5 - 12}}" in rec["text"] or f"CHF {tot:.2f}" in rec["text"]
    return o, rec


# TEST 1 – only food 2.6%
o1, r1 = check(order([{"product_id": ids["diavola"], "quantity": 1, "size_key": "32"}]), "TEST1 food only")
assert [g["rate"] for g in o1["vat_breakdown"]] == [2.6]
# TEST 2 – food + coca (all 2.6)
o2, _ = check(order([{"product_id": ids["diavola"], "quantity": 1, "size_key": "32"}, {"product_id": ids["coca"], "quantity": 2}]), "TEST2 food+coca")
assert [g["rate"] for g in o2["vat_breakdown"]] == [2.6]
# TEST 3 – food + beer
o3, _ = check(order([{"product_id": ids["diavola"], "quantity": 1, "size_key": "32"}, {"product_id": ids["beer"], "quantity": 1}], age=True), "TEST3 food+beer")
assert [g["rate"] for g in o3["vat_breakdown"]] == [2.6, 8.1]
assert o3["items"][1]["vat_rate"] == 8.1 and o3["items"][0]["vat_rate"] == 2.6
# TEST 4 – food + wine + extras
o4, r4 = check(order([
    {"product_id": ids["diavola"], "quantity": 1, "size_key": "40", "removed_ingredient_ids": ["oignons"],
     "extras": [{"extra_id": ids["ex_moz"], "quantity": 1}, {"extra_id": ids["ex_champ"], "quantity": 1}]},
    {"product_id": ids["wine"], "quantity": 1}], age=True), "TEST4 food+wine+extras")
ex = o4["items"][0]["extras"]
assert all(e["vat_rate"] == 2.6 and abs(e["net_amount"] + e["vat_amount"] - e["gross_amount"]) < 0.005 for e in ex)
# TEST 5 – delivery with fee VAT (set fee to 5.00 temporarily)
s = requests.get(f"{BASE}/settings").json()
requests.put(f"{BASE}/settings", json={**s, "delivery_fee": 5.0, "delivery_fee_vat_rate": 8.1})
o5, r5 = check(order([{"product_id": ids["diavola"], "quantity": 2, "size_key": "32"}], "delivery",
                     {"street": "Route de Chésalles", "number": "19", "npa": "1723", "city": "Marly"}), "TEST5 delivery fee VAT 8.1")
assert o5["delivery_fee_gross"] == 5.0 and o5["delivery_fee_vat_rate"] == 8.1 and 8.1 in [g["rate"] for g in o5["vat_breakdown"]]
requests.put(f"{BASE}/settings", json=s)  # restore
# TEST 6 – several quantities
o6, _ = check(order([{"product_id": ids["coca"], "quantity": 7}]), "TEST6 quantities")
assert abs(o6["items"][0]["gross_amount"] - 24.5) < 0.005
# TEST 7 – decimal price (Profiteroles 8.50 / Tiramisu 8.00)
o7, r7 = check(order([{"product_id": ids["salad"], "quantity": 3}, {"product_id": ids["tiramisu"], "quantity": 1}]), "TEST7 decimals")

# Historical snapshot: change Diavola VAT to 8.1 then verify old order unchanged
requests.patch(f"{BASE}/products/{ids['diavola']}", json={"vat_rate": 8.1})
again = requests.get(f"{BASE}/orders/{o1['id']}").json()
assert again["items"][0]["vat_rate"] == 2.6 and again["vat_breakdown"] == o1["vat_breakdown"], "historical order changed!"
requests.patch(f"{BASE}/products/{ids['diavola']}", json={"vat_rate": 2.6})
print("\nHistorical snapshot preserved: OK")

print("\n================ SAMPLE RECEIPT 2.6% only ================\n" + r1["text"])
print("\n================ SAMPLE RECEIPT mixed 2.6% + 8.1% ================\n" + r4["text"])
print("\nALL VAT SCENARIOS PASSED")
json.dump({"only26": o1["id"], "mixed": o4["id"]}, open("/tmp/vat_orders.json", "w"))

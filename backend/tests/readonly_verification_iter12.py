"""Iteration 12 – READ-ONLY verification pass (PrintNode is LIVE, do NOT create/accept orders).

- Manager login via POST /api/auth/staff/login {pin:'1234'} (safe – only returns a JWT, no side effect).
- GET /api/reports/closing for the requested dates.
- Recompute every driver entry independently from Mongo (READ ONLY).
- Confirm no automated test data leftovers.
- List distinct driver_shifts names and any orders whose driver_name still starts with 'Test'.
- Dumps results to /tmp/iter12_readonly.json for the test report.
"""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") if os.environ.get("EXPO_PUBLIC_BACKEND_URL") else None
if not BASE_URL:
    # Fallback – frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL not set"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

TZ_OFFSET = timedelta(hours=1)  # Europe/Zurich – Sep 17/18 in 2026 is still on CEST (UTC+2)
# But to be safe compute both possibilities. Sep is always CEST (DST), so UTC+2.
CEST = timezone(timedelta(hours=2))


def day_range_zurich(day_str: str):
    d = datetime.strptime(day_str, "%Y-%m-%d").date()
    # Zurich CEST in Sept -> UTC+2
    start_local = datetime(d.year, d.month, d.day, tzinfo=CEST)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def manager_login() -> str:
    r = requests.post(f"{BASE_URL}/api/auth/staff/login", json={"pin": "1234"}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


def api_get(path: str, token: str) -> dict:
    r = requests.get(f"{BASE_URL}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()
    return r.json()


async def recompute_closing_from_mongo(day_str: str) -> Dict[str, Any]:
    """Independent recomputation using the exact rules from the review request."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    start, end = day_range_zurich(day_str)
    docs = await db.orders.find({
        "type": "delivery",
        "driver": {"$ne": None},
        "created_at": {"$gte": start, "$lt": end},
    }).to_list(5000)

    # Group by (driver_slot, driver_name) – driver_name resolved to snapshot
    groups: Dict[tuple, List[dict]] = {}
    for o in docs:
        key = (o["driver"], o.get("driver_name"))
        groups.setdefault(key, []).append(o)

    out = []
    for (slot, name), items in sorted(groups.items(), key=lambda kv: (kv[0][0], (kv[0][1] or ""))):
        delivered = [o for o in items if o.get("status") in ("delivered", "completed")]
        cancelled = [o for o in items if o.get("status") == "cancelled"]
        in_progress = [o for o in items if o.get("status") not in ("delivered", "completed", "cancelled")]
        cash = round(sum(o["total"] for o in delivered if (o.get("collection_method") in (None, "cash"))), 2)
        terminal = round(sum(o["total"] for o in delivered if o.get("collection_method") == "terminal"), 2)
        paid = round(sum(o["total"] for o in delivered if o.get("collection_method") == "none"), 2)
        # Verify: every doc in items has driver == slot
        all_same_slot = all(o.get("driver") == slot for o in items)
        out.append({
            "driver": slot, "driver_name": name,
            "count_orders": len(items),
            "deliveries": len(delivered),
            "cancelled": len(cancelled),
            "in_progress": len(in_progress),
            "cash_expected": cash,
            "terminal_expected": terminal,
            "paid_no_collection": paid,
            "total": round(cash + terminal + paid, 2),
            "all_docs_have_correct_slot": all_same_slot,
            "order_numbers": [o.get("order_number") for o in sorted(items, key=lambda x: x["created_at"])],
        })
    client.close()
    return {"date": day_str, "groups": out}


async def check_test_leftovers() -> Dict[str, Any]:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    order_pat = re.compile(r"^(TEST|Test$|Test-|Demo$|Regression$|Sec$|NoKey$)")
    user_pat = re.compile(r"^TEST")
    shift_pat = re.compile(r"^(Test|TEST)")
    driver_name_pat = re.compile(r"^Test")

    # count orders
    orders_bad = await db.orders.count_documents({"customer.first_name": {"$regex": order_pat.pattern}})
    users_bad = await db.users.count_documents({"first_name": {"$regex": user_pat.pattern}})
    shifts_bad = await db.driver_shifts.count_documents({
        "name": {"$regex": shift_pat.pattern},
        "closed_at": {"$ne": None},
    })

    # distinct driver_shifts names
    shift_names = await db.driver_shifts.distinct("name")

    # orders with driver_name starting with 'Test' – full details
    test_driver_orders = await db.orders.find(
        {"driver_name": {"$regex": driver_name_pat.pattern}},
        {"order_number": 1, "customer": 1, "status": 1, "created_at": 1, "driver_name": 1, "driver": 1}
    ).to_list(50)

    ret = {
        "orders_matching_test_pattern": orders_bad,
        "users_matching_test_pattern": users_bad,
        "closed_driver_shifts_matching_test_pattern": shifts_bad,
        "distinct_driver_shift_names": sorted([n for n in shift_names if n]),
        "orders_with_test_driver_name": [
            {
                "order_number": o.get("order_number"),
                "customer": o.get("customer"),
                "status": o.get("status"),
                "created_at": o.get("created_at").isoformat() if o.get("created_at") else None,
                "driver": o.get("driver"),
                "driver_name": o.get("driver_name"),
            }
            for o in test_driver_orders
        ],
    }
    client.close()
    return ret


def compare_api_vs_recomputed(api_result: dict, recomputed: dict) -> List[Dict[str, Any]]:
    """Compare per (driver, driver_name) identity."""
    api_by_identity = {(d["driver"], d.get("driver_name")): d for d in api_result["drivers"]}
    recomp_by_identity = {(g["driver"], g.get("driver_name")): g for g in recomputed["groups"]}

    mismatches = []
    all_keys = set(api_by_identity) | set(recomp_by_identity)
    for k in sorted(all_keys, key=lambda x: (x[0], x[1] or "")):
        a = api_by_identity.get(k)
        r = recomp_by_identity.get(k)
        entry = {"identity": k, "api": None, "recomputed": None, "issues": []}
        if a is None:
            entry["issues"].append("in Mongo groups but MISSING from API response")
            entry["recomputed"] = r
            mismatches.append(entry)
            continue
        entry["api"] = {kk: a.get(kk) for kk in ("deliveries", "cancelled", "cash_expected", "terminal_expected", "paid_no_collection", "total")}
        entry["api"]["orders_len"] = len(a.get("orders", []))
        entry["api"]["order_numbers"] = [o.get("order_number") for o in a.get("orders", [])]
        if r is None:
            # API added it (e.g. person on duty with 0 orders today) – acceptable if all values are 0/empty
            if a.get("deliveries") == 0 and a.get("cancelled") == 0 and len(a.get("orders", [])) == 0:
                continue
            entry["issues"].append("API returns non-empty identity but Mongo has no orders for it")
            mismatches.append(entry)
            continue
        entry["recomputed"] = {kk: r.get(kk) for kk in ("count_orders", "deliveries", "cancelled", "in_progress", "cash_expected", "terminal_expected", "paid_no_collection", "total", "order_numbers", "all_docs_have_correct_slot")}
        # Compare
        for field in ("deliveries", "cancelled", "cash_expected", "terminal_expected", "paid_no_collection", "total"):
            if a.get(field) != r.get(field):
                entry["issues"].append(f"{field}: API={a.get(field)} vs recomputed={r.get(field)}")
        # len(orders) == deliveries + cancelled + in_progress
        expected_len = r["deliveries"] + r["cancelled"] + r["in_progress"]
        if len(a.get("orders", [])) != expected_len:
            entry["issues"].append(f"len(orders)={len(a.get('orders', []))} != deliveries+cancelled+in_progress={expected_len}")
        if r["count_orders"] != len(a.get("orders", [])):
            entry["issues"].append(f"Mongo has {r['count_orders']} orders vs API {len(a.get('orders', []))}")
        if not r["all_docs_have_correct_slot"]:
            entry["issues"].append("some Mongo docs in this identity have driver != slot")
        # order_numbers match
        api_nums = sorted(a.get("orders", []), key=lambda o: o.get("order_number") or "")
        recomp_nums = sorted(r["order_numbers"] or [])
        api_num_list = sorted([o.get("order_number") for o in a.get("orders", [])])
        if api_num_list != recomp_nums:
            entry["issues"].append(f"order_numbers differ: API={api_num_list} vs recomputed={recomp_nums}")
        if entry["issues"]:
            mismatches.append(entry)
    return mismatches


async def main():
    token = manager_login()
    result: Dict[str, Any] = {"base_url": BASE_URL, "closing_reports": {}}
    for day in ("2026-09-17", "2026-09-18", datetime.now(CEST).date().isoformat()):
        try:
            api_result = api_get(f"/api/reports/closing?date={day}", token)
        except Exception as e:
            result["closing_reports"][day] = {"error": str(e)}
            continue
        recomputed = await recompute_closing_from_mongo(day)
        mismatches = compare_api_vs_recomputed(api_result, recomputed)
        result["closing_reports"][day] = {
            "api_driver_count": len(api_result["drivers"]),
            "recomputed_group_count": len(recomputed["groups"]),
            "api_summary": [
                {"identity_key": d["identity_key"], "driver": d["driver"], "driver_name": d.get("driver_name"),
                 "deliveries": d["deliveries"], "cancelled": d["cancelled"], "cash_expected": d["cash_expected"],
                 "terminal_expected": d["terminal_expected"], "paid_no_collection": d["paid_no_collection"],
                 "total": d["total"], "orders_len": len(d.get("orders", []))}
                for d in api_result["drivers"]
            ],
            "recomputed_summary": recomputed["groups"],
            "mismatches": mismatches,
        }
    result["test_leftovers"] = await check_test_leftovers()
    with open("/tmp/iter12_readonly.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())

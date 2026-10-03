"""Carte Fidélité – digital twin of the paper loyalty card (server-side source of truth, customer ACCOUNTS only).

Rule: every eligible pizza = 1 stamp; every 10th pizza is 50 % off, always on the cheapest eligible pizza(s) of the order
(base pizza price only – supplements, options, drinks, desserts, delivery fee never discounted).

State (collection `loyalty`, _id = user id):
  stamps      0..9   stamps of the current cycle (final – completed orders only)
  rewards     ≥ 0    banked 50 % rewards not yet used (earned by a completed order that could not apply them itself)
  reserved    ≥ 0    rewards applied by orders that are still open (pending … delivering) – blocks double use
  lifetime_pizzas / rewards_earned / rewards_used – statistics

Order document: `loyalty` sub-document (see `plan()`), finalized exactly once when the order becomes completed or
cancelled (`finalize()`): completed -> stamps/rewards move; cancelled -> nothing is gained, reservation released.

Why open orders do NOT add stamps to the projection of a new order: using only FINAL state makes
rewards + floor((stamps + n) / 10) non-decreasing under completions, so a reward granted at creation can never be
"taken back" by another order completing or being cancelled – `rewards` never goes negative.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import ReturnDocument

PIZZA_CATEGORY_SLUGS = {"pizza", "creer-votre-pizza"}
BLOCK = 10        # pizzas per reward
RATE = 0.5        # 50 %

_pizza_cat_cache: Dict[str, Any] = {"ids": None, "at": None}


def _now():
    return datetime.now(timezone.utc)


async def pizza_category_ids(db) -> set:
    """Category ids (as str) whose products count as pizzas – cached 60 s."""
    now = _now()
    if _pizza_cat_cache["ids"] is not None and (now - _pizza_cat_cache["at"]).total_seconds() < 60:
        return _pizza_cat_cache["ids"]
    ids = {str(c["_id"]) async for c in db.categories.find({"slug": {"$in": list(PIZZA_CATEGORY_SLUGS)}}, {"_id": 1})}
    _pizza_cat_cache.update(ids=ids, at=now)
    return ids


def is_pizza(pdoc: dict, pizza_cats: set) -> bool:
    return str(pdoc.get("category_id")) in pizza_cats


async def get_state(db, user_id: str) -> dict:
    """The customer's loyalty document (created on first use)."""
    doc = await db.loyalty.find_one_and_update(
        {"_id": user_id},
        {"$setOnInsert": {"stamps": 0, "rewards": 0, "reserved": 0, "lifetime_pizzas": 0, "rewards_earned": 0, "rewards_used": 0,
                          "created_at": _now(), "updated_at": _now()}},
        upsert=True, return_document=ReturnDocument.AFTER)
    doc["reserved"] = max(0, int(doc.get("reserved", 0)))
    return doc


def plan(state: dict, units: List[float]) -> dict:
    """Reward plan for an order containing `units` eligible pizzas (one base price per pizza).
    rewards usable now = banked rewards + rewards completed by this order's own pizzas − rewards held by open orders."""
    n = len(units)
    stamps, rewards, reserved = int(state["stamps"]), int(state["rewards"]), int(state["reserved"])
    usable = max(0, rewards + (stamps + n) // BLOCK - reserved)
    r = min(n, usable)
    cheapest = sorted(units)[:r]
    amounts = [round(u * RATE, 2) for u in cheapest]
    return {"pizzas": n, "stamps_before": stamps, "rewards_before": rewards, "reserved_before": reserved,
            "rewards_applied": r, "discount": round(sum(amounts), 2), "discounted_prices": cheapest,
            "stamps_preview": (stamps + n) % BLOCK, "finalized": False}


async def reserve(db, info: dict) -> bool:
    """Hold the rewards this order applies so a simultaneous order cannot use them too.
    Compare-and-set on `reserved`: succeeds only if nobody else changed the reservation since the plan was computed."""
    r = int(info.get("rewards_applied", 0))
    if r <= 0:
        return True
    res = await db.loyalty.update_one({"_id": info["user_id"], "reserved": info["reserved_before"]},
                                      {"$inc": {"reserved": r}, "$set": {"updated_at": _now()}})
    return res.matched_count == 1


async def finalize(db, order: dict, outcome: str) -> None:
    """Called when an order reaches `completed` or `cancelled`. Idempotent: the order's loyalty block is claimed
    atomically first, so a retried / duplicated status call can never add stamps or consume a reward twice."""
    info = order.get("loyalty")
    if not info or info.get("finalized") or not info.get("user_id"):
        return
    now = _now()
    claimed = await db.orders.find_one_and_update(
        {"_id": order["_id"], "loyalty.finalized": {"$ne": True}},
        {"$set": {"loyalty.finalized": True, "loyalty.finalized_at": now, "loyalty.outcome": outcome}})
    if not claimed:
        return
    uid, p, r = info["user_id"], int(info.get("pizzas", 0)), int(info.get("rewards_applied", 0))
    await get_state(db, uid)  # make sure the document exists
    if outcome == "completed":
        # single atomic pipeline update: stamps = (stamps + p) mod 10, rewards += completed blocks − rewards used here
        total = {"$add": ["$stamps", p]}
        blocks = {"$floor": {"$divide": [total, BLOCK]}}
        new = await db.loyalty.find_one_and_update({"_id": uid}, [{"$set": {
            "stamps": {"$mod": [total, BLOCK]},
            "rewards": {"$max": [0, {"$add": ["$rewards", blocks, -r]}]},
            "reserved": {"$max": [0, {"$subtract": ["$reserved", r]}]},
            "lifetime_pizzas": {"$add": ["$lifetime_pizzas", p]},
            "rewards_earned": {"$add": ["$rewards_earned", blocks]},
            "rewards_used": {"$add": ["$rewards_used", r]},
            "updated_at": now,
        }}], return_document=ReturnDocument.AFTER)
        await db.orders.update_one({"_id": order["_id"]}, {"$set": {"loyalty.stamps_after": new["stamps"], "loyalty.rewards_after": new["rewards"]}})
    else:  # cancelled / refused: no stamps, the held reward becomes available again
        await db.loyalty.update_one({"_id": uid}, [{"$set": {"reserved": {"$max": [0, {"$subtract": ["$reserved", r]}]}, "updated_at": now}}])


async def summary(db, user_id: str) -> dict:
    """What the customer (and the Manager) sees: progress of the current cycle + reward availability (read-only)."""
    s = await db.loyalty.find_one({"_id": user_id}) or {"stamps": 0, "rewards": 0, "reserved": 0}
    open_orders = await db.orders.count_documents({"loyalty.user_id": user_id, "loyalty.finalized": {"$ne": True}})
    available = max(0, int(s["rewards"]) - int(s["reserved"]))
    return {"stamps": int(s["stamps"]), "block": BLOCK, "rate": RATE,
            "rewards_available": available, "rewards_reserved": int(s["reserved"]), "open_orders": open_orders,
            "lifetime_pizzas": int(s.get("lifetime_pizzas", 0)), "rewards_earned": int(s.get("rewards_earned", 0)),
            "rewards_used": int(s.get("rewards_used", 0)), "updated_at": s.get("updated_at")}

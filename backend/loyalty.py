"""Carte Fidélité – digital twin of the paper loyalty card (server-side source of truth, customer ACCOUNTS only).

Rules (final): 32 cm pizza = 1 stamp, 40 cm = 1 stamp, 50 cm = 2 stamps; other pizzas (26 cm Bambino, sizeless Calzone),
drinks, desserts, extras and delivery fees never count. Every 10 stamps = 1 reward = 50 % off ONE 32 cm pizza only
(cheapest 32 cm base price of the order; supplements/options never discounted). A 40 / 50 cm pizza is never discounted.
A reward is consumed only when a 32 cm pizza is in the order – otherwise it stays available for a future order.

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
BLOCK = 10        # stamps per reward
RATE = 0.5        # 50 %
STAMPS_BY_SIZE = {"32": 1, "40": 1, "50": 2}   # any other size (26 cm Bambino/kids) -> 0 stamps, never discounted
CALZONE_STAMPS = 1                              # Calzone (pizza without size) = 1 stamp like a 32 cm, but never discounted
REWARD_SIZE = "32"                              # the reward applies to ONE 32 cm pizza only

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


def is_calzone(pdoc: dict) -> bool:
    return any("calzone" in str((pdoc.get("name") or {}).get(lang, "")).lower() for lang in ("fr", "de"))


def stamps_for(pdoc: dict, size_key: Optional[str], pizza_cats: set) -> int:
    """Stamps ONE pizza of this product/size earns (0 = does not take part in the Carte Fidélité)."""
    if not is_pizza(pdoc, pizza_cats):
        return 0
    if size_key:
        return STAMPS_BY_SIZE.get(str(size_key), 0)
    return CALZONE_STAMPS if is_calzone(pdoc) else 0


async def get_state(db, user_id: str) -> dict:
    """The customer's loyalty document (created on first use)."""
    doc = await db.loyalty.find_one_and_update(
        {"_id": user_id},
        {"$setOnInsert": {"stamps": 0, "rewards": 0, "reserved": 0, "lifetime_pizzas": 0, "rewards_earned": 0, "rewards_used": 0,
                          "created_at": _now(), "updated_at": _now()}},
        upsert=True, return_document=ReturnDocument.AFTER)
    doc["reserved"] = max(0, int(doc.get("reserved", 0)))
    return doc


def plan(state: dict, pizzas: List[tuple]) -> dict:
    """Reward plan for an order. `pizzas` = one (size_key, base_price, stamps) per counted pizza (stamps > 0).
    rewards usable now = banked rewards + rewards completed by this order's own stamps − rewards held by open orders;
    they are applied only to 32 cm pizzas (cheapest first) – without a 32 cm pizza nothing is consumed (`rewards_kept`)."""
    n = len(pizzas)
    total = sum(int(st) for _s, _p, st in pizzas)
    eligible = sorted(p for s, p, _st in pizzas if str(s) == REWARD_SIZE)
    stamps, rewards, reserved = int(state["stamps"]), int(state["rewards"]), int(state["reserved"])
    usable = max(0, rewards + (stamps + total) // BLOCK - reserved)
    r = min(len(eligible), usable)
    cheapest = eligible[:r]
    amounts = [round(u * RATE, 2) for u in cheapest]
    return {"pizzas": n, "stamps": total, "stamps_before": stamps, "rewards_before": rewards, "reserved_before": reserved,
            "rewards_applied": r, "rewards_kept": usable - r, "discount": round(sum(amounts), 2), "discounted_prices": cheapest,
            "stamps_preview": (stamps + total) % BLOCK, "finalized": False}


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
    st = int(info.get("stamps", p))  # stamps earned by this order (orders created before the size rule: 1 per pizza)
    await get_state(db, uid)  # make sure the document exists
    if outcome == "completed":
        # single atomic pipeline update: stamps = (stamps + st) mod 10, rewards += completed blocks − rewards used here
        total = {"$add": ["$stamps", st]}
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

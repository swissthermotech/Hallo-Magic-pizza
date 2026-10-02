"""Time-slot lead time (Settings.min_lead_minutes, default 15) – pure hours.py rules + POST /orders validation path.

Expected with closing 22:00, 15-min grid, delivery cutoff 15, lead 15:
  pickup   21:15 -> 21:30 21:45 22:00 | 21:30 -> 21:45 22:00 | 21:45 -> 22:00 | 21:46 -> none (ASAP still ok until 21:59)
  delivery 21:15 -> 21:30 21:45       | 21:30 -> 21:45       | 21:31 -> none  (ASAP still ok until 21:44)
Test names contain "requires" so the legacy autouse manager-token fixture (PIN login) is skipped.
compute_order() runs against the sandbox DB with a frozen clock; it never creates / prints an order.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hours  # noqa: E402

TZ = ZoneInfo("Europe/Zurich")
FRIDAY = datetime(2026, 10, 2, tzinfo=TZ)  # a normal open evening: 11:00-14:00, 17:00-22:00


class S:
    def __init__(self, lead=15, cutoff=15, evening_first=""):
        self.opening_hours = {"fri": "11:00-14:00, 17:00-22:00", "sat": "11:00-14:00, 17:00-22:00"}
        self.delivery_cutoff_minutes = cutoff
        self.min_lead_minutes = lead
        self.first_delivery = {"lunch": "", "evening": evening_first}


def at(hm: str) -> datetime:
    h, m = map(int, hm.split(":"))
    return FRIDAY.replace(hour=h, minute=m)


EXPECTED = {
    #  now      pickup slots                                          delivery slots                  asap_p asap_d
    "18:00": (["18:15", "18:30", "18:45", "19:00", "19:15", "19:30", "19:45", "20:00", "20:15", "20:30", "20:45", "21:00", "21:15", "21:30", "21:45", "22:00"],
              ["18:15", "18:30", "18:45", "19:00", "19:15", "19:30", "19:45", "20:00", "20:15", "20:30", "20:45", "21:00", "21:15", "21:30", "21:45"], True, True),
    "19:00": (["19:15", "19:30", "19:45", "20:00", "20:15", "20:30", "20:45", "21:00", "21:15", "21:30", "21:45", "22:00"],
              ["19:15", "19:30", "19:45", "20:00", "20:15", "20:30", "20:45", "21:00", "21:15", "21:30", "21:45"], True, True),
    "20:00": (["20:15", "20:30", "20:45", "21:00", "21:15", "21:30", "21:45", "22:00"], ["20:15", "20:30", "20:45", "21:00", "21:15", "21:30", "21:45"], True, True),
    "21:00": (["21:15", "21:30", "21:45", "22:00"], ["21:15", "21:30", "21:45"], True, True),
    "21:01": (["21:30", "21:45", "22:00"], ["21:30", "21:45"], True, True),
    "21:15": (["21:30", "21:45", "22:00"], ["21:30", "21:45"], True, True),
    "21:16": (["21:45", "22:00"], ["21:45"], True, True),
    "21:30": (["21:45", "22:00"], ["21:45"], True, True),
    "21:31": (["22:00"], [], True, True),
    "21:44": (["22:00"], [], True, True),
    "21:45": (["22:00"], [], True, False),
    "21:46": ([], [], True, False),
    "21:59": ([], [], True, False),
    "22:00": ([], [], False, False),
}


@pytest.mark.parametrize("now_hm", list(EXPECTED.keys()))
def test_requires_evening_slots_lead_15(now_hm):
    pickup, delivery, asap_p, asap_d = EXPECTED[now_hm]
    st = hours.ordering_status(S(), at(now_hm))
    assert st["pickup_slots"] == pickup, (now_hm, st["pickup_slots"])
    assert st["delivery_slots"] == delivery, (now_hm, st["delivery_slots"])
    assert st["asap_pickup"] is asap_p and st["asap_delivery"] is asap_d, (now_hm, st["asap_pickup"], st["asap_delivery"])
    # the per-day schedule used by both checkouts (days[today]) is exactly the same list
    today = [d for d in st["days"] if d["is_today"]]
    if pickup:
        assert today and today[0]["pickup_slots"] == pickup and today[0]["delivery_slots"] == delivery
    else:
        assert not today  # today is dropped from the day picker once nothing can be scheduled
    # tomorrow always keeps the full windows (unchanged)
    tomorrow = next(d for d in st["days"] if d["is_tomorrow"])
    assert tomorrow["pickup_slots"][0] == "11:00" and tomorrow["pickup_slots"][-1] == "22:00" and tomorrow["delivery_slots"][-1] == "21:45"


def test_requires_lead_is_configurable():
    # 30 = previous hard-coded behaviour; 0 = next grid point from now
    assert hours.ordering_status(S(lead=30), at("21:15"))["pickup_slots"] == ["21:45", "22:00"]
    assert hours.ordering_status(S(lead=30), at("21:15"))["delivery_slots"] == ["21:45"]
    assert hours.ordering_status(S(lead=0), at("21:50"))["pickup_slots"] == ["22:00"]
    assert hours.ordering_status(S(lead=45), at("21:15"))["pickup_slots"] == ["22:00"]
    # missing attribute (old settings document) -> default 15
    s = S(); del s.min_lead_minutes
    assert hours.ordering_status(s, at("21:15"))["pickup_slots"] == ["21:30", "21:45", "22:00"]


def test_requires_other_rules_unchanged():
    # delivery cutoff still applied, first-delivery override still applied, ASAP rules identical to before
    assert hours.ordering_status(S(cutoff=30), at("21:00"))["delivery_slots"] == ["21:15", "21:30"]
    closed = hours.ordering_status(S(evening_first="closed"), at("19:00"))
    assert closed["delivery_slots"] == [] and closed["asap_delivery"] is False and closed["asap_pickup"] is True
    late = hours.ordering_status(S(evening_first="20:30"), at("19:00"))
    assert late["delivery_slots"][0] == "20:30" and late["delivery_from"] == "20:30"
    # before opening: ASAP = first time after opening, slots from opening
    pre = hours.ordering_status(S(), at("16:40"))
    assert pre["asap_pickup"] and pre["asap_from"] == "17:00" and pre["pickup_slots"][0] == "17:00" and pre["delivery_slots"][0] == "17:00"


# ---- POST /orders validation path (compute_order) with a frozen clock – same hours.py rules ----------------------
def _frozen(server, when: datetime):
    class FrozenDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return when.astimezone(tz) if tz else when.replace(tzinfo=None)
    return FrozenDT


async def _try_order(server, when, order_type, requested_time):
    from fastapi import HTTPException
    product = await server.db.products.find_one({"active": {"$ne": False}, "sizes.0": {"$exists": True}})
    body = server.OrderIn(
        type=order_type,
        items=[server.OrderItemIn(product_id=str(product["_id"]), quantity=1, size_key=product["sizes"][0]["key"])],
        customer=server.CustomerIn(first_name="Slot", last_name="Test", phone="0790000001", email="slot.test@example.com"),
        address=server.AddressIn(street="Route de Chésalles", number="19", npa="1723", city="Marly") if order_type == "delivery" else None,
        requested_time=requested_time, age_confirmed=True, language="fr", payment_method="cash",
    )
    real = server.datetime
    server.datetime = _frozen(server, when)
    try:
        await server.compute_order(body, None, enforce_minimum=False)
        return "ok"
    except HTTPException as e:
        return e.detail
    finally:
        server.datetime = real


def test_requires_post_orders_validation_uses_same_rules():
    import server  # sandbox backend module (local Mongo)

    async def run():
        s = await server.get_settings()
        assert s.min_lead_minutes == 15 and s.delivery_cutoff_minutes == 15 and s.opening_hours["fri"] == "11:00-14:00, 17:00-22:00"
        out = {}
        out["pickup 21:15 -> 21:30"] = await _try_order(server, at("21:15"), "pickup", "21:30")
        out["pickup 21:15 -> 22:00"] = await _try_order(server, at("21:15"), "pickup", "22:00")
        out["pickup 21:15 -> 21:15"] = await _try_order(server, at("21:15"), "pickup", "21:15")
        out["pickup 21:45 -> 22:00"] = await _try_order(server, at("21:45"), "pickup", "22:00")
        out["pickup 21:46 -> 22:00"] = await _try_order(server, at("21:46"), "pickup", "22:00")
        out["pickup 21:46 -> asap"] = await _try_order(server, at("21:46"), "pickup", "asap")
        out["delivery 21:15 -> 21:45"] = await _try_order(server, at("21:15"), "delivery", "21:45")
        out["delivery 21:15 -> 22:00"] = await _try_order(server, at("21:15"), "delivery", "22:00")
        out["delivery 21:31 -> 21:45"] = await _try_order(server, at("21:31"), "delivery", "21:45")
        out["delivery 21:31 -> asap"] = await _try_order(server, at("21:31"), "delivery", "asap")
        out["delivery 21:45 -> asap"] = await _try_order(server, at("21:45"), "delivery", "asap")
        out["delivery 19:00 -> 19:15"] = await _try_order(server, at("19:00"), "delivery", "19:15")
        return out

    out = asyncio.run(run())
    for k, v in out.items():
        print(f"  {k:<28} {v}")
    assert out["pickup 21:15 -> 21:30"] == "ok"
    assert out["pickup 21:15 -> 22:00"] == "ok"
    assert out["pickup 21:15 -> 21:15"].startswith("Heure non disponible")
    assert out["pickup 21:45 -> 22:00"] == "ok"
    assert out["pickup 21:46 -> 22:00"].startswith("Heure non disponible")
    assert out["pickup 21:46 -> asap"] == "ok"
    assert out["delivery 21:15 -> 21:45"] == "ok"
    assert out["delivery 21:15 -> 22:00"].startswith("Heure non disponible")
    assert out["delivery 21:31 -> 21:45"].startswith("Heure non disponible")
    assert out["delivery 21:31 -> asap"] == "ok"
    assert out["delivery 21:45 -> asap"].startswith("Livraison indisponible")
    assert out["delivery 19:00 -> 19:15"] == "ok"

"""Fully closed calendar day (test names contain "requires": skips the legacy conftest PIN fixture). (opening hours = source of truth) + requested DATE on kitchen tickets.
Runs in-process against the sandbox DB: NO order is created, NO print job, settings are patched in memory only."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import hours as hm  # noqa: E402
import server  # noqa: E402
from server import TZ, CustomerIn, OrderIn, OrderItemIn, db  # noqa: E402

HOURS = {"mon": "", "tue": "17:00-22:00", "wed": "11:00-14:00, 17:00-22:00", "thu": "11:00-14:00, 17:00-22:00",
         "fri": "11:00-14:00, 17:00-22:00", "sat": "11:00-14:00, 17:00-22:00", "sun": "11:00-14:00, 17:00-22:00"}
S = SimpleNamespace(opening_hours=HOURS, delivery_cutoff_minutes=15, min_lead_minutes=15, first_delivery={"lunch": "", "evening": ""})
MON = datetime(2026, 10, 5, 12, 0, tzinfo=TZ)   # Monday – fully closed
TUE = datetime(2026, 10, 6, 12, 0, tzinfo=TZ)   # Tuesday – open 17:00-22:00


def test_requires_closed_day_detection_uses_opening_hours():
    assert hm.closed_all_day(S, MON) is True
    assert hm.closed_all_day(S, MON.replace(hour=0, minute=1)) is True      # whole calendar day
    assert hm.closed_all_day(S, MON.replace(hour=23, minute=59)) is True
    assert hm.closed_all_day(S, TUE) is False
    # not hard-coded on Monday: close Wednesday instead -> Wednesday blocked, Monday open
    alt = SimpleNamespace(**{**S.__dict__, "opening_hours": {**HOURS, "mon": "11:00-14:00", "wed": ""}})
    assert hm.closed_all_day(alt, MON) is False
    assert hm.closed_all_day(alt, datetime(2026, 10, 7, 12, 0, tzinfo=TZ)) is True


def test_requires_ordering_status_on_closed_day_offers_nothing():
    st = hm.ordering_status(S, MON)
    assert st["closed_today"] is True
    assert st["days"] == [], "no tomorrow / future dates on a fully closed day"
    assert st["asap_pickup"] is False and st["asap_delivery"] is False
    assert st["pickup_slots"] == [] and st["delivery_slots"] == []
    assert st["next_open"] == "mardi 17:00"


def test_requires_ordering_reopens_automatically_next_day_rules_unchanged():
    # Tuesday 00:30 – the closed day is over: normal rules (ASAP = first time after opening, scheduled days) apply again
    st = hm.ordering_status(S, TUE.replace(hour=0, minute=30))
    assert st["closed_today"] is False
    assert st["asap_pickup"] is True and st["asap_from"] == "17:00"
    assert st["days"] and st["days"][0]["date"] == "2026-10-06"
    # Tuesday 20:50 – open day, exact same slot grid / lead / cutoff as before
    st = hm.ordering_status(S, TUE.replace(hour=20, minute=50))
    assert st["closed_today"] is False and st["open_now"] is True
    assert st["pickup_slots"] == ["21:15", "21:30", "21:45", "22:00"]      # 15-min grid, 15-min lead rounded up
    assert st["delivery_slots"] == ["21:15", "21:30", "21:45"]             # 15-min delivery cutoff
    assert st["delivery_from"] == "21:05"
    days = {d["date"]: d for d in st["days"]}
    assert "2026-10-12" not in days, "closed Monday skipped in the scheduled days"
    assert days["2026-10-07"]["pickup_slots"][0] == "11:00" and len(days["2026-10-07"]["pickup_slots"]) == 34


async def _compute(body, enforce_hours=True):
    return await server.compute_order(body, None, enforce_minimum=False, enforce_hours=enforce_hours, allocate_number=False)


def _body(**kw):
    marg = asyncio.get_event_loop().run_until_complete(db.products.find_one({"name.fr": "Margherita"}))
    base = dict(type="pickup", items=[OrderItemIn(product_id=str(marg["_id"]), quantity=1, size_key="32")],
                customer=CustomerIn(first_name="Closed", phone="079 555 01 04", email="c@example.com"), requested_time="asap", age_confirmed=True)
    base.update(kw)
    return OrderIn(**base)


def test_requires_orders_rejected_server_side_on_closed_day(monkeypatch):
    """Server-side rule: whatever the client sends (ASAP, exact time, or a FUTURE date), a customer order is refused
    while the current calendar day is fully closed. Staff phone orders (enforce_hours=False) are unaffected."""
    real_settings = asyncio.get_event_loop().run_until_complete(server.get_settings())
    today = hm.DAYS[datetime.now(TZ).weekday()]
    closed = real_settings.model_copy(update={"opening_hours": {**real_settings.opening_hours, today: ""}})

    async def fake_settings():
        return closed
    monkeypatch.setattr(server, "get_settings", fake_settings)
    tomorrow = (datetime.now(TZ) + timedelta(days=1)).date()
    p_slots, _ = hm.slots_for_day(closed, tomorrow, datetime.now(TZ))
    for label, body in [("ASAP today", _body()),
                        ("exact time today", _body(requested_time="19:30")),
                        ("tomorrow (valid slot)", _body(requested_time=p_slots[0] if p_slots else "19:00", requested_date=tomorrow.isoformat())),
                        ("in 3 days", _body(requested_time="19:00", requested_date=(tomorrow + timedelta(days=2)).isoformat()))]:
        with pytest.raises(server.HTTPException) as e:
            asyncio.get_event_loop().run_until_complete(_compute(body))
        assert e.value.status_code == 400 and e.value.detail == hm.CLOSED_TODAY_FR, label
    # staff override path (phone orders) still computes
    o = asyncio.get_event_loop().run_until_complete(_compute(_body(requested_time="19:30"), enforce_hours=False))
    assert o.total == 14.0


def test_requires_open_day_scheduled_order_still_works():
    """Normal open day (sandbox settings, today): a scheduled order for the next open day with a proposed slot computes."""
    settings = asyncio.get_event_loop().run_until_complete(server.get_settings())
    now = datetime.now(TZ)
    if hm.closed_all_day(settings, now):
        pytest.skip("sandbox is on a closed day right now")
    days = hm.ordering_status(settings, now)["days"]
    future = next(d for d in days if not d["is_today"])
    o = asyncio.get_event_loop().run_until_complete(_compute(_body(requested_time=future["pickup_slots"][5], requested_date=future["date"])))
    assert o.requested_date == future["date"] and o.requested_time == future["pickup_slots"][5] and o.total == 14.0
    # ...and a slot that is not proposed is still refused (unchanged rule)
    with pytest.raises(server.HTTPException):
        asyncio.get_event_loop().run_until_complete(_compute(_body(requested_time="03:15", requested_date=future["date"])))


def _utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=TZ).astimezone(timezone.utc).replace(tzinfo=None)  # Mongo-style naive UTC


def _order(**kw):
    o = {"order_number": 1601, "type": "delivery", "status": "accepted", "source": "web", "payment_method": "cash", "total": 36.0, "subtotal": 36.0,
         "extras_total": 0.0, "delivery_fee": 0.0, "customer": {"first_name": "Anna", "last_name": "Test", "phone": "079 555 01 04", "email": "a@b.ch"},
         "address": {"street": "Rue Test", "number": "1", "npa": "1723", "city": "Marly"}, "items": [], "created_at": _utc(2026, 10, 5, 18, 36),
         "accepted_at": _utc(2026, 10, 6, 16, 15), "requested_date": "2026-10-06", "requested_time": "19:15", "estimated_ready_at": _utc(2026, 10, 6, 19, 15),
         "scheduled_for": _utc(2026, 10, 6, 19, 15)}
    o.update(kw)
    return o


def test_requires_ticket_shows_requested_date_received_and_accepted():
    settings = asyncio.get_event_loop().run_until_complete(server.get_settings())
    t = server.strip_escpos(server.build_ticket(_order(), settings))
    lines = [l.strip() for l in t.splitlines()]
    assert "LIVRAISON DEMANDÉE" in lines and "MARDI 06.10.2026" in lines and "19:15" in lines
    assert lines.index("LIVRAISON DEMANDÉE") < lines.index("MARDI 06.10.2026") < lines.index("19:15")
    assert lines.index("MARDI 06.10.2026") < 12, "requested date is near the top of the ticket"
    assert "Commande reçue :    05.10.2026 · 18:36" in lines
    assert "Commande acceptée : 06.10.2026 · 16:15" in lines
    # the three moments are all different and all readable with their full date
    assert t.count("05.10.2026") >= 1 and t.count("06.10.2026") >= 2
    # bottom audit trail also carries the full date
    assert "Recue:    05.10.2026 · 18:36" in lines and "Acceptee: 06.10.2026 · 16:15" in lines
    # pickup wording
    tp = server.strip_escpos(server.build_ticket(_order(type="pickup"), settings))
    assert "RETRAIT DEMANDÉ" in tp and "MARDI 06.10.2026" in tp and "LIVRAISON" not in tp.split("RETRAIT DEMANDÉ")[1][:200]


def test_requires_ticket_same_day_and_asap_orders_carry_their_date():
    settings = asyncio.get_event_loop().run_until_complete(server.get_settings())
    # same-day exact time: requested day = day the order was placed
    same = _order(created_at=_utc(2026, 10, 7, 11, 2), accepted_at=_utc(2026, 10, 7, 11, 5), requested_date=None, requested_time="12:30",
                  estimated_ready_at=_utc(2026, 10, 7, 12, 30), scheduled_for=None, type="pickup")
    t = server.strip_escpos(server.build_ticket(same, settings))
    assert "RETRAIT DEMANDÉ" in t and "MERCREDI 07.10.2026" in t and "12:30" in t
    assert "Commande reçue :    07.10.2026 · 11:02" in t and "Commande acceptée : 07.10.2026 · 11:05" in t
    # ASAP: date line + DÈS QUE POSSIBLE + confirmed time
    asap = _order(created_at=_utc(2026, 10, 7, 18, 0), accepted_at=_utc(2026, 10, 7, 18, 1), requested_date=None, requested_time="asap",
                  estimated_ready_at=_utc(2026, 10, 7, 18, 31), scheduled_for=None)
    t = server.strip_escpos(server.build_ticket(asap, settings))
    assert "LIVRAISON DEMANDÉE" in t and "MERCREDI 07.10.2026" in t and "DÈS QUE POSSIBLE" in t and "18:31" in t
    # pending (not yet accepted) ticket preview: no accepted line, received line present
    pend = _order(accepted_at=None, estimated_ready_at=None, status="pending")
    t = server.strip_escpos(server.build_ticket(pend, settings))
    assert "Commande reçue :    05.10.2026 · 18:36" in t and "Commande acceptée" not in t and "MARDI 06.10.2026" in t and "19:15" in t
    # staff changed the time: both shown, requested day unchanged
    chg = _order(estimated_ready_at=_utc(2026, 10, 6, 19, 45))
    t = server.strip_escpos(server.build_ticket(chg, settings))
    assert "DEMANDÉE 19:15" in t and "CONFIRMÉE 19:45" in t and "MARDI 06.10.2026" in t

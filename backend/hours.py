"""Customer ordering hours (Europe/Zurich). Pure functions – used by GET /settings (status + slots) and POST /orders validation.
Settings.opening_hours: {"mon": "" (closed) | "11:00-14:00, 17:00-22:00", ...}
Settings.delivery_cutoff_minutes: last delivery order N minutes before each window closes (15 -> 13:45 / 21:45).
Settings.first_delivery: {"lunch": "11:30" | "closed" | "", "evening": "17:00" | ...} – manager quick control per service."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_FR = {"mon": "lundi", "tue": "mardi", "wed": "mercredi", "thu": "jeudi", "fri": "vendredi", "sat": "samedi", "sun": "dimanche"}


def _hm(s: str) -> int:
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def _fmt(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def windows(opening_hours: Dict[str, str], day: str) -> List[Tuple[int, int]]:
    spec = (opening_hours or {}).get(day, "") or ""
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            try:
                out.append((_hm(a), _hm(b)))
            except ValueError:
                continue
    return sorted(out)


def service_of(start: int) -> str:
    return "lunch" if start < 16 * 60 else "evening"


def first_delivery_for(first_delivery: Dict[str, str], win: Tuple[int, int]) -> Optional[int]:
    """Earliest delivery minute for a window: manager value if set (or None if 'closed'), else window start."""
    v = (first_delivery or {}).get(service_of(win[0]), "") or ""
    if v.lower() in ("closed", "fermee", "fermée"):
        return None
    try:
        return max(win[0], _hm(v)) if v else win[0]
    except ValueError:
        return win[0]


def ordering_status(settings, now: datetime, step: int = 15) -> dict:
    """open_now / pickup_open / delivery_open, next opening text, and valid ASAP-relative slots for today."""
    oh = settings.opening_hours or {}
    cutoff = getattr(settings, "delivery_cutoff_minutes", 15) or 15
    fd = getattr(settings, "first_delivery", {}) or {}
    day = DAYS[now.weekday()]
    cur = now.hour * 60 + now.minute
    pickup_open = delivery_open = False
    delivery_from: Optional[int] = None
    pickup_slots: List[str] = []
    delivery_slots: List[str] = []
    for a, b in windows(oh, day):
        if a <= cur < b:
            pickup_open = True
        fdl = first_delivery_for(fd, (a, b))
        if fdl is not None and a <= cur < b - cutoff:
            delivery_open = True
            delivery_from = max(fdl, cur + 30)
        # slots: 15-min grid, at least 30 min from now, inside the window
        t = ((max(cur + 30, a) + step - 1) // step) * step
        while t <= b:
            if a <= t:
                pickup_slots.append(_fmt(t))
                if fdl is not None and t >= fdl and t <= b - cutoff:
                    delivery_slots.append(_fmt(t))
            t += step
    next_open = None
    if not pickup_open:
        for i in range(0, 8):
            d = now + timedelta(days=i)
            for a, b in windows(oh, DAYS[d.weekday()]):
                if i == 0 and a <= cur:
                    continue
                next_open = f"{DAY_FR[DAYS[d.weekday()]]} {_fmt(a)}" if i else f"aujourd'hui {_fmt(a)}"
                break
            if next_open:
                break
    # "Dès que possible" BEFORE opening: the order is accepted now and means "first available time after opening today"
    asap_pickup, asap_delivery, asap_from = pickup_open, delivery_open, None
    if not pickup_open:
        for a, b in windows(oh, day):
            if a > cur:
                asap_pickup, asap_from = True, a
                fdl = first_delivery_for(fd, (a, b))
                asap_delivery = fdl is not None and fdl <= b - cutoff
                break
    return {"open_now": pickup_open, "pickup_open": pickup_open, "delivery_open": delivery_open,
            "asap_pickup": asap_pickup, "asap_delivery": asap_delivery, "asap_from": _fmt(asap_from) if asap_from is not None else None,
            "delivery_from": _fmt(delivery_from) if delivery_from is not None else None, "next_open": next_open,
            "pickup_slots": pickup_slots, "delivery_slots": delivery_slots, "day": day,
            "days": upcoming_days(settings, now, step)}


def slots_for_day(settings, day_date, now: datetime, step: int = 15) -> Tuple[List[str], List[str]]:
    """Valid pickup / delivery slots for a calendar day. Today: at least 30 min from now; future days: full windows."""
    oh = settings.opening_hours or {}
    cutoff = getattr(settings, "delivery_cutoff_minutes", 15) or 15
    fd = getattr(settings, "first_delivery", {}) or {}
    today = day_date == now.date()
    cur = now.hour * 60 + now.minute if today else -1
    pickup, delivery = [], []
    for a, b in windows(oh, DAYS[day_date.weekday()]):
        fdl = first_delivery_for(fd, (a, b)) if today else a  # the manager's "first delivery" override is a same-day control
        t = ((max(cur + 30, a) + step - 1) // step) * step
        while t <= b:
            pickup.append(_fmt(t))
            if fdl is not None and t >= fdl and t <= b - cutoff:
                delivery.append(_fmt(t))
            t += step
    return pickup, delivery


def upcoming_days(settings, now: datetime, step: int = 15, horizon: int = 7) -> List[dict]:
    """Scheduled ordering: the next `horizon` calendar days that still have at least one slot (closed days are skipped)."""
    out = []
    for i in range(0, horizon + 1):
        d = (now + timedelta(days=i)).date()
        p, dl = slots_for_day(settings, d, now, step)
        if not p:
            continue
        out.append({"date": d.isoformat(), "weekday": DAY_FR[DAYS[d.weekday()]], "is_today": i == 0, "is_tomorrow": i == 1,
                    "pickup_slots": p, "delivery_slots": dl})
    return out

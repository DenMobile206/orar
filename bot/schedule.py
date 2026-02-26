"""Week-type and calendar calculations for the teaching semester."""
from datetime import date, timedelta
from typing import Optional, List, Tuple
import datetime as _dt

import pytz

TZ = pytz.timezone("Europe/Bucharest")

# Each tuple is (monday_of_first_week, monday_of_first_week_of_next_period)
# Periods are (inclusive start, inclusive end).  Both starts are Mondays.
TEACHING_PERIODS: List[Tuple[date, date]] = [
    (date(2026, 2, 23), date(2026, 4, 9)),   # 7 weeks (weeks 1-7)
    (date(2026, 4, 20), date(2026, 6, 5)),   # 7 weeks (weeks 8-14)
]

VACATION_START = date(2026, 4, 10)
VACATION_END = date(2026, 4, 19)

DAYS_RO = {
    0: "Luni",
    1: "Marți",
    2: "Miercuri",
    3: "Joi",
    4: "Vineri",
}


def is_vacation(d: date) -> bool:
    return VACATION_START <= d <= VACATION_END


def get_day_name(d: date) -> Optional[str]:
    """Return Romanian day name or None if weekend."""
    return DAYS_RO.get(d.weekday())


def build_teaching_calendar() -> List[Tuple[int, date]]:
    """Return list of (week_index, monday_date) for all 14 teaching weeks.

    Week index 0 → IMPAR, 1 → PAR, 2 → IMPAR, …
    """
    weeks: List[Tuple[int, date]] = []
    week_idx = 0
    for start, end in TEACHING_PERIODS:
        # Both starts are known Mondays; align defensively
        monday = start - timedelta(days=start.weekday())
        while monday <= end:
            if monday + timedelta(days=6) >= start:
                weeks.append((week_idx, monday))
                week_idx += 1
            monday += timedelta(weeks=1)
    return weeks


def get_week_type(d: date, override: Optional[str] = None) -> Optional[str]:
    """Return 'impar'/'par' for *d*, or None if outside teaching periods.

    *override* ('impar' | 'par') bypasses auto-detection.
    """
    if is_vacation(d):
        return None
    if override in ("impar", "par"):
        return override

    for week_idx, monday in build_teaching_calendar():
        if monday <= d <= monday + timedelta(days=6):
            return "impar" if week_idx % 2 == 0 else "par"
    return None


def now_bucharest() -> _dt.datetime:
    return _dt.datetime.now(TZ)


def today_bucharest() -> date:
    return now_bucharest().date()

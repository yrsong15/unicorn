"""Weekly sauna sessions and time. Weeks run Monday through Sunday, like mileage."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import Run
from app.services.mileage import range_start, week_start


@dataclass
class SaunaWeek:
    start: date
    sessions: int = 0
    seconds: float = 0.0
    ids: list[int] = field(default_factory=list)


def bucket_sauna_weeks(saunas: list[Run], start: date, end: date) -> list[SaunaWeek]:
    """Zero-filled weekly sauna totals from `start`'s week through `end`'s week."""
    start, end = week_start(start), week_start(end)
    weeks: dict[date, SaunaWeek] = {}
    cursor = start
    while cursor <= end:
        weeks[cursor] = SaunaWeek(start=cursor)
        cursor += timedelta(weeks=1)
    for sauna in saunas:
        week = weeks.get(week_start(sauna.local_date))
        if week is None or sauna.sport != "sauna":
            continue
        week.sessions += 1
        week.seconds += sauna.duration_s or 0.0
        week.ids.append(sauna.id)
    return list(weeks.values())


def sauna_weeks(session: Session, range_key: str, today: date) -> list[SaunaWeek]:
    first = session.exec(select(Run.local_date).where(Run.sport == "sauna").order_by(Run.local_date)).first()
    start = range_start(range_key, today, first)
    saunas = session.exec(
        select(Run).where(Run.sport == "sauna", Run.local_date >= start, Run.local_date <= today).order_by(Run.start_local)
    )
    return bucket_sauna_weeks(list(saunas), start, today)

"""Weekly mileage. Weeks run Monday through Sunday in the local time of each run.

Rides count as run-equivalent miles by training load: a ride's Garmin training
load divided by the average load per run mile over the trailing year. Rides
without a training load add nothing.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import METERS_PER_MILE, Run

RANGES = {"3m": 13, "6m": 26, "1y": 52}
ROLLING_WEEKS = 4
LOAD_WINDOW = timedelta(days=365)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


@dataclass
class Week:
    start: date
    miles: float = 0.0  # running miles only
    runs: int = 0
    longest_miles: float = 0.0
    rolling_avg: float = 0.0
    run_ids: list[int] = field(default_factory=list)
    ride_equiv_miles: float = 0.0
    rides: int = 0
    rolling_avg_total: float = 0.0
    ride_ids: list[int] = field(default_factory=list)

    @property
    def total_miles(self) -> float:
        return self.miles + self.ride_equiv_miles


def load_per_run_mile(runs: list[Run]) -> float | None:
    """Average training load per running mile, from runs that have a load."""
    loaded = [r for r in runs if r.sport == "run" and r.training_load and r.distance_m > 0]
    miles = sum(r.distance_m for r in loaded) / METERS_PER_MILE
    return sum(r.training_load for r in loaded) / miles if miles else None


def trailing_load_per_run_mile(session: Session, today: date) -> float | None:
    runs = session.exec(select(Run).where(Run.sport == "run", Run.local_date > today - LOAD_WINDOW, Run.local_date <= today))
    return load_per_run_mile(list(runs))


def ride_equiv_miles(ride: Run, per_mile: float | None) -> float:
    if not per_mile or not ride.training_load or ride.training_load <= 0:
        return 0.0
    return ride.training_load / per_mile


def range_start(range_key: str, today: date, first_run: date | None) -> date:
    this_week = week_start(today)
    if range_key in RANGES:
        return this_week - timedelta(weeks=RANGES[range_key] - 1)
    if range_key == "ytd":
        return week_start(date(today.year, 1, 1))
    if range_key == "all":
        return week_start(first_run) if first_run else this_week
    raise ValueError(f"Unknown range {range_key!r}; use 3m, 6m, 1y, ytd or all")


def bucket_weeks(runs: list[Run], start: date, end: date, per_mile: float | None = None) -> list[Week]:
    """Zero-filled weekly totals from `start`'s week through `end`'s week.

    Rides only add run-equivalent miles, converted at `per_mile` load per run mile.
    """
    start, end = week_start(start), week_start(end)
    weeks: dict[date, Week] = {}
    cursor = start
    while cursor <= end:
        weeks[cursor] = Week(start=cursor)
        cursor += timedelta(weeks=1)
    for run in runs:
        week = weeks.get(week_start(run.local_date))
        if week is None:
            continue
        if run.sport == "ride":
            week.ride_equiv_miles += ride_equiv_miles(run, per_mile)
            week.rides += 1
            week.ride_ids.append(run.id)
            continue
        if run.sport != "run":  # sauna sessions aren't mileage
            continue
        miles = run.distance_m / METERS_PER_MILE
        week.miles += miles
        week.runs += 1
        week.longest_miles = max(week.longest_miles, miles)
        week.run_ids.append(run.id)
    return list(weeks.values())


def with_rolling_average(weeks: list[Week]) -> list[Week]:
    for i, week in enumerate(weeks):
        window = weeks[max(0, i - ROLLING_WEEKS + 1) : i + 1]
        week.rolling_avg = sum(w.miles for w in window) / len(window)
        week.rolling_avg_total = sum(w.total_miles for w in window) / len(window)
    return weeks


def weekly_series(session: Session, range_key: str, today: date | None = None) -> tuple[list[Week], float | None]:
    """Weeks in the range, plus the load-per-run-mile factor used for rides."""
    today = today or date.today()
    first = session.exec(select(Run.local_date).where(Run.sport == "run").order_by(Run.local_date)).first()
    start = range_start(range_key, today, first)
    # Read a few extra weeks so the first visible week's rolling average is real.
    lead_in = start - timedelta(weeks=ROLLING_WEEKS - 1)
    runs = list(session.exec(select(Run).where(Run.local_date >= lead_in, Run.local_date <= today)))
    per_mile = trailing_load_per_run_mile(session, today)
    weeks = with_rolling_average(bucket_weeks(runs, lead_in, today, per_mile))
    return [w for w in weeks if w.start >= start], per_mile

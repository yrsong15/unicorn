from datetime import date, datetime, time

from app.models import METERS_PER_MILE, Lap, Run, Shoe, utcnow

_next_id = [1000]


def app_today() -> date:
    """The app's "today" for factory-made runs, which have no UTC offset."""
    return utcnow().date()


def make_run(
    session,
    day: date,
    miles: float,
    *,
    hour: int = 7,
    category: str = "road",
    laps: list[float] | None = None,
    sport: str = "run",
    load: float | None = None,
) -> Run:
    _next_id[0] += 1
    start = datetime.combine(day, time(hour))
    run = Run(
        garmin_activity_id=_next_id[0],
        start_local=start,
        start_utc=start,
        local_date=day,
        name="Run" if sport == "run" else "Ride",
        sport=sport,
        category=category,
        training_load=load,
        distance_m=miles * METERS_PER_MILE,
        duration_s=miles * 480,
    )
    session.add(run)
    session.flush()
    for i, lap_miles in enumerate(laps or [], start=1):
        session.add(Lap(run_id=run.id, idx=i, distance_m=lap_miles * METERS_PER_MILE, duration_s=lap_miles * 480))
    session.commit()
    return run


def make_shoe(session, name: str = "Shoe", **kwargs) -> Shoe:
    shoe = Shoe(name=name, **kwargs)
    session.add(shoe)
    session.commit()
    session.refresh(shoe)
    return shoe


def make_ride(session, day: date, miles: float, load: float | None, **kwargs) -> Run:
    return make_run(session, day, miles, sport="ride", load=load, **kwargs)

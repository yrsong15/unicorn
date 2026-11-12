"""Incremental Garmin -> database sync, shared by the API, the cron, and the CLI."""

import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta

from garminconnect import Garmin, GarminConnectTooManyRequestsError
from sqlmodel import Session, delete, select

from app.clock import local_today
from app.config import SYNC_STALE_AFTER_S
from app.garmin import parse
from app.models import DailyMetrics, Lap, PersonalRecord, Run, SyncState, utcnow
from app.services.shoes import apply_default_shoe

log = logging.getLogger(__name__)

# How far back an incremental sync re-reads activities, to catch late uploads
# and edits (renames, distance corrections) made in Garmin Connect.
ACTIVITY_OVERLAP = timedelta(days=2)
FIRST_SYNC_LOOKBACK = timedelta(days=30)
REQUEST_DELAY_S = 0.3


class SyncBusy(RuntimeError):
    pass


def get_state(session: Session) -> SyncState:
    state = session.get(SyncState, 1)
    if state is None:
        state = SyncState()
        session.add(state)
        session.commit()
        session.refresh(state)
    return state


def is_stale(state: SyncState, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return state.last_sync_at is None or (now - state.last_sync_at).total_seconds() > SYNC_STALE_AFTER_S


def _claim(session: Session) -> SyncState:
    state = get_state(session)
    if state.status == "running" and state.started_at and utcnow() - state.started_at < timedelta(minutes=5):
        raise SyncBusy("A sync is already running")
    state.status = "running"
    state.started_at = utcnow()
    session.add(state)
    session.commit()
    return state


def _call(fn: Callable, *args, **kwargs):
    """One Garmin request. Non-fatal failures return None; 429s stop the sync."""
    time.sleep(REQUEST_DELAY_S)
    try:
        return fn(*args, **kwargs)
    except GarminConnectTooManyRequestsError:
        raise
    except Exception as exc:  # Garmin returns odd 4xx/5xx for days without data
        log.info("Garmin call %s%s failed: %s", getattr(fn, "__name__", fn), args, exc)
        return None


def upsert_run(session: Session, garmin: Garmin | None, activity: dict) -> Run | None:
    fields = parse.parse_activity(activity)
    if fields is None:
        return None
    run = session.exec(select(Run).where(Run.garmin_activity_id == fields["garmin_activity_id"])).first()
    is_new = run is None
    if is_new:
        run = Run(**fields)
    else:
        for key, value in fields.items():
            setattr(run, key, value)
    session.add(run)
    session.flush()

    if is_new:
        laps = parse.parse_laps(_call(garmin.get_activity_splits, run.garmin_activity_id)) if garmin else []
        session.exec(delete(Lap).where(Lap.run_id == run.id))
        for lap in laps:
            session.add(Lap(run_id=run.id, **lap))
        apply_default_shoe(session, run)
    return run


def sync_activities(session: Session, garmin: Garmin, start: date, end: date) -> dict[str, int]:
    """Upsert runs and rides; returns how many of each were seen."""
    activities = _call(garmin.get_activities_by_date, start.isoformat(), end.isoformat()) or []
    counts = {"run": 0, "ride": 0}
    latest: datetime | None = None
    for activity in activities:
        run = upsert_run(session, garmin, activity)
        if run is not None:
            counts[run.sport] += 1
            latest = max(latest or run.start_local, run.start_local)
        session.commit()
    state = get_state(session)
    if latest and (state.last_activity_start is None or latest > state.last_activity_start):
        state.last_activity_start = latest
        session.add(state)
        session.commit()
    return counts


def _metrics_row(session: Session, day: date) -> DailyMetrics:
    return session.get(DailyMetrics, day) or DailyMetrics(day=day)


def _apply(row: DailyMetrics, values: dict) -> None:
    for key, value in values.items():
        if value is not None:
            setattr(row, key, value)


def sync_metrics(session: Session, garmin: Garmin, start: date, end: date) -> int:
    # Range endpoints first (one request each), then per-day endpoints.
    vo2 = parse.parse_vo2max_range(_call(garmin.get_max_metrics_range, start.isoformat(), end.isoformat()))
    races: dict[date, dict] = {}
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(end, chunk_start + timedelta(days=365))
        races |= parse.parse_race_predictions(
            _call(garmin.get_race_predictions, chunk_start.isoformat(), chunk_end.isoformat(), "daily")
        )
        chunk_start = chunk_end + timedelta(days=1)

    days = 0
    day = start
    while day <= end:
        iso = day.isoformat()
        row = _metrics_row(session, day)
        _apply(row, {"vo2max": vo2.get(day)})
        _apply(row, races.get(day, {}))
        _apply(row, parse.parse_resting_hr(_call(garmin.get_user_summary, iso)))
        _apply(row, parse.parse_readiness(_call(garmin.get_training_readiness, iso)))
        _apply(row, parse.parse_hrv(_call(garmin.get_hrv_data, iso)))
        _apply(row, parse.parse_training_status(_call(garmin.get_training_status, iso)))
        session.add(row)
        session.commit()
        days += 1
        day += timedelta(days=1)

    lt = parse.parse_lactate_threshold(_call(garmin.get_lactate_threshold, latest=True))
    if any(v is not None for v in lt.values()):
        row = _metrics_row(session, end)
        _apply(row, lt)
        session.add(row)
        session.commit()

    state = get_state(session)
    state.last_metrics_date = end
    session.add(state)
    session.commit()
    return days


def sync_personal_records(session: Session, garmin: Garmin) -> None:
    records = parse.parse_personal_records(_call(garmin.get_personal_record))
    for record in records:
        session.merge(PersonalRecord(**record))
    session.commit()


def run_sync(
    session: Session,
    garmin: Garmin,
    activities_since: date | None = None,
    metrics_since: date | None = None,
) -> dict:
    """Pull new runs, rides and daily metrics. Returns a short summary."""
    state = _claim(session)
    today = local_today(session)
    try:
        if activities_since is None:
            activities_since = (
                (state.last_activity_start - ACTIVITY_OVERLAP).date()
                if state.last_activity_start
                else today - FIRST_SYNC_LOOKBACK
            )
        if metrics_since is None:
            metrics_since = (
                state.last_metrics_date - timedelta(days=1)
                if state.last_metrics_date
                else today - FIRST_SYNC_LOOKBACK
            )
        counts = sync_activities(session, garmin, activities_since, today)
        days = sync_metrics(session, garmin, metrics_since, today)
        sync_personal_records(session, garmin)
    except GarminConnectTooManyRequestsError:
        _finish(session, "error", "Garmin is rate-limiting requests. The next sync will pick up where this left off.")
        raise
    except Exception as exc:
        _finish(session, "error", f"Sync failed: {exc}"[:500])
        raise
    runs, rides = counts["run"], counts["ride"]
    rides_part = f", {rides} ride{'s' if rides != 1 else ''}" if rides else ""
    message = f"Synced {runs} run{'s' if runs != 1 else ''}{rides_part} and {days} day{'s' if days != 1 else ''} of metrics"
    _finish(session, "ok", message)
    return {"runs": runs, "rides": rides, "metric_days": days, "message": message}


def _finish(session: Session, status: str, message: str) -> None:
    session.rollback()
    state = get_state(session)
    state.status = status
    state.message = message
    state.last_sync_at = utcnow()
    session.add(state)
    session.commit()

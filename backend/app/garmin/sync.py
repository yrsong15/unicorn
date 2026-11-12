"""Incremental Garmin -> database sync, shared by the API, the cron, and the CLI."""

import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectNotFoundError,
    GarminConnectTooManyRequestsError,
)
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete, select

from app.clock import local_today
from app.config import SYNC_STALE_AFTER_S
from app.garmin import parse
from app.garmin.client import GarminNotConnected, mark_needs_reconnect
from app.models import DailyMetrics, Lap, PersonalRecord, Run, RunShoe, SyncState, utcnow
from app.services.shoes import TOLERANCE_M, apply_default_shoe

log = logging.getLogger(__name__)

# How far back an incremental sync re-reads activities, to catch late uploads
# and edits (renames, distance corrections) made in Garmin Connect.
ACTIVITY_OVERLAP = timedelta(days=2)
FIRST_SYNC_LOOKBACK = timedelta(days=30)
REQUEST_DELAY_S = 0.3
# A sync with this many failed requests gives up instead of reporting success.
MAX_FAILED_REQUESTS = 15
# A running sync refreshes its lock at least this often; a lock older than
# LOCK_STALE_AFTER belongs to a sync that died and can be taken over.
HEARTBEAT_EVERY = timedelta(seconds=30)
LOCK_STALE_AFTER = timedelta(minutes=5)


class SyncBusy(RuntimeError):
    pass


class SyncFailed(RuntimeError):
    """Garmin kept failing (not rate limits or an expired login, which have their own errors)."""


def get_state(session: Session) -> SyncState:
    state = session.get(SyncState, 1)
    if state is None:
        try:
            session.add(SyncState())
            session.commit()
        except IntegrityError:  # another request created it first
            session.rollback()
        state = session.get(SyncState, 1)
    return state


def is_stale(state: SyncState, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return state.last_sync_at is None or (now - state.last_sync_at).total_seconds() > SYNC_STALE_AFTER_S


class SyncLock:
    """The single sync_state row, used as a lock so only one sync runs at a time.

    Claiming is one conditional UPDATE, so two syncs that start together can't
    both win. The holder's `started_at` is its token: `beat()` moves it forward
    while the sync runs, and fails if another sync has since taken the lock.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.token: datetime | None = None

    def claim(self) -> None:
        get_state(self.session)
        now = utcnow()
        result = self.session.execute(
            update(SyncState)
            .where(
                SyncState.id == 1,
                or_(
                    SyncState.status != "running",
                    SyncState.started_at.is_(None),
                    SyncState.started_at < now - LOCK_STALE_AFTER,
                ),
            )
            .values(status="running", started_at=now)
        )
        self.session.commit()
        if result.rowcount != 1:
            raise SyncBusy("A sync is already running")
        self.token = now
        self.session.expire_all()

    def beat(self, force: bool = False) -> None:
        """Refresh the lock; call between commits, at most every HEARTBEAT_EVERY."""
        if self.token is None:
            return
        now = utcnow()
        if not force and now - self.token < HEARTBEAT_EVERY:
            return
        result = self.session.execute(
            update(SyncState)
            .where(SyncState.id == 1, SyncState.status == "running", SyncState.started_at == self.token)
            .values(started_at=now)
        )
        self.session.commit()
        if result.rowcount != 1:
            self.token = None
            raise SyncBusy("Another sync took over")
        self.token = now


class Requests:
    """Makes the Garmin requests for one sync and counts the ones that failed.

    A 404 means "no data for that day" and isn't a failure. Rate limits and an
    expired login stop the sync. Other errors are counted and skipped, unless
    the request is `required` or too many have failed.
    """

    def __init__(self, lock: SyncLock | None = None) -> None:
        self.failed = 0
        self.last_error: str | None = None
        self.lock = lock

    def checkpoint(self) -> None:
        """Called after each commit: keeps the sync lock fresh."""
        if self.lock:
            self.lock.beat()

    def __call__(self, fn: Callable, *args, required: bool = False, **kwargs):
        time.sleep(REQUEST_DELAY_S)
        try:
            return fn(*args, **kwargs)
        except (GarminConnectTooManyRequestsError, GarminConnectAuthenticationError):
            raise
        except GarminConnectNotFoundError:
            return None
        except Exception as exc:
            name = getattr(fn, "__name__", fn)
            if required:
                raise SyncFailed(f"Garmin request {name} failed: {exc}") from exc
            log.info("Garmin call %s%s failed: %s", name, args, exc)
            self.record_failure(f"{name}: {exc}", exc)
            return None

    def record_failure(self, what: str, exc: Exception) -> None:
        self.failed += 1
        self.last_error = what
        if self.failed >= MAX_FAILED_REQUESTS:
            raise SyncFailed(f"{self.failed} Garmin requests failed; last was {what}") from exc


# A distance change smaller than this (meters) is rounding, not an edit.
DISTANCE_EDIT_M = 1.0


def upsert_run(session: Session, garmin: Garmin | None, activity: dict, call: Requests | None = None) -> Run | None:
    """Insert or update one activity.

    Laps are fetched for new activities, for ones that still have none (an
    earlier request failed), and when the distance was edited in Garmin
    Connect. After a distance edit, a single shoe that covered the whole old
    distance is stretched to the new one.
    """
    fields = parse.parse_activity(activity)
    if fields is None:
        return None
    run = session.exec(select(Run).where(Run.garmin_activity_id == fields["garmin_activity_id"])).first()
    is_new = run is None
    old_distance = None if is_new else run.distance_m
    if is_new:
        run = Run(**fields)
    else:
        for key, value in fields.items():
            setattr(run, key, value)
    session.add(run)
    session.flush()

    distance_edited = old_distance is not None and abs(old_distance - run.distance_m) > DISTANCE_EDIT_M
    has_laps = not is_new and session.exec(select(Lap.id).where(Lap.run_id == run.id)).first() is not None
    if garmin and (is_new or not has_laps or distance_edited):
        call = call or Requests()
        laps = parse.parse_laps(call(garmin.get_activity_splits, run.garmin_activity_id))
        # Keep the laps we have if the refetch came back empty or failed.
        if laps or is_new:
            session.exec(delete(Lap).where(Lap.run_id == run.id))
            for lap in laps:
                session.add(Lap(run_id=run.id, **lap))

    if is_new:
        apply_default_shoe(session, run)
    elif distance_edited:
        follow_distance_edit(session, run, old_distance)
    return run


def follow_distance_edit(session: Session, run: Run, old_distance: float) -> None:
    """Stretch a run's only shoe segment if it covered the whole old distance."""
    segments = session.exec(select(RunShoe).where(RunShoe.run_id == run.id)).all()
    if len(segments) != 1 or run.distance_m <= 0:
        return
    seg = segments[0]
    if seg.lap_from is None and abs(seg.distance_m - old_distance) <= TOLERANCE_M:
        seg.distance_m = run.distance_m
        session.add(seg)


def sync_activities(session: Session, garmin: Garmin, start: date, end: date, call: Requests) -> dict[str, int]:
    """Upsert runs and rides; returns how many of each were seen."""
    activities = call(garmin.get_activities_by_date, start.isoformat(), end.isoformat(), required=True) or []
    counts = {"run": 0, "ride": 0}
    latest: datetime | None = None
    for activity in activities if isinstance(activities, list) else []:
        try:
            run = upsert_run(session, garmin, activity, call)
            if run is not None:
                counts[run.sport] += 1
                latest = max(latest or run.start_local, run.start_local)
            session.commit()
        except (GarminConnectTooManyRequestsError, GarminConnectAuthenticationError, SyncFailed):
            raise
        except Exception as exc:  # one bad activity shouldn't stop the rest
            session.rollback()
            activity_id = activity.get("activityId") if isinstance(activity, dict) else None
            log.warning("Skipped activity %s: %s", activity_id, exc)
            call.record_failure(f"activity {activity_id}: {exc}", exc)
        call.checkpoint()
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


def sync_metrics(session: Session, garmin: Garmin, start: date, end: date, call: Requests) -> int:
    # Range endpoints first (one request each), then per-day endpoints.
    vo2 = parse.parse_vo2max_range(call(garmin.get_max_metrics_range, start.isoformat(), end.isoformat()))
    races: dict[date, dict] = {}
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(end, chunk_start + timedelta(days=365))
        races |= parse.parse_race_predictions(
            call(garmin.get_race_predictions, chunk_start.isoformat(), chunk_end.isoformat(), "daily")
        )
        chunk_start = chunk_end + timedelta(days=1)

    days = 0
    day = start
    while day <= end:
        iso = day.isoformat()
        row = _metrics_row(session, day)
        _apply(row, {"vo2max": vo2.get(day)})
        _apply(row, races.get(day, {}))
        _apply(row, parse.parse_resting_hr(call(garmin.get_user_summary, iso)))
        _apply(row, parse.parse_readiness(call(garmin.get_training_readiness, iso)))
        _apply(row, parse.parse_hrv(call(garmin.get_hrv_data, iso)))
        _apply(row, parse.parse_training_status(call(garmin.get_training_status, iso)))
        session.add(row)
        session.commit()
        call.checkpoint()
        days += 1
        day += timedelta(days=1)

    lt = parse.parse_lactate_threshold(call(garmin.get_lactate_threshold, latest=True))
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


def sync_personal_records(session: Session, garmin: Garmin, call: Requests) -> None:
    records = parse.parse_personal_records(call(garmin.get_personal_record))
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
    lock = SyncLock(session)
    lock.claim()
    state = get_state(session)
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
        call = Requests(lock)
        counts = sync_activities(session, garmin, activities_since, today, call)
        days = sync_metrics(session, garmin, metrics_since, today, call)
        sync_personal_records(session, garmin, call)
    except SyncBusy:
        raise  # another sync owns the state now; leave it alone
    except GarminConnectAuthenticationError as exc:
        _finish(session, "error", "Garmin rejected the stored login. Run `cli login` on your Mac to reconnect.")
        mark_needs_reconnect(session, f"Garmin rejected the stored tokens during sync: {exc}")
        raise GarminNotConnected("Garmin tokens expired. Run `cli login` on your Mac to reconnect.") from exc
    except GarminConnectTooManyRequestsError:
        _finish(session, "error", "Garmin is rate-limiting requests. The next sync will pick up where this left off.")
        raise
    except Exception as exc:
        _finish(session, "error", f"Sync failed: {exc}"[:500])
        raise
    runs, rides = counts["run"], counts["ride"]
    rides_part = f", {rides} ride{'s' if rides != 1 else ''}" if rides else ""
    message = f"Synced {runs} run{'s' if runs != 1 else ''}{rides_part} and {days} day{'s' if days != 1 else ''} of metrics"
    if call.failed:
        message += f", but {call.failed} Garmin request{'s' if call.failed != 1 else ''} failed (last: {call.last_error})"
    message = message[:500]
    _finish(session, "partial" if call.failed else "ok", message)
    return {"runs": runs, "rides": rides, "metric_days": days, "failed_requests": call.failed, "message": message}


def _finish(session: Session, status: str, message: str) -> None:
    session.rollback()
    state = get_state(session)
    state.status = status
    state.message = message
    state.last_sync_at = utcnow()
    session.add(state)
    session.commit()

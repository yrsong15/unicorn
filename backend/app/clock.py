"""The athlete's local date.

The server runs in UTC, but runs are bucketed by their local start date. Using
the server's date would flip "today" and "this week" hours early or late. The
UTC offset comes from the most recent activity (Garmin records both its local
and UTC start), so "today" follows wherever you last ran. After a daylight
saving change it can be an hour off until the next activity, which only matters
right around midnight.
"""

from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from app.models import Run, utcnow

MAX_OFFSET = timedelta(hours=14)


def utc_offset(session: Session) -> timedelta:
    latest = session.exec(select(Run.start_local, Run.start_utc).order_by(Run.start_utc.desc())).first()
    if latest is None:
        return timedelta(0)
    offset = latest[0] - latest[1]
    # Garmin offsets are whole quarter hours; anything else is bad data.
    if abs(offset) > MAX_OFFSET or offset % timedelta(minutes=15):
        return timedelta(0)
    return offset


def local_now(session: Session) -> datetime:
    return utcnow() + utc_offset(session)


def local_today(session: Session) -> date:
    return local_now(session).date()

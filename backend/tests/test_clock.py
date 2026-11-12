from datetime import date, datetime, timedelta

from app import clock
from tests.factories import make_run


def _run(session, start_local: datetime, start_utc: datetime):
    run = make_run(session, start_local.date(), 3)
    run.start_local, run.start_utc = start_local, start_utc
    session.add(run)
    session.commit()


def test_offset_comes_from_latest_activity(session):
    _run(session, datetime(2026, 6, 1, 7), datetime(2026, 6, 1, 11))  # older, EDT
    _run(session, datetime(2026, 11, 2, 7), datetime(2026, 11, 2, 12))  # latest, EST
    assert clock.utc_offset(session) == timedelta(hours=-5)


def test_today_is_local_not_utc(session, monkeypatch):
    _run(session, datetime(2026, 11, 2, 7), datetime(2026, 11, 2, 12))
    # 02:30 UTC on Nov 10 is still the evening of Nov 9 in New York.
    monkeypatch.setattr(clock, "utcnow", lambda: datetime(2026, 11, 10, 2, 30))
    assert clock.local_today(session) == date(2026, 11, 9)


def test_falls_back_to_utc(session, monkeypatch):
    monkeypatch.setattr(clock, "utcnow", lambda: datetime(2026, 11, 10, 2, 30))
    assert clock.local_today(session) == date(2026, 11, 10)  # no runs yet
    _run(session, datetime(2026, 11, 2, 7, 7), datetime(2026, 11, 2, 12))  # not a real offset
    assert clock.utc_offset(session) == timedelta(0)

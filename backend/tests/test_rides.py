from datetime import date, timedelta

import pytest
from sqlmodel import select

from app.models import RunShoe
from app.services.mileage import (
    bucket_weeks,
    load_per_run_mile,
    ride_equiv_miles,
    trailing_load_per_run_mile,
    weekly_series,
    with_rolling_average,
)
from app.services.records import compute_records
from app.services.shoes import SegmentError, SegmentInput, apply_default_shoe, replace_segments
from tests.factories import make_ride, make_run, make_shoe, app_today

TODAY = date(2026, 10, 17)  # Saturday; week starts 2026-10-12


def test_load_per_run_mile_ignores_rides_and_runs_without_load(session):
    runs = [
        make_run(session, TODAY, 5, load=150),
        make_run(session, TODAY, 3, load=90),
        make_run(session, TODAY, 10),  # no load: must not dilute the average
        make_ride(session, TODAY, 20, 500),
    ]
    assert load_per_run_mile(runs) == pytest.approx(30)
    assert load_per_run_mile([make_run(session, TODAY, 4)]) is None
    assert load_per_run_mile([]) is None


def test_trailing_factor_uses_last_365_days(session):
    make_run(session, TODAY - timedelta(days=400), 10, load=1000)  # too old
    make_run(session, TODAY - timedelta(days=30), 4, load=100)
    assert trailing_load_per_run_mile(session, TODAY) == pytest.approx(25)


def test_ride_equivalent_miles(session):
    ride = make_ride(session, TODAY, 25, 54)
    assert ride_equiv_miles(ride, 27) == pytest.approx(2)
    assert ride_equiv_miles(make_ride(session, TODAY, 25, None), 27) == 0
    assert ride_equiv_miles(make_ride(session, TODAY, 25, 0), 27) == 0
    assert ride_equiv_miles(ride, None) == 0  # no run history to convert with


def test_weekly_buckets_keep_run_miles_separate_from_ride_equivalents(session):
    activities = [
        make_run(session, date(2026, 10, 5), 6, load=150),
        make_run(session, date(2026, 10, 12), 5, load=125),
        make_ride(session, date(2026, 10, 13), 30, 50),
        make_ride(session, date(2026, 10, 14), 12, None),
    ]
    weeks = with_rolling_average(bucket_weeks(activities, date(2026, 10, 5), TODAY, per_mile=25))
    last, this = weeks
    assert (last.miles, last.ride_equiv_miles, last.rides) == (pytest.approx(6), 0, 0)
    assert this.miles == pytest.approx(5)
    assert this.ride_equiv_miles == pytest.approx(2)
    assert this.total_miles == pytest.approx(7)
    assert (this.runs, this.rides, this.longest_miles) == (1, 2, pytest.approx(5))
    assert this.ride_ids == [activities[2].id, activities[3].id]
    assert this.rolling_avg == pytest.approx(5.5)
    assert this.rolling_avg_total == pytest.approx(6.5)


def test_weekly_buckets_without_rides_match_run_miles(session):
    weeks = bucket_weeks([make_run(session, TODAY, 5, load=100)], TODAY, TODAY, per_mile=20)
    assert weeks[0].total_miles == weeks[0].miles == pytest.approx(5)


def test_weekly_series_returns_factor(session):
    make_run(session, TODAY, 4, load=108)
    make_ride(session, TODAY, 20, 54)
    weeks, per_mile = weekly_series(session, "3m", today=TODAY)
    assert per_mile == pytest.approx(27)
    assert weeks[-1].miles == pytest.approx(4) and weeks[-1].ride_equiv_miles == pytest.approx(2)


def test_weekly_api_exposes_both_series(logged_in, session):
    today = app_today()
    make_run(session, today, 4, load=100)
    make_ride(session, today, 20, 50)
    body = logged_in.get("/api/summary/weekly?range=3m").json()
    week = body["weeks"][-1]
    assert body["load_per_run_mile"] == 25
    assert (week["run_miles"], week["ride_equiv_miles"], week["total_miles"]) == (4, 2, 6)
    assert week["rolling_avg_total"] > week["rolling_avg"]
    dash = logged_in.get("/api/summary/dashboard").json()
    assert dash["this_week"]["total_miles"] == 6 and dash["load_per_run_mile"] == 25


def test_rides_never_get_shoes(session):
    make_shoe(session, "Daily", is_default=True)
    ride = make_ride(session, TODAY, 20, 50)
    apply_default_shoe(session, ride)
    session.commit()
    assert session.exec(select(RunShoe)).all() == []
    shoe = make_shoe(session, "Other")
    with pytest.raises(SegmentError):
        replace_segments(session, ride, [SegmentInput(shoe_id=shoe.id, distance_m=1000)])


def test_records_ignore_rides(session):
    make_run(session, TODAY, 5)
    make_ride(session, TODAY - timedelta(weeks=1), 40, 80)
    rec = compute_records(session, today=TODAY)
    assert rec["longest_run"]["miles"] == pytest.approx(5)
    assert rec["totals"]["runs"] == 1 and rec["totals"]["miles"] == pytest.approx(5)
    assert rec["current_streak_weeks"] == 1


def test_run_list_filters_by_sport(logged_in, session):
    run = make_run(session, app_today(), 5)
    ride = make_ride(session, app_today(), 20, 50)
    assert [r["id"] for r in logged_in.get("/api/runs").json()["items"]] == [run.id]
    rides = logged_in.get("/api/runs?sport=ride").json()["items"]
    assert [r["id"] for r in rides] == [ride.id]
    assert rides[0]["sport"] == "ride" and rides[0]["speed_mph"] == pytest.approx(7.5)
    assert logged_in.get("/api/runs?sport=all").json()["total"] == 2
    assert logged_in.get("/api/runs?sport=swim").status_code == 422


def test_training_daily_load_is_split_by_sport(logged_in, session):
    from app.models import DailyMetrics

    today = app_today()
    session.add(DailyMetrics(day=today - timedelta(days=2), acute_load=300))
    session.commit()
    make_run(session, today, 5, load=120)
    make_ride(session, today, 20, 45)
    daily = logged_in.get("/api/metrics/training?range=3m").json()["daily_load"]
    assert len(daily) == 3  # zero-filled from the first metrics day
    assert daily[0] == {"day": (today - timedelta(days=2)).isoformat(), "run": 0, "ride": 0, "total": 0}
    assert daily[-1] == {"day": today.isoformat(), "run": 120, "ride": 45, "total": 165}

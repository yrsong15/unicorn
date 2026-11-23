from datetime import date, timedelta

import pytest
from sqlmodel import select

from app.garmin import parse
from app.garmin.sync import run_sync, upsert_run
from app.models import DailyMetrics, Lap, Run, RunShoe
from app.services.mileage import bucket_weeks
from app.services.records import compute_records
from app.services.sauna import bucket_sauna_weeks, sauna_weeks
from app.services.shoes import apply_default_shoe
from tests.factories import app_today, make_ride, make_run, make_sauna, make_shoe
from tests.test_sync import FakeGarmin, _fast

TODAY = date(2026, 10, 17)  # Saturday; week starts 2026-10-12


def sauna_activity(name="Sauna", type_key="other", activity_id=9001, start="2026-10-15 19:00:00", duration=1200.0):
    return {"activityId": activity_id, "activityName": name, "startTimeLocal": start,
            "startTimeGMT": start, "activityType": {"typeKey": type_key}, "duration": duration, "distance": 0.0,
            "averageHR": 110.0}


@pytest.mark.parametrize("name", ["Sauna", "sauna", "SAUNA", " Sauna ", "sAuNa"])
def test_sauna_name_matches_case_insensitively(name):
    parsed = parse.parse_activity(sauna_activity(name))
    assert (parsed["sport"], parsed["category"]) == ("sauna", "sauna")
    assert parsed["duration_s"] == 1200 and parsed["avg_hr"] == 110 and parsed["avg_cadence"] is None


@pytest.mark.parametrize(
    ("name", "type_key"),
    [("Yoga", "other"), ("Sauna and stretch", "other"), (None, "other"), ("Sauna", "lap_swimming")],
)
def test_other_activities_are_not_saunas(name, type_key):
    assert parse.parse_activity(sauna_activity(name, type_key)) is None


class WithSauna(FakeGarmin):
    def get_activities_by_date(self, start, end):
        return [*super().get_activities_by_date(start, end), sauna_activity("SAUNA")]


def test_sync_imports_saunas_without_laps_or_shoes(session, monkeypatch):
    _fast(monkeypatch)
    make_shoe(session, "Daily", is_default=True)
    garmin = WithSauna()
    result = run_sync(session, garmin, activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 15))

    sauna = session.exec(select(Run).where(Run.sport == "sauna")).one()
    assert sauna.name == "SAUNA" and sauna.duration_s == 1200
    assert result["saunas"] == 1 and result["runs"] == 2 and "1 sauna session" in result["message"]
    assert ("splits", (sauna.garmin_activity_id,)) not in garmin.calls
    assert session.exec(select(Lap).where(Lap.run_id == sauna.id)).all() == []
    assert session.exec(select(RunShoe).where(RunShoe.run_id == sauna.id)).all() == []

    # A resync updates the same row instead of adding another.
    run_sync(session, garmin, activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 15))
    assert len(session.exec(select(Run).where(Run.sport == "sauna")).all()) == 1


def test_upsert_sauna_makes_no_splits_call(session):
    garmin = FakeGarmin()
    sauna = upsert_run(session, garmin, sauna_activity())
    assert sauna.sport == "sauna" and garmin.calls == []


def test_saunas_add_nothing_to_mileage(session):
    activities = [make_run(session, TODAY, 5), make_ride(session, TODAY, 20, 50), make_sauna(session, TODAY, 20)]
    (week,) = bucket_weeks(activities, TODAY, TODAY, per_mile=25)
    assert week.runs == 1 and week.rides == 1
    assert week.miles == pytest.approx(5) and week.total_miles == pytest.approx(7)
    assert activities[2].id not in week.run_ids + week.ride_ids


def test_sauna_weeks_are_zero_filled_monday_to_sunday(session):
    saunas = [
        make_sauna(session, date(2026, 10, 4), 30),  # Sunday: week of 2026-09-28
        make_sauna(session, date(2026, 10, 12), 15),  # Monday
        make_sauna(session, date(2026, 10, 17), 20.5),  # Saturday, same week
        make_run(session, date(2026, 10, 13), 5),  # not a sauna
    ]
    weeks = bucket_sauna_weeks(saunas, date(2026, 9, 28), TODAY)
    assert [w.start for w in weeks] == [date(2026, 9, 28), date(2026, 10, 5), date(2026, 10, 12)]
    assert [w.sessions for w in weeks] == [1, 0, 2]
    assert [w.seconds / 60 for w in weeks] == [pytest.approx(30), 0, pytest.approx(35.5)]
    assert weeks[2].ids == [saunas[1].id, saunas[2].id]


def test_sauna_weeks_range(session):
    make_sauna(session, TODAY - timedelta(weeks=20), 10)  # outside 3m
    make_sauna(session, TODAY, 10)
    weeks = sauna_weeks(session, "3m", TODAY)
    assert len(weeks) == 13 and sum(w.sessions for w in weeks) == 1
    assert sum(w.sessions for w in sauna_weeks(session, "all", TODAY)) == 2


def test_sauna_summary_api(logged_in, session):
    today = app_today()
    make_sauna(session, today, 18)
    make_sauna(session, today, 12)
    make_run(session, today, 5)
    body = logged_in.get("/api/summary/sauna?range=3m").json()
    assert body["total_sessions"] == 2 and body["total_minutes"] == 30
    this = body["weeks"][-1]
    assert this["sessions"] == 2 and this["minutes"] == 30 and len(this["ids"]) == 2
    assert set(this) == {"week_start", "week_end", "sessions", "minutes", "ids"}
    assert logged_in.get("/api/summary/sauna?range=5y").status_code == 422
    # The mileage summaries don't see the saunas.
    assert logged_in.get("/api/summary/dashboard").json()["this_week"]["runs"] == 1


def test_run_list_filters_saunas(logged_in, session):
    make_run(session, app_today(), 5)
    sauna = make_sauna(session, app_today(), 20)
    items = logged_in.get("/api/runs?sport=sauna").json()["items"]
    assert [r["id"] for r in items] == [sauna.id]
    assert items[0]["pace_s_per_mile"] is None
    assert sauna.id not in [r["id"] for r in logged_in.get("/api/runs").json()["items"]]
    detail = logged_in.get(f"/api/runs/{sauna.id}").json()
    assert detail["sport"] == "sauna" and detail["laps"] == []


def test_saunas_stay_out_of_shoes_records_and_load(logged_in, session):
    make_shoe(session, "Daily", is_default=True)
    sauna = make_sauna(session, TODAY, 20)
    apply_default_shoe(session, sauna)
    session.commit()
    assert session.exec(select(RunShoe)).all() == []
    make_run(session, TODAY, 5)
    assert compute_records(session, today=TODAY)["totals"]["runs"] == 1

    today = app_today()
    session.add(DailyMetrics(day=today, acute_load=300))
    session.commit()
    make_sauna(session, today, 20)
    daily = logged_in.get("/api/metrics/training?range=3m").json()["daily_load"]
    assert daily[-1]["total"] == 0

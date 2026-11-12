import json
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import select

from app.garmin import parse
from app.garmin.sync import run_sync
from app.models import DailyMetrics, Lap, PersonalRecord, Run, RunShoe
from tests.factories import make_shoe

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


class FakeGarmin:
    """Answers the calls sync.py makes with recorded Garmin JSON."""

    def __init__(self):
        self.calls = []

    def _log(self, name, *args):
        self.calls.append((name, args))

    def get_activities_by_date(self, start, end):
        self._log("activities", start, end)
        return load("activities.json")

    def get_activity_splits(self, activity_id):
        self._log("splits", activity_id)
        return load("splits.json")

    def get_max_metrics_range(self, start, end):
        return load("max_metrics.json")

    def get_race_predictions(self, start, end, _type):
        return load("race_predictions.json")

    def get_user_summary(self, day):
        return {"restingHeartRate": 48}

    def get_training_readiness(self, day):
        return load("training_readiness.json")

    def get_hrv_data(self, day):
        return load("hrv.json")

    def get_training_status(self, day):
        return load("training_status.json")

    def get_lactate_threshold(self, latest=True):
        return {"speed_and_heart_rate": {"heartRate": 171, "speed": 0.38}}

    def get_personal_record(self):
        return load("personal_records.json")


def _fast(monkeypatch, today=None):
    monkeypatch.setattr("app.garmin.sync.REQUEST_DELAY_S", 0)
    if today:
        monkeypatch.setattr("app.garmin.sync.local_today", lambda session: today)


def test_parse_activity_maps_runs_and_rides():
    acts = load("activities.json")
    parsed = [parse.parse_activity(a) for a in acts]
    assert [(p["sport"], p["category"]) for p in parsed] == [("run", "track"), ("ride", "road"), ("run", "road")]
    track = parsed[0]
    assert track["local_date"] == date(2026, 10, 14)
    assert track["hr_zones"] == [120.0, 900.0, 600.0, 400.0, 100.0]


@pytest.mark.parametrize(
    ("type_key", "category"),
    [("cycling", "road"), ("road_biking", "road"), ("indoor_cycling", "indoor"), ("virtual_ride", "indoor"),
     ("mountain_biking", "mountain"), ("gravel_cycling", "gravel")],
)
def test_parse_activity_maps_cycling_types_to_rides(type_key, category):
    activity = {"activityId": 1, "startTimeLocal": "2026-10-15 18:00:00", "activityType": {"typeKey": type_key},
                "activityTrainingLoad": 40.0, "averageBikingCadenceInRevPerMinute": 85.0}
    parsed = parse.parse_activity(activity)
    assert (parsed["sport"], parsed["category"], parsed["name"]) == ("ride", category, "Ride")
    assert parsed["training_load"] == 40.0 and parsed["avg_cadence"] == 85.0


def test_parse_activity_skips_other_sports():
    swim = {"activityId": 1, "startTimeLocal": "2026-10-15 18:00:00", "activityType": {"typeKey": "lap_swimming"}}
    assert parse.parse_activity(swim) is None


def test_sync_imports_runs_rides_laps_metrics_and_default_shoe(session, monkeypatch):
    _fast(monkeypatch)
    shoe = make_shoe(session, "Daily", is_default=True)
    result = run_sync(session, FakeGarmin(), activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 15))

    activities = session.exec(select(Run).order_by(Run.start_local)).all()
    assert [a.sport for a in activities] == ["run", "ride", "run"]
    assert result["runs"] == 2 and result["rides"] == 1
    assert "1 ride" in result["message"]
    assert len(session.exec(select(Lap).where(Lap.run_id == activities[0].id)).all()) == 3
    # Rides never get a shoe.
    assert [(s.run_id, s.shoe_id) for s in session.exec(select(RunShoe))] == [
        (activities[0].id, shoe.id), (activities[2].id, shoe.id)]

    metrics = session.get(DailyMetrics, date(2026, 10, 15))
    assert metrics.vo2max == 54.2
    assert metrics.race_5k_s == 1210
    assert metrics.resting_hr == 48
    assert metrics.readiness_score == 81  # latest snapshot wins
    assert metrics.hrv_status == "BALANCED"
    assert metrics.acwr == 1.1 and metrics.training_status == "PRODUCTIVE_1"
    assert {pr.type_id for pr in session.exec(select(PersonalRecord))} == {3, 7}


def test_resync_is_idempotent_and_keeps_shoe_edits(session, monkeypatch):
    _fast(monkeypatch)
    make_shoe(session, "Daily", is_default=True)
    other = make_shoe(session, "Other")
    garmin = FakeGarmin()
    run_sync(session, garmin, activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 15))
    run = session.exec(select(Run)).first()
    for seg in session.exec(select(RunShoe).where(RunShoe.run_id == run.id)):
        seg.shoe_id = other.id
        session.add(seg)
    session.commit()

    run_sync(session, garmin, activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 15))
    assert len(session.exec(select(Run)).all()) == 3
    assert len(session.exec(select(Lap)).all()) == 9  # laps fetched once per new activity
    assert [s.shoe_id for s in session.exec(select(RunShoe).where(RunShoe.run_id == run.id))] == [other.id]
    assert sum(1 for name, _ in garmin.calls if name == "splits") == 3


def test_sync_status_endpoint_reports_not_connected(logged_in):
    res = logged_in.post("/api/sync")
    assert res.status_code == 409
    assert "cli login" in res.json()["detail"]
    status = logged_in.get("/api/sync/status").json()
    assert status["garmin"]["status"] == "disconnected"


class FlakyGarmin(FakeGarmin):
    """FakeGarmin whose per-day HRV endpoint fails with a given error."""

    def __init__(self, error):
        super().__init__()
        self.error = error

    def get_hrv_data(self, day):
        raise self.error


def test_failed_requests_are_reported_not_hidden(session, monkeypatch):
    from garminconnect import GarminConnectConnectionError

    from app.garmin.sync import get_state

    _fast(monkeypatch, today=date(2026, 10, 15))
    result = run_sync(session, FlakyGarmin(GarminConnectConnectionError("500 server error")),
                      activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 14))
    assert result["failed_requests"] == 2  # two days of HRV
    assert "2 Garmin requests failed" in result["message"]
    assert get_state(session).status == "partial"


def test_not_found_is_not_a_failure(session, monkeypatch):
    from garminconnect import GarminConnectNotFoundError

    _fast(monkeypatch, today=date(2026, 10, 15))
    result = run_sync(session, FlakyGarmin(GarminConnectNotFoundError("404")),
                      activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 14))
    assert result["failed_requests"] == 0


def test_too_many_failures_stop_the_sync(session, monkeypatch):
    from garminconnect import GarminConnectConnectionError

    from app.garmin.sync import SyncFailed, get_state

    _fast(monkeypatch)
    monkeypatch.setattr("app.garmin.sync.MAX_FAILED_REQUESTS", 3)
    with pytest.raises(SyncFailed):
        run_sync(session, FlakyGarmin(GarminConnectConnectionError("500")),
                 activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 10))
    assert get_state(session).status == "error"


def test_activity_list_failure_fails_the_sync(session, monkeypatch):
    from garminconnect import GarminConnectConnectionError

    from app.garmin.sync import SyncFailed, get_state

    class NoActivities(FakeGarmin):
        def get_activities_by_date(self, start, end):
            raise GarminConnectConnectionError("503")

    _fast(monkeypatch)
    with pytest.raises(SyncFailed):
        run_sync(session, NoActivities(), activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 15))
    state = get_state(session)
    assert state.status == "error" and "get_activities_by_date" in state.message


def test_expired_login_mid_sync_asks_to_reconnect(session, monkeypatch):
    from garminconnect import GarminConnectAuthenticationError

    from app.garmin.client import GarminNotConnected, get_auth

    _fast(monkeypatch)
    with pytest.raises(GarminNotConnected):
        run_sync(session, FlakyGarmin(GarminConnectAuthenticationError("401")),
                 activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 15))
    assert get_auth(session).status == "needs_reconnect"


def test_unreachable_garmin_returns_502(logged_in, monkeypatch):
    from garminconnect import GarminConnectConnectionError

    def unreachable(session):
        raise GarminConnectConnectionError("connection reset")

    monkeypatch.setattr("app.routers.sync.restore_client", unreachable)
    res = logged_in.post("/api/sync")
    assert res.status_code == 502 and "Couldn't reach Garmin" in res.json()["detail"]

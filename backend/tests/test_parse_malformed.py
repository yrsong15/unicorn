"""Garmin's endpoints are undocumented; odd shapes must not crash a sync."""

from datetime import date

import pytest

from app.garmin import parse

JUNK = [None, 0, True, "x", [], {}, [None, 1, "x", []], {"a": [1]}, [{"generic": []}], {"lapDTOs": "x"}]
PARSERS = [
    parse.parse_activity, parse.parse_laps, parse.parse_vo2max_range, parse.parse_race_predictions,
    parse.parse_readiness, parse.parse_hrv, parse.parse_training_status, parse.parse_resting_hr,
    parse.parse_lactate_threshold, parse.parse_personal_records,
]


@pytest.mark.parametrize("parser", PARSERS, ids=lambda f: f.__name__)
@pytest.mark.parametrize("payload", JUNK, ids=repr)
def test_parsers_never_raise_on_junk(parser, payload):
    parser(payload)


def test_bad_entries_are_skipped_and_good_ones_kept():
    races = parse.parse_race_predictions([
        "junk", {"calendarDate": "not-a-date"}, {"calendarDate": "2026-10-15", "time5K": 1200},
    ])
    assert list(races) == [date(2026, 10, 15)]

    prs = parse.parse_personal_records([
        None, {"typeId": [3], "value": 1}, {"typeId": 3, "value": 1190.0, "activityId": "abc"},
    ])
    assert prs == [{"type_id": 3, "value": 1190.0, "activity_id": None, "record_date": None}]

    laps = parse.parse_laps({"lapDTOs": [None, {"lapIndex": "x", "distance": 1609.0}]})
    assert [lap["idx"] for lap in laps] == [2]

    vo2 = parse.parse_vo2max_range([{"generic": {"calendarDate": "bad", "vo2MaxValue": 50}},
                                    {"generic": {"calendarDate": "2026-10-15", "vo2MaxValue": 51}}])
    assert vo2 == {date(2026, 10, 15): 51.0}

    status = parse.parse_training_status({"mostRecentTrainingStatus": {"latestTrainingStatusData": {
        "dev": {"trainingStatus": True, "acuteTrainingLoadDTO": "x"}}}})
    assert status["training_status"] is None and status["acute_load"] is None


def test_one_bad_activity_does_not_stop_the_sync(session, monkeypatch):
    from app.garmin.sync import run_sync
    from tests.test_sync import FakeGarmin, _fast

    class OneBad(FakeGarmin):
        def get_activities_by_date(self, start, end):
            acts = super().get_activities_by_date(start, end)
            # The same activity twice; the stubbed upsert below rejects the repeat.
            return [acts[0], {**acts[0], "activityId": acts[0]["activityId"]}, *acts[1:]]

    monkeypatch.setattr("app.garmin.sync.upsert_run", _flaky_upsert())
    _fast(monkeypatch, today=date(2026, 10, 15))
    result = run_sync(session, OneBad(), activities_since=date(2026, 10, 13), metrics_since=date(2026, 10, 15))
    assert result["runs"] + result["rides"] == 3
    assert result["failed_requests"] == 1


def _flaky_upsert():
    from app.garmin import sync

    real = sync.upsert_run
    seen = set()

    def upsert(session, garmin, activity, call=None):
        key = activity.get("activityId")
        if key in seen:
            raise ValueError("bad activity")
        seen.add(key)
        return real(session, garmin, activity, call)

    return upsert

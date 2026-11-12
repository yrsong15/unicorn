"""Pure functions that turn Garmin Connect JSON into our field values.

Garmin's endpoints are undocumented and shift over time, so every lookup here is
defensive: a missing or renamed field becomes None instead of an exception.
"""

import re
from datetime import date, datetime
from typing import Any

from app.models import METERS_PER_MILE

RUN_CATEGORIES = {
    "running": "road",
    "street_running": "road",
    "treadmill_running": "treadmill",
    "indoor_running": "treadmill",
    "virtual_run": "treadmill",
    "track_running": "track",
    "trail_running": "trail",
    "ultra_run": "trail",
    "obstacle_run": "trail",
}

RIDE_CATEGORIES = {
    "cycling": "road",
    "road_biking": "road",
    "indoor_cycling": "indoor",
    "virtual_ride": "indoor",
    "mountain_biking": "mountain",
    "gravel_cycling": "gravel",
}


def dig(obj: Any, *path: str | int) -> Any:
    for key in path:
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list) and isinstance(key, int) and -len(obj) <= key < len(obj):
            obj = obj[key]
        else:
            return None
    return obj


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def run_category(activity: dict) -> str | None:
    return RUN_CATEGORIES.get(dig(activity, "activityType", "typeKey") or "")


def sport_and_category(activity: dict) -> tuple[str, str] | None:
    type_key = dig(activity, "activityType", "typeKey") or ""
    if type_key in RUN_CATEGORIES:
        return "run", RUN_CATEGORIES[type_key]
    if type_key in RIDE_CATEGORIES:
        return "ride", RIDE_CATEGORIES[type_key]
    return None


def parse_activity(activity: dict) -> dict | None:
    """Fields for a Run row (a run or a ride), or None for any other activity."""
    kind = sport_and_category(activity)
    start_local = _dt(activity.get("startTimeLocal"))
    activity_id = activity.get("activityId")
    if kind is None or start_local is None or activity_id is None:
        return None
    sport, category = kind
    cadence = "averageRunningCadenceInStepsPerMinute" if sport == "run" else "averageBikingCadenceInRevPerMinute"
    zones = [_num(activity.get(f"hrTimeInZone_{i}")) for i in range(1, 6)]
    return {
        "garmin_activity_id": int(activity_id),
        "start_local": start_local,
        "start_utc": _dt(activity.get("startTimeGMT")) or start_local,
        "local_date": start_local.date(),
        "name": activity.get("activityName") or ("Run" if sport == "run" else "Ride"),
        "type_key": dig(activity, "activityType", "typeKey"),
        "sport": sport,
        "category": category,
        "distance_m": _num(activity.get("distance")) or 0.0,
        "duration_s": _num(activity.get("duration")) or 0.0,
        "moving_s": _num(activity.get("movingDuration")),
        "avg_hr": _num(activity.get("averageHR")),
        "max_hr": _num(activity.get("maxHR")),
        "avg_cadence": _num(activity.get(cadence)),
        "elev_gain_m": _num(activity.get("elevationGain")),
        "aerobic_te": _num(activity.get("aerobicTrainingEffect")),
        "anaerobic_te": _num(activity.get("anaerobicTrainingEffect")),
        "training_load": _num(activity.get("activityTrainingLoad")),
        "vo2max": _num(activity.get("vO2MaxValue")),
        "hr_zones": [z or 0.0 for z in zones] if any(zones) else None,
        "raw": strip_personal(activity),
    }


# Activity fields that identify the athlete or where they were. Not needed for
# anything the app shows, so they aren't stored.
_COORDINATE_KEY = re.compile(r"(^|[a-z])(lat|lon|Lat|Lon)(itude|gitude)?$")
_PERSONAL_KEY = re.compile(r"location|owner|profile|device|polyline|geo|userpro|username|displayname|fullname", re.I)


def strip_personal(activity: dict) -> dict:
    return {k: v for k, v in activity.items() if not (_COORDINATE_KEY.search(k) or _PERSONAL_KEY.search(k))}


def parse_laps(splits: dict | None) -> list[dict]:
    laps = []
    for i, lap in enumerate(dig(splits, "lapDTOs") or []):
        laps.append(
            {
                "idx": int(lap.get("lapIndex") or i + 1),
                "distance_m": _num(lap.get("distance")) or 0.0,
                "duration_s": _num(lap.get("duration")) or 0.0,
                "avg_hr": _num(lap.get("averageHR")),
                "avg_cadence": _num(lap.get("averageRunCadence")),
                "elev_gain_m": _num(lap.get("elevationGain")),
            }
        )
    return laps


def parse_vo2max_range(payload: Any) -> dict[date, float]:
    out: dict[date, float] = {}
    for entry in payload if isinstance(payload, list) else []:
        generic = dig(entry, "generic") or {}
        value = _num(generic.get("vo2MaxPreciseValue")) or _num(generic.get("vo2MaxValue"))
        day = generic.get("calendarDate")
        if value and isinstance(day, str):
            out[date.fromisoformat(day[:10])] = value
    return out


def parse_race_predictions(payload: Any) -> dict[date, dict]:
    entries = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
    out: dict[date, dict] = {}
    for entry in entries:
        day = entry.get("calendarDate")
        if not isinstance(day, str):
            continue
        out[date.fromisoformat(day[:10])] = {
            "race_5k_s": _num(entry.get("time5K")),
            "race_10k_s": _num(entry.get("time10K")),
            "race_half_s": _num(entry.get("timeHalfMarathon")),
            "race_full_s": _num(entry.get("timeMarathon")),
        }
    return out


def parse_readiness(payload: Any) -> dict:
    snapshots = [s for s in payload if isinstance(s, dict)] if isinstance(payload, list) else []
    if not snapshots:
        return {}
    latest = max(snapshots, key=lambda s: s.get("timestamp") or "")
    return {"readiness_score": _num(latest.get("score")), "readiness_level": latest.get("level")}


def parse_hrv(payload: Any) -> dict:
    summary = dig(payload, "hrvSummary") or {}
    return {
        "hrv_last_night": _num(summary.get("lastNightAvg")),
        "hrv_weekly_avg": _num(summary.get("weeklyAvg")),
        "hrv_status": summary.get("status"),
    }


def parse_training_status(payload: Any) -> dict:
    by_device = dig(payload, "mostRecentTrainingStatus", "latestTrainingStatusData") or {}
    devices = [d for d in by_device.values() if isinstance(d, dict)]
    # Prefer the primary training device when Garmin marks one.
    devices.sort(key=lambda d: not d.get("primaryTrainingDevice"))
    if not devices:
        return {}
    data = devices[0]
    load = data.get("acuteTrainingLoadDTO") or {}
    return {
        "training_status": data.get("trainingStatusFeedbackPhrase") or _status_name(data.get("trainingStatus")),
        "acute_load": _num(load.get("dailyTrainingLoadAcute")),
        "chronic_load": _num(load.get("dailyTrainingLoadChronic")),
        "acwr": _num(load.get("dailyAcuteChronicWorkloadRatio")),
    }


_TRAINING_STATUS = {
    0: "NO_STATUS", 1: "DETRAINING", 2: "RECOVERY", 3: "MAINTAINING", 4: "PRODUCTIVE",
    5: "PEAKING", 6: "OVERREACHING", 7: "UNPRODUCTIVE", 8: "STRAINED",
}


def _status_name(code: Any) -> str | None:
    return _TRAINING_STATUS.get(code) if isinstance(code, int) else None


def parse_resting_hr(user_summary: Any) -> dict:
    return {"resting_hr": _num(dig(user_summary, "restingHeartRate"))}


def parse_lactate_threshold(payload: Any) -> dict:
    data = dig(payload, "speed_and_heart_rate") or {}
    hr = _num(data.get("heartRate"))
    speed = _num(data.get("speed"))
    # Garmin reports LT speed in tenths of m/s on this endpoint (0.36 ≈ 3.6 m/s).
    if speed is not None and speed < 1.5:
        speed *= 10
    pace = METERS_PER_MILE / speed if speed else None
    return {"lt_hr": hr, "lt_pace_s_per_mile": pace}


# typeIds from Garmin's personal-record service for running.
PR_TYPES = {1: "1K", 2: "1 mile", 3: "5K", 4: "10K", 5: "Half marathon", 6: "Marathon", 7: "Longest run"}


def parse_personal_records(payload: Any) -> list[dict]:
    out = []
    for entry in payload if isinstance(payload, list) else []:
        type_id = entry.get("typeId")
        value = _num(entry.get("value"))
        if type_id not in PR_TYPES or value is None:
            continue
        when = entry.get("prStartTimeGmtFormatted") or entry.get("actStartDateTimeInGMTFormatted")
        parsed = _dt(when) if isinstance(when, str) else None
        out.append(
            {
                "type_id": type_id,
                "value": value,
                "activity_id": entry.get("activityId"),
                "record_date": parsed.date() if parsed else None,
            }
        )
    return out

"""API response shapes. Distances are miles, paces are seconds per mile."""

from datetime import date, datetime

from pydantic import BaseModel

from app.models import METERS_PER_MILE, Lap, Run, RunShoe, Shoe


def miles(meters: float | None) -> float | None:
    return None if meters is None else meters / METERS_PER_MILE


def pace(distance_m: float, seconds: float | None) -> float | None:
    if not distance_m or not seconds:
        return None
    return seconds / (distance_m / METERS_PER_MILE)


def speed_mph(distance_m: float, seconds: float | None) -> float | None:
    if not distance_m or not seconds:
        return None
    return distance_m / METERS_PER_MILE / (seconds / 3600)


class ShoeSegmentOut(BaseModel):
    shoe_id: int
    shoe_name: str
    miles: float
    lap_from: int | None
    lap_to: int | None


class RunSummaryOut(BaseModel):
    id: int
    garmin_activity_id: int
    name: str
    start_local: datetime
    local_date: date
    sport: str  # run | ride
    category: str
    miles: float
    duration_s: float
    pace_s_per_mile: float | None
    speed_mph: float | None
    avg_hr: float | None
    training_load: float | None
    shoes: list[ShoeSegmentOut]
    unassigned_miles: float


class LapOut(BaseModel):
    idx: int
    miles: float
    duration_s: float
    pace_s_per_mile: float | None
    speed_mph: float | None
    avg_hr: float | None
    avg_cadence: float | None
    elev_gain_ft: float | None


class RunDetailOut(RunSummaryOut):
    moving_s: float | None
    max_hr: float | None
    avg_cadence: float | None
    elev_gain_ft: float | None
    aerobic_te: float | None
    anaerobic_te: float | None
    vo2max: float | None
    hr_zones_s: list[float] | None
    laps: list[LapOut]


class ShoeOut(BaseModel):
    id: int
    name: str
    brand: str | None
    model: str | None
    color: str | None
    start_miles: float
    retire_at_miles: float
    is_default: bool
    default_for_category: str | None
    retired_at: date | None
    notes: str | None
    miles: float
    wear: str  # ok | warn | over
    run_count: int


def segment_out(seg: RunShoe, shoes: dict[int, Shoe]) -> ShoeSegmentOut:
    shoe = shoes.get(seg.shoe_id)
    return ShoeSegmentOut(
        shoe_id=seg.shoe_id,
        shoe_name=shoe.name if shoe else "Unknown shoe",
        miles=seg.distance_m / METERS_PER_MILE,
        lap_from=seg.lap_from,
        lap_to=seg.lap_to,
    )


def run_summary(run: Run, segments: list[RunShoe], shoes: dict[int, Shoe]) -> dict:
    assigned = sum(s.distance_m for s in segments)
    return {
        "id": run.id,
        "garmin_activity_id": run.garmin_activity_id,
        "name": run.name,
        "start_local": run.start_local,
        "local_date": run.local_date,
        "sport": run.sport,
        "category": run.category,
        "miles": run.distance_m / METERS_PER_MILE,
        "duration_s": run.duration_s,
        "pace_s_per_mile": pace(run.distance_m, run.moving_s or run.duration_s),
        "speed_mph": speed_mph(run.distance_m, run.moving_s or run.duration_s),
        "avg_hr": run.avg_hr,
        "training_load": run.training_load,
        "shoes": [segment_out(s, shoes) for s in segments],
        "unassigned_miles": max(0.0, (run.distance_m - assigned) / METERS_PER_MILE),
    }


def run_detail(run: Run, segments: list[RunShoe], shoes: dict[int, Shoe], laps: list[Lap]) -> RunDetailOut:
    feet = lambda m: None if m is None else m * 3.28084  # noqa: E731
    return RunDetailOut(
        **run_summary(run, segments, shoes),
        moving_s=run.moving_s,
        max_hr=run.max_hr,
        avg_cadence=run.avg_cadence,
        elev_gain_ft=feet(run.elev_gain_m),
        aerobic_te=run.aerobic_te,
        anaerobic_te=run.anaerobic_te,
        vo2max=run.vo2max,
        hr_zones_s=run.hr_zones,
        laps=[
            LapOut(
                idx=lap.idx,
                miles=lap.distance_m / METERS_PER_MILE,
                duration_s=lap.duration_s,
                pace_s_per_mile=pace(lap.distance_m, lap.duration_s),
                speed_mph=speed_mph(lap.distance_m, lap.duration_s),
                avg_hr=lap.avg_hr,
                avg_cadence=lap.avg_cadence,
                elev_gain_ft=feet(lap.elev_gain_m),
            )
            for lap in sorted(laps, key=lambda lap: lap.idx)
        ],
    )

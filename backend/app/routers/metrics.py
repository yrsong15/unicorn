from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.clock import local_today
from app.db import get_session
from app.models import DailyMetrics, Run
from app.services.mileage import range_start

router = APIRouter(prefix="/metrics", tags=["metrics"])

FITNESS = ["vo2max", "resting_hr", "race_5k_s", "race_10k_s", "race_half_s", "race_full_s", "lt_hr", "lt_pace_s_per_mile"]
TRAINING = ["acute_load", "chronic_load", "acwr", "readiness_score", "readiness_level",
            "hrv_last_night", "hrv_weekly_avg", "hrv_status", "training_status"]


def _series(session: Session, range_key: str, fields: list[str]) -> list[dict]:
    first = session.exec(select(DailyMetrics.day).order_by(DailyMetrics.day)).first()
    try:
        start = range_start(range_key, local_today(session), first)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    rows = session.exec(select(DailyMetrics).where(DailyMetrics.day >= start).order_by(DailyMetrics.day))
    out = []
    for row in rows:
        values = {f: getattr(row, f) for f in fields}
        if any(v is not None for v in values.values()):
            out.append({"day": row.day, **values})
    return out


@router.get("/fitness")
def fitness(range: str = "6m", session: Session = Depends(get_session)):  # noqa: A002
    series = _series(session, range, FITNESS)
    latest = {f: next((d[f] for d in reversed(series) if d[f] is not None), None) for f in FITNESS}
    return {"range": range, "series": series, "latest": latest}


@router.get("/training")
def training(range: str = "3m", session: Session = Depends(get_session)):  # noqa: A002
    series = _series(session, range, TRAINING)
    latest = {f: next((d[f] for d in reversed(series) if d[f] is not None), None) for f in TRAINING}
    today = local_today(session)
    first = series[0]["day"] if series else today
    return {"range": range, "series": series, "latest": latest, "daily_load": daily_load(session, first, today)}


def daily_load(session: Session, start: date, end: date) -> list[dict]:
    """Zero-filled daily Garmin training load from `start` through `end`, split by sport."""
    days = {start + timedelta(days=i): {"run": 0.0, "ride": 0.0} for i in range((end - start).days + 1)}
    rows = session.exec(select(Run.local_date, Run.sport, Run.training_load).where(Run.local_date >= start, Run.local_date <= end))
    for day, sport, load in rows:
        if sport in days[day]:
            days[day][sport] += load or 0.0
    return [
        {"day": d, "run": round(v["run"], 1), "ride": round(v["ride"], 1), "total": round(v["run"] + v["ride"], 1)}
        for d, v in days.items()
    ]

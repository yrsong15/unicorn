from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.clock import local_today
from app.db import get_session
from app.models import DailyMetrics, Run, Shoe
from app.routers.shoes import shoe_out
from app.services.mileage import bucket_weeks, trailing_load_per_run_mile, weekly_series, week_start
from app.services.shoes import logged_meters_by_shoe

router = APIRouter(prefix="/summary", tags=["summary"])


def _week_dict(w) -> dict:
    return {
        "week_start": w.start,
        "week_end": w.start + timedelta(days=6),
        "run_miles": round(w.miles, 2),
        "ride_equiv_miles": round(w.ride_equiv_miles, 2),
        "total_miles": round(w.total_miles, 2),
        "runs": w.runs,
        "rides": w.rides,
        "longest_miles": round(w.longest_miles, 2),
        "rolling_avg": round(w.rolling_avg, 2),
        "rolling_avg_total": round(w.rolling_avg_total, 2),
        "run_ids": w.run_ids,
        "ride_ids": w.ride_ids,
    }


def _factor(per_mile: float | None) -> float | None:
    return None if per_mile is None else round(per_mile, 2)


@router.get("/weekly")
def weekly(range: str = "3m", session: Session = Depends(get_session)):  # noqa: A002
    try:
        weeks, per_mile = weekly_series(session, range, local_today(session))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"range": range, "load_per_run_mile": _factor(per_mile), "weeks": [_week_dict(w) for w in weeks]}


@router.get("/dashboard")
def dashboard(session: Session = Depends(get_session)):
    today = local_today(session)
    this_week = week_start(today)
    last_week = this_week - timedelta(weeks=1)
    runs = list(session.exec(select(Run).where(Run.local_date >= last_week)))
    per_mile = trailing_load_per_run_mile(session, today)
    last, this = bucket_weeks(runs, last_week, today, per_mile)

    logged = logged_meters_by_shoe(session)
    active = [shoe_out(session, s, logged) for s in session.exec(select(Shoe).where(Shoe.retired_at.is_(None)))]
    latest_metrics = session.exec(select(DailyMetrics).order_by(DailyMetrics.day.desc())).first()
    return {
        "this_week": _week_dict(this),
        "last_week": _week_dict(last),
        "load_per_run_mile": _factor(per_mile),
        "shoe_alerts": [s for s in active if s.wear != "ok"],
        "today": latest_metrics.model_dump() if latest_metrics else None,
    }

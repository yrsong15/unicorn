from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, func, select

from app.db import get_session
from app.models import METERS_PER_MILE, Lap, Run, RunShoe, Shoe
from app.schemas import RunDetailOut, RunSummaryOut, run_detail, run_summary
from app.services.shoes import SegmentError, SegmentInput, replace_segments
from app.validation import MAX_ID, MAX_MILES, BodyId, DbId, OptionalDbIdQuery

router = APIRouter(prefix="/runs", tags=["runs"])
SPORTS = {"run", "ride", "all"}


def _shoes(session: Session) -> dict[int, Shoe]:
    return {s.id: s for s in session.exec(select(Shoe))}


def _segments(session: Session, run_ids: list[int]) -> dict[int, list[RunShoe]]:
    out: dict[int, list[RunShoe]] = {rid: [] for rid in run_ids}
    if run_ids:
        for seg in session.exec(select(RunShoe).where(RunShoe.run_id.in_(run_ids)).order_by(RunShoe.id)):
            out[seg.run_id].append(seg)
    return out


class RunPage(BaseModel):
    items: list[RunSummaryOut]
    total: int


@router.get("", response_model=RunPage)
def list_runs(
    start: date | None = None,
    end: date | None = None,
    shoe_id: OptionalDbIdQuery = None,
    ids: str | None = Query(default=None, max_length=5000),
    sport: str = "run",
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    if sport not in SPORTS:
        raise HTTPException(422, f"Sport must be one of {sorted(SPORTS)}")
    query = select(Run)
    if sport != "all":
        query = query.where(Run.sport == sport)
    if start:
        query = query.where(Run.local_date >= start)
    if end:
        query = query.where(Run.local_date <= end)
    if shoe_id is not None:
        query = query.where(Run.id.in_(select(RunShoe.run_id).where(RunShoe.shoe_id == shoe_id)))
    if ids:
        wanted = [int(i) for i in ids.split(",") if i.strip().isdigit()]
        query = query.where(Run.id.in_([i for i in wanted if 1 <= i <= MAX_ID]))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    runs = list(session.exec(query.order_by(Run.start_local.desc()).offset(offset).limit(limit)))
    segments = _segments(session, [r.id for r in runs])
    shoes = _shoes(session)
    return {"items": [run_summary(r, segments[r.id], shoes) for r in runs], "total": total}


def _get_run(session: Session, run_id: int) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}", response_model=RunDetailOut)
def get_run(run_id: DbId, session: Session = Depends(get_session)):
    run = _get_run(session, run_id)
    laps = list(session.exec(select(Lap).where(Lap.run_id == run.id)))
    return run_detail(run, _segments(session, [run.id])[run.id], _shoes(session), laps)


class SegmentIn(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    shoe_id: BodyId
    miles: float | None = Field(default=None, gt=0, le=MAX_MILES)
    lap_from: int | None = Field(default=None, ge=1, le=10_000)
    lap_to: int | None = Field(default=None, ge=1, le=10_000)


class SegmentsIn(BaseModel):
    segments: list[SegmentIn] = Field(max_length=50)


@router.put("/{run_id}/shoes", response_model=RunDetailOut)
def set_run_shoes(run_id: DbId, body: SegmentsIn, session: Session = Depends(get_session)):
    run = _get_run(session, run_id)
    inputs = [
        SegmentInput(
            shoe_id=s.shoe_id,
            distance_m=None if s.miles is None else s.miles * METERS_PER_MILE,
            lap_from=s.lap_from,
            lap_to=s.lap_to,
        )
        for s in body.segments
    ]
    try:
        replace_segments(session, run, inputs)
    except SegmentError as exc:
        raise HTTPException(422, str(exc)) from exc
    return get_run(run_id, session)

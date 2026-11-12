from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import METERS_PER_MILE, Lap, Run, RunShoe, Shoe
from app.schemas import ShoeOut

# A split may overshoot the run's distance by this much (GPS rounding, typing 2.0 for 1.98).
TOLERANCE_M = 0.05 * METERS_PER_MILE
WARN_FRACTION = 0.85


class SegmentError(ValueError):
    pass


@dataclass
class SegmentInput:
    shoe_id: int
    distance_m: float | None = None
    lap_from: int | None = None
    lap_to: int | None = None


def default_shoe_for(session: Session, category: str) -> Shoe | None:
    active = select(Shoe).where(Shoe.retired_at.is_(None))
    by_category = session.exec(active.where(Shoe.default_for_category == category)).first()
    return by_category or session.exec(active.where(Shoe.is_default.is_(True))).first()


def apply_default_shoe(session: Session, run: Run) -> None:
    """Give a newly imported run its default shoe, covering the whole distance. Rides get none."""
    if run.sport != "run":
        return
    has_segments = session.exec(select(RunShoe).where(RunShoe.run_id == run.id)).first()
    if has_segments or run.distance_m <= 0:
        return
    shoe = default_shoe_for(session, run.category)
    if shoe is not None:
        session.add(RunShoe(run_id=run.id, shoe_id=shoe.id, distance_m=run.distance_m))


def resolve_segments(session: Session, run: Run, segments: list[SegmentInput]) -> list[RunShoe]:
    """Validate a full replacement list of shoe segments for a run."""
    if run.sport != "run" and segments:
        raise SegmentError("Rides don't track shoes")
    laps = {lap.idx: lap for lap in session.exec(select(Lap).where(Lap.run_id == run.id))}
    resolved: list[RunShoe] = []
    for seg in segments:
        if session.get(Shoe, seg.shoe_id) is None:
            raise SegmentError(f"Shoe {seg.shoe_id} doesn't exist")
        distance = seg.distance_m
        if seg.lap_from is not None:
            lap_to = seg.lap_to if seg.lap_to is not None else seg.lap_from
            if lap_to < seg.lap_from:
                raise SegmentError("Lap range is backwards")
            missing = [i for i in range(seg.lap_from, lap_to + 1) if i not in laps]
            if missing:
                raise SegmentError(f"Run has no lap {missing[0]}")
            if distance is None:
                distance = sum(laps[i].distance_m for i in range(seg.lap_from, lap_to + 1))
        if distance is None or distance <= 0:
            raise SegmentError("Each shoe needs a distance greater than 0")
        resolved.append(
            RunShoe(
                run_id=run.id,
                shoe_id=seg.shoe_id,
                distance_m=distance,
                lap_from=seg.lap_from,
                lap_to=seg.lap_to if seg.lap_from is not None else None,
            )
        )
    total = sum(s.distance_m for s in resolved)
    if total > run.distance_m + TOLERANCE_M:
        raise SegmentError(
            f"Shoes add up to {total / METERS_PER_MILE:.2f} mi, "
            f"but the run is only {run.distance_m / METERS_PER_MILE:.2f} mi"
        )
    return resolved


def replace_segments(session: Session, run: Run, segments: list[SegmentInput]) -> list[RunShoe]:
    resolved = resolve_segments(session, run, segments)
    for existing in session.exec(select(RunShoe).where(RunShoe.run_id == run.id)):
        session.delete(existing)
    session.flush()
    for seg in resolved:
        session.add(seg)
    session.commit()
    return resolved


def logged_meters_by_shoe(session: Session) -> dict[int, float]:
    rows = session.exec(select(RunShoe.shoe_id, func.sum(RunShoe.distance_m)).group_by(RunShoe.shoe_id))
    return {shoe_id: total or 0.0 for shoe_id, total in rows}


def shoe_miles(shoe: Shoe, logged_m: float) -> float:
    return shoe.start_miles + logged_m / METERS_PER_MILE


def wear_level(miles: float, retire_at: float) -> str:
    if retire_at <= 0:
        return "ok"
    if miles >= retire_at:
        return "over"
    if miles >= retire_at * WARN_FRACTION:
        return "warn"
    return "ok"


def run_counts_by_shoe(session: Session) -> dict[int, int]:
    rows = session.exec(
        select(RunShoe.shoe_id, func.count(func.distinct(RunShoe.run_id))).group_by(RunShoe.shoe_id)
    )
    return {shoe_id: count for shoe_id, count in rows}


def shoes_out(session: Session, shoes: list[Shoe]) -> list[ShoeOut]:
    """API view of each shoe, with mileage and run counts from two grouped queries."""
    logged = logged_meters_by_shoe(session)
    counts = run_counts_by_shoe(session)
    out = []
    for shoe in shoes:
        miles = shoe_miles(shoe, logged.get(shoe.id, 0.0))
        out.append(ShoeOut(
            **shoe.model_dump(exclude={"created_at"}),
            miles=miles,
            wear=wear_level(miles, shoe.retire_at_miles),
            run_count=counts.get(shoe.id, 0),
        ))
    return out


def shoe_out(session: Session, shoe: Shoe) -> ShoeOut:
    return shoes_out(session, [shoe])[0]

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlmodel import Session, func, select

from app.clock import local_today
from app.db import get_session
from app.models import RunShoe, Shoe
from app.schemas import ShoeOut
from app.services.shoes import logged_meters_by_shoe, shoe_miles, wear_level
from app.validation import MAX_MILES, DbId

router = APIRouter(prefix="/shoes", tags=["shoes"])
CATEGORIES = {"road", "treadmill", "track", "trail"}


def shoe_out(session: Session, shoe: Shoe, logged: dict[int, float] | None = None) -> ShoeOut:
    logged = logged if logged is not None else logged_meters_by_shoe(session)
    miles = shoe_miles(shoe, logged.get(shoe.id, 0.0))
    run_count = session.exec(
        select(func.count(func.distinct(RunShoe.run_id))).where(RunShoe.shoe_id == shoe.id)
    ).one()
    return ShoeOut(
        **shoe.model_dump(exclude={"created_at"}),
        miles=miles,
        wear=wear_level(miles, shoe.retire_at_miles),
        run_count=run_count,
    )


@router.get("", response_model=list[ShoeOut])
def list_shoes(session: Session = Depends(get_session)):
    query = select(Shoe).order_by(Shoe.retired_at.is_not(None), Shoe.created_at.desc())
    logged = logged_meters_by_shoe(session)
    return [shoe_out(session, s, logged) for s in session.exec(query)]


COLOR = r"^#[0-9a-fA-F]{6}$"


class ShoeIn(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    name: str = Field(min_length=1, max_length=80)
    brand: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, pattern=COLOR)
    start_miles: float = Field(default=0, ge=0, le=MAX_MILES)
    retire_at_miles: float = Field(default=400, gt=0, le=MAX_MILES)
    is_default: bool = False
    default_for_category: str | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ShoePatch(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    name: str | None = Field(default=None, min_length=1, max_length=80)
    brand: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, pattern=COLOR)
    start_miles: float | None = Field(default=None, ge=0, le=MAX_MILES)
    retire_at_miles: float | None = Field(default=None, gt=0, le=MAX_MILES)
    is_default: bool | None = None
    default_for_category: str | None = None
    retired_at: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def required_fields_not_null(self):
        # These may be left out of a patch, but not set to null.
        nulled = [f for f in ("name", "start_miles", "retire_at_miles", "is_default")
                  if f in self.model_fields_set and getattr(self, f) is None]
        if nulled:
            raise ValueError(f"{', '.join(nulled)} can't be null")
        return self


def _apply_defaults(session: Session, shoe: Shoe) -> None:
    """Only one overall default, and one default per run category."""
    if shoe.default_for_category is not None and shoe.default_for_category not in CATEGORIES:
        raise HTTPException(422, f"Category must be one of {sorted(CATEGORIES)}")
    for other in session.exec(select(Shoe).where(Shoe.id != shoe.id)):
        changed = False
        if shoe.is_default and other.is_default:
            other.is_default, changed = False, True
        if shoe.default_for_category and other.default_for_category == shoe.default_for_category:
            other.default_for_category, changed = None, True
        if changed:
            session.add(other)


@router.post("", response_model=ShoeOut, status_code=201)
def create_shoe(body: ShoeIn, session: Session = Depends(get_session)):
    shoe = Shoe(**body.model_dump())
    session.add(shoe)
    session.flush()
    _apply_defaults(session, shoe)
    session.commit()
    session.refresh(shoe)
    return shoe_out(session, shoe)


def _get(session: Session, shoe_id: int) -> Shoe:
    shoe = session.get(Shoe, shoe_id)
    if shoe is None:
        raise HTTPException(404, "Shoe not found")
    return shoe


@router.patch("/{shoe_id}", response_model=ShoeOut)
def update_shoe(shoe_id: DbId, body: ShoePatch, session: Session = Depends(get_session)):
    shoe = _get(session, shoe_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(shoe, key, value)
    if shoe.retired_at is not None:
        shoe.is_default, shoe.default_for_category = False, None
    _apply_defaults(session, shoe)
    session.add(shoe)
    session.commit()
    session.refresh(shoe)
    return shoe_out(session, shoe)


@router.post("/{shoe_id}/retire", response_model=ShoeOut)
def retire_shoe(shoe_id: DbId, session: Session = Depends(get_session)):
    return update_shoe(shoe_id, ShoePatch(retired_at=local_today(session)), session)


@router.post("/{shoe_id}/unretire", response_model=ShoeOut)
def unretire_shoe(shoe_id: DbId, session: Session = Depends(get_session)):
    shoe = _get(session, shoe_id)
    shoe.retired_at = None
    session.add(shoe)
    session.commit()
    session.refresh(shoe)
    return shoe_out(session, shoe)

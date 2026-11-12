from datetime import UTC, date, datetime
from typing import Any

from pydantic import NaiveDatetime
from sqlalchemy import JSON, BigInteger, Column, DateTime, Text
from sqlmodel import Field, SQLModel

METERS_PER_MILE = 1609.344


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class GarminAuth(SQLModel, table=True):
    __tablename__ = "garmin_auth"

    id: int = Field(default=1, primary_key=True)
    tokens_encrypted: str | None = Field(default=None, sa_column=Column(Text))
    status: str = "disconnected"  # disconnected | ok | needs_reconnect
    last_error: str | None = None
    updated_at: NaiveDatetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=False), nullable=False))


class SyncState(SQLModel, table=True):
    __tablename__ = "sync_state"

    id: int = Field(default=1, primary_key=True)
    last_sync_at: NaiveDatetime | None = Field(default=None, sa_column=Column(DateTime(timezone=False), nullable=True))
    started_at: NaiveDatetime | None = Field(default=None, sa_column=Column(DateTime(timezone=False), nullable=True))
    last_activity_start: NaiveDatetime | None = Field(default=None, sa_column=Column(DateTime(timezone=False), nullable=True))
    last_metrics_date: date | None = None
    status: str = "idle"  # idle | running | ok | error
    message: str | None = None


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: int | None = Field(default=None, primary_key=True)
    # Garmin activity IDs exceed 32-bit integers.
    garmin_activity_id: int = Field(sa_column=Column(BigInteger, unique=True, index=True, nullable=False))
    start_utc: NaiveDatetime = Field(sa_column=Column(DateTime(timezone=False), nullable=False))
    start_local: NaiveDatetime = Field(sa_column=Column(DateTime(timezone=False), nullable=False))
    local_date: date = Field(index=True)
    name: str = ""
    type_key: str = "running"
    # Rides share this table so they can count toward weekly load; shoes and records stay run-only.
    sport: str = Field(default="run", index=True, sa_column_kwargs={"server_default": "run"})  # run | ride
    category: str = "road"  # runs: road | treadmill | track | trail; rides: road | indoor | mountain | gravel
    distance_m: float = 0
    duration_s: float = 0
    moving_s: float | None = None
    avg_hr: float | None = None
    max_hr: float | None = None
    avg_cadence: float | None = None
    elev_gain_m: float | None = None
    aerobic_te: float | None = None
    anaerobic_te: float | None = None
    training_load: float | None = None
    vo2max: float | None = None
    hr_zones: list[float] | None = Field(default=None, sa_column=Column(JSON))
    raw: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class Lap(SQLModel, table=True):
    __tablename__ = "laps"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id", index=True, ondelete="CASCADE")
    idx: int
    distance_m: float = 0
    duration_s: float = 0
    avg_hr: float | None = None
    avg_cadence: float | None = None
    elev_gain_m: float | None = None


class Shoe(SQLModel, table=True):
    __tablename__ = "shoes"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    brand: str | None = None
    model: str | None = None
    color: str | None = None
    start_miles: float = 0
    retire_at_miles: float = 400
    is_default: bool = False
    default_for_category: str | None = None
    retired_at: date | None = None
    notes: str | None = None
    created_at: NaiveDatetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=False), nullable=False))


class RunShoe(SQLModel, table=True):
    __tablename__ = "run_shoes"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id", index=True, ondelete="CASCADE")
    shoe_id: int = Field(foreign_key="shoes.id", index=True)
    distance_m: float
    lap_from: int | None = None
    lap_to: int | None = None
    note: str | None = None


class DailyMetrics(SQLModel, table=True):
    __tablename__ = "daily_metrics"

    day: date = Field(primary_key=True)
    vo2max: float | None = None
    resting_hr: float | None = None
    hrv_last_night: float | None = None
    hrv_weekly_avg: float | None = None
    hrv_status: str | None = None
    readiness_score: float | None = None
    readiness_level: str | None = None
    training_status: str | None = None
    acute_load: float | None = None
    chronic_load: float | None = None
    acwr: float | None = None
    race_5k_s: float | None = None
    race_10k_s: float | None = None
    race_half_s: float | None = None
    race_full_s: float | None = None
    lt_hr: float | None = None
    lt_pace_s_per_mile: float | None = None


class LoginAttempt(SQLModel, table=True):
    """Failed logins per client IP, for throttling password guesses."""

    __tablename__ = "login_attempts"

    ip: str = Field(primary_key=True, max_length=64)
    failures: int = 0
    first_failure_at: NaiveDatetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=False), nullable=False))
    locked_until: NaiveDatetime | None = Field(default=None, sa_column=Column(DateTime(timezone=False), nullable=True))


class PersonalRecord(SQLModel, table=True):
    __tablename__ = "personal_records"

    type_id: int = Field(primary_key=True)
    value: float
    activity_id: int | None = Field(default=None, sa_column=Column(BigInteger))
    record_date: date | None = None

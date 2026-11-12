"""Throttle password guesses.

Each client IP gets MAX_FAILURES wrong passwords per WINDOW, then is locked out
for LOCKOUT. Across all IPs, more than GLOBAL_MAX_FAILURES in GLOBAL_WINDOW
locks every login for LOCKOUT, which bounds a guessing attack spread over many
IPs. That global lock can also block the owner from signing in during an
attack; existing sessions keep working.

State lives in the database because serverless instances share no memory.
"""

from datetime import datetime, timedelta

from fastapi import Request
from sqlmodel import Session, delete, func, select

from app.config import ON_VERCEL
from app.models import LoginAttempt, utcnow

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)
LOCKOUT = timedelta(minutes=15)
GLOBAL_MAX_FAILURES = 100
GLOBAL_WINDOW = timedelta(hours=1)


def client_ip(request: Request) -> str:
    # Vercel's edge sets X-Forwarded-For itself, so it can be trusted there.
    # Anywhere else a client could forge it, so use the socket address.
    if ON_VERCEL:
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() or request.headers.get("x-real-ip", "")
        if ip:
            return ip[:64]
    return (request.client.host if request.client else "unknown")[:64]


def locked_for(session: Session, ip: str, now: datetime | None = None) -> timedelta | None:
    """How much longer `ip` must wait, or None if it may try a password."""
    now = now or utcnow()
    row = session.get(LoginAttempt, ip)
    if row and row.locked_until and row.locked_until > now:
        return row.locked_until - now
    recent = session.exec(
        select(func.coalesce(func.sum(LoginAttempt.failures), 0)).where(
            LoginAttempt.first_failure_at > now - GLOBAL_WINDOW
        )
    ).one()
    if recent >= GLOBAL_MAX_FAILURES:
        return LOCKOUT
    return None


def record_failure(session: Session, ip: str, now: datetime | None = None) -> None:
    now = now or utcnow()
    row = session.get(LoginAttempt, ip)
    if row is None or now - row.first_failure_at > WINDOW:
        row = row or LoginAttempt(ip=ip)
        row.failures, row.first_failure_at, row.locked_until = 0, now, None
    row.failures += 1
    if row.failures >= MAX_FAILURES:
        row.locked_until = now + LOCKOUT
    session.add(row)
    # Drop stale rows so the table stays small.
    session.exec(
        delete(LoginAttempt).where(
            LoginAttempt.first_failure_at < now - max(WINDOW, GLOBAL_WINDOW) - LOCKOUT,
            LoginAttempt.ip != ip,
        )
    )
    session.commit()


def record_success(session: Session, ip: str) -> None:
    session.exec(delete(LoginAttempt).where(LoginAttempt.ip == ip))
    session.commit()

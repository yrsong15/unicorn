import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from garminconnect import GarminConnectConnectionError, GarminConnectTooManyRequestsError
from sqlmodel import Session

from app.config import CRON_SECRET
from app.db import get_session
from app.garmin.client import GarminNotConnected, get_auth, restore_client
from app.garmin.sync import SyncBusy, SyncFailed, get_state, is_stale, run_sync

router = APIRouter(tags=["sync"])


def _status(session: Session) -> dict:
    state, auth = get_state(session), get_auth(session)
    return {
        "garmin": {"status": auth.status, "last_error": auth.last_error, "updated_at": auth.updated_at},
        "last_sync_at": state.last_sync_at,
        "status": state.status,
        "message": state.message,
        "last_activity_start": state.last_activity_start,
        "stale": is_stale(state),
    }


def _sync(session: Session) -> dict:
    try:
        garmin = restore_client(session)
        result = run_sync(session, garmin)
    except GarminNotConnected as exc:
        raise HTTPException(409, str(exc)) from exc
    except SyncBusy as exc:
        return {"skipped": True, "reason": str(exc), **_status(session)}
    except GarminConnectTooManyRequestsError as exc:
        raise HTTPException(429, "Garmin is rate-limiting requests; try again later") from exc
    except SyncFailed as exc:
        raise HTTPException(502, str(exc)[:300]) from exc
    except GarminConnectConnectionError as exc:
        raise HTTPException(502, f"Couldn't reach Garmin: {exc}"[:300]) from exc
    return {"skipped": False, **result, **_status(session)}


@router.get("/sync/status")
def sync_status(session: Session = Depends(get_session)):
    return _status(session)


@router.post("/sync")
def sync_now(if_stale: bool = False, session: Session = Depends(get_session)):
    if if_stale and not is_stale(get_state(session)):
        return {"skipped": True, "reason": "Synced recently", **_status(session)}
    return _sync(session)


def cron_router() -> APIRouter:
    """Unauthenticated by session; guarded by Vercel's CRON_SECRET bearer token."""
    cron = APIRouter(tags=["sync"])

    @cron.get("/cron/sync")
    def cron_sync(authorization: str | None = Header(default=None), session: Session = Depends(get_session)):
        expected = f"Bearer {CRON_SECRET}" if CRON_SECRET else None
        # Compare bytes: compare_digest raises on non-ASCII str, and a client
        # controls this header.
        given = (authorization or "").encode("utf-8", "surrogateescape")
        if not expected or not hmac.compare_digest(given, expected.encode()):
            raise HTTPException(401, "Bad cron secret")
        return _sync(session)

    return cron

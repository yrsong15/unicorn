import math

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import auth
from app.db import get_session
from app.services import login_throttle

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    password: str = Field(max_length=1024)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)):
    if not auth.password_configured():
        raise HTTPException(503, "APP_PASSWORD_HASH isn't set on the server")
    ip = login_throttle.client_ip(request)
    wait = login_throttle.locked_for(session, ip)
    if wait is not None:
        minutes = max(1, math.ceil(wait.total_seconds() / 60))
        raise HTTPException(
            429,
            f"Too many wrong passwords. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(math.ceil(wait.total_seconds()))},
        )
    if not auth.check_password(body.password):
        login_throttle.record_failure(session, ip)
        raise HTTPException(401, "Wrong password")
    login_throttle.record_success(session, ip)
    auth.start_session(response)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    auth.end_session(response)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    return {"logged_in": auth.is_logged_in(request)}

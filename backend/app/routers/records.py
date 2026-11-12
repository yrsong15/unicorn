from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.clock import local_today
from app.db import get_session
from app.services.records import compute_records

router = APIRouter(prefix="/records", tags=["records"])


@router.get("")
def records(session: Session = Depends(get_session)):
    return compute_records(session, local_today(session))

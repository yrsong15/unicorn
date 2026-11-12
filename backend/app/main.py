from fastapi import APIRouter, Depends, FastAPI, Request
from sqlmodel import Session

from app.auth import require_login
from app.config import IS_PRODUCTION, ON_VERCEL
from app.db import get_session
from app.routers import auth, metrics, runs, shoes, summary, sync
from app.services.records import compute_records

# Interactive API docs are for local development only; the deployed app keeps
# its endpoint list private.
_docs = not (ON_VERCEL or IS_PRODUCTION)
app = FastAPI(
    title="Unicorn",
    docs_url="/api/docs" if _docs else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if _docs else None,
)

API_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for key, value in API_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


public = APIRouter(prefix="/api")
public.include_router(auth.router)
public.include_router(sync.cron_router())


@public.get("/health")
def health():
    return {"ok": True}


private = APIRouter(prefix="/api", dependencies=[Depends(require_login)])
for module in (runs, shoes, summary, metrics, sync):
    private.include_router(module.router)


@private.get("/records")
def records(session: Session = Depends(get_session)):
    return compute_records(session)


app.include_router(public)
app.include_router(private)

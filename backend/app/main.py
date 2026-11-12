from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth import require_login
from app.config import IS_PRODUCTION, ON_VERCEL
from app.routers import auth, metrics, records, runs, shoes, summary, sync

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


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # FastAPI's default response echoes each bad value back. Leave it out: a
    # NaN can't be written as JSON (turning the 422 into a 500), and there's no
    # need to repeat a rejected value, such as a password, in the response.
    errors = [{k: v for k, v in e.items() if k != "input"} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


public = APIRouter(prefix="/api")
public.include_router(auth.router)
public.include_router(sync.cron_router())


@public.get("/health")
def health():
    return {"ok": True}


private = APIRouter(prefix="/api", dependencies=[Depends(require_login)])
for module in (runs, shoes, summary, metrics, records, sync):
    private.include_router(module.router)


app.include_router(public)
app.include_router(private)

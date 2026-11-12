import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


DATABASE_URL = env("DATABASE_URL", "sqlite:///./dev.db")
APP_PASSWORD_HASH = env("APP_PASSWORD_HASH")
SESSION_SECRET = env("SESSION_SECRET", "dev-only-session-secret")
GARMIN_TOKEN_KEY = env("GARMIN_TOKEN_KEY")
CRON_SECRET = env("CRON_SECRET")
IS_PRODUCTION = env("VERCEL_ENV") == "production" or env("APP_ENV") == "production"
ON_VERCEL = env("VERCEL") == "1"

if ON_VERCEL and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("DATABASE_URL must point at Supabase Postgres when running on Vercel")
if (ON_VERCEL or IS_PRODUCTION) and SESSION_SECRET == "dev-only-session-secret":
    raise RuntimeError("SESSION_SECRET must be set to a long random value (cli gen-key) in production")

SESSION_MAX_AGE_S = 60 * 60 * 24 * 30
SYNC_STALE_AFTER_S = 10 * 60

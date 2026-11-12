"""Commands you run on your Mac:

    uv run python -m app.cli login                 # one-time Garmin login (password + MFA stay local)
    uv run python -m app.cli backfill --since 2023-01-01
    uv run python -m app.cli sync                  # same incremental sync the website runs
    uv run python -m app.cli hash-password         # value for APP_PASSWORD_HASH
    uv run python -m app.cli gen-key               # value for GARMIN_TOKEN_KEY
    uv run python -m app.cli seed-demo             # fake data for local UI work (SQLite only)
    uv run python -m app.cli migrate               # apply database migrations (alembic upgrade head)
"""

import argparse
import getpass
import logging
import secrets
import sys
from datetime import date, timedelta

from cryptography.fernet import Fernet
from sqlmodel import Session

from app.db import engine


def cmd_login(_args) -> None:
    from app.garmin.client import interactive_login, store_tokens

    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password: ")
    garmin = interactive_login(email, password, prompt_mfa=lambda: input("MFA code: ").strip())
    with Session(engine) as session:
        store_tokens(session, garmin)
    print(f"Connected as {email}. Tokens saved (encrypted) to the database.")


def _sync(activities_since: date | None, metrics_since: date | None) -> None:
    from app.garmin.client import restore_client
    from app.garmin.sync import run_sync

    with Session(engine) as session:
        garmin = restore_client(session)
        result = run_sync(session, garmin, activities_since=activities_since, metrics_since=metrics_since)
    print(result["message"])


def cmd_backfill(args) -> None:
    since = date.fromisoformat(args.since)
    metrics_since = max(since, date.today() - timedelta(days=args.metrics_days))
    print(f"Importing runs since {since} and daily metrics since {metrics_since}. This can take a while…")
    _sync(since, metrics_since)


def cmd_sync(_args) -> None:
    _sync(None, None)


def cmd_hash_password(_args) -> None:
    from app.auth import hash_password

    password = getpass.getpass("New app password: ")
    if password != getpass.getpass("Again: "):
        sys.exit("Passwords didn't match")
    print(hash_password(password))


def cmd_gen_key(_args) -> None:
    print(f"GARMIN_TOKEN_KEY={Fernet.generate_key().decode()}")
    print(f"SESSION_SECRET={secrets.token_urlsafe(32)}")
    print(f"CRON_SECRET={secrets.token_urlsafe(32)}")


def cmd_seed_demo(_args) -> None:
    from app.demo import seed

    if not str(engine.url).startswith("sqlite"):
        sys.exit("seed-demo only runs against a local SQLite database")
    seed()
    print("Demo data written.")


def cmd_migrate(_args) -> None:
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login").set_defaults(fn=cmd_login)
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--since", required=True, help="YYYY-MM-DD")
    backfill.add_argument("--metrics-days", type=int, default=365, help="days of daily metrics to import")
    backfill.set_defaults(fn=cmd_backfill)
    sub.add_parser("sync").set_defaults(fn=cmd_sync)
    sub.add_parser("hash-password").set_defaults(fn=cmd_hash_password)
    sub.add_parser("gen-key").set_defaults(fn=cmd_gen_key)
    sub.add_parser("seed-demo").set_defaults(fn=cmd_seed_demo)
    sub.add_parser("migrate").set_defaults(fn=cmd_migrate)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

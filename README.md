# unicorn

Named after the unicorn in the logo of the Boston Athletic Association (B.A.A.), which organizes the Boston Marathon.

**Live app:** https://unicorn-taupe-nu.vercel.app

Unicorn is a personal running tracker that pulls runs and fitness data from Garmin Connect. It has:

- **Weekly mileage:** Monday–Sunday weeks over 3M / 6M / 1Y / YTD / All.
- **Shoe mileage:** one run can be split across several shoes (e.g. warmup in one, track reps in another).
- **Fitness trends:** VO2 max, race predictions, resting HR, lactate threshold.
- **Training load and readiness:** acute/chronic load, ACWR, readiness, HRV, training status.
- **Run detail:** laps, HR zones, and assigning shoes by lap.
- **Records and streaks.**

```
backend/   FastAPI + SQLModel + Alembic, Garmin sync (python-garminconnect)
frontend/  React + Vite + Tailwind + Recharts
vercel.json  one Vercel project: frontend + backend services, daily cron
```

## Run it again

Once setup is done (see [Local development](#local-development)), start the two servers in separate terminals:

```bash
cd backend && uv run uvicorn app.main:app --port 8000 --reload
```

```bash
cd frontend && npm run dev
```

Then open http://localhost:5173.

## How Garmin access works

This app uses the unofficial
[`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect) library.
Garmin's business developer program isn't open to individuals, and its official
[Personal API](https://developer.garmin.com/gc-developer-program/personal/personal-api)
doesn't expose VO2max, training status, readiness, race predictions, lactate threshold
or personal records (checked 2026-11-09). See
[GARMIN_PERSONAL_API_SWITCH.md](GARMIN_PERSONAL_API_SWITCH.md) for what a switch would take.

- **Login stays on your Mac.** Your Garmin password and MFA code are only ever typed on your Mac (`cli login`). The resulting OAuth tokens are encrypted (`GARMIN_TOKEN_KEY`) and stored in the database.
- **The server only uses tokens.** The deployed app restores the session from those tokens and refreshes them. It never has your password.
- **Reconnecting:** if the tokens stop working, the app shows **Reconnect Garmin**. Run `cli login` again.
- **When syncs happen:**
  - Whenever you open the app, if the last sync was more than 10 minutes ago.
  - When you click **Sync now**.
  - From a daily Vercel cron. Vercel's Hobby plan only allows daily crons; Pro allows more often.
- **Fallback:** if Garmin ever blocks requests from Vercel, run `uv run python -m app.cli sync` on your Mac on a schedule (e.g. launchd every 15 min). It writes to the same database, so the site keeps working.

## Local development

You need `uv` (`brew install uv`) and Node 20+.

```bash
cd backend
uv sync
uv run python -m app.cli gen-key         # paste the output into backend/.env
uv run python -m app.cli hash-password   # APP_PASSWORD_HASH=... into backend/.env
uv run python -m app.cli migrate
uv run python -m app.cli seed-demo       # optional fake data (SQLite only)
uv run uvicorn app.main:app --port 8000 --reload
```

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api to :8000
```

Without `DATABASE_URL`, the backend uses a local SQLite file (`backend/dev.db`).

Run the tests:

```bash
cd backend && uv run pytest
```

## Going live (Supabase + Vercel)

1. **Supabase:**
   - Create a new project.
   - Under **Connect → Transaction pooler**, copy the connection string (port 6543).
   - Put it in `backend/.env` as `DATABASE_URL=...`.
2. **Create the tables** by running `uv run python -m app.cli migrate` from `backend/`. The migration also enables Row Level Security on every table, which blocks Supabase's public Data API from reading anything, including Garmin tokens. The backend connects as the table owner, so it's unaffected.
3. **Connect Garmin and import history:**
   ```bash
   uv run python -m app.cli login
   uv run python -m app.cli backfill --since 2024-01-01
   ```
4. **Vercel:**
   - Import the GitHub repo as a new project.
   - In Project → Settings → Environment Variables, set `DATABASE_URL`, `APP_PASSWORD_HASH`, `SESSION_SECRET`, `GARMIN_TOKEN_KEY` (the same key you used locally), and `CRON_SECRET`.
   - Deploy.
5. **Test a server-side sync:** open the deployed app and click **Sync now**. This confirms Garmin accepts requests from Vercel.

## Data notes

- **Week boundaries:** weeks use each run's local start time, so a Sunday-night run counts toward that week.
- **Shoe totals:** a shoe's total is its starting miles plus every segment assigned to it.
  - New runs automatically get the default shoe for their run type (road / treadmill / track / trail), or the overall default.
  - A split can't add up to more than the run's distance.
  - Any shortfall shows as "unassigned."
- **Rate limits:** Garmin's endpoints are undocumented. The sync parses responses defensively and stops as soon as it gets a 429 (rate limit).

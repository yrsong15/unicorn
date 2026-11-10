# Switching to the Garmin Personal API

A checklist for moving Unicorn off the unofficial `python-garminconnect` login and onto
Garmin's official [Personal API](https://developer.garmin.com/gc-developer-program/personal/personal-api).

**Status: not planned.** As of 2026-11-09 the Personal API is missing too much (see
[What you lose](#what-you-lose)). This file exists so the switch is quick if the
unofficial login breaks or Garmin blocks it.

## Before you start: re-run the probe

Garmin may have added endpoints since this was written. From `backend/`:

```bash
uv run python scripts/probe_personal_api.py --dump /tmp/garmin-probe
```

It needs a Personal API key (step 1 below). Anything that now returns 200 can come off
the "lose" list. Delete `/tmp/garmin-probe` afterwards; it holds your health data.

## Probe results on 2026-11-09

| What the app needs | Today's call (`sync.py`) | Personal API |
|---|---|---|
| Runs and rides | `get_activities_by_date` | Works: `/activitylist-service/activities/search/activities` |
| Activity detail | (not used) | Works: `/activity-service/activity/{id}` |
| Laps | `get_activity_splits` | 404. FIT download works: `/download-service/files/activity/{id}` |
| HRV | `get_hrv_data` | Works: `/hrv-service/hrv/{date}` |
| Resting HR | `get_user_summary` | 404. Official replacement works: `/usersummary-service/v2/dailysummaries` |
| VO2max | `get_max_metrics_range` | 404 |
| Training readiness | `get_training_readiness` | 404 |
| Training status, acute/chronic load | `get_training_status` | 404 |
| Race predictions | `get_race_predictions` | 404 |
| Lactate threshold | `get_lactate_threshold` | 404 |
| Personal records | `get_personal_record` | 404 |

The 404s come from Garmin's gateway, not from a missing permission, so no key setting
unlocks them.

## What you lose

These stop updating on the switch date. Existing history stays in the database.

- **Fitness page:** VO2max, training readiness, training status, acute and chronic load
  (and the ratio), race predictions, lactate threshold.
- **Records page:** Garmin's personal records.
- **Per-run VO2max:** the Personal API's activity list has no `vO2MaxValue` field.

Two of these can be rebuilt from data we still get, if you want them back:

- **Acute/chronic load:** compute from `runs.training_load` (7-day and 28-day sums).
- **Personal records:** compute from the `fastestSplit_1000`, `fastestSplit_1609` and
  `fastestSplit_5000` fields on each activity. Longer distances would need FIT parsing.

## Steps

### 1. Create a key (you, in the browser)

1. Open <https://connect.garmin.com/app/settings/personalApiToken>.
2. Create a key with the one-year expiry.
3. Copy it straight away. Garmin shows it only once.

Garmin emails you about a week before it expires. Put a reminder in your calendar too.

### 2. Auth: replace the login with the key

- [ ] `backend/app/garmin/client.py`: replace `restore_client` and `interactive_login`
      with a small client that:
  - decrypts the key from `garmin_auth.tokens_encrypted` (same column, same
    `GARMIN_TOKEN_KEY` encryption);
  - POSTs to `/personalapitoken-service/personal-api/personal-api-key/token` with
    `Authorization: ApiKey <key>` and `Accept: */*`. The reply is the bearer token as
    plain text, not JSON; asking for JSON returns 406;
  - sends `Authorization: Bearer <token>` on every request to
    `https://personal.connectapi.garmin.com`.
- [ ] Tokens last 24 hours and there are no refresh tokens. Fetch a new one per sync run;
      caching isn't worth it for a daily cron.
- [ ] A 401 on the token request means the key expired or was deleted. Call
      `mark_needs_reconnect` so the app shows the reconnect banner.
- [ ] `backend/app/cli.py`: change `login` to prompt for the key (hidden) instead of
      email, password and MFA. Update the docstring at the top.
- [ ] Either use Garmin's SDK (`garmin-connect-personal-api-python`) or plain HTTP as
      the probe script does. Plain HTTP avoids the SDK's on-disk token cache, which
      doesn't suit Vercel.

### 3. Activities

- [ ] `backend/app/garmin/sync.py` `sync_activities`: call the search endpoint with
      `startDate`, `endDate`, `start`, `limit`, and page until a short page comes back.
- [ ] `parse_activity` in `backend/app/garmin/parse.py` should work unchanged. The
      payload has the same field names (`activityId`, `startTimeLocal`, `distance`,
      `averageHR`, `activityTrainingLoad`, `hrTimeInZone_N`, …). Confirm against a
      dumped response.

### 4. Laps from FIT files

- [ ] Add a FIT parser dependency (for example `fitdecode` or `fitparse`).
- [ ] `upsert_run`: download `/download-service/files/activity/{id}` with `Accept: */*`.
      The response is a ZIP; read the `.fit` file inside it and build laps from its
      `lap` messages.
- [ ] Map to the `laps` columns: `idx`, `distance_m`, `duration_s`, `avg_hr`,
      `avg_cadence`, `elev_gain_m`. Check cadence units: FIT stores running cadence per
      leg, so it may need doubling to match today's steps per minute.
- [ ] Compare the laps of a few existing runs against what's already in the database.

### 5. Daily metrics

- [ ] `sync_metrics`: keep only HRV and resting HR.
  - HRV: `/hrv-service/hrv/{date}`, same payload, `parse_hrv` unchanged. The range
    version `/hrv-service/hrv/daily/{start}/{end}` saves requests on a backfill.
  - Resting HR: `/usersummary-service/v2/dailysummaries?startDate=&endDate=`, one
    request for the whole range. Rewrite `parse_resting_hr` to read
    `data[].heartRate.restingValue`, keyed by `calendarDate`.
- [ ] Remove the calls for VO2max, readiness, training status, race predictions and
      lactate threshold, plus their parsers.
- [ ] Remove `sync_personal_records`, or replace it with records computed from runs.

### 6. Errors and rate limits

- [ ] Replace `GarminConnectTooManyRequestsError` and
      `GarminConnectAuthenticationError` in `sync.py`, `client.py` and
      `backend/app/routers/sync.py` with your own exceptions for HTTP 429 and 401.
- [ ] Garmin doesn't document rate limits for the Personal API. Keep the 0.3 s delay
      between requests and keep stopping the sync on a 429.

### 7. Frontend

- [ ] Fitness and Records pages: hide the cards and charts that no longer update, or
      label them "history only" with the switch date.
- [ ] Settings and the reconnect banner: change the wording from "run `cli login`" to
      "create a new key and run `cli login`".
- [ ] `frontend/src/api/types.ts`: no change unless you remove fields from the API.

### 8. Database

No migration is required. Every affected column is nullable, and the key fits in
`garmin_auth.tokens_encrypted`.

Optional:

- [ ] Add `key_expires_at` to `garmin_auth` so the app can warn you a few weeks ahead.
      The bearer token is a JWT whose `exp` is capped by the key's expiry, but only
      within the last 24 hours, so store the date you chose instead.
- [ ] Add columns to `daily_metrics` for data the official summary offers and we don't
      store yet: steps, stress, body battery.

### 9. Cleanup

- [ ] `backend/pyproject.toml`: remove `garminconnect` and `curl_cffi` (only there for
      the login), then `uv lock`.
- [ ] `backend/tests/test_sync.py` and `backend/tests/fixtures`: replace fixtures with
      responses dumped by the probe (scrub anything personal first).
- [ ] `README.md`: rewrite "How Garmin access works". Drop the password, MFA and
      "if Garmin blocks Vercel" notes.

### 10. Cut over

1. Run `uv run python -m app.cli login` and paste the key. This overwrites the old
   tokens in the database.
2. Run `uv run python -m app.cli sync` locally and check new runs, laps, HRV and resting
   HR against Garmin Connect.
3. Deploy. `GARMIN_TOKEN_KEY` stays the same; no new environment variables.
4. Click **Sync now** on the deployed app to confirm it works from Vercel.

### 11. Every year

Create a new key before the old one expires, run `cli login` again, then delete the old
key in Garmin Connect.

## A smaller option: hybrid

If the unofficial login is only flaky rather than dead, do steps 1–6 for activities,
laps, HRV and resting HR, and keep `python-garminconnect` for the metrics the Personal
API lacks. The core run log then keeps syncing when the unofficial login breaks, and
only the Fitness and Records numbers go stale. The cost is two auth paths to maintain,
and `garmin_auth` needs a second encrypted column for the key.

## Unknowns

- **History depth:** how far back the activity search and daily summaries go was not
  tested. The probe only read the last 30 days. Test before relying on `backfill`.
- **Rate limits:** undocumented.
- **Sauna sessions:** they appear as activity type `other` with the name "Sauna". This
  is the same on both APIs.

"""Check which Garmin endpoints our sync needs are reachable with the Personal API.

Garmin's Personal API (https://developer.garmin.com/gc-developer-program/personal/personal-api)
serves the same Connect service paths python-garminconnect uses, on a different host
and with an official key instead of a scraped login. This script calls each path
app/garmin/sync.py depends on and reports which ones work.

Usage (from backend/):

    GARMIN_PERSONAL_API_KEY=... uv run python scripts/probe_personal_api.py
    uv run python scripts/probe_personal_api.py --dump ~/garmin-probe   # also save responses (private to you)

If the env var isn't set, the key is prompted for (hidden). Nothing is written to the
database, and the key and token are never stored or printed.
"""

import argparse
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = os.environ.get("GARMIN_PERSONAL_API_BASE_URL", "https://personal.connectapi.garmin.com")
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
TIMEOUT_S = 30
DELAY_S = 0.5


def request(path: str, *, headers: dict[str, str], method: str = "GET", params: dict | None = None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method, headers={"Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        return None, str(exc.reason).encode()


def get_token(api_key: str) -> str:
    # The token endpoint returns the JWT as plain text and rejects Accept: application/json (406).
    status, body = request(
        TOKEN_PATH, method="POST", headers={"Accept": "*/*", "Authorization": f"ApiKey {api_key}"}
    )
    if status != 200:
        hint = " Check the key was pasted in full and hasn't been deleted or expired." if status == 401 else ""
        sys.exit(f"Token exchange failed ({status}): {body[:300].decode(errors='replace')}{hint}")
    token = body.decode().strip()
    if token.count(".") != 2:
        sys.exit("Token response wasn't a JWT.")
    return token


def summarize(body: bytes) -> str:
    try:
        data = json.loads(body)
    except ValueError:
        return f"{len(body)} bytes, not JSON"
    if isinstance(data, list):
        first = data[0] if data else None
        keys = sorted(first)[:6] if isinstance(first, dict) else []
        return f"list[{len(data)}]" + (f" keys {keys}" if keys else "")
    if isinstance(data, dict):
        return f"dict keys {sorted(data)[:8]}"
    return repr(data)[:80]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump", type=Path, help="directory to save each JSON response in")
    args = parser.parse_args()

    api_key = os.environ.get("GARMIN_PERSONAL_API_KEY") or getpass.getpass("Personal API key: ").strip()
    auth = {"Authorization": f"Bearer {get_token(api_key)}"}
    print(f"Got a bearer token from {BASE}\n")

    if args.dump:
        # Responses hold personal data, so keep the folder readable only by you.
        args.dump.mkdir(mode=0o700, parents=True, exist_ok=True)
        args.dump.chmod(0o700)

    results: list[tuple[str, str, int | None, str]] = []

    def probe(label: str, path: str, params: dict | None = None, needed_by: str = ""):
        time.sleep(DELAY_S)
        status, body = request(path, headers=auth, params=params)
        ok = status == 200
        info = summarize(body) if ok else body[:120].decode(errors="replace").replace("\n", " ")
        results.append((label, needed_by, status, info))
        print(f"{'OK ' if ok else 'ERR'} {status!s:>4}  {label:<28} {info}")
        if args.dump and status is not None:
            (args.dump / f"{label}.json").write_bytes(body)
        return json.loads(body) if ok and body else None

    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Identity: several garminconnect endpoints are keyed by displayName.
    settings = probe("profile_settings", "/userprofile-service/userprofile/settings")
    social = probe("social_profile", "/userprofile-service/socialProfile")
    display_name = (social or {}).get("displayName") or (settings or {}).get("displayName")
    print(f"    displayName: {'found' if display_name else 'NOT FOUND (displayName endpoints will be skipped)'}")

    # Activities (sync.py: get_activities_by_date, get_activity_splits).
    activities = probe(
        "activities_search",
        "/activitylist-service/activities/search/activities",
        {"startDate": month_ago.isoformat(), "endDate": today.isoformat(), "start": 0, "limit": 100},
        "runs, rides",
    )
    activity_id = None
    if isinstance(activities, list) and activities:
        types = sorted({(a.get("activityType") or {}).get("typeKey") for a in activities} - {None})
        print(f"    activity types in last 30 days: {types}")
        run = next((a for a in activities if "running" in ((a.get("activityType") or {}).get("typeKey") or "")), None)
        activity_id = (run or activities[0]).get("activityId")
    if activity_id:
        probe("activity", f"/activity-service/activity/{activity_id}", needed_by="run detail")
        probe("activity_splits", f"/activity-service/activity/{activity_id}/splits", needed_by="laps")
        probe("activity_typedsplits", f"/activity-service/activity/{activity_id}/typedsplits", needed_by="laps (alt)")
        probe("activity_hr_zones", f"/activity-service/activity/{activity_id}/hrTimeInZones", needed_by="(nice to have)")
        time.sleep(DELAY_S)
        status, body = request(
            f"/download-service/files/activity/{activity_id}", headers={**auth, "Accept": "*/*"}
        )
        info = f"{len(body)} bytes" if status == 200 else body[:120].decode(errors="replace")
        results.append(("fit_download", "laps fallback", status, info))
        print(f"{'OK ' if status == 200 else 'ERR'} {status!s:>4}  {'fit_download':<28} {info}")
    else:
        print("    no activities found; skipping per-activity endpoints")

    # Daily metrics (sync.py: get_hrv_data, get_training_readiness, get_training_status, ...).
    d = today.isoformat()
    probe("hrv", f"/hrv-service/hrv/{d}", needed_by="HRV")
    probe("training_readiness", f"/metrics-service/metrics/trainingreadiness/{d}", needed_by="readiness")
    probe("training_status", f"/metrics-service/metrics/trainingstatus/aggregated/{d}", needed_by="training status")
    probe("training_status_daily", f"/metrics-service/metrics/trainingstatus/daily/{d}", needed_by="training status (alt)")
    probe(
        "max_metrics",
        f"/metrics-service/metrics/maxmet/daily/{month_ago.isoformat()}/{d}",
        needed_by="VO2max",
    )
    probe("lactate_threshold", "/biometric-service/biometric/latestLactateThreshold", needed_by="LT")
    probe(
        "daily_summaries_v2",
        "/usersummary-service/v2/dailysummaries",
        {"startDate": week_ago.isoformat(), "endDate": d},
        "user summary (official alt)",
    )
    if display_name:
        dn = urllib.parse.quote(display_name)
        probe("user_summary", f"/usersummary-service/usersummary/daily/{dn}", {"calendarDate": d}, "RHR, steps, stress")
        probe("race_predictions", f"/metrics-service/metrics/racepredictions/latest/{dn}", needed_by="race predictions")
        probe("personal_records", f"/personalrecord-service/personalrecord/prs/{dn}", needed_by="records")

    failed = [r for r in results if r[2] != 200]
    print(f"\n{len(results) - len(failed)}/{len(results)} endpoints returned 200.")
    if failed:
        print("Not reachable:")
        for label, needed_by, status, _ in failed:
            print(f"  - {label} ({status}){f'  — needed for {needed_by}' if needed_by else ''}")


if __name__ == "__main__":
    main()

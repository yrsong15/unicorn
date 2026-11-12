from datetime import timedelta

import app.auth
from app.garmin.parse import parse_activity, strip_personal
from app.models import LoginAttempt, utcnow
from app.services import login_throttle


def _fail(client, n):
    return [client.post("/api/auth/login", json={"password": "nope"}).status_code for _ in range(n)]


def test_login_locks_after_repeated_failures(client):
    codes = _fail(client, login_throttle.MAX_FAILURES + 1)
    assert codes[:-1] == [401] * login_throttle.MAX_FAILURES
    assert codes[-1] == 429
    # Even the right password is refused while locked.
    locked = client.post("/api/auth/login", json={"password": "hunter2"})
    assert locked.status_code == 429 and "Retry-After" in locked.headers


def test_lock_expires(client, session):
    _fail(client, login_throttle.MAX_FAILURES)
    row = session.get(LoginAttempt, "testclient")
    row.locked_until = utcnow() - timedelta(seconds=1)
    row.first_failure_at = utcnow() - login_throttle.WINDOW - timedelta(minutes=1)
    session.add(row)
    session.commit()
    assert client.post("/api/auth/login", json={"password": "hunter2"}).status_code == 200
    assert session.get(LoginAttempt, "testclient") is None


def test_success_clears_failures(client, session):
    _fail(client, login_throttle.MAX_FAILURES - 1)
    assert client.post("/api/auth/login", json={"password": "hunter2"}).status_code == 200
    assert session.get(LoginAttempt, "testclient") is None


def test_global_limit_blocks_distributed_guessing(client, session):
    now = utcnow()
    for i in range(login_throttle.GLOBAL_MAX_FAILURES):
        session.add(LoginAttempt(ip=f"10.0.{i // 256}.{i % 256}", failures=1, first_failure_at=now))
    session.commit()
    assert client.post("/api/auth/login", json={"password": "hunter2"}).status_code == 429


def test_password_change_invalidates_sessions(logged_in, monkeypatch):
    assert logged_in.get("/api/runs").status_code == 200
    monkeypatch.setattr(app.auth, "APP_PASSWORD_HASH", app.auth.hash_password("new-password"))
    assert logged_in.get("/api/runs").status_code == 401


def test_api_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_raw_payload_drops_personal_fields():
    activity = {
        "activityId": 1, "activityName": "Run", "activityType": {"typeKey": "running"},
        "startTimeLocal": "2026-11-01 07:00:00", "distance": 5000.0, "duration": 1500.0,
        "startLatitude": 42.35, "startLongitude": -71.06, "endLatitude": 42.36, "endLongitude": -71.05,
        "ownerId": 123, "ownerFullName": "Someone", "locationName": "Boston", "deviceId": 9,
    }
    raw = parse_activity(activity)["raw"]
    assert set(raw) == {"activityId", "activityName", "activityType", "startTimeLocal", "distance", "duration"}
    assert strip_personal({"relativeEffort": 1, "longestSplit": 2}) == {"relativeEffort": 1, "longestSplit": 2}

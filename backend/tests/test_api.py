from datetime import timedelta

from tests.factories import make_run, app_today


def test_api_requires_login(client):
    assert client.get("/api/runs").status_code == 401
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/me").json() == {"logged_in": False}


def test_wrong_password_rejected(client):
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401


def test_login_logout(logged_in):
    assert logged_in.get("/api/auth/me").json() == {"logged_in": True}
    logged_in.post("/api/auth/logout")
    assert logged_in.get("/api/runs").status_code == 401


def test_cron_requires_secret(client):
    assert client.get("/api/cron/sync").status_code == 401
    assert client.get("/api/cron/sync", headers={"Authorization": "Bearer wrong"}).status_code == 401
    # Right secret gets past auth; Garmin isn't connected in tests.
    assert client.get("/api/cron/sync", headers={"Authorization": "Bearer cron-test"}).status_code == 409


def test_weekly_and_dashboard(logged_in, session):
    today = app_today()
    make_run(session, today, 5)
    make_run(session, today - timedelta(days=7), 8)
    weekly = logged_in.get("/api/summary/weekly?range=3m").json()["weeks"]
    assert len(weekly) == 13 and round(weekly[-1]["run_miles"]) == 5
    dash = logged_in.get("/api/summary/dashboard").json()
    assert round(dash["this_week"]["run_miles"]) == 5 and round(dash["last_week"]["run_miles"]) == 8
    assert logged_in.get("/api/summary/weekly?range=bogus").status_code == 422


def test_records(logged_in, session):
    today = app_today()
    for weeks_ago in (0, 1, 2, 4):
        make_run(session, today - timedelta(weeks=weeks_ago), 3 + weeks_ago)
    rec = logged_in.get("/api/records").json()
    assert rec["current_streak_weeks"] == 3
    assert round(rec["longest_run"]["miles"], 6) == 7
    assert rec["totals"]["runs"] == 4


def test_run_detail_and_list(logged_in, session):
    run = make_run(session, app_today(), 6, laps=[2, 4])
    detail = logged_in.get(f"/api/runs/{run.id}").json()
    assert [round(l["miles"]) for l in detail["laps"]] == [2, 4]
    assert detail["unassigned_miles"] == 6
    page = logged_in.get("/api/runs").json()
    assert page["total"] == 1


def test_cron_rejects_non_ascii_secret(client):
    # Header values arrive as Latin-1; compare_digest refuses non-ASCII str.
    res = client.get("/api/cron/sync", headers={"Authorization": "Bearer café".encode("latin-1")})
    assert res.status_code == 401

"""Bad input gets a 422, never a 500 from the database."""

import pytest

from tests.factories import app_today, make_run, make_shoe


@pytest.mark.parametrize("query", ["limit=-1", "limit=0", "limit=501", "offset=-5", "shoe_id=99999999999", "shoe_id=0"])
def test_run_list_rejects_bad_paging(logged_in, query):
    assert logged_in.get(f"/api/runs?{query}").status_code == 422


def test_run_list_ignores_out_of_range_ids(logged_in, session):
    run = make_run(session, app_today(), 3)
    page = logged_in.get(f"/api/runs?ids={run.id},99999999999999,abc").json()
    assert [r["id"] for r in page["items"]] == [run.id]


@pytest.mark.parametrize("path", ["/api/runs/99999999999", "/api/runs/0"])
def test_ids_out_of_range_are_422(logged_in, path):
    assert logged_in.get(path).status_code == 422


def test_shoe_id_out_of_range_is_422(logged_in):
    assert logged_in.patch("/api/shoes/99999999999", json={"name": "x"}).status_code == 422


@pytest.mark.parametrize("field", ["name", "start_miles", "retire_at_miles", "is_default"])
def test_shoe_patch_rejects_null_required_fields(logged_in, session, field):
    shoe = make_shoe(session, "Pegasus")
    res = logged_in.patch(f"/api/shoes/{shoe.id}", json={field: None})
    assert res.status_code == 422
    session.refresh(shoe)
    assert shoe.name == "Pegasus"


def test_shoe_patch_allows_clearing_optional_fields(logged_in, session):
    shoe = make_shoe(session, "Pegasus", brand="Nike")
    assert logged_in.patch(f"/api/shoes/{shoe.id}", json={"brand": None}).json()["brand"] is None


@pytest.mark.parametrize("body", [
    {"name": "x" * 81}, {"name": "ok", "brand": "x" * 81}, {"name": "ok", "color": "red"},
    {"name": "ok", "notes": "x" * 2001}, {"name": "ok", "start_miles": 1e9},
])
def test_shoe_create_limits(logged_in, body):
    assert logged_in.post("/api/shoes", json=body).status_code == 422


def test_non_finite_numbers_rejected(logged_in, session):
    # Python's JSON parser accepts NaN and Infinity even though JSON doesn't.
    res = logged_in.post("/api/shoes", content='{"name": "ok", "start_miles": NaN}',
                         headers={"Content-Type": "application/json"})
    assert res.status_code == 422
    run = make_run(session, app_today(), 3)
    shoe = make_shoe(session)
    res = logged_in.put(f"/api/runs/{run.id}/shoes", content=f'{{"segments": [{{"shoe_id": {shoe.id}, "miles": Infinity}}]}}',
                        headers={"Content-Type": "application/json"})
    assert res.status_code == 422


def test_segment_bounds(logged_in, session):
    run = make_run(session, app_today(), 3, laps=[1, 2])
    shoe = make_shoe(session)
    for seg in ({"shoe_id": shoe.id, "lap_from": 0}, {"shoe_id": 2**40, "miles": 1}):
        assert logged_in.put(f"/api/runs/{run.id}/shoes", json={"segments": [seg]}).status_code == 422

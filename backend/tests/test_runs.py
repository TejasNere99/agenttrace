from datetime import datetime, timedelta, timezone

from bson import ObjectId


def make_run(project_id: str, *, status: str = "success") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "_id": ObjectId(),
        "project_id": project_id,
        "task": "Inspect a report",
        "agent_name": "Research Agent",
        "status": status,
        "started_at": now,
        "ended_at": None,
        "duration_ms": None,
        "event_count": 2,
        "created_at": now,
    }


def test_run_list_filters_and_get(client, database):
    project = client.post("/api/projects", json={"name": "Trace test"}).json()
    run = make_run(project["id"])
    database.agent_runs.documents.append(run)

    listed = client.get("/api/runs", params={"project_id": project["id"], "status": "success"})
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == str(run["_id"])
    assert client.get(f"/api/runs/{run['_id']}").json()["task"] == "Inspect a report"

    invalid_filter = client.get("/api/runs", params={"project_id": "bad-id"})
    assert invalid_filter.status_code == 400
    invalid_status = client.get("/api/runs", params={"status": "done"})
    assert invalid_status.status_code == 422


def test_run_not_found_and_invalid_id(client):
    assert client.get("/api/runs/bad-id").status_code == 400
    response = client.get(f"/api/runs/{ObjectId()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_run_events_are_ordered_and_pagination_works(client, database):
    project = client.post("/api/projects", json={"name": "Events"}).json()
    run = make_run(project["id"])
    database.agent_runs.documents.append(run)
    base_time = datetime.now(timezone.utc)
    for sequence in (3, 1, 2):
        database.trace_events.documents.append({
            "_id": ObjectId(),
            "run_id": str(run["_id"]),
            "parent_event_id": None,
            "sequence_number": sequence,
            "event_type": "planning",
            "name": f"Event {sequence}",
            "status": "success",
            "inputs": {"nested": {"value": sequence}},
            "outputs": {},
            "error": None,
            "timestamp": base_time + timedelta(seconds=sequence),
            "duration_ms": None,
            "metadata": {},
        })

    response = client.get(f"/api/runs/{run['_id']}/events")
    assert response.status_code == 200
    assert [event["sequence_number"] for event in response.json()] == [1, 2, 3]
    assert response.json()[0]["inputs"] == {"nested": {"value": 1}}
    page = client.get(f"/api/runs/{run['_id']}/events", params={"skip": 1, "limit": 1})
    assert [event["sequence_number"] for event in page.json()] == [2]


def test_events_return_404_for_missing_run(client):
    response = client.get(f"/api/runs/{ObjectId()}/events")
    assert response.status_code == 404

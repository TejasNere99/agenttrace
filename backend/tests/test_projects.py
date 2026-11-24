from datetime import datetime, timezone

from bson import ObjectId


def test_project_create_list_get_and_patch(client):
    created = client.post("/api/projects", json={"name": "  Research Assistant ", "description": "Paper review"})
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Research Assistant"
    assert ObjectId.is_valid(project["id"])
    assert project["created_at"].endswith("Z") or "+00:00" in project["created_at"]

    listed = client.get("/api/projects", params={"limit": 1})
    assert listed.status_code == 200
    assert listed.json() == [project]

    fetched = client.get(f"/api/projects/{project['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == project["id"]

    updated = client.patch(f"/api/projects/{project['id']}", json={"description": "Updated notes"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated notes"


def test_project_validation_and_missing_records(client):
    blank_name = client.post("/api/projects", json={"name": "  "})
    assert blank_name.status_code == 422
    assert blank_name.json()["error"]["code"] == "validation_error"

    invalid = client.get("/api/projects/not-an-object-id")
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_id"

    missing = client.get(f"/api/projects/{ObjectId()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"

    empty_patch = client.patch(f"/api/projects/{ObjectId()}", json={})
    assert empty_patch.status_code == 422


def test_project_delete_and_run_protection(client, database):
    created = client.post("/api/projects", json={"name": "Keep trace data"}).json()
    run_id = ObjectId()
    database.agent_runs.documents.append({"_id": run_id, "project_id": created["id"]})
    blocked = client.delete(f"/api/projects/{created['id']}")
    assert blocked.status_code == 409
    assert client.get(f"/api/projects/{created['id']}").status_code == 200

    empty = client.post("/api/projects", json={"name": "Empty project"}).json()
    deleted = client.delete(f"/api/projects/{empty['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/projects/{empty['id']}").status_code == 404


def test_project_pagination_validation(client):
    response = client.get("/api/projects", params={"skip": -1})
    assert response.status_code == 422


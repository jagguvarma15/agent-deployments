"""Unit tests for research API."""

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_start_research():
    client = TestClient(app)
    response = client.post("/research", json={"question": "What is machine learning?"})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["question"] == "What is machine learning?"
    assert len(data["steps"]) > 0


def test_get_research_status():
    client = TestClient(app)
    # First create a research
    res = client.post("/research", json={"question": "Test"})
    research_id = res.json()["id"]
    # Then check status
    status_res = client.get(f"/research/{research_id}/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "completed"

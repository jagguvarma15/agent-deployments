"""Unit tests for the API layer using mocked agents."""

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"


def test_health():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_post_documents():
    """Test document ingestion endpoint with real DB."""
    from httpx import ASGITransport, AsyncClient

    from app.db.models import Base
    from app.db.session import engine
    from app.main import app

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/documents",
            json={
                "content": "Python is great. It supports many paradigms. It is widely used.",
                "title": "Python Intro",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ingested"
    assert data["chunk_count"] >= 1
    assert "document_id" in data


@pytest.mark.asyncio
@patch("app.api.query.answer_question", new_callable=AsyncMock)
async def test_post_query(mock_answer):
    """Test query endpoint with mocked agent."""
    mock_answer.return_value = ("Python is a programming language.", [])

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/query",
            json={"question": "What is Python?"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] == "Python is a programming language."
    assert "trace_id" in data

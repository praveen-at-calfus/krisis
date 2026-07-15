"""API tests via TestClient — no LLM calls (DB is best-effort)."""
from fastapi.testclient import TestClient

from app.api import app


def test_empty_ticket_returns_422():
    with TestClient(app) as c:
        assert c.post("/classify", json={"ticket": "   "}).status_code == 422


def test_oversized_ticket_returns_422():
    with TestClient(app) as c:
        assert c.post("/classify", json={"ticket": "x" * 20001}).status_code == 422


def test_health_shape():
    with TestClient(app) as c:
        d = c.get("/health").json()
        assert {"status", "openai_key", "db"} <= set(d)

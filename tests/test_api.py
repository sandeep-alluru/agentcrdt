"""Tests for the FastAPI REST server."""
from __future__ import annotations

from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient

    from agentcrdt.api import app

    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Return a temp DB path for API tests."""
    return str(tmp_path / "api_test.db")


class TestHealth:
    """Tests for GET /health."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """GET /health must return 200."""
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_has_status_ok(self, client: TestClient) -> None:
        """GET /health must return {'status': 'ok'}."""
        r = client.get("/health")
        assert r.json()["status"] == "ok"

    def test_health_has_version(self, client: TestClient) -> None:
        """GET /health must include a version field."""
        r = client.get("/health")
        assert "version" in r.json()


class TestPostFact:
    """Tests for POST /fact."""

    def test_post_fact_returns_200(self, client: TestClient, db_path: str) -> None:
        """POST /fact must return 200 with the stored fact."""
        r = client.post(
            "/fact",
            json={
                "domain": "life",
                "entity": "king",
                "attribute": "alive",
                "value": True,
                "db": db_path,
            },
        )
        assert r.status_code == 200

    def test_post_fact_returns_id(self, client: TestClient, db_path: str) -> None:
        """POST /fact must return the fact's content-addressed id."""
        r = client.post(
            "/fact",
            json={
                "domain": "life",
                "entity": "king",
                "attribute": "alive",
                "value": True,
                "db": db_path,
            },
        )
        data = r.json()
        assert "id" in data
        assert len(data["id"]) == 16  # SHA-256[:16]

    def test_post_fact_correct_domain(self, client: TestClient, db_path: str) -> None:
        """POST /fact must echo back the domain."""
        r = client.post(
            "/fact",
            json={
                "domain": "possession",
                "entity": "sword",
                "attribute": "owner",
                "value": "knight",
                "db": db_path,
            },
        )
        assert r.json()["domain"] == "possession"


class TestGetFacts:
    """Tests for GET /facts."""

    def test_empty_store_returns_empty_list(self, client: TestClient, db_path: str) -> None:
        """GET /facts on an empty store must return {'facts': []}."""
        r = client.get("/facts", params={"db": db_path})
        assert r.status_code == 200
        assert r.json()["facts"] == []

    def test_stored_fact_appears_in_list(self, client: TestClient, db_path: str) -> None:
        """A stored fact must appear in GET /facts."""
        client.post(
            "/fact",
            json={
                "domain": "life",
                "entity": "king",
                "attribute": "alive",
                "value": True,
                "db": db_path,
            },
        )
        r = client.get("/facts", params={"db": db_path})
        assert len(r.json()["facts"]) == 1

    def test_domain_filter(self, client: TestClient, db_path: str) -> None:
        """GET /facts?domain=life must only return life-domain facts."""
        client.post(
            "/fact",
            json={
                "domain": "life",
                "entity": "king",
                "attribute": "alive",
                "value": True,
                "db": db_path,
            },
        )
        client.post(
            "/fact",
            json={
                "domain": "possession",
                "entity": "sword",
                "attribute": "owner",
                "value": "knight",
                "db": db_path,
            },
        )
        r = client.get("/facts", params={"db": db_path, "domain": "life"})
        facts = r.json()["facts"]
        assert len(facts) == 1
        assert facts[0]["domain"] == "life"


class TestPostMerge:
    """Tests for POST /merge."""

    def test_merge_empty_dbs(self, client: TestClient, tmp_path: Path) -> None:
        """POST /merge with two empty DBs must return merged_count=0."""
        local_db = str(tmp_path / "local.db")
        remote_db = str(tmp_path / "remote.db")
        r = client.post("/merge", json={"db": local_db, "other_db": remote_db})
        assert r.status_code == 200
        assert r.json()["merged_count"] == 0

    def test_merge_copies_facts(self, client: TestClient, tmp_path: Path) -> None:
        """POST /merge must copy facts from other_db into db."""
        local_db = str(tmp_path / "local.db")
        remote_db = str(tmp_path / "remote.db")
        client.post(
            "/fact",
            json={
                "domain": "life",
                "entity": "king",
                "attribute": "alive",
                "value": True,
                "db": remote_db,
            },
        )
        r = client.post("/merge", json={"db": local_db, "other_db": remote_db})
        assert r.json()["merged_count"] == 1


class TestGetEvents:
    """Tests for GET /events."""

    def test_empty_events(self, client: TestClient, db_path: str) -> None:
        """GET /events on an empty store must return {'events': []}."""
        r = client.get("/events", params={"db": db_path})
        assert r.status_code == 200
        assert r.json()["events"] == []

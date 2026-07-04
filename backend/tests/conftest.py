"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        anthropic_api_key="sk-test-key",
        anthropic_model="claude-sonnet-5",
        session_secret="test-session-secret",
        data_dir=tmp_path / "data",
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


def register_and_login(
    client: TestClient, username: str = "cole", password: str = "hunter2secure"
) -> dict:
    """Register a user and log in; returns the user payload. Cookie sticks to the client."""
    resp = client.post("/api/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201, resp.text
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def logged_in_user(client) -> dict:
    return register_and_login(client)

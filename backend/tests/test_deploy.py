"""Tests for the production-deployment surface: health check, invite-code registration
gate, Secure session cookie, and SPA static serving."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

CREDS = {"username": "cole", "password": "hunter2secure"}


def make_client(tmp_path, **overrides) -> TestClient:
    settings = Settings(
        _env_file=None,
        anthropic_api_key="sk-test-key",
        session_secret="test-session-secret",
        data_dir=tmp_path / "data",
        **overrides,
    )
    return TestClient(create_app(settings))


class TestHealth:
    def test_health_is_public_and_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestInviteCode:
    def test_register_without_code_when_unconfigured(self, client):
        assert client.post("/api/auth/register", json=CREDS).status_code == 201

    def test_register_requires_matching_code(self, tmp_path):
        client = make_client(tmp_path, invite_code="secret-invite")

        missing = client.post("/api/auth/register", json=CREDS)
        assert missing.status_code == 403

        wrong = client.post("/api/auth/register", json={**CREDS, "invite_code": "nope"})
        assert wrong.status_code == 403

        right = client.post("/api/auth/register", json={**CREDS, "invite_code": "secret-invite"})
        assert right.status_code == 201

    def test_login_never_needs_the_code(self, tmp_path):
        client = make_client(tmp_path, invite_code="secret-invite")
        client.post("/api/auth/register", json={**CREDS, "invite_code": "secret-invite"})
        assert client.post("/api/auth/login", json=CREDS).status_code == 200


class TestSecureCookie:
    def login_cookie(self, client) -> str:
        client.post("/api/auth/register", json=CREDS)
        resp = client.post("/api/auth/login", json=CREDS)
        assert resp.status_code == 200
        return resp.headers["set-cookie"]

    def test_secure_flag_off_by_default_for_local_dev(self, tmp_path):
        cookie = self.login_cookie(make_client(tmp_path))
        assert "Secure" not in cookie
        assert "HttpOnly" in cookie

    def test_secure_flag_on_when_configured(self, tmp_path):
        cookie = self.login_cookie(make_client(tmp_path, session_cookie_secure=True))
        assert "Secure" in cookie
        assert "HttpOnly" in cookie


class TestSpaServing:
    @pytest.fixture
    def spa_client(self, tmp_path) -> TestClient:
        static = tmp_path / "static"
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text("<html>SPA SHELL</html>")
        (static / "assets" / "app.js").write_text("console.log('app')")
        return make_client(tmp_path, static_dir=static)

    def test_root_serves_index(self, spa_client):
        resp = spa_client.get("/")
        assert resp.status_code == 200
        assert "SPA SHELL" in resp.text

    def test_client_side_routes_fall_back_to_index(self, spa_client):
        for path in ("/topics", "/decks/d_123", "/upload"):
            resp = spa_client.get(path)
            assert resp.status_code == 200, path
            assert "SPA SHELL" in resp.text, path

    def test_real_assets_are_served(self, spa_client):
        resp = spa_client.get("/assets/app.js")
        assert resp.status_code == 200
        assert "console.log" in resp.text

    def test_api_routes_still_win(self, spa_client):
        resp = spa_client.get("/api/auth/me")
        assert resp.status_code == 401  # JSON API response, not the SPA shell
        assert resp.json()["detail"]

    def test_no_static_dir_means_no_spa(self, client):
        assert client.get("/").status_code == 404

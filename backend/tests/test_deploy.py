"""Tests for the production-deployment surface: health check, invite-code registration
gate, Secure session cookie, and SPA static serving."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings, register_and_login

CREDS = {"username": "cole", "password": "hunter2secure"}


def make_client(tmp_path, **overrides) -> TestClient:
    return TestClient(create_app(make_settings(tmp_path, **overrides)))


class TestHealth:
    def test_health_is_public_and_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestSettingsIsolation:
    def test_ambient_env_vars_cannot_leak_into_test_settings(self, tmp_path, monkeypatch):
        """A developer's exported deploy vars must not poison the suite."""
        monkeypatch.setenv("INVITE_CODE", "leaked")
        monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
        settings = make_settings(tmp_path)
        assert settings.invite_code == ""
        assert settings.session_cookie_secure is False


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

    def test_failed_attempts_are_logged(self, tmp_path, caplog):
        """Brute-force attempts must leave a trace in the logs."""
        client = make_client(tmp_path, invite_code="secret-invite")
        with caplog.at_level("WARNING", logger="app"):
            client.post("/api/auth/register", json={**CREDS, "invite_code": "guess1"})
        assert any("invite code" in r.message.lower() for r in caplog.records)

    def test_login_never_needs_the_code(self, tmp_path):
        client = make_client(tmp_path, invite_code="secret-invite")
        client.post("/api/auth/register", json={**CREDS, "invite_code": "secret-invite"})
        assert client.post("/api/auth/login", json=CREDS).status_code == 200


class TestSecureCookie:
    def login_cookie(self, client) -> str:
        register_and_login(client)
        resp = client.post("/api/auth/login", json=CREDS)  # fresh response to read headers
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

    def test_missing_asset_is_404_not_html(self, spa_client):
        """A stale cached index.html requesting a deleted hashed bundle must get a 404
        (signals the browser/user to reload), never index.html masquerading as JS."""
        resp = spa_client.get("/assets/app-oldhash.js")
        assert resp.status_code == 404
        assert "SPA SHELL" not in resp.text

    def test_unknown_api_path_is_json_404_not_html(self, spa_client):
        """The frontend's error contract is ApiError-from-JSON; an unknown /api route
        must never fall back to the SPA shell."""
        resp = spa_client.get("/api/nope/definitely-not-a-route")
        assert resp.status_code == 404
        assert resp.headers["content-type"].startswith("application/json")

    def test_known_api_routes_still_win(self, spa_client):
        resp = spa_client.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.json()["detail"]

    def test_no_static_dir_means_no_spa(self, client):
        assert client.get("/").status_code == 404

    def test_configured_but_missing_static_dir_fails_fast(self, tmp_path):
        """A typo'd STATIC_DIR must kill startup so the platform healthcheck rejects
        the deploy, instead of shipping an API-only app with a green healthcheck."""
        with pytest.raises(RuntimeError, match="STATIC_DIR"):
            make_client(tmp_path, static_dir=tmp_path / "does-not-exist")

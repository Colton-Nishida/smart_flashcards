"""Tests for app.auth — register/login/logout/me with signed session cookies."""

from tests.conftest import register_and_login


class TestRegister:
    def test_register_creates_user(self, client):
        resp = client.post(
            "/api/auth/register", json={"username": "cole", "password": "hunter2secure"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == "cole"
        assert body["id"].startswith("u_")
        assert "created_at" in body
        assert "password" not in body
        assert "password_hash" not in body

    def test_register_duplicate_username_conflict(self, client):
        client.post("/api/auth/register", json={"username": "cole", "password": "hunter2secure"})
        resp = client.post(
            "/api/auth/register", json={"username": "cole", "password": "otherpassword"}
        )
        assert resp.status_code == 409

    def test_register_rejects_short_password(self, client):
        resp = client.post("/api/auth/register", json={"username": "cole", "password": "abc"})
        assert resp.status_code == 422

    def test_register_rejects_empty_username(self, client):
        resp = client.post("/api/auth/register", json={"username": "", "password": "hunter2secure"})
        assert resp.status_code == 422

    def test_password_is_hashed_on_disk(self, client, settings):
        client.post("/api/auth/register", json={"username": "cole", "password": "hunter2secure"})
        users = (settings.data_dir / "users.json").read_text()
        assert "hunter2secure" not in users


class TestLogin:
    def test_login_sets_httponly_cookie(self, client):
        client.post("/api/auth/register", json={"username": "cole", "password": "hunter2secure"})
        resp = client.post(
            "/api/auth/login", json={"username": "cole", "password": "hunter2secure"}
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "cole"
        set_cookie = resp.headers["set-cookie"]
        assert "session=" in set_cookie
        assert "HttpOnly" in set_cookie

    def test_login_wrong_password_rejected(self, client):
        client.post("/api/auth/register", json={"username": "cole", "password": "hunter2secure"})
        resp = client.post("/api/auth/login", json={"username": "cole", "password": "wrongpass1"})
        assert resp.status_code == 401
        assert "session" not in resp.cookies

    def test_login_unknown_user_rejected(self, client):
        resp = client.post("/api/auth/login", json={"username": "ghost", "password": "whatever12"})
        assert resp.status_code == 401


class TestMe:
    def test_me_returns_current_user(self, client):
        user = register_and_login(client)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json() == user

    def test_me_unauthenticated_401(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_tampered_cookie_401(self, client):
        register_and_login(client)
        client.cookies.set("session", "forged-token")
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_session_not_valid_across_secret_change(self, client, settings, tmp_path):
        """A cookie signed with a different secret must be rejected."""
        from app.auth.sessions import sign_session

        register_and_login(client)
        forged = sign_session("some-other-secret", "u_whatever")
        client.cookies.set("session", forged)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestLogout:
    def test_logout_clears_session(self, client):
        register_and_login(client)
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 204
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestFullFlow:
    def test_register_login_me_logout_flow(self, client):
        reg = client.post(
            "/api/auth/register", json={"username": "ana", "password": "sup3rsecret"}
        )
        assert reg.status_code == 201
        login = client.post("/api/auth/login", json={"username": "ana", "password": "sup3rsecret"})
        assert login.status_code == 200
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["username"] == "ana"
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401

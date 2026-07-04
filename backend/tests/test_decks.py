"""Tests for app.decks — deck + card CRUD with per-user isolation."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_and_login

CARDS = [
    {"front": "What is glycolysis?", "back": "Breakdown of glucose.", "tags": ["metabolism"]},
    {"front": "What is ATP?", "back": "The cell's energy currency.", "tags": []},
]


def make_deck(app, user_id: str, name: str = "Bio 101", cards=None) -> dict:
    """Create a deck directly through the service layer (HTTP creation is Phase 2)."""
    from app.decks import service

    return service.create_deck(
        app.state.storage,
        user_id,
        name=name,
        description="Cell respiration",
        source_filename="chapter4.pdf",
        cards=cards if cards is not None else CARDS,
    )


@pytest.fixture
def deck(client, app, logged_in_user) -> dict:
    return make_deck(app, logged_in_user["id"])


class TestAuthRequired:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/decks"),
            ("GET", "/api/decks/d_x"),
            ("PATCH", "/api/decks/d_x"),
            ("DELETE", "/api/decks/d_x"),
            ("POST", "/api/decks/d_x/cards"),
            ("PATCH", "/api/decks/d_x/cards/c_x"),
            ("DELETE", "/api/decks/d_x/cards/c_x"),
        ],
    )
    def test_unauthenticated_401(self, client, method, path):
        resp = client.request(method, path, json={})
        assert resp.status_code == 401


class TestListDecks:
    def test_empty_list(self, client, logged_in_user):
        resp = client.get("/api/decks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_summaries(self, client, deck):
        resp = client.get("/api/decks")
        assert resp.status_code == 200
        [summary] = resp.json()
        assert summary["id"] == deck["id"]
        assert summary["name"] == "Bio 101"
        assert summary["card_count"] == 2
        assert "cards" not in summary

    def test_list_is_ordered_newest_first(self, client, app, logged_in_user):
        """Decks must come back newest-first, not in random deck-id order.

        Regression: list_decks sorted by filename (the random hex deck id), so the
        order was arbitrary and unstable relative to creation time.
        """
        storage = app.state.storage
        user_id = logged_in_user["id"]
        # Craft decks whose ids sort in the OPPOSITE order of their created_at, so a
        # filename sort would disagree with a chronological one.
        specs = [
            ("d_aaa", "oldest", "2026-01-01T00:00:00Z"),
            ("d_ccc", "middle", "2026-06-01T00:00:00Z"),
            ("d_bbb", "newest", "2026-12-01T00:00:00Z"),
        ]
        for deck_id, name, created_at in specs:
            storage.write_deck(
                user_id,
                {
                    "id": deck_id,
                    "name": name,
                    "description": "",
                    "created_at": created_at,
                    "source_filename": "x.pdf",
                    "cards": [],
                },
            )
        names = [d["name"] for d in client.get("/api/decks").json()]
        assert names == ["newest", "middle", "oldest"]


class TestGetDeck:
    def test_get_full_deck(self, client, deck):
        resp = client.get(f"/api/decks/{deck['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == deck["id"]
        assert len(body["cards"]) == 2
        assert body["cards"][0]["front"] == "What is glycolysis?"
        assert body["cards"][0]["id"].startswith("c_")

    def test_get_missing_404(self, client, logged_in_user):
        assert client.get("/api/decks/d_missing").status_code == 404


class TestUpdateDeck:
    def test_patch_name(self, client, deck):
        resp = client.patch(f"/api/decks/{deck['id']}", json={"name": "Bio 102"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bio 102"
        assert resp.json()["description"] == "Cell respiration"

    def test_patch_description_only(self, client, deck):
        resp = client.patch(f"/api/decks/{deck['id']}", json={"description": "New desc"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bio 101"
        assert resp.json()["description"] == "New desc"

    def test_patch_missing_404(self, client, logged_in_user):
        assert client.patch("/api/decks/d_missing", json={"name": "X"}).status_code == 404


class TestDeleteDeck:
    def test_delete(self, client, deck):
        assert client.delete(f"/api/decks/{deck['id']}").status_code == 204
        assert client.get(f"/api/decks/{deck['id']}").status_code == 404

    def test_delete_missing_404(self, client, logged_in_user):
        assert client.delete("/api/decks/d_missing").status_code == 404


class TestCards:
    def test_add_card(self, client, deck):
        resp = client.post(
            f"/api/decks/{deck['id']}/cards",
            json={"front": "New Q", "back": "New A", "tags": ["misc"]},
        )
        assert resp.status_code == 201
        card = resp.json()
        assert card["id"].startswith("c_")
        assert card["front"] == "New Q"
        deck_body = client.get(f"/api/decks/{deck['id']}").json()
        assert len(deck_body["cards"]) == 3

    def test_add_card_default_tags(self, client, deck):
        resp = client.post(f"/api/decks/{deck['id']}/cards", json={"front": "Q", "back": "A"})
        assert resp.status_code == 201
        assert resp.json()["tags"] == []

    def test_edit_card(self, client, deck):
        card_id = client.get(f"/api/decks/{deck['id']}").json()["cards"][0]["id"]
        resp = client.patch(
            f"/api/decks/{deck['id']}/cards/{card_id}", json={"back": "Edited answer"}
        )
        assert resp.status_code == 200
        assert resp.json()["back"] == "Edited answer"
        assert resp.json()["front"] == "What is glycolysis?"

    def test_edit_missing_card_404(self, client, deck):
        resp = client.patch(f"/api/decks/{deck['id']}/cards/c_missing", json={"back": "X"})
        assert resp.status_code == 404

    def test_delete_card(self, client, deck):
        card_id = client.get(f"/api/decks/{deck['id']}").json()["cards"][0]["id"]
        assert client.delete(f"/api/decks/{deck['id']}/cards/{card_id}").status_code == 204
        remaining = client.get(f"/api/decks/{deck['id']}").json()["cards"]
        assert card_id not in [c["id"] for c in remaining]

    def test_delete_missing_card_404(self, client, deck):
        assert client.delete(f"/api/decks/{deck['id']}/cards/c_missing").status_code == 404


class TestPerUserIsolation:
    """User A must never be able to read or modify user B's decks."""

    def test_other_users_deck_is_invisible(self, app, deck):
        other = TestClient(app)
        register_and_login(other, username="mallory")
        assert other.get("/api/decks").json() == []
        assert other.get(f"/api/decks/{deck['id']}").status_code == 404

    def test_other_user_cannot_modify_or_delete(self, app, deck):
        other = TestClient(app)
        register_and_login(other, username="mallory")
        assert other.patch(f"/api/decks/{deck['id']}", json={"name": "pwned"}).status_code == 404
        assert other.delete(f"/api/decks/{deck['id']}").status_code == 404
        assert (
            other.post(
                f"/api/decks/{deck['id']}/cards", json={"front": "x", "back": "y"}
            ).status_code
            == 404
        )

    def test_owner_unaffected_by_foreign_attempts(self, client, app, deck):
        other = TestClient(app)
        register_and_login(other, username="mallory")
        other.patch(f"/api/decks/{deck['id']}", json={"name": "pwned"})
        assert client.get(f"/api/decks/{deck['id']}").json()["name"] == "Bio 101"

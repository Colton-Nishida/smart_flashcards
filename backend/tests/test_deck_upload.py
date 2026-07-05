"""Tests for POST /api/decks — multipart upload -> synchronous generation -> persisted deck."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from app.generation.deps import get_anthropic_client
from app.generation.models import Flashcard, FlashcardDeck
from app.generation.service import MAX_PDF_BYTES
from tests.conftest import register_and_login

PDF_BYTES = b"%PDF-1.4 fake pdf content for testing"

GENERATED = FlashcardDeck(
    cards=[
        Flashcard(front="What is glycolysis?", back="Breakdown of glucose.", tags=["metabolism"]),
        Flashcard(front="What is ATP?", back="Energy currency.", tags=[]),
    ]
)


@pytest.fixture
def mock_anthropic(app) -> MagicMock:
    client = MagicMock()
    client.messages.parse.return_value = SimpleNamespace(
        stop_reason="end_turn", parsed_output=GENERATED
    )
    app.dependency_overrides[get_anthropic_client] = lambda: client
    return client


def upload(client, *, data: bytes = PDF_BYTES, name: str = "Bio 101", filename: str = "ch4.pdf"):
    return client.post(
        "/api/decks",
        files={"file": (filename, data, "application/pdf")},
        data={"name": name, "description": "Cell respiration"},
    )


def upload_with(client, **fields):
    data = {"name": "Bio 101", "description": "Cell respiration", **fields}
    return client.post(
        "/api/decks",
        files={"file": ("ch4.pdf", PDF_BYTES, "application/pdf")},
        data=data,
    )


class TestAdditionalInstructions:
    def test_forwarded_to_prompt_and_persisted(self, client, mock_anthropic, logged_in_user):
        resp = upload_with(
            client, additional_instructions="Only make cards about glycolysis; skip the intro."
        )
        assert resp.status_code == 201, resp.text
        assert (
            resp.json()["additional_instructions"]
            == "Only make cards about glycolysis; skip the intro."
        )
        text = mock_anthropic.messages.parse.call_args.kwargs["messages"][0]["content"][1]["text"]
        assert "Only make cards about glycolysis" in text

    def test_optional_defaults_to_empty(self, client, mock_anthropic, logged_in_user):
        resp = upload(client)  # no additional_instructions sent
        assert resp.status_code == 201, resp.text
        assert resp.json()["additional_instructions"] == ""

    def test_too_long_rejected_422(self, client, mock_anthropic, logged_in_user):
        resp = upload_with(client, additional_instructions="x" * 2001)
        assert resp.status_code == 422
        mock_anthropic.messages.parse.assert_not_called()


class TestCreateDeck:
    def test_unauthenticated_401(self, client, mock_anthropic):
        assert upload(client).status_code == 401

    def test_creates_and_persists_deck(self, client, mock_anthropic, logged_in_user):
        resp = upload(client)
        assert resp.status_code == 201, resp.text
        deck = resp.json()
        assert deck["name"] == "Bio 101"
        assert deck["description"] == "Cell respiration"
        assert deck["source_filename"] == "ch4.pdf"
        assert [c["front"] for c in deck["cards"]] == ["What is glycolysis?", "What is ATP?"]
        assert all(c["id"].startswith("c_") for c in deck["cards"])

        # persisted: retrievable and listed
        assert client.get(f"/api/decks/{deck['id']}").status_code == 200
        [summary] = client.get("/api/decks").json()
        assert summary["card_count"] == 2

    def test_generation_uses_configured_model(self, client, mock_anthropic, logged_in_user):
        upload(client)
        assert mock_anthropic.messages.parse.call_args.kwargs["model"] == "claude-sonnet-5"

    def test_non_pdf_rejected_400(self, client, mock_anthropic, logged_in_user):
        resp = upload(client, data=b"just some text", filename="notes.txt")
        assert resp.status_code == 400
        mock_anthropic.messages.parse.assert_not_called()

    def test_oversized_pdf_rejected_413(self, client, mock_anthropic, logged_in_user):
        resp = upload(client, data=b"%PDF-" + b"0" * MAX_PDF_BYTES)
        assert resp.status_code == 413
        mock_anthropic.messages.parse.assert_not_called()

    def test_max_tokens_maps_to_413_document_too_large(
        self, client, mock_anthropic, logged_in_user
    ):
        mock_anthropic.messages.parse.return_value = SimpleNamespace(
            stop_reason="max_tokens", parsed_output=None
        )
        resp = upload(client)
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"].lower()

    def test_truncated_json_maps_to_413_not_500(self, client, mock_anthropic, logged_in_user):
        """Regression: a large PDF that overflows the output cap truncates the JSON,
        which used to surface as a raw 500 instead of a friendly 413."""
        from pydantic import ValidationError

        from app.generation.models import FlashcardDeck

        try:
            FlashcardDeck.model_validate_json('{"cards": [{"front": "What is')
        except ValidationError as truncated:
            mock_anthropic.messages.parse.side_effect = truncated
        resp = upload(client)
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"].lower()

    def test_refusal_empty_output_maps_to_502_not_500(self, client, mock_anthropic, logged_in_user):
        """A model refusal (or any response with no parsed output) has stop_reason
        != max_tokens and parsed_output=None. It must map to a clean 502, not a raw 500."""
        mock_anthropic.messages.parse.return_value = SimpleNamespace(
            stop_reason="refusal", parsed_output=None
        )
        resp = upload(client)
        assert resp.status_code == 502
        assert client.get("/api/decks").json() == []

    def test_missing_name_422(self, client, mock_anthropic, logged_in_user):
        resp = client.post(
            "/api/decks",
            files={"file": ("ch4.pdf", PDF_BYTES, "application/pdf")},
            data={"description": "no name"},
        )
        assert resp.status_code == 422

    def test_anthropic_api_error_maps_to_502(self, client, mock_anthropic, logged_in_user):
        mock_anthropic.messages.parse.side_effect = anthropic.APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )
        resp = upload(client)
        assert resp.status_code == 502

    def test_failed_generation_persists_nothing(self, client, mock_anthropic, logged_in_user):
        mock_anthropic.messages.parse.return_value = SimpleNamespace(
            stop_reason="max_tokens", parsed_output=None
        )
        upload(client)
        assert client.get("/api/decks").json() == []


class TestUnconfiguredApiKey:
    def test_upload_without_api_key_returns_503(self, tmp_path):
        """No ANTHROPIC_API_KEY configured -> friendly 503, not a raw 500 TypeError."""
        from fastapi.testclient import TestClient

        from app.config import Settings
        from app.main import create_app

        settings = Settings(
            _env_file=None,
            anthropic_api_key="",
            session_secret="test-session-secret",
            data_dir=tmp_path / "data",
        )
        client = TestClient(create_app(settings))
        register_and_login(client)

        resp = upload(client)
        assert resp.status_code == 503
        assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


class TestIsolationOnCreate:
    def test_created_deck_belongs_to_creator_only(self, client, app, mock_anthropic):
        from fastapi.testclient import TestClient

        register_and_login(client, username="alice")
        deck_id = upload(client).json()["id"]

        other = TestClient(app)
        register_and_login(other, username="bob")
        assert other.get(f"/api/decks/{deck_id}").status_code == 404

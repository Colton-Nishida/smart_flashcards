"""Tests for /api/topics — PDF upload -> notes extraction -> topic CRUD."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from app.generation.deps import get_anthropic_client
from app.generation.service import MAX_PDF_BYTES
from app.quiz.models import TopicNotes
from app.storage import Storage
from tests.conftest import register_and_login

PDF_BYTES = b"%PDF-1.4 fake pdf content for testing"

EXTRACTED = TopicNotes(
    notes_md="# Photosynthesis\n\nLight reactions convert light energy into ATP and NADPH."
)


def respond(output, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, parsed_output=output)


@pytest.fixture
def mock_anthropic(app) -> MagicMock:
    client = MagicMock()
    client.messages.parse.return_value = respond(EXTRACTED)
    app.dependency_overrides[get_anthropic_client] = lambda: client
    return client


def create_topic(
    client,
    *,
    data: bytes = PDF_BYTES,
    name: str = "Photosynthesis",
    description: str = "Bio chapter 8",
    filename: str = "ch8.pdf",
):
    return client.post(
        "/api/topics",
        files={"file": (filename, data, "application/pdf")},
        data={"name": name, "description": description},
    )


class TestTopicStorage:
    def test_topic_roundtrip(self, tmp_path):
        storage = Storage(tmp_path)
        topic = {"id": "t_abc", "name": "X"}
        storage.write_topic("u1", topic)
        assert storage.read_topic("u1", "t_abc") == topic
        assert storage.list_topics("u1") == [topic]
        assert storage.delete_topic("u1", "t_abc") is True
        assert storage.read_topic("u1", "t_abc") is None

    def test_missing_topic_reads_none(self, tmp_path):
        storage = Storage(tmp_path)
        assert storage.read_topic("u1", "t_missing") is None
        assert storage.list_topics("u1") == []
        assert storage.delete_topic("u1", "t_missing") is False

    def test_pdf_roundtrip(self, tmp_path):
        storage = Storage(tmp_path)
        storage.write_topic_pdf("u1", "t_abc", PDF_BYTES)
        assert storage.read_topic_pdf("u1", "t_abc") == PDF_BYTES
        assert storage.read_topic_pdf("u1", "t_missing") is None

    def test_delete_topic_removes_pdf(self, tmp_path):
        storage = Storage(tmp_path)
        storage.write_topic("u1", {"id": "t_abc"})
        storage.write_topic_pdf("u1", "t_abc", PDF_BYTES)
        storage.delete_topic("u1", "t_abc")
        assert storage.read_topic_pdf("u1", "t_abc") is None


class TestCreateTopic:
    def test_unauthenticated_401(self, client, mock_anthropic):
        assert create_topic(client).status_code == 401

    def test_creates_and_persists_topic(self, client, mock_anthropic, logged_in_user):
        resp = create_topic(client)
        assert resp.status_code == 201, resp.text
        topic = resp.json()
        assert topic["id"].startswith("t_")
        assert topic["name"] == "Photosynthesis"
        assert topic["description"] == "Bio chapter 8"
        assert topic["source_filename"] == "ch8.pdf"
        assert topic["notes_md"] == EXTRACTED.notes_md
        assert topic["mastery_score"] == 0
        assert topic["mastery_notes"] == ""
        assert topic["sessions"] == []
        assert topic["active_session"] is None

        # persisted: retrievable and listed
        assert client.get(f"/api/topics/{topic['id']}").status_code == 200
        [summary] = client.get("/api/topics").json()
        assert summary["mastery_score"] == 0
        assert summary["has_active_session"] is False
        assert summary["session_count"] == 0

    def test_extraction_sends_pdf_document_block(self, client, mock_anthropic, logged_in_user):
        create_topic(client)
        kwargs = mock_anthropic.messages.parse.call_args.kwargs
        assert kwargs["model"] == "claude-sonnet-5"
        assert kwargs["output_format"] is TopicNotes
        [message] = kwargs["messages"]
        assert message["content"][0]["type"] == "document"
        assert message["content"][0]["source"]["media_type"] == "application/pdf"

    def test_non_pdf_rejected_400(self, client, mock_anthropic, logged_in_user):
        resp = create_topic(client, data=b"just some text", filename="notes.txt")
        assert resp.status_code == 400
        mock_anthropic.messages.parse.assert_not_called()

    def test_oversized_pdf_rejected_413(self, client, mock_anthropic, logged_in_user):
        resp = create_topic(client, data=b"%PDF-" + b"0" * MAX_PDF_BYTES)
        assert resp.status_code == 413
        mock_anthropic.messages.parse.assert_not_called()

    def test_max_tokens_maps_to_413(self, client, mock_anthropic, logged_in_user):
        mock_anthropic.messages.parse.return_value = respond(None, stop_reason="max_tokens")
        assert create_topic(client).status_code == 413

    def test_anthropic_api_error_maps_to_502(self, client, mock_anthropic, logged_in_user):
        mock_anthropic.messages.parse.side_effect = anthropic.APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )
        assert create_topic(client).status_code == 502

    def test_failed_extraction_persists_nothing(self, client, mock_anthropic, logged_in_user):
        mock_anthropic.messages.parse.return_value = respond(None, stop_reason="max_tokens")
        create_topic(client)
        assert client.get("/api/topics").json() == []

    def test_missing_name_422(self, client, mock_anthropic, logged_in_user):
        resp = client.post(
            "/api/topics",
            files={"file": ("ch8.pdf", PDF_BYTES, "application/pdf")},
            data={"description": "no name"},
        )
        assert resp.status_code == 422


class TestTopicCrud:
    @pytest.fixture
    def topic(self, client, mock_anthropic, logged_in_user) -> dict:
        return create_topic(client).json()

    def test_get_missing_404(self, client, logged_in_user):
        assert client.get("/api/topics/t_missing").status_code == 404

    def test_patch_updates_metadata(self, client, topic):
        resp = client.patch(f"/api/topics/{topic['id']}", json={"name": "Photo II"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Photo II"
        assert resp.json()["description"] == "Bio chapter 8"

    def test_delete_removes_topic(self, client, topic):
        assert client.delete(f"/api/topics/{topic['id']}").status_code == 204
        assert client.get(f"/api/topics/{topic['id']}").status_code == 404
        assert client.get(f"/api/topics/{topic['id']}/pdf").status_code == 404

    def test_pdf_download(self, client, topic):
        resp = client.get(f"/api/topics/{topic['id']}/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == PDF_BYTES

    def test_isolation_between_users(self, client, app, topic):
        from fastapi.testclient import TestClient

        other = TestClient(app)
        register_and_login(other, username="bob")
        assert other.get(f"/api/topics/{topic['id']}").status_code == 404
        assert other.get("/api/topics").json() == []

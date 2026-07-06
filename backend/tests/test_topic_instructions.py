"""Tests for per-topic "additional instructions": persisted at upload, editable via
PATCH, injected into notes extraction and every quiz-agent call, back-compatible
with topics stored before the field existed."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.generation.deps import get_anthropic_client
from app.quiz.models import (
    AnswerGrade,
    DisputeVerdict,
    MasteryUpdate,
    QuizQuestion,
    TopicNotes,
)
from app.storage import Storage

PDF_BYTES = b"%PDF-1.4 fake pdf content for testing"
INSTRUCTIONS = "Only focus on chapter 2. Ask definition-style questions only."


def respond(output):
    return SimpleNamespace(stop_reason="end_turn", parsed_output=output)


@pytest.fixture
def mock_anthropic(app) -> MagicMock:
    client = MagicMock()
    outputs = {
        TopicNotes: TopicNotes(notes_md="# Notes\n\nChlorophyll absorbs light."),
        QuizQuestion: QuizQuestion(question="What does chlorophyll absorb?"),
        AnswerGrade: AnswerGrade(grade="good", feedback="Right."),
        DisputeVerdict: DisputeVerdict(
            verdict="upheld", revised_grade=None, reply="Stands.", correction_note=None
        ),
        MasteryUpdate: MasteryUpdate(
            score=50, mastery_notes="Fine.", session_summary="One question."
        ),
    }
    client.messages.parse.side_effect = lambda **kw: respond(outputs[kw["output_format"]])
    app.dependency_overrides[get_anthropic_client] = lambda: client
    return client


def create_topic(client, instructions=INSTRUCTIONS):
    data = {"name": "Photosynthesis", "description": "Bio ch8"}
    if instructions is not None:
        data["instructions"] = instructions
    return client.post(
        "/api/topics",
        files={"file": ("ch8.pdf", PDF_BYTES, "application/pdf")},
        data=data,
    )


def last_prompt_text(mock) -> str:
    content = mock.messages.parse.call_args.kwargs["messages"][0]["content"]
    if isinstance(content, str):
        return content
    return " ".join(block.get("text", "") for block in content if isinstance(block, dict))


class TestCreateWithInstructions:
    def test_instructions_persisted(self, client, mock_anthropic, logged_in_user):
        topic = create_topic(client).json()
        assert topic["instructions"] == INSTRUCTIONS
        detail = client.get(f"/api/topics/{topic['id']}").json()
        assert detail["instructions"] == INSTRUCTIONS

    def test_default_is_empty(self, client, mock_anthropic, logged_in_user):
        topic = create_topic(client, instructions=None).json()
        assert topic["instructions"] == ""

    def test_extraction_prompt_includes_instructions(self, client, mock_anthropic, logged_in_user):
        create_topic(client)
        assert INSTRUCTIONS in last_prompt_text(mock_anthropic)

    def test_extraction_prompt_omits_section_when_empty(
        self, client, mock_anthropic, logged_in_user
    ):
        create_topic(client, instructions=None)
        assert "instructions" not in last_prompt_text(mock_anthropic).lower()

    def test_too_long_instructions_422(self, client, mock_anthropic, logged_in_user):
        assert create_topic(client, instructions="x" * 4001).status_code == 422


class TestPatchInstructions:
    def test_patch_updates_instructions(self, client, mock_anthropic, logged_in_user):
        topic = create_topic(client).json()
        resp = client.patch(
            f"/api/topics/{topic['id']}", json={"instructions": "New focus: only formulas."}
        )
        assert resp.status_code == 200
        assert resp.json()["instructions"] == "New focus: only formulas."

    def test_patch_name_leaves_instructions(self, client, mock_anthropic, logged_in_user):
        topic = create_topic(client).json()
        resp = client.patch(f"/api/topics/{topic['id']}", json={"name": "Photo II"})
        assert resp.json()["instructions"] == INSTRUCTIONS

    def test_patch_can_clear_instructions(self, client, mock_anthropic, logged_in_user):
        topic = create_topic(client).json()
        resp = client.patch(f"/api/topics/{topic['id']}", json={"instructions": ""})
        assert resp.json()["instructions"] == ""


class TestBackCompat:
    def test_storage_backfills_missing_field_on_read(self, tmp_path):
        """The compat rule lives once, at the storage seam — every read path gets it."""
        storage = Storage(tmp_path)
        storage.write_topic("u1", {"id": "t_old", "name": "Legacy"})
        assert storage.read_topic("u1", "t_old")["instructions"] == ""
        [topic] = storage.list_topics("u1")
        assert topic["instructions"] == ""

    def test_topic_stored_before_field_existed_still_loads(
        self, app, client, mock_anthropic, logged_in_user
    ):
        """Topics already on the production volume have no 'instructions' key."""
        topic = create_topic(client).json()
        storage = app.state.storage
        stored = storage.read_topic(logged_in_user["id"], topic["id"])
        del stored["instructions"]
        storage.write_topic(logged_in_user["id"], stored)

        resp = client.get(f"/api/topics/{topic['id']}")
        assert resp.status_code == 200
        assert resp.json()["instructions"] == ""
        [summary] = client.get("/api/topics").json()
        assert summary["id"] == topic["id"]

    def test_quiz_works_on_legacy_topic(self, app, client, mock_anthropic, logged_in_user):
        topic = create_topic(client).json()
        storage = app.state.storage
        stored = storage.read_topic(logged_in_user["id"], topic["id"])
        del stored["instructions"]
        storage.write_topic(logged_in_user["id"], stored)

        resp = client.post(f"/api/topics/{topic['id']}/quiz/start", json={"num_questions": 1})
        assert resp.status_code == 201, resp.text


class TestQuizCallsSeeInstructions:
    @pytest.fixture
    def topic(self, client, mock_anthropic, logged_in_user) -> dict:
        return create_topic(client).json()

    def test_question_prompt(self, client, topic, mock_anthropic):
        client.post(f"/api/topics/{topic['id']}/quiz/start", json={"num_questions": 2})
        assert INSTRUCTIONS in last_prompt_text(mock_anthropic)

    def test_grading_prompt(self, client, topic, mock_anthropic):
        client.post(f"/api/topics/{topic['id']}/quiz/start", json={"num_questions": 2})
        client.post(f"/api/topics/{topic['id']}/quiz/answer", json={"answer": "Light"})
        assert INSTRUCTIONS in last_prompt_text(mock_anthropic)

    def test_dispute_prompt(self, client, topic, mock_anthropic):
        client.post(f"/api/topics/{topic['id']}/quiz/start", json={"num_questions": 2})
        client.post(f"/api/topics/{topic['id']}/quiz/answer", json={"answer": "Light"})
        client.post(f"/api/topics/{topic['id']}/quiz/dispute", json={"message": "Too harsh"})
        assert INSTRUCTIONS in last_prompt_text(mock_anthropic)

    def test_scoring_prompt(self, client, topic, mock_anthropic):
        client.post(f"/api/topics/{topic['id']}/quiz/start", json={"num_questions": 1})
        client.post(f"/api/topics/{topic['id']}/quiz/answer", json={"answer": "Light"})
        client.post(f"/api/topics/{topic['id']}/quiz/finish")
        assert INSTRUCTIONS in last_prompt_text(mock_anthropic)

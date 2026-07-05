"""Tests for the quiz agent flow: /api/topics/{id}/quiz/* (start/answer/next/dispute/finish)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from app.generation.deps import get_anthropic_client
from app.quiz.models import (
    AnswerGrade,
    DisputeVerdict,
    MasteryUpdate,
    QuizQuestion,
    TopicNotes,
)

PDF_BYTES = b"%PDF-1.4 fake pdf content for testing"

NOTES_MD = "# Photosynthesis\n\nChlorophyll absorbs red and blue light."


def respond(output):
    return SimpleNamespace(stop_reason="end_turn", parsed_output=output)


@pytest.fixture
def mock_anthropic(app) -> MagicMock:
    """Dispatches on output_format so one mock serves every call in the flow."""
    client = MagicMock()
    outputs = {
        TopicNotes: TopicNotes(notes_md=NOTES_MD),
        QuizQuestion: QuizQuestion(question="What does chlorophyll absorb?"),
        AnswerGrade: AnswerGrade(grade="good", feedback="Exactly right."),
        DisputeVerdict: DisputeVerdict(
            verdict="revised",
            revised_grade="good",
            reply="Fair point — your phrasing was fine.",
            correction_note=None,
        ),
        MasteryUpdate: MasteryUpdate(
            score=64,
            mastery_notes="Solid on light absorption; shaky on the Calvin cycle.",
            session_summary="3 questions, mostly good answers.",
        ),
    }
    client.messages.parse.side_effect = lambda **kw: respond(outputs[kw["output_format"]])
    client._outputs = outputs
    app.dependency_overrides[get_anthropic_client] = lambda: client
    return client


@pytest.fixture
def topic(client, mock_anthropic, logged_in_user) -> dict:
    resp = client.post(
        "/api/topics",
        files={"file": ("ch8.pdf", PDF_BYTES, "application/pdf")},
        data={"name": "Photosynthesis", "description": ""},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def start(client, topic_id, num_questions=3):
    return client.post(f"/api/topics/{topic_id}/quiz/start", json={"num_questions": num_questions})


def answer(client, topic_id, text="Red and blue light"):
    return client.post(f"/api/topics/{topic_id}/quiz/answer", json={"answer": text})


class TestStart:
    def test_unauthenticated_401(self, client, mock_anthropic):
        assert start(client, "t_whatever").status_code == 401

    def test_starts_session_with_first_question(self, client, topic):
        resp = start(client, topic["id"])
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["question"] == "What does chlorophyll absorb?"
        assert body["question_number"] == 1
        assert body["total_questions"] == 3
        assert body["session_id"].startswith("q_")

        detail = client.get(f"/api/topics/{topic['id']}").json()
        session = detail["active_session"]
        assert session["status"] == "awaiting_answer"
        assert len(session["questions"]) == 1
        [summary] = client.get("/api/topics").json()
        assert summary["has_active_session"] is True

    def test_question_prompt_includes_notes_and_memory(self, client, topic, mock_anthropic):
        start(client, topic["id"])
        kwargs = mock_anthropic.messages.parse.call_args.kwargs
        assert kwargs["output_format"] is QuizQuestion
        user_text = kwargs["messages"][0]["content"]
        assert NOTES_MD in user_text

    def test_num_questions_bounds_422(self, client, topic):
        assert start(client, topic["id"], num_questions=0).status_code == 422
        assert start(client, topic["id"], num_questions=26).status_code == 422

    def test_start_replaces_existing_session(self, client, topic):
        first = start(client, topic["id"]).json()["session_id"]
        second = start(client, topic["id"], num_questions=5).json()
        assert second["session_id"] != first
        detail = client.get(f"/api/topics/{topic['id']}").json()
        assert detail["active_session"]["total_questions"] == 5
        assert len(detail["active_session"]["questions"]) == 1

    def test_missing_topic_404(self, client, logged_in_user, mock_anthropic):
        assert start(client, "t_missing").status_code == 404

    def test_api_error_maps_to_502_and_no_session(self, client, topic, mock_anthropic):
        mock_anthropic.messages.parse.side_effect = anthropic.APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )
        assert start(client, topic["id"]).status_code == 502
        assert client.get(f"/api/topics/{topic['id']}").json()["active_session"] is None


class TestAnswer:
    def test_grades_answer(self, client, topic):
        start(client, topic["id"])
        resp = answer(client, topic["id"])
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["grade"] == "good"
        assert body["feedback"] == "Exactly right."
        assert body["question_number"] == 1
        assert body["is_last"] is False

        session = client.get(f"/api/topics/{topic['id']}").json()["active_session"]
        assert session["status"] == "awaiting_next"
        assert session["questions"][0]["answer"] == "Red and blue light"
        assert session["questions"][0]["grade"] == "good"

    def test_grading_prompt_includes_question_and_answer(self, client, topic, mock_anthropic):
        start(client, topic["id"])
        answer(client, topic["id"], "My answer text")
        kwargs = mock_anthropic.messages.parse.call_args.kwargs
        assert kwargs["output_format"] is AnswerGrade
        user_text = kwargs["messages"][0]["content"]
        assert "What does chlorophyll absorb?" in user_text
        assert "My answer text" in user_text

    def test_is_last_on_final_question(self, client, topic):
        start(client, topic["id"], num_questions=1)
        assert answer(client, topic["id"]).json()["is_last"] is True

    def test_answer_without_session_409(self, client, topic):
        assert answer(client, topic["id"]).status_code == 409

    def test_answer_twice_409(self, client, topic):
        start(client, topic["id"])
        answer(client, topic["id"])
        assert answer(client, topic["id"]).status_code == 409

    def test_empty_answer_422(self, client, topic):
        start(client, topic["id"])
        assert answer(client, topic["id"], "").status_code == 422


class TestNext:
    def test_generates_next_question(self, client, topic):
        start(client, topic["id"])
        answer(client, topic["id"])
        resp = client.post(f"/api/topics/{topic['id']}/quiz/next")
        assert resp.status_code == 200, resp.text
        assert resp.json()["question_number"] == 2
        session = client.get(f"/api/topics/{topic['id']}").json()["active_session"]
        assert session["status"] == "awaiting_answer"
        assert len(session["questions"]) == 2

    def test_next_prompt_includes_prior_qa(self, client, topic, mock_anthropic):
        start(client, topic["id"])
        answer(client, topic["id"], "Red and blue light")
        client.post(f"/api/topics/{topic['id']}/quiz/next")
        kwargs = mock_anthropic.messages.parse.call_args.kwargs
        user_text = kwargs["messages"][0]["content"]
        assert "What does chlorophyll absorb?" in user_text
        assert "Red and blue light" in user_text

    def test_next_while_awaiting_answer_409(self, client, topic):
        start(client, topic["id"])
        assert client.post(f"/api/topics/{topic['id']}/quiz/next").status_code == 409

    def test_next_after_last_question_409(self, client, topic):
        start(client, topic["id"], num_questions=1)
        answer(client, topic["id"])
        assert client.post(f"/api/topics/{topic['id']}/quiz/next").status_code == 409


class TestDispute:
    def dispute(self, client, topic_id, message="You misread my answer"):
        return client.post(f"/api/topics/{topic_id}/quiz/dispute", json={"message": message})

    def test_revised_grade_is_stored(self, client, topic, mock_anthropic):
        mock_anthropic._outputs[AnswerGrade] = AnswerGrade(grade="bad", feedback="Wrong.")
        start(client, topic["id"])
        answer(client, topic["id"])
        resp = self.dispute(client, topic["id"])
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "revised"
        assert body["grade"] == "good"
        assert body["reply"] == "Fair point — your phrasing was fine."
        assert body["notes_updated"] is False

        session = client.get(f"/api/topics/{topic['id']}").json()["active_session"]
        entry = session["questions"][0]
        assert entry["grade"] == "good"
        assert entry["disputes"][0]["message"] == "You misread my answer"

    def test_upheld_keeps_grade(self, client, topic, mock_anthropic):
        mock_anthropic._outputs[AnswerGrade] = AnswerGrade(grade="ok", feedback="Partial.")
        mock_anthropic._outputs[DisputeVerdict] = DisputeVerdict(
            verdict="upheld", revised_grade=None, reply="The grade stands.", correction_note=None
        )
        start(client, topic["id"])
        answer(client, topic["id"])
        body = self.dispute(client, topic["id"]).json()
        assert body["verdict"] == "upheld"
        assert body["grade"] == "ok"
        session = client.get(f"/api/topics/{topic['id']}").json()["active_session"]
        assert session["questions"][0]["grade"] == "ok"

    def test_correction_note_edits_notes_doc(self, client, topic, mock_anthropic):
        mock_anthropic._outputs[DisputeVerdict] = DisputeVerdict(
            verdict="revised",
            revised_grade="good",
            reply="The notes were ambiguous there.",
            correction_note="Chlorophyll a and b absorb slightly different wavelengths.",
        )
        start(client, topic["id"])
        answer(client, topic["id"])
        body = self.dispute(client, topic["id"]).json()
        assert body["notes_updated"] is True
        notes = client.get(f"/api/topics/{topic['id']}").json()["notes_md"]
        assert "Chlorophyll a and b absorb slightly different wavelengths." in notes
        assert NOTES_MD in notes  # original content untouched

    def test_dispute_while_awaiting_answer_409(self, client, topic):
        start(client, topic["id"])
        assert self.dispute(client, topic["id"]).status_code == 409

    def test_dispute_without_session_409(self, client, topic):
        assert self.dispute(client, topic["id"]).status_code == 409


class TestFinish:
    def finish(self, client, topic_id):
        return client.post(f"/api/topics/{topic_id}/quiz/finish")

    def run_full_session(self, client, topic_id, n=2):
        start(client, topic_id, num_questions=n)
        for _ in range(n - 1):
            answer(client, topic_id)
            client.post(f"/api/topics/{topic_id}/quiz/next")
        answer(client, topic_id)

    def test_finish_updates_score_and_memory(self, client, topic):
        self.run_full_session(client, topic["id"])
        resp = self.finish(client, topic["id"])
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["score_before"] == 0
        assert body["score_after"] == 64
        assert body["mastery_notes"].startswith("Solid on light absorption")
        assert body["grades"] == {"good": 2, "ok": 0, "bad": 0}

        detail = client.get(f"/api/topics/{topic['id']}").json()
        assert detail["mastery_score"] == 64
        assert detail["mastery_notes"].startswith("Solid on light absorption")
        assert detail["active_session"] is None
        [record] = detail["sessions"]
        assert record["score_before"] == 0
        assert record["score_after"] == 64
        assert record["questions_answered"] == 2
        assert record["summary"] == "3 questions, mostly good answers."

    def test_scoring_prompt_includes_transcript_and_prior_memory(
        self, client, topic, mock_anthropic
    ):
        client.post(f"/api/topics/{topic['id']}/quiz/start", json={"num_questions": 1})
        answer(client, topic["id"], "Red and blue light")
        self.finish(client, topic["id"])
        kwargs = mock_anthropic.messages.parse.call_args.kwargs
        assert kwargs["output_format"] is MasteryUpdate
        user_text = kwargs["messages"][0]["content"]
        assert "What does chlorophyll absorb?" in user_text
        assert "Red and blue light" in user_text

    def test_early_finish_allowed_after_one_answer(self, client, topic):
        start(client, topic["id"], num_questions=5)
        answer(client, topic["id"])
        assert self.finish(client, topic["id"]).status_code == 200
        detail = client.get(f"/api/topics/{topic['id']}").json()
        assert detail["sessions"][0]["questions_answered"] == 1

    def test_finish_with_no_answers_409(self, client, topic):
        start(client, topic["id"])
        assert self.finish(client, topic["id"]).status_code == 409

    def test_finish_without_session_409(self, client, topic):
        assert self.finish(client, topic["id"]).status_code == 409

    def test_score_can_decrease(self, client, topic, mock_anthropic):
        self.run_full_session(client, topic["id"])
        self.finish(client, topic["id"])
        mock_anthropic._outputs[MasteryUpdate] = MasteryUpdate(
            score=40, mastery_notes="Regressed.", session_summary="Rough session."
        )
        self.run_full_session(client, topic["id"])
        body = self.finish(client, topic["id"]).json()
        assert body["score_before"] == 64
        assert body["score_after"] == 40


class TestAbandon:
    def test_abandon_clears_session_without_scoring(self, client, topic):
        start(client, topic["id"])
        answer(client, topic["id"])
        assert client.delete(f"/api/topics/{topic['id']}/quiz").status_code == 204
        detail = client.get(f"/api/topics/{topic['id']}").json()
        assert detail["active_session"] is None
        assert detail["sessions"] == []
        assert detail["mastery_score"] == 0

    def test_abandon_without_session_is_noop(self, client, topic):
        assert client.delete(f"/api/topics/{topic['id']}/quiz").status_code == 204


class TestIsolation:
    def test_other_user_cannot_quiz_someone_elses_topic(self, client, app, topic):
        from fastapi.testclient import TestClient

        from tests.conftest import register_and_login

        other = TestClient(app)
        register_and_login(other, username="bob")
        assert start(other, topic["id"]).status_code == 404

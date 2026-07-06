"""Topic + quiz-session business logic. All functions stay within one user's namespace.

The quiz session is a small state machine stored inline on the topic dict
(``active_session``): ``awaiting_answer`` -> (answer graded) -> ``awaiting_next`` ->
(next question) -> ``awaiting_answer`` ... until finish/abandon clears it.
LLM calls live in ``app.quiz.agent``; this module only mutates and persists state.
"""

import secrets
from datetime import UTC, datetime
from typing import Any

from app.quiz.models import DisputeVerdict, MasteryUpdate
from app.storage import Storage

AWAITING_ANSWER = "awaiting_answer"
AWAITING_NEXT = "awaiting_next"

_CORRECTIONS_HEADING = "## Corrections & clarifications"


class TopicNotFoundError(Exception):
    pass


class QuizStateError(Exception):
    """The requested quiz action is invalid in the session's current state. -> HTTP 409"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _save(storage: Storage, user_id: str, topic: dict[str, Any]) -> None:
    topic["updated_at"] = _now_iso()
    storage.write_topic(user_id, topic)


# ---- CRUD ----


def create_topic(
    storage: Storage,
    user_id: str,
    *,
    name: str,
    description: str,
    instructions: str,
    source_filename: str,
    notes_md: str,
    pdf_bytes: bytes,
) -> dict[str, Any]:
    now = _now_iso()
    topic = {
        "id": _new_id("t"),
        "name": name,
        "description": description,
        "instructions": instructions,
        "created_at": now,
        "updated_at": now,
        "source_filename": source_filename,
        "notes_md": notes_md,
        "mastery_score": 0,
        "mastery_notes": "",
        "sessions": [],
        "active_session": None,
    }
    # PDF first: if it fails, no topic record exists; an orphaned PDF is harmless.
    storage.write_topic_pdf(user_id, topic["id"], pdf_bytes)
    storage.write_topic(user_id, topic)
    return topic


def get_topic(storage: Storage, user_id: str, topic_id: str) -> dict[str, Any]:
    # Legacy-field backfill (e.g. `instructions`) happens in Storage._normalize_topic.
    topic = storage.read_topic(user_id, topic_id)
    if topic is None:
        raise TopicNotFoundError(topic_id)
    return topic


def list_topic_summaries(storage: Storage, user_id: str) -> list[dict[str, Any]]:
    summaries = []
    for topic in storage.list_topics(user_id):
        keys = ("id", "name", "description", "created_at", "updated_at", "source_filename")
        summary = {k: topic[k] for k in keys}
        summary["mastery_score"] = topic["mastery_score"]
        summary["session_count"] = len(topic["sessions"])
        summary["has_active_session"] = topic["active_session"] is not None
        summaries.append(summary)
    return summaries


def update_topic(
    storage: Storage,
    user_id: str,
    topic_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    instructions: str | None = None,
) -> dict[str, Any]:
    topic = get_topic(storage, user_id, topic_id)
    if name is not None:
        topic["name"] = name
    if description is not None:
        topic["description"] = description
    if instructions is not None:
        topic["instructions"] = instructions
    _save(storage, user_id, topic)
    return topic


def delete_topic(storage: Storage, user_id: str, topic_id: str) -> None:
    if not storage.delete_topic(user_id, topic_id):
        raise TopicNotFoundError(topic_id)


# ---- quiz session state machine ----


def _active_session(topic: dict[str, Any]) -> dict[str, Any]:
    session = topic["active_session"]
    if session is None:
        raise QuizStateError("No quiz session is in progress")
    return session


def _require_status(topic: dict[str, Any], status: str) -> dict[str, Any]:
    session = _active_session(topic)
    if session["status"] != status:
        raise QuizStateError(f"Session is {session['status']}, expected {status}")
    return session


def verify_binding(
    topic: dict[str, Any], *, session_id: str | None, question_number: int | None
) -> None:
    """Reject writes from a stale client (another tab/device moved the session on)."""
    session = _active_session(topic)
    if session_id is not None and session_id != session["id"]:
        raise QuizStateError("That quiz session is no longer active")
    if question_number is not None and question_number != len(session["questions"]):
        raise QuizStateError("The session has moved past that question")


def begin_session(
    topic: dict[str, Any], *, total_questions: int, replace: bool = False
) -> dict[str, Any]:
    """Attach a fresh (unpersisted) session. Refuses to clobber one in progress
    unless ``replace`` is set."""
    if topic["active_session"] is not None and not replace:
        raise QuizStateError("A quiz session is already in progress for this topic")
    session = {
        "id": _new_id("q"),
        "started_at": _now_iso(),
        "total_questions": total_questions,
        "status": AWAITING_ANSWER,
        "questions": [],
    }
    topic["active_session"] = session
    return session


def add_question(storage: Storage, user_id: str, topic: dict[str, Any], *, question: str) -> int:
    """Append the next question and persist. Returns the 1-based question number."""
    session = _active_session(topic)
    if len(session["questions"]) >= session["total_questions"]:
        raise QuizStateError("All questions have been asked")
    session["questions"].append(
        {"question": question, "answer": None, "grade": None, "feedback": None, "disputes": []}
    )
    session["status"] = AWAITING_ANSWER
    _save(storage, user_id, topic)
    return len(session["questions"])


def require_next_allowed(topic: dict[str, Any]) -> None:
    session = _require_status(topic, AWAITING_NEXT)
    if len(session["questions"]) >= session["total_questions"]:
        raise QuizStateError("The session is complete — finish it to get your score")


def current_question(topic: dict[str, Any]) -> dict[str, Any]:
    session = _require_status(topic, AWAITING_ANSWER)
    if not session["questions"]:
        raise QuizStateError("No question has been asked yet")
    return session["questions"][-1]


def record_answer(
    storage: Storage,
    user_id: str,
    topic: dict[str, Any],
    *,
    answer: str,
    grade: str,
    feedback: str,
) -> tuple[int, bool]:
    """Store the graded answer. Returns (question_number, is_last)."""
    session = _require_status(topic, AWAITING_ANSWER)
    entry = session["questions"][-1]
    entry["answer"] = answer
    entry["grade"] = grade
    entry["feedback"] = feedback
    session["status"] = AWAITING_NEXT
    _save(storage, user_id, topic)
    return len(session["questions"]), len(session["questions"]) >= session["total_questions"]


def latest_graded(topic: dict[str, Any]) -> dict[str, Any]:
    session = _require_status(topic, AWAITING_NEXT)
    return session["questions"][-1]


_GRADE_ORDER = {"bad": 0, "ok": 1, "good": 2}


def record_dispute(
    storage: Storage,
    user_id: str,
    topic: dict[str, Any],
    *,
    message: str,
    verdict: DisputeVerdict,
) -> tuple[str, str, bool]:
    """Apply a dispute ruling to the latest graded question.

    A "revised" verdict only counts if it actually raises the grade — a dispute may
    never lower one, and a revision that names no (or the same) grade is reported as
    upheld so the user is never told their grade changed when it didn't.

    Returns (effective_verdict, final_grade, notes_updated).
    """
    entry = latest_graded(topic)
    effective_verdict = verdict.verdict
    if effective_verdict == "revised":
        revised = verdict.revised_grade
        if revised is not None and _GRADE_ORDER[revised] > _GRADE_ORDER[entry["grade"]]:
            entry["grade"] = revised
        else:
            effective_verdict = "upheld"
    entry["disputes"].append(
        {"message": message, "verdict": effective_verdict, "reply": verdict.reply}
    )
    notes_updated = False
    if verdict.correction_note:
        topic["notes_md"] = _append_correction(topic["notes_md"], verdict.correction_note)
        notes_updated = True
    _save(storage, user_id, topic)
    return effective_verdict, entry["grade"], notes_updated


def _append_correction(notes_md: str, correction: str) -> str:
    if _CORRECTIONS_HEADING not in notes_md:
        notes_md = f"{notes_md.rstrip()}\n\n{_CORRECTIONS_HEADING}\n"
    return f"{notes_md.rstrip()}\n\n- {correction.strip()}"


def grade_counts(session: dict[str, Any]) -> dict[str, int]:
    counts = {"good": 0, "ok": 0, "bad": 0}
    for entry in session["questions"]:
        if entry["grade"] is not None:
            counts[entry["grade"]] += 1
    return counts


def answered_count(session: dict[str, Any]) -> int:
    return sum(1 for entry in session["questions"] if entry["answer"] is not None)


def require_finishable(topic: dict[str, Any]) -> dict[str, Any]:
    session = _active_session(topic)
    if answered_count(session) == 0:
        raise QuizStateError("Answer at least one question before finishing")
    return session


def finish_session(
    storage: Storage, user_id: str, topic: dict[str, Any], *, update: MasteryUpdate
) -> dict[str, Any]:
    """Archive the active session with the agent's mastery update. Returns the record."""
    session = require_finishable(topic)
    record = {
        "id": session["id"],
        "started_at": session["started_at"],
        "completed_at": _now_iso(),
        "total_questions": session["total_questions"],
        "questions_answered": answered_count(session),
        "grades": grade_counts(session),
        "score_before": topic["mastery_score"],
        "score_after": update.score,
        "summary": update.session_summary,
    }
    topic["sessions"].append(record)
    topic["mastery_score"] = update.score
    topic["mastery_notes"] = update.mastery_notes
    topic["active_session"] = None
    _save(storage, user_id, topic)
    return record


def abandon_session(storage: Storage, user_id: str, topic: dict[str, Any]) -> None:
    if topic["active_session"] is None:
        return
    topic["active_session"] = None
    _save(storage, user_id, topic)

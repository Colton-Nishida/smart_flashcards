"""Quiz session routes: /api/topics/{topic_id}/quiz/*.

Each route loads the topic, runs at most one LLM call, applies the state
transition, and persists — the session state machine itself lives in
``app.topics.service``.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import CurrentUser
from app.config import Settings
from app.deps import get_settings, get_storage
from app.generation.deps import AnthropicClient
from app.quiz import agent
from app.storage import Storage, StorageIdError
from app.topics import service
from app.topics.errors import llm_errors
from app.topics.models import (
    QuizAnswer,
    QuizAnswerOut,
    QuizDispute,
    QuizDisputeOut,
    QuizFinishOut,
    QuizQuestionOut,
    QuizStart,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/topics/{topic_id}/quiz", tags=["quiz"])

StorageDep = Annotated[Storage, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _load_topic(storage: Storage, user_id: str, topic_id: str) -> dict:
    try:
        return service.get_topic(storage, user_id, topic_id)
    except (service.TopicNotFoundError, StorageIdError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Topic not found") from None


def _409(exc: service.QuizStateError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/start", response_model=QuizQuestionOut, status_code=status.HTTP_201_CREATED)
def start_quiz(
    topic_id: str,
    body: QuizStart,
    user: CurrentUser,
    storage: StorageDep,
    settings: SettingsDep,
    client: AnthropicClient,
) -> QuizQuestionOut:
    """Begin a session (replacing any in progress) and ask the first question."""
    topic = _load_topic(storage, user["id"], topic_id)
    session = service.begin_session(topic, total_questions=body.num_questions)
    with llm_errors("question generation"):
        question = agent.generate_question(client, topic=topic, model=settings.anthropic_model)
    number = service.add_question(storage, user["id"], topic, question=question.question)
    return QuizQuestionOut(
        session_id=session["id"],
        question=question.question,
        question_number=number,
        total_questions=body.num_questions,
    )


@router.post("/answer", response_model=QuizAnswerOut)
def answer_question(
    topic_id: str,
    body: QuizAnswer,
    user: CurrentUser,
    storage: StorageDep,
    settings: SettingsDep,
    client: AnthropicClient,
) -> QuizAnswerOut:
    topic = _load_topic(storage, user["id"], topic_id)
    try:
        entry = service.current_question(topic)
    except service.QuizStateError as exc:
        raise _409(exc) from None
    with llm_errors("answer grading"):
        graded = agent.grade_answer(
            client,
            topic=topic,
            question=entry["question"],
            answer=body.answer,
            model=settings.anthropic_model,
        )
    number, is_last = service.record_answer(
        storage,
        user["id"],
        topic,
        answer=body.answer,
        grade=graded.grade,
        feedback=graded.feedback,
    )
    return QuizAnswerOut(
        grade=graded.grade, feedback=graded.feedback, question_number=number, is_last=is_last
    )


@router.post("/next", response_model=QuizQuestionOut)
def next_question(
    topic_id: str,
    user: CurrentUser,
    storage: StorageDep,
    settings: SettingsDep,
    client: AnthropicClient,
) -> QuizQuestionOut:
    topic = _load_topic(storage, user["id"], topic_id)
    try:
        service.require_next_allowed(topic)
    except service.QuizStateError as exc:
        raise _409(exc) from None
    with llm_errors("question generation"):
        question = agent.generate_question(client, topic=topic, model=settings.anthropic_model)
    number = service.add_question(storage, user["id"], topic, question=question.question)
    session = topic["active_session"]
    return QuizQuestionOut(
        session_id=session["id"],
        question=question.question,
        question_number=number,
        total_questions=session["total_questions"],
    )


@router.post("/dispute", response_model=QuizDisputeOut)
def dispute_grade(
    topic_id: str,
    body: QuizDispute,
    user: CurrentUser,
    storage: StorageDep,
    settings: SettingsDep,
    client: AnthropicClient,
) -> QuizDisputeOut:
    """The user pushes back on the latest grade; the agent rules and takes notes."""
    topic = _load_topic(storage, user["id"], topic_id)
    try:
        entry = service.latest_graded(topic)
    except service.QuizStateError as exc:
        raise _409(exc) from None
    with llm_errors("dispute evaluation"):
        verdict = agent.evaluate_dispute(
            client, topic=topic, entry=entry, message=body.message, model=settings.anthropic_model
        )
    final_grade, notes_updated = service.record_dispute(
        storage, user["id"], topic, message=body.message, verdict=verdict
    )
    return QuizDisputeOut(
        verdict=verdict.verdict, grade=final_grade, reply=verdict.reply, notes_updated=notes_updated
    )


@router.post("/finish", response_model=QuizFinishOut)
def finish_quiz(
    topic_id: str,
    user: CurrentUser,
    storage: StorageDep,
    settings: SettingsDep,
    client: AnthropicClient,
) -> QuizFinishOut:
    """Score the session: update the mastery bar + memory, archive the session."""
    topic = _load_topic(storage, user["id"], topic_id)
    try:
        service.require_finishable(topic)
    except service.QuizStateError as exc:
        raise _409(exc) from None
    with llm_errors("session scoring"):
        update = agent.score_session(client, topic=topic, model=settings.anthropic_model)
    record = service.finish_session(storage, user["id"], topic, update=update)
    return QuizFinishOut(
        score_before=record["score_before"],
        score_after=record["score_after"],
        mastery_notes=update.mastery_notes,
        summary=update.session_summary,
        grades=record["grades"],
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def abandon_quiz(topic_id: str, user: CurrentUser, storage: StorageDep) -> None:
    """Drop the active session without scoring. Idempotent."""
    topic = _load_topic(storage, user["id"], topic_id)
    service.abandon_session(storage, user["id"], topic)

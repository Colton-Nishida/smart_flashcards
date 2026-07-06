"""Request/response schemas for topics and quiz sessions."""

from typing import Literal

from pydantic import BaseModel, Field

from app.quiz.models import Grade


class Dispute(BaseModel):
    message: str
    verdict: Literal["upheld", "revised"]
    reply: str


class SessionQuestion(BaseModel):
    question: str
    answer: str | None = None
    grade: Grade | None = None
    feedback: str | None = None
    disputes: list[Dispute] = []


class ActiveSession(BaseModel):
    id: str
    started_at: str
    total_questions: int
    status: Literal["awaiting_answer", "awaiting_next"]
    questions: list[SessionQuestion]


class SessionRecord(BaseModel):
    id: str
    started_at: str
    completed_at: str
    total_questions: int
    questions_answered: int
    grades: dict[str, int]
    score_before: int
    score_after: int
    summary: str


class Topic(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    source_filename: str
    instructions: str = ""
    """User's standing guidance to the tutor (focus areas, question style). Defaults
    for topics stored before the field existed."""
    notes_md: str
    mastery_score: int
    mastery_notes: str
    sessions: list[SessionRecord]
    active_session: ActiveSession | None


class TopicSummary(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    source_filename: str
    mastery_score: int
    session_count: int
    has_active_session: bool


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=4000)


# ---- quiz request/response bodies ----


class QuizStart(BaseModel):
    num_questions: int = Field(ge=1, le=25)
    replace: bool = False
    """Explicit consent to discard an in-progress session (otherwise 409)."""


class _SessionBound(BaseModel):
    """Optional optimistic-concurrency binding: when present, the write is rejected
    if another tab/device has moved the session past this point."""

    session_id: str | None = None
    question_number: int | None = Field(default=None, ge=1)


class QuizAnswer(_SessionBound):
    answer: str = Field(min_length=1, max_length=5000)


class QuizDispute(_SessionBound):
    message: str = Field(min_length=1, max_length=5000)


class QuizQuestionOut(BaseModel):
    session_id: str
    question: str
    question_number: int
    total_questions: int


class QuizAnswerOut(BaseModel):
    grade: Grade
    feedback: str
    question_number: int
    is_last: bool


class QuizDisputeOut(BaseModel):
    verdict: Literal["upheld", "revised"]
    grade: Grade
    reply: str
    notes_updated: bool


class QuizFinishOut(BaseModel):
    score_before: int
    score_after: int
    mastery_notes: str
    summary: str
    grades: dict[str, int]

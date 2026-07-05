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


# ---- quiz request/response bodies ----


class QuizStart(BaseModel):
    num_questions: int = Field(ge=1, le=25)


class QuizAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)


class QuizDispute(BaseModel):
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

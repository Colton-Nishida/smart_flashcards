"""Structured-output schemas for the quiz agent's Anthropic calls."""

from typing import Literal

from pydantic import BaseModel, Field

Grade = Literal["good", "ok", "bad"]


class TopicNotes(BaseModel):
    """Extraction call: the PDF distilled into a studyable markdown notes document."""

    notes_md: str


class QuizQuestion(BaseModel):
    question: str


class AnswerGrade(BaseModel):
    grade: Grade
    feedback: str


class DisputeVerdict(BaseModel):
    """Ruling on a user's objection to a grade or question.

    ``correction_note`` is a self-contained correction appended to the topic's notes doc
    when the dispute revealed the notes themselves were wrong or ambiguous.
    """

    verdict: Literal["upheld", "revised"]
    revised_grade: Grade | None = None
    reply: str
    correction_note: str | None = None


class MasteryUpdate(BaseModel):
    """End-of-session scoring: new 0-100 mastery score plus the memory explaining it."""

    score: int = Field(ge=0, le=100)
    mastery_notes: str
    session_summary: str

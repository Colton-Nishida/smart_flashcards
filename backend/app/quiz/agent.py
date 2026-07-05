"""Quiz agent: each step of the Q/A loop is a single Anthropic structured-output call.

No agent loop — session state lives in the topic JSON, and every call gets the
context it needs (notes doc, mastery memory, session transcript) rebuilt as text.
"""

import base64
import logging
from pathlib import Path
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.generation.errors import DocumentTooLargeError, MalformedGenerationError
from app.generation.service import _is_truncated_json
from app.quiz.models import (
    AnswerGrade,
    DisputeVerdict,
    MasteryUpdate,
    QuizQuestion,
    TopicNotes,
)

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

# The notes doc for a whole PDF can be long; quiz turns are small. 21000 is the
# largest max_tokens the SDK allows on a non-streaming call (see generation.service).
_EXTRACTION_MAX_TOKENS = 21000
_TURN_MAX_TOKENS = 4000

T = TypeVar("T", bound=BaseModel)


def load_skill_prompt(name: str) -> str:
    """Quiz prompts are versioned markdown skill files, same as flashcard generation."""
    return (_SKILLS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _parse(
    client: anthropic.Anthropic,
    *,
    model: str,
    skill: str,
    content: Any,
    output_format: type[T],
    max_tokens: int = _TURN_MAX_TOKENS,
    truncation_error: type[Exception] = MalformedGenerationError,
) -> T:
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=load_skill_prompt(skill),
            messages=[{"role": "user", "content": content}],
            output_format=output_format,
        )
    except ValidationError as exc:
        if _is_truncated_json(exc):
            logger.warning("Quiz call truncated at %d tokens: skill=%s", max_tokens, skill)
            raise truncation_error("The response overflowed the output limit.") from exc
        logger.exception("Quiz call failed schema validation: skill=%s", skill)
        raise MalformedGenerationError("Model returned malformed quiz data") from exc
    if response.stop_reason == "max_tokens":
        logger.warning("Quiz call stopped at max_tokens: skill=%s", skill)
        raise truncation_error("The response overflowed the output limit.")
    return response.parsed_output


def _transcript(session: dict[str, Any]) -> str:
    """The session so far, rendered for the model."""
    lines = []
    for i, entry in enumerate(session["questions"], start=1):
        lines.append(f"Question {i}: {entry['question']}")
        if entry.get("answer") is not None:
            lines.append(f"Student's answer: {entry['answer']}")
            lines.append(f"Grade: {entry['grade']} — {entry['feedback']}")
        for dispute in entry.get("disputes", []):
            lines.append(f"Student disputed: {dispute['message']}")
            lines.append(f"Ruling ({dispute['verdict']}): {dispute['reply']}")
    return "\n".join(lines) if lines else "(no questions asked yet)"


def _topic_context(topic: dict[str, Any]) -> str:
    memory = topic["mastery_notes"] or "(no history yet — this is a new topic for the student)"
    return (
        f"# Topic: {topic['name']}\n\n"
        f"## Study notes\n\n{topic['notes_md']}\n\n"
        f"## Mastery memory (current score {topic['mastery_score']}/100)\n\n{memory}"
    )


def extract_topic_notes(
    client: anthropic.Anthropic,
    *,
    pdf_bytes: bytes,
    topic_name: str,
    description: str,
    model: str,
) -> TopicNotes:
    """Distill the uploaded PDF into the markdown notes doc the quiz runs off."""
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    logger.info(
        "Extracting topic notes: model=%s pdf_bytes=%d topic=%r", model, len(pdf_bytes), topic_name
    )
    return _parse(
        client,
        model=model,
        skill="topic_notes_extraction",
        content=[
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_b64,
                },
            },
            {
                "type": "text",
                "text": (
                    f"Extract study notes for a topic named '{topic_name}'. "
                    f"User's description: {description or '(none)'}"
                ),
            },
        ],
        output_format=TopicNotes,
        max_tokens=_EXTRACTION_MAX_TOKENS,
        truncation_error=DocumentTooLargeError,
    )


def generate_question(
    client: anthropic.Anthropic, *, topic: dict[str, Any], model: str
) -> QuizQuestion:
    session = topic["active_session"]
    number = len(session["questions"]) + 1
    content = (
        f"{_topic_context(topic)}\n\n"
        f"## Session so far\n\n{_transcript(session)}\n\n"
        f"Ask question {number} of {session['total_questions']}."
    )
    return _parse(
        client, model=model, skill="quiz_question", content=content, output_format=QuizQuestion
    )


def grade_answer(
    client: anthropic.Anthropic, *, topic: dict[str, Any], question: str, answer: str, model: str
) -> AnswerGrade:
    content = (
        f"{_topic_context(topic)}\n\n"
        f"## To grade\n\n"
        f"Question: {question}\n"
        f"Student's answer: {answer}"
    )
    return _parse(
        client, model=model, skill="quiz_grading", content=content, output_format=AnswerGrade
    )


def evaluate_dispute(
    client: anthropic.Anthropic,
    *,
    topic: dict[str, Any],
    entry: dict[str, Any],
    message: str,
    model: str,
) -> DisputeVerdict:
    content = (
        f"{_topic_context(topic)}\n\n"
        f"## Disputed exchange\n\n"
        f"Question: {entry['question']}\n"
        f"Student's answer: {entry['answer']}\n"
        f"Grade given: {entry['grade']} — {entry['feedback']}\n\n"
        f"## Student's objection\n\n{message}"
    )
    return _parse(
        client, model=model, skill="quiz_dispute", content=content, output_format=DisputeVerdict
    )


def score_session(
    client: anthropic.Anthropic, *, topic: dict[str, Any], model: str
) -> MasteryUpdate:
    session = topic["active_session"]
    content = (
        f"{_topic_context(topic)}\n\n"
        f"## Completed session transcript "
        f"({session['total_questions']} questions planned)\n\n"
        f"{_transcript(session)}"
    )
    return _parse(
        client, model=model, skill="quiz_scoring", content=content, output_format=MasteryUpdate
    )

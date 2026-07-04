"""PDF -> flashcards via a single Anthropic structured-output call."""

import base64
import logging
from pathlib import Path

import anthropic
from pydantic import ValidationError

from app.generation.errors import (
    DocumentTooLargeError,
    InvalidPdfError,
    MalformedGenerationError,
    PdfTooLargeError,
)
from app.generation.models import FlashcardDeck

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 20 * 1024 * 1024  # practical cap, well under the 32 MB API limit
_PDF_MAGIC = b"%PDF-"
_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "flashcard_generation.md"
# Output-token budget for one generation call. Above ~21k the SDK refuses a non-streaming
# request unless an explicit per-request timeout is given (its default guard estimates the
# response could exceed 10 min). We pass _REQUEST_TIMEOUT_SECONDS below to opt in. Going to
# the model's 128k ceiling would instead require switching to a streaming call.
_MAX_OUTPUT_TOKENS = 32000
# Explicit per-request timeout — also disables the SDK's non-streaming max_tokens guard.
_REQUEST_TIMEOUT_SECONDS = 300.0


def _is_truncated_json(exc: ValidationError) -> bool:
    """True when the response body was incomplete JSON (output overflowed the token cap),
    as opposed to well-formed JSON that failed schema validation."""
    return any(err.get("type") == "json_invalid" for err in exc.errors())


def validate_pdf(data: bytes) -> None:
    """Reject non-PDF payloads (magic bytes) and files over the size cap."""
    if not data.startswith(_PDF_MAGIC):
        raise InvalidPdfError("File is not a PDF")
    if len(data) > MAX_PDF_BYTES:
        raise PdfTooLargeError(f"PDF exceeds the {MAX_PDF_BYTES // (1024 * 1024)} MB limit")


def load_skill_prompt() -> str:
    """The generation system prompt lives in a versioned markdown skill file."""
    return _SKILL_PATH.read_text(encoding="utf-8")


def generate_flashcards(
    client: anthropic.Anthropic,
    *,
    pdf_bytes: bytes,
    deck_name: str,
    description: str,
    model: str,
) -> FlashcardDeck:
    """Send the PDF natively as a document block; parse guaranteed-valid card JSON."""
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    logger.info(
        "Generating flashcards: model=%s pdf_bytes=%d deck=%r", model, len(pdf_bytes), deck_name
    )
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=_MAX_OUTPUT_TOKENS,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            system=load_skill_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": [
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
                                f"Create flashcards for a deck named '{deck_name}'. "
                                f"User's description of what they want: {description or '(none)'}"
                            ),
                        },
                    ],
                }
            ],
            output_format=FlashcardDeck,
        )
    except ValidationError as exc:
        # messages.parse() validates the response body and raises here BEFORE returning,
        # so we can't inspect stop_reason. Truncated JSON == output overflowed the token cap.
        if _is_truncated_json(exc):
            logger.warning(
                "Generation output was truncated (hit the %d-token cap): "
                "deck=%r pdf_bytes=%d — treating as document-too-large",
                _MAX_OUTPUT_TOKENS,
                deck_name,
                len(pdf_bytes),
            )
            raise DocumentTooLargeError(
                "The document produced more cards than fit in one response; it is too large."
            ) from exc
        logger.exception("Generation output failed schema validation: deck=%r", deck_name)
        raise MalformedGenerationError("Model returned malformed flashcard data") from exc

    if response.stop_reason == "max_tokens":
        logger.warning(
            "Generation stopped at max_tokens: deck=%r pdf_bytes=%d", deck_name, len(pdf_bytes)
        )
        raise DocumentTooLargeError(
            "The document produced more cards than fit in one response; it is too large."
        )
    deck = response.parsed_output
    logger.info("Generated %d cards: deck=%r", len(deck.cards), deck_name)
    return deck

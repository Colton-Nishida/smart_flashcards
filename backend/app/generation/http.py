"""Shared HTTP mapping for LLM-call failures (used by the topic and quiz routes)."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import anthropic
from fastapi import HTTPException, status

from app.generation.errors import DocumentTooLargeError, MalformedGenerationError

logger = logging.getLogger(__name__)


@contextmanager
def llm_errors(action: str) -> Iterator[None]:
    """Map LLM failures to HTTP: overflow -> 413, API/malformed -> 502."""
    try:
        yield
    except DocumentTooLargeError:
        logger.info("LLM output overflowed during %s", action)
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="That document is too large to process in one pass. "
            "Try a shorter PDF or split it into sections.",
        ) from None
    except (anthropic.APIError, MalformedGenerationError):
        logger.exception("LLM call failed during %s", action)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"The {action} call failed; please retry"
        ) from None

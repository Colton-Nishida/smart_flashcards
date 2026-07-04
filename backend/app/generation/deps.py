"""Anthropic client dependency (override in tests to avoid live API calls)."""

from typing import Annotated

import anthropic
from fastapi import Depends, HTTPException

from app.config import Settings
from app.deps import get_settings


def get_anthropic_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Flashcard generation is not configured: set ANTHROPIC_API_KEY on the server.",
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


AnthropicClient = Annotated[anthropic.Anthropic, Depends(get_anthropic_client)]

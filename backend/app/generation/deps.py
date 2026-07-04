"""Anthropic client dependency (override in tests to avoid live API calls)."""

from typing import Annotated

import anthropic
from fastapi import Depends

from app.config import Settings
from app.deps import get_settings


def get_anthropic_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


AnthropicClient = Annotated[anthropic.Anthropic, Depends(get_anthropic_client)]

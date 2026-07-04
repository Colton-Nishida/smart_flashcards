"""Structured-output schema for flashcard generation."""

from pydantic import BaseModel


class Flashcard(BaseModel):
    front: str
    back: str
    tags: list[str] = []


class FlashcardDeck(BaseModel):
    cards: list[Flashcard]

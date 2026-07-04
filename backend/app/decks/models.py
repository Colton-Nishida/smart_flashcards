"""Request/response schemas for decks and cards."""

from pydantic import BaseModel, Field


class Card(BaseModel):
    id: str
    front: str
    back: str
    tags: list[str] = []


class CardCreate(BaseModel):
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    tags: list[str] = []


class CardUpdate(BaseModel):
    front: str | None = Field(default=None, min_length=1)
    back: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None


class Deck(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    source_filename: str
    # Generation-time guidance the user supplied (focus/scope). "" for decks made before
    # this field existed or when the user left it blank.
    additional_instructions: str = ""
    cards: list[Card]


class DeckSummary(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    source_filename: str
    card_count: int


class DeckUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

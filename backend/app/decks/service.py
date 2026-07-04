"""Deck business logic. Every function operates strictly within one user's namespace."""

import secrets
from datetime import UTC, datetime
from typing import Any

from app.storage import Storage


class DeckNotFoundError(Exception):
    pass


class CardNotFoundError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def create_deck(
    storage: Storage,
    user_id: str,
    *,
    name: str,
    description: str,
    source_filename: str,
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist a new deck. ``cards`` entries need front/back (+ optional tags)."""
    deck = {
        "id": _new_id("d"),
        "name": name,
        "description": description,
        "created_at": _now_iso(),
        "source_filename": source_filename,
        "cards": [
            {
                "id": _new_id("c"),
                "front": card["front"],
                "back": card["back"],
                "tags": card.get("tags", []),
            }
            for card in cards
        ],
    }
    storage.write_deck(user_id, deck)
    return deck


def get_deck(storage: Storage, user_id: str, deck_id: str) -> dict[str, Any]:
    deck = storage.read_deck(user_id, deck_id)
    if deck is None:
        raise DeckNotFoundError(deck_id)
    return deck


def list_deck_summaries(storage: Storage, user_id: str) -> list[dict[str, Any]]:
    summaries = []
    for deck in storage.list_decks(user_id):
        summary = {k: deck[k] for k in ("id", "name", "description", "created_at")}
        summary["source_filename"] = deck["source_filename"]
        summary["card_count"] = len(deck["cards"])
        summaries.append(summary)
    # storage.list_decks orders by filename (the random hex deck id), which is
    # arbitrary relative to creation time. Present decks newest-first instead.
    summaries.sort(key=lambda s: s["created_at"], reverse=True)
    return summaries


def update_deck(
    storage: Storage,
    user_id: str,
    deck_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    deck = get_deck(storage, user_id, deck_id)
    if name is not None:
        deck["name"] = name
    if description is not None:
        deck["description"] = description
    storage.write_deck(user_id, deck)
    return deck


def delete_deck(storage: Storage, user_id: str, deck_id: str) -> None:
    if not storage.delete_deck(user_id, deck_id):
        raise DeckNotFoundError(deck_id)


def add_card(
    storage: Storage,
    user_id: str,
    deck_id: str,
    *,
    front: str,
    back: str,
    tags: list[str],
) -> dict[str, Any]:
    deck = get_deck(storage, user_id, deck_id)
    card = {"id": _new_id("c"), "front": front, "back": back, "tags": tags}
    deck["cards"].append(card)
    storage.write_deck(user_id, deck)
    return card


def update_card(
    storage: Storage,
    user_id: str,
    deck_id: str,
    card_id: str,
    *,
    front: str | None = None,
    back: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    deck = get_deck(storage, user_id, deck_id)
    card = next((c for c in deck["cards"] if c["id"] == card_id), None)
    if card is None:
        raise CardNotFoundError(card_id)
    if front is not None:
        card["front"] = front
    if back is not None:
        card["back"] = back
    if tags is not None:
        card["tags"] = tags
    storage.write_deck(user_id, deck)
    return card


def delete_card(storage: Storage, user_id: str, deck_id: str, card_id: str) -> None:
    deck = get_deck(storage, user_id, deck_id)
    remaining = [c for c in deck["cards"] if c["id"] != card_id]
    if len(remaining) == len(deck["cards"]):
        raise CardNotFoundError(card_id)
    deck["cards"] = remaining
    storage.write_deck(user_id, deck)

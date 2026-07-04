"""Deck routes: /api/decks/*. Every route requires an authenticated user."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import CurrentUser
from app.decks import service
from app.decks.models import Card, CardCreate, CardUpdate, Deck, DeckSummary, DeckUpdate
from app.deps import get_storage
from app.storage import Storage, StorageIdError

router = APIRouter(prefix="/api/decks", tags=["decks"])

_NOT_FOUND = (service.DeckNotFoundError, service.CardNotFoundError, StorageIdError)

StorageDep = Annotated[Storage, Depends(get_storage)]


def _404(exc: Exception) -> HTTPException:
    kind = "Card" if isinstance(exc, service.CardNotFoundError) else "Deck"
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{kind} not found")


@router.get("", response_model=list[DeckSummary])
def list_decks(user: CurrentUser, storage: StorageDep) -> list[DeckSummary]:
    return [DeckSummary(**s) for s in service.list_deck_summaries(storage, user["id"])]


@router.get("/{deck_id}", response_model=Deck)
def get_deck(deck_id: str, user: CurrentUser, storage: StorageDep) -> Deck:
    try:
        return Deck(**service.get_deck(storage, user["id"], deck_id))
    except _NOT_FOUND as exc:
        raise _404(exc) from None


@router.patch("/{deck_id}", response_model=Deck)
def update_deck(deck_id: str, update: DeckUpdate, user: CurrentUser, storage: StorageDep) -> Deck:
    try:
        deck = service.update_deck(
            storage, user["id"], deck_id, name=update.name, description=update.description
        )
        return Deck(**deck)
    except _NOT_FOUND as exc:
        raise _404(exc) from None


@router.delete("/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deck(deck_id: str, user: CurrentUser, storage: StorageDep) -> None:
    try:
        service.delete_deck(storage, user["id"], deck_id)
    except _NOT_FOUND as exc:
        raise _404(exc) from None


@router.post("/{deck_id}/cards", response_model=Card, status_code=status.HTTP_201_CREATED)
def add_card(deck_id: str, card: CardCreate, user: CurrentUser, storage: StorageDep) -> Card:
    try:
        created = service.add_card(
            storage, user["id"], deck_id, front=card.front, back=card.back, tags=card.tags
        )
        return Card(**created)
    except _NOT_FOUND as exc:
        raise _404(exc) from None


@router.patch("/{deck_id}/cards/{card_id}", response_model=Card)
def update_card(
    deck_id: str, card_id: str, update: CardUpdate, user: CurrentUser, storage: StorageDep
) -> Card:
    try:
        card = service.update_card(
            storage,
            user["id"],
            deck_id,
            card_id,
            front=update.front,
            back=update.back,
            tags=update.tags,
        )
        return Card(**card)
    except _NOT_FOUND as exc:
        raise _404(exc) from None


@router.delete("/{deck_id}/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(deck_id: str, card_id: str, user: CurrentUser, storage: StorageDep) -> None:
    try:
        service.delete_card(storage, user["id"], deck_id, card_id)
    except _NOT_FOUND as exc:
        raise _404(exc) from None

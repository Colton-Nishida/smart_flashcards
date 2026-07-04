"""Optional live smoke test against the real Anthropic API.

Skipped unless RUN_LIVE_API_TESTS=1 (and ANTHROPIC_API_KEY is set in the env).
Every other test in the suite mocks the client — this is the only place a real
request can happen.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="live API smoke test; set RUN_LIVE_API_TESTS=1 to run",
)

MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
    b"4 0 obj<</Length 60>>stream\n"
    b"BT /F1 12 Tf 72 720 Td (Mitochondria make ATP for cells.) Tj ET\n"
    b"endstream endobj\n"
    b"trailer<</Root 1 0 R>>\n"
    b"%%EOF\n"
)


def test_live_generation_smoke():
    import anthropic

    from app.config import Settings
    from app.generation.service import generate_flashcards

    settings = Settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    deck = generate_flashcards(
        client,
        pdf_bytes=MINIMAL_PDF,
        deck_name="Live smoke",
        description="One or two cards about the single fact in this document.",
        model=settings.anthropic_model,
    )
    assert len(deck.cards) >= 1
    assert all(card.front and card.back for card in deck.cards)

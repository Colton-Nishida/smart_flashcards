"""Tests for app.generation — PDF validation + flashcard generation (mocked Anthropic client)."""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.generation.errors import (
    DocumentTooLargeError,
    GenerationError,
    InvalidPdfError,
    MalformedGenerationError,
    PdfTooLargeError,
)
from app.generation.models import Flashcard, FlashcardDeck
from app.generation.service import (
    MAX_PDF_BYTES,
    generate_flashcards,
    load_skill_prompt,
    validate_pdf,
)

PDF_BYTES = b"%PDF-1.4 fake pdf content"


class TestModels:
    def test_flashcard_tags_default_empty(self):
        card = Flashcard(front="Q", back="A")
        assert card.tags == []

    def test_flashcard_deck_holds_cards(self):
        deck = FlashcardDeck(cards=[Flashcard(front="Q", back="A", tags=["t"])])
        assert deck.cards[0].tags == ["t"]


class TestValidatePdf:
    def test_accepts_pdf_magic_bytes(self):
        validate_pdf(PDF_BYTES)  # must not raise

    @pytest.mark.parametrize("data", [b"", b"not a pdf", b"<html></html>", b"PDF-1.4 nope"])
    def test_rejects_non_pdf(self, data):
        with pytest.raises(InvalidPdfError):
            validate_pdf(data)

    def test_rejects_oversized_pdf(self):
        big = b"%PDF-" + b"0" * MAX_PDF_BYTES
        with pytest.raises(PdfTooLargeError):
            validate_pdf(big)

    def test_max_size_is_20mb(self):
        assert MAX_PDF_BYTES == 20 * 1024 * 1024


class TestSkillPrompt:
    def test_loads_skill_markdown(self):
        prompt = load_skill_prompt()
        assert "flashcard" in prompt.lower()
        assert "Atomic" in prompt  # anchored to the checked-in skill file

    def test_skill_forbids_outside_information(self):
        """The skill must keep generation strictly source-only (regression guard)."""
        prompt = load_skill_prompt().lower()
        assert "only source" in prompt
        assert "internet" in prompt
        assert "prior knowledge" in prompt


def _mock_client(stop_reason="end_turn", cards=None):
    if cards is None:
        cards = [Flashcard(front="Q1", back="A1", tags=["bio"])]
    client = MagicMock()
    client.messages.parse.return_value = SimpleNamespace(
        stop_reason=stop_reason,
        parsed_output=FlashcardDeck(cards=cards),
    )
    return client


class TestGenerateFlashcards:
    def test_returns_parsed_deck(self):
        client = _mock_client()
        deck = generate_flashcards(
            client,
            pdf_bytes=PDF_BYTES,
            deck_name="Bio",
            description="Cells",
            model="claude-sonnet-5",
        )
        assert isinstance(deck, FlashcardDeck)
        assert deck.cards[0].front == "Q1"

    def test_request_shape(self):
        client = _mock_client()
        generate_flashcards(
            client,
            pdf_bytes=PDF_BYTES,
            deck_name="Bio 101",
            description="Focus on definitions",
            model="claude-haiku-4-5",
        )
        kwargs = client.messages.parse.call_args.kwargs
        assert kwargs["model"] == "claude-haiku-4-5"
        assert kwargs["max_tokens"] == 32000
        assert kwargs["output_format"] is FlashcardDeck
        assert "Atomic" in kwargs["system"]  # skill prompt loaded into system

        [message] = kwargs["messages"]
        assert message["role"] == "user"
        doc_block, text_block = message["content"]  # document must precede text
        assert doc_block["type"] == "document"
        assert doc_block["source"]["type"] == "base64"
        assert doc_block["source"]["media_type"] == "application/pdf"
        assert doc_block["source"]["data"] == base64.standard_b64encode(PDF_BYTES).decode()
        assert text_block["type"] == "text"
        assert "Bio 101" in text_block["text"]
        assert "Focus on definitions" in text_block["text"]

    def test_max_tokens_stop_reason_raises_document_too_large(self):
        client = _mock_client(stop_reason="max_tokens")
        with pytest.raises(DocumentTooLargeError):
            generate_flashcards(
                client,
                pdf_bytes=PDF_BYTES,
                deck_name="Huge",
                description="",
                model="claude-sonnet-5",
            )

    def test_truncated_json_raises_document_too_large(self):
        """A large PDF can overflow the output cap, leaving parse() with incomplete JSON.

        messages.parse() raises a JSON-decode ValidationError BEFORE we can inspect
        stop_reason, so this path must be caught and mapped to 'document too large'.
        """
        try:
            FlashcardDeck.model_validate_json('{"cards": [{"front": "What is')
        except ValidationError as truncated:  # a real json_invalid error
            err = truncated
        client = MagicMock()
        client.messages.parse.side_effect = err

        with pytest.raises(DocumentTooLargeError):
            generate_flashcards(
                client,
                pdf_bytes=PDF_BYTES,
                deck_name="Huge",
                description="",
                model="claude-sonnet-5",
            )

    def test_schema_mismatch_raises_malformed_generation(self):
        """A validation error that is NOT truncation maps to a malformed-output error (502)."""
        try:
            FlashcardDeck.model_validate({"cards": "not-a-list"})
        except ValidationError as bad_schema:
            err = bad_schema
        client = MagicMock()
        client.messages.parse.side_effect = err

        with pytest.raises(MalformedGenerationError):
            generate_flashcards(
                client,
                pdf_bytes=PDF_BYTES,
                deck_name="Weird",
                description="",
                model="claude-sonnet-5",
            )

    def test_error_types_are_generation_errors(self):
        assert issubclass(DocumentTooLargeError, GenerationError)
        assert issubclass(MalformedGenerationError, GenerationError)

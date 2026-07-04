"""PDF -> flashcards via a single Anthropic structured-output call."""

import base64
from pathlib import Path

import anthropic

from app.generation.errors import DocumentTooLargeError, InvalidPdfError, PdfTooLargeError
from app.generation.models import FlashcardDeck

MAX_PDF_BYTES = 20 * 1024 * 1024  # practical cap, well under the 32 MB API limit
_PDF_MAGIC = b"%PDF-"
_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "flashcard_generation.md"
# Output-token budget for one generation call. Kept under the SDK's non-streaming
# timeout guard (which rejects very large max_tokens on a blocking request). The model
# supports up to 128k, but going that high requires switching to a streaming call.
_MAX_OUTPUT_TOKENS = 32000


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
    response = client.messages.parse(
        model=model,
        max_tokens=_MAX_OUTPUT_TOKENS,
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
    if response.stop_reason == "max_tokens":
        raise DocumentTooLargeError(
            "The document produced more cards than fit in one response; it is too large."
        )
    return response.parsed_output

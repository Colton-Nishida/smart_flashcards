"""Typed errors raised by the generation pipeline (mapped to HTTP codes in the router)."""


class GenerationError(Exception):
    """Base class for generation failures."""


class InvalidPdfError(GenerationError):
    """Upload is not a PDF (magic-byte check failed). -> HTTP 400"""


class PdfTooLargeError(GenerationError):
    """Upload exceeds the size cap. -> HTTP 413"""


class DocumentTooLargeError(GenerationError):
    """The model hit max_tokens before finishing the deck. -> HTTP 413

    Includes the case where the response JSON is truncated mid-object because output
    overflowed the token cap — messages.parse() then raises a JSON-decode ValidationError.
    """


class MalformedGenerationError(GenerationError):
    """The model returned output that isn't valid FlashcardDeck data (not truncation).
    -> HTTP 502"""

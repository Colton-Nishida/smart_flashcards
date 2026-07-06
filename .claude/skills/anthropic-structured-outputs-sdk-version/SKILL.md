---
name: anthropic-structured-outputs-sdk-version
description: When touching backend generation code or the anthropic dependency pin — messages.parse needs a recent SDK, and the request/response surface has specifics worth knowing.
---

# Anthropic SDK: structured outputs surface used by this repo

- `client.messages.parse(..., output_format=FlashcardDeck)` does **not exist** in
  `anthropic==0.60` (the version originally pinned in `backend/pyproject.toml`). It was added
  later; the repo now pins `anthropic = "^0.116"`. If you ever downgrade or re-resolve deps,
  verify with: `python -c "import anthropic; print(hasattr(anthropic.Anthropic(api_key='x').messages, 'parse'))"`.
- `parse()` returns a `ParsedMessage`; the validated Pydantic instance is on
  `response.parsed_output` (a property, not a model field — it won't show up in
  `model_fields`).
- `output_format=<PydanticModel>` is the convenience param on `.parse()`; the canonical
  API-level param on `messages.create()` is `output_config={"format": ...}`. Stick with
  `.parse()` here.
- Always check `response.stop_reason == "max_tokens"` before trusting `parsed_output` — a
  truncated structured response maps to our `DocumentTooLargeError` → HTTP 413.
- In tests, mock the client as `MagicMock()` with
  `client.messages.parse.return_value = SimpleNamespace(stop_reason="end_turn", parsed_output=...)`
  and inject via FastAPI `app.dependency_overrides[get_anthropic_client]`
  (see `backend/app/generation/deps.py`). No API key needed to run the suite.
- Constructing anthropic exceptions in tests: `anthropic.APIConnectionError(request=httpx.Request(...))`.
- **Non-streaming `max_tokens` hard ceiling: 21333.** `_calculate_nonstreaming_timeout` raises
  `ValueError("Streaming is required...")` at request time whenever
  `3600s * max_tokens / 128_000 > 600s`, i.e. `max_tokens > 21333` — regardless of model. This
  repo uses 21000 (`generation/service.py`, `quiz/agent.py`). Mocked tests can NOT catch a
  violation (the mock never reaches the SDK's timeout math); it only fails on a live call.
  A 32k budget shipped green through the whole suite and 500'd on the first real upload.
  Going higher means switching to a streaming call, not raising the number.

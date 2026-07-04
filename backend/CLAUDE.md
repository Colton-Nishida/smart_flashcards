# backend/ — FastAPI service

Poetry-managed Python 3.12 project. JSON API under `/api`. See `docs/DESIGN.md` for the full
API surface and data model; root `CLAUDE.md` for working rules (worktrees, TDD, ruff).

## Layout

| Path | Purpose |
|---|---|
| `app/main.py` | App factory, router mounting, CORS for the Vite dev server |
| `app/config.py` | `pydantic-settings` — `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `SESSION_SECRET`, `DATA_DIR` |
| `app/auth/` | register / login / logout / me — bcrypt hashes, itsdangerous-signed session cookie |
| `app/decks/` | Deck + card CRUD routes |
| `app/generation/` | PDF → flashcards via the `anthropic` SDK |
| `app/skills/flashcard_generation.md` | The generation system prompt ("agent skill"). Tune card quality HERE, not in code |
| `app/storage/` | File persistence: `data/users.json`, `data/decks/<user_id>/<deck_id>.json`. Atomic write-then-rename. ALL disk access goes through this module (it's the future DB seam) |
| `tests/` | pytest. Write tests BEFORE implementation |

## Conventions

- Pydantic models for every request/response body; no untyped dicts across module boundaries.
- Routes are thin; logic lives in the module's service functions so it's testable without HTTP.
- Every deck access must check ownership (user id from session vs deck path) — enforce in one
  dependency, test per-user isolation explicitly.
- Generation calls: send the PDF as a base64 `document` content block; use
  `client.messages.parse(..., output_format=FlashcardDeck)` for guaranteed-valid JSON.
  `max_tokens=16000`, model from settings. Mock the Anthropic client in tests
  (live smoke test only behind `RUN_LIVE_API_TESTS=1`).
- Upload validation: PDF mime/magic check, ≤20 MB. Map `stop_reason == "max_tokens"` to a
  user-facing "document too large" error.

## Commands (run from this directory)

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8000
poetry run pytest
poetry run ruff check . && poetry run ruff format .
```

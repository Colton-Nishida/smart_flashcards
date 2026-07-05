# Smart Flashcards

Web app: sign in → upload a PDF → Claude generates an Anki-style flashcard deck → study it.
FastAPI backend (Poetry, Python 3.12) + React/TypeScript/Tailwind frontend (Vite).
Full spec, architecture, and phased plan: **`docs/DESIGN.md`** (read it before nontrivial work).

## Non-negotiable working rules

1. **Always work off a git worktree** when making changes — never edit `main`'s checkout
   directly. (`git worktree add ../smart_flashcards-<feature> -b <feature>`)
2. **Commit to branches regularly** — small, focused commits as you go, not one blob at the end.
3. **Ruff is the linter/formatter for all Python.** `ruff check` and `ruff format --check`
   must be clean before any commit.
4. **Tests first (TDD).** Write failing tests BEFORE implementing a change, then verify they
   pass AFTER. Backend: `pytest` in `backend/`.
5. **Always update CLAUDE.md files** (this one and the relevant subdir ones) when a change
   makes them stale.
6. **Capture new learnings as skills.** If you learn something non-obvious about this repo,
   its tooling, or its APIs, create a skill under `.claude/skills/<name>/SKILL.md`.

## Repo map

| Path | What lives there |
|---|---|
| `backend/` | FastAPI app, Poetry project — see `backend/CLAUDE.md` |
| `frontend/` | Vite + React + TS + Tailwind — see `frontend/CLAUDE.md` |
| `docs/DESIGN.md` | The spec: architecture, API surface, data model, dev plan, decisions log |
| `tasks/` | Task briefs from Cole |
| `.claude/skills/` | Repo skills (learnings) |
| `data/` | Runtime storage (users.json, decks) — gitignored, never commit its contents |

## Commands

```bash
# Backend (from backend/)
poetry install
poetry run uvicorn app.main:app --reload --port 8000
poetry run pytest
poetry run ruff check . && poetry run ruff format --check .

# Frontend (from frontend/)
npm install
npm run dev        # Vite dev server, proxies /api → localhost:8000
```

## Key facts

- Flashcard generation = single Anthropic API call: PDF sent as a native `document` block,
  output enforced with structured outputs (`client.messages.parse` + Pydantic). No agent loop.
  The dynamic quiz (Topics tab) follows the same pattern: every step (notes extraction,
  question, grading, dispute, scoring) is one structured-output call; session state lives on
  the topic JSON, not in an agent loop.
- All LLM prompts are versioned "skill" files under `backend/app/skills/`
  (`flashcard_generation`, `topic_notes_extraction`, `quiz_question`, `quiz_grading`,
  `quiz_dispute`, `quiz_scoring`). Output-quality tuning happens there, not in code.
- Non-streaming Anthropic calls must keep `max_tokens <= 21000` — the SDK rejects more at
  request time, and only live calls (not mocked tests) catch it.
- Model comes from `ANTHROPIC_MODEL` env (default `claude-sonnet-5`). Never hardcode model IDs
  in application code.
- Secrets (`ANTHROPIC_API_KEY`, `SESSION_SECRET`) come from env / `.env` (gitignored).
- Playwright MCP is installed — use it to drive the running app in a browser when verifying
  frontend work end-to-end.

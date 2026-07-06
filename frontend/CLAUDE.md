# frontend/ — React app

Vite + React + TypeScript + Tailwind CSS. Talks to the backend via `/api` (Vite dev-server
proxy → `localhost:8000`). See `docs/DESIGN.md` for UX decisions; root `CLAUDE.md` for
working rules.

## UX (decided — don't re-litigate)

- **Three tabs**: `Upload`, `Decks`, and `Topics` (plus a login screen when unauthenticated).
- **Upload tab**: PDF file picker + deck name + description → synchronous generation with a
  clear in-progress state (this call takes 15–60s; disable resubmit, show progress copy).
  The description doubles as guidance to Claude — hint that in the placeholder.
- **Decks tab**: deck list → deck view. Study mode = shuffled flip-through: show front,
  click/space to reveal back, then "again" / "got it"; "again" cards recycle to the end of
  the session. No persisted study results in MVP.
- Cards and decks are editable/deletable inline. One PDF = one deck; no appending.
- **Topics tab** (dynamic quiz): two-column layout (wider `max-w-6xl` main). Left = topic list
  with a red→green 0-100 mastery bar + inline new-topic PDF upload (name, description, and
  optional standing *instructions* for the tutor — focus areas / question style); right =
  tutor chat panel.
  Chat flow: pick question count (1-25) → free-text answer → Good/Ok/Bad grade + feedback →
  Next / Dispute / Finish. Disputing can revise the grade and correct the notes doc. Finishing
  scores the session (mastery bar + memory update). A `Notes & progress` sub-tab shows the
  extracted notes doc (source PDF linked), the tutor's "why this score" memory, and past
  sessions. In-flight sessions resume from `topic.active_session` on reload; `answer`/`dispute`
  send a `session_id`/`question_number` binding so a stale tab gets a 409 instead of
  corrupting the session.
- Styling: Tailwind utilities only. No component library.

## Layout

| Path | Purpose |
|---|---|
| `src/App.tsx` | Auth gate + tab shell (react-router); routes: `/upload`, `/decks`, `/decks/:deckId`, `/topics` |
| `src/api/` | Typed fetch client — the ONLY place that calls the backend; `types.ts` mirrors backend Pydantic schemas, `client.ts` has one function per endpoint |
| `src/pages/Login.tsx` | Login screen with register/login toggle |
| `src/pages/Upload.tsx` | Upload flow (validation, sync-generation progress state) |
| `src/pages/Decks.tsx` | Deck list |
| `src/pages/DeckView.tsx` | Deck view: metadata/card editing + study-mode entry |
| `src/pages/Topics.tsx` | Topics + quiz split view: topic list w/ mastery bars, selection, delete |
| `src/components/` | `StudyMode`, `CardRow` (inline edit/delete), `AddCardForm`, `QuizPanel` (the tutor chat + notes/progress tabs), `NewTopicForm`, `MasteryBar` |
| `src/lib/format.ts` | Small shared helpers (date formatting) |
| `src/index.css` | Tailwind v4 entry: `@import "tailwindcss"` + `@theme` design tokens |

## Conventions

- `fetch` with `credentials: "include"` (session cookie auth); handle 401 by routing to login.
  Implementation: `src/api/client.ts` dispatches `UNAUTHORIZED_EVENT` on `window` for any 401;
  `App.tsx` listens and clears the user, which renders the login screen.
- All API failures throw `ApiError` (status + FastAPI `detail`); use `isUnauthorized()` /
  `errorMessage()` from `src/api` in pages.
- Keep state local/component-level; no Redux/Zustand at this size.
- Tailwind v4: no `tailwind.config.*` — the `@tailwindcss/vite` plugin + `@theme` tokens in
  `src/index.css` (`paper`, `card`, `ink`, `accent`, `accent-deep` colors; `font-display` serif).
- Verify UI changes end-to-end with the Playwright MCP against the running dev servers.

## Commands (run from this directory)

```bash
npm install
npm run dev      # dev server on :5173, proxies /api → :8000
npm run build
```

# frontend/ — React app

Vite + React + TypeScript + Tailwind CSS. Talks to the backend via `/api` (Vite dev-server
proxy → `localhost:8000`). See `docs/DESIGN.md` for UX decisions; root `CLAUDE.md` for
working rules.

## UX (decided — don't re-litigate)

- **Two tabs**: `Upload` and `Decks` (plus a login screen when unauthenticated).
- **Upload tab**: PDF file picker + deck name + description + optional "additional instructions"
  → synchronous generation with a clear in-progress state (this call takes 15–60s; disable
  resubmit, show progress copy). "Additional instructions" is free-text generation guidance
  (e.g. "focus on the first page", "only cards about X"); it's sent as the
  `additional_instructions` form field and scopes what Claude covers — cards still come only
  from the PDF.
- **Decks tab**: deck list → deck view. Study mode = shuffled flip-through: show front,
  click/space to reveal back, then "again" / "got it"; "again" cards recycle to the end of
  the session. No persisted study results in MVP.
- Cards and decks are editable/deletable inline. One PDF = one deck; no appending.
- Styling: Tailwind utilities only. No component library.

## Layout

| Path | Purpose |
|---|---|
| `src/App.tsx` | Auth gate + tab shell (react-router); routes: `/upload`, `/decks`, `/decks/:deckId` |
| `src/api/` | Typed fetch client — the ONLY place that calls the backend; `types.ts` mirrors backend Pydantic schemas, `client.ts` has one function per endpoint |
| `src/pages/Login.tsx` | Login screen with register/login toggle |
| `src/pages/Upload.tsx` | Upload flow (validation, sync-generation progress state) |
| `src/pages/Decks.tsx` | Deck list |
| `src/pages/DeckView.tsx` | Deck view: metadata/card editing + study-mode entry |
| `src/components/` | `StudyMode`, `CardRow` (inline edit/delete), `AddCardForm` |
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

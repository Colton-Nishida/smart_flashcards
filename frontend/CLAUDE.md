# frontend/ — React app

Vite + React + TypeScript + Tailwind CSS. Talks to the backend via `/api` (Vite dev-server
proxy → `localhost:8000`). See `docs/DESIGN.md` for UX decisions; root `CLAUDE.md` for
working rules.

## UX (decided — don't re-litigate)

- **Two tabs**: `Upload` and `Decks` (plus a login screen when unauthenticated).
- **Upload tab**: PDF file picker + deck name + description → synchronous generation with a
  clear in-progress state (this call takes 15–60s; disable resubmit, show progress copy).
  The description doubles as guidance to Claude — hint that in the placeholder.
- **Decks tab**: deck list → deck view. Study mode = shuffled flip-through: show front,
  click/space to reveal back, then "again" / "got it"; "again" cards recycle to the end of
  the session. No persisted study results in MVP.
- Cards and decks are editable/deletable inline. One PDF = one deck; no appending.
- Styling: Tailwind utilities only. No component library.

## Layout

| Path | Purpose |
|---|---|
| `src/App.tsx` | Auth gate + tab shell (react-router) |
| `src/api/` | Typed fetch client — the ONLY place that calls the backend; mirror backend Pydantic schemas as TS types here |
| `src/pages/Upload.tsx` | Upload flow |
| `src/pages/Decks.tsx` | Deck list / deck view / study mode |
| `src/components/` | CardViewer, DeckList, etc. |

## Conventions

- `fetch` with `credentials: "include"` (session cookie auth); handle 401 by routing to login.
- Keep state local/component-level; no Redux/Zustand at this size.
- Verify UI changes end-to-end with the Playwright MCP against the running dev servers.

## Commands (run from this directory)

```bash
npm install
npm run dev      # dev server on :5173, proxies /api → :8000
npm run build
```

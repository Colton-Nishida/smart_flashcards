---
name: tailwind-v4-vite-setup
description: How Tailwind is wired up in frontend/ — v4 has no tailwind.config.js; theming lives in CSS. Read before touching frontend styling/config.
---

This repo uses **Tailwind CSS v4**, which works differently from the v3 setup most docs show:

- No `tailwind.config.js`, no `postcss.config.js`, no `npx tailwindcss init`. Setup is just:
  1. `npm i -D tailwindcss @tailwindcss/vite`
  2. Add `tailwindcss()` from `@tailwindcss/vite` to `plugins` in `vite.config.ts`
  3. `@import "tailwindcss";` at the top of `src/index.css` (replaces the three `@tailwind` directives)
- Custom design tokens are declared in CSS via `@theme { ... }` in `src/index.css`.
  Declaring `--color-paper: #f6f3ec;` there auto-generates `bg-paper`, `text-paper`,
  `border-paper`, etc. Same for `--font-display` → `font-display` utility.
- Content scanning is automatic (no `content: [...]` array); it respects `.gitignore`.
- Opacity shorthand like `ring-accent/20` and `border-accent/40` works with custom tokens.

Also note: the current `create-vite` react-ts template ships **oxlint** (not eslint — `npm run
lint`) and does NOT set `"strict": true` in `tsconfig.app.json`; we added it manually. Keep it.

---
name: bughunt
description: Adversarially hunt for bugs in the current git diff (or whole codebase). Poke holes, prove each bug with a failing test, then fix it. Use before merging a branch, when the user says "bughunt", or to audit recent changes.
---

# bughunt — adversarial bug hunting

Your job is to **break the code**, not admire it. Assume every change hides a bug and go looking
for it. A pass that finds nothing should be the exception, not the rule.

## Scope

Default target is the **current git diff**:

```bash
git diff main...HEAD        # changes on this branch vs main
git diff                    # uncommitted changes
git diff --stat main...HEAD # file overview first
```

If asked to "bughunt all code," audit the whole tree, not just the diff. Read each changed file
with enough surrounding context to understand the call sites, not just the changed lines.

## What counts as a bug (hunt for these)

- **Correctness / logic**: wrong result, inverted condition, off-by-one, wrong operator, mishandled
  return value, a check that's unreachable because something upstream throws first.
- **Error handling**: an exception type that isn't caught and escapes as a raw 500; catching too
  broadly and hiding real errors; `except`/`catch` that swallows and continues with bad state.
- **Edge cases**: empty input, `None`/`null`/missing field, zero-length, very large input, unicode,
  duplicate, concurrent access, first-run (missing file/dir), the boundary value of any limit.
- **Security**: missing authorization / ownership check, path traversal, injection, secrets in logs
  or responses or persisted state, trusting client-supplied ids/paths.
- **Resource & lifecycle**: files not closed, non-atomic writes, races between check and use,
  partial writes on failure, unbounded growth.
- **Contract mismatches**: frontend expects a field/shape the backend doesn't send (or vice versa);
  status codes the client doesn't handle; a type that's `X | null` treated as always-`X`.
- **Async / blocking**: a long blocking call on the event loop; a timeout that isn't a wall-clock
  cap; missing `await`.
- **Third-party API quirks**: an SDK that raises before returning; a guard that rejects a value
  range; a response field that's optional but read unconditionally.

## Repo-specific hot spots (this project)

- **Per-user isolation**: every deck/card route must verify the deck belongs to the session user.
  Try to read/edit/delete another user's deck — it must 404, not leak.
- **Storage**: writes must be atomic (write-temp-then-rename); model-supplied ids must not escape
  the data dir (path traversal); concurrent writes to the same file.
- **Auth**: session cookie signing/expiry, wrong-password path, tampered cookie, missing cookie.
- **Generation**: `messages.parse()` raises `ValidationError` on truncated output *before* the
  `stop_reason` check; the SDK rejects non-streaming `max_tokens` above ~21k without an explicit
  `timeout`; missing `ANTHROPIC_API_KEY` raises `TypeError`, not an `APIError`. Map each to a clean
  HTTP status, never a raw 500.
- **Frontend/backend contract**: `src/api/types.ts` must match the Pydantic models; a 401 anywhere
  must route to login; the 15–60s synchronous upload must not double-submit.

## Process — one bug at a time

1. **Survey**: `git diff --stat`, then read the changed files (and their callers) in full.
2. **Hunt**: for each change, ask "what input or ordering makes this wrong?" Write the candidate
   bugs down with `file:line` and a concrete failure scenario (specific inputs → wrong output).
3. **Verify it's real before fixing.** Reproduce it — a failing test, a curl, or a REPL. If you
   can't make it fail, it's not a confirmed bug; note it as "suspected" and move on. Do not fix
   phantom bugs.
4. **Fix, test-first** (repo rule): write the failing test, make it pass, keep the rest of the
   suite green (`poetry run pytest`) and `ruff check` / `ruff format --check` clean. Frontend:
   `npm run build` must stay clean.
5. **One bug per commit**, message describing the bug and the fix.
6. **Loop** until a full pass finds no new *critical* bugs. Don't stop at the first one.

## Severity — fix critical first

- **Critical**: crash on normal input, auth bypass / data leak, data loss or corruption, wrong
  results returned to the user, security hole. Fix these.
- **Minor**: cosmetic, unreachable-in-practice, style, missing nice-to-have validation. List them;
  fix only if cheap and safe.

## Output

Report every confirmed bug: `file:line`, severity, the failure scenario (inputs → wrong behavior),
the fix, and the commit. List suspected-but-unconfirmed items separately. End with an explicit
statement of what you could NOT break (the invariants you tried to violate and couldn't) so the
reader knows what was actually exercised.

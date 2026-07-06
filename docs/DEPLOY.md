# Deploying Smart Flashcards (Railway)

One Docker container runs everything: FastAPI serves the JSON API under `/api/*` and the
built React app for every other path (same origin — no CORS or proxy config). User data is
flat files, so the app needs **a persistent volume and exactly one replica**.

## Environment variables

| Variable | Required | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | Claude API key (set a spend limit in the Anthropic console) |
| `SESSION_SECRET` | yes | Cookie-signing key. Generate: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `INVITE_CODE` | strongly recommended | When set, registration requires this code — without it, anyone who finds the URL can create an account and spend your API credits |
| `SESSION_COOKIE_SECURE` | `true` in production | Marks the session cookie HTTPS-only |
| `DATA_DIR` | baked into the image as `/data` | Must match the volume mount path |
| `STATIC_DIR` | baked into the image as `/app/static` | Where the built frontend lives |
| `ANTHROPIC_MODEL` | no | Defaults to `claude-sonnet-5` |

## Railway walkthrough

1. **Create the project**: railway.com → *New Project* → *Deploy from GitHub repo* →
   pick `Colton-Nishida/smart_flashcards` (authorize the GitHub app if asked). Railway
   detects the `Dockerfile` via `railway.json` and starts building.
2. **Add the volume** (before first real use): right-click the service → *Attach Volume*
   → mount path **`/data`**. Start with 1 GB; grow later if needed.
3. **Set variables**: service → *Variables* → add `ANTHROPIC_API_KEY`, `SESSION_SECRET`
   (fresh random value — NOT the dev one), `INVITE_CODE`, `SESSION_COOKIE_SECURE=true`.
   Save → Railway redeploys.
4. **Expose it**: service → *Settings* → *Networking* → *Generate Domain* (port 8000).
   You get `https://<something>.up.railway.app`.
5. **Smoke test**: open `https://<domain>/api/health` → `{"status":"ok"}`, then the root
   URL → sign-up screen. Register with the invite code, upload a small PDF, confirm a deck
   generates. Redeploy once more and confirm the account still exists (proves the volume
   is doing its job).
6. **Deploys from now on**: every push to the tracked branch redeploys automatically.
   Point Railway at `main` (Settings → Source) so merged PRs go live.

## Costs & limits to know

- Railway Hobby plan is $5/mo (includes usage credit); this app idles well under that.
- Each deck/topic generation costs roughly $0.10–0.25 in Anthropic usage; set a monthly
  spend limit on the key in the Anthropic console as a backstop.
- Generation requests block for 15–90s. Railway tolerates this; if you ever front it with
  Cloudflare, watch the ~100s proxy timeout (upgrade path: background jobs + polling,
  DESIGN.md Phase 5).
- **Never scale above 1 replica** — storage is flat JSON files on the volume; two replicas
  would clobber each other's writes (`railway.json` pins `numReplicas: 1`).

## Local production rehearsal (optional, needs Docker)

```bash
docker build -t smart-flashcards .
docker run --rm -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-... -e SESSION_SECRET=whatever -e INVITE_CODE=letmein \
  -v sf-data:/data smart-flashcards
# open http://localhost:8000
```

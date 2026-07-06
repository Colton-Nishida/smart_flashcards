"""Single-page-app static serving: real files when they exist, index.html for
client-side navigation routes.

Mounted at "/" AFTER all API routers, so registered /api/* routes always win.
The index.html fallback is deliberately narrow:

- ``/api/...`` paths that reached the mount are unknown endpoints — they stay 404
  (JSON error contract; the SPA shell would break the frontend's ApiError parsing).
- Paths whose last segment has a file extension (e.g. a stale cached bundle asking
  for ``/assets/app-<oldhash>.js``) stay 404 — serving HTML as a script gives a
  MIME-blocked white screen instead of a signal to reload.
- Everything else (``/topics``, ``/decks/d_123``) is a client-side route:
  serve the shell and let react-router take it from there.
"""

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


def _is_spa_route(path: str) -> bool:
    path = path.lstrip("/")
    if path == "api" or path.startswith("api/"):
        return False
    last_segment = path.rsplit("/", 1)[-1]
    return "." not in last_segment


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404 and _is_spa_route(path):
                return await super().get_response("index.html", scope)
            raise

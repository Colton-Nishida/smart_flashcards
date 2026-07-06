"""Single-page-app static serving: real files when they exist, index.html otherwise.

Mounted at "/" AFTER all API routers, so /api/* always wins; anything else that
isn't a real file (client-side routes like /decks/d_123) falls back to the SPA
shell and react-router takes it from there.
"""

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise

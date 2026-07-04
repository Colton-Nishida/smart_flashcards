"""The ``current_user`` dependency — required by every deck route."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status

from app.auth import service
from app.auth.sessions import SESSION_COOKIE, verify_session
from app.config import Settings
from app.deps import get_settings, get_storage
from app.storage import Storage


def current_user(
    request: Request,
    storage: Annotated[Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = verify_session(settings.session_secret, token)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    user = service.get_user_by_id(storage, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(current_user)]

"""Auth routes: /api/auth/*."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import service
from app.auth.deps import CurrentUser
from app.auth.models import Credentials, UserPublic
from app.auth.sessions import SESSION_COOKIE, SESSION_MAX_AGE_SECONDS, sign_session
from app.config import Settings
from app.deps import get_settings, get_storage
from app.storage import Storage

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(
    credentials: Credentials,
    storage: Annotated[Storage, Depends(get_storage)],
) -> UserPublic:
    try:
        user = service.register_user(storage, credentials.username, credentials.password)
    except service.UsernameTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username already taken") from None
    return UserPublic(**{k: user[k] for k in ("id", "username", "created_at")})


@router.post("/login", response_model=UserPublic)
def login(
    credentials: Credentials,
    response: Response,
    storage: Annotated[Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserPublic:
    user = service.authenticate(storage, credentials.username, credentials.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    response.set_cookie(
        SESSION_COOKIE,
        sign_session(settings.session_secret, user["id"]),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return UserPublic(**{k: user[k] for k in ("id", "username", "created_at")})


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser) -> UserPublic:
    return UserPublic(**{k: user[k] for k in ("id", "username", "created_at")})

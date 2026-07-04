"""Signed session tokens (itsdangerous) carried in an httponly cookie."""

from itsdangerous import BadSignature, URLSafeTimedSerializer

SESSION_COOKIE = "session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600
_SALT = "smart-flashcards-session"


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=_SALT)


def sign_session(secret: str, user_id: str) -> str:
    return _serializer(secret).dumps(user_id)


def verify_session(secret: str, token: str) -> str | None:
    """Return the user id, or None if the token is invalid/expired."""
    try:
        return _serializer(secret).loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except BadSignature:
        return None

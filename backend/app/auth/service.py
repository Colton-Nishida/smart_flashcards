"""Auth business logic: user creation and password verification."""

import secrets
from datetime import UTC, datetime
from typing import Any

import bcrypt

from app.storage import Storage


class UsernameTakenError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def register_user(storage: Storage, username: str, password: str) -> dict[str, Any]:
    data = storage.read_users()
    if any(u["username"] == username for u in data["users"]):
        raise UsernameTakenError(username)
    user = {
        "id": f"u_{secrets.token_hex(8)}",
        "username": username,
        "password_hash": hash_password(password),
        "created_at": _now_iso(),
    }
    data["users"].append(user)
    storage.write_users(data)
    return user


def authenticate(storage: Storage, username: str, password: str) -> dict[str, Any] | None:
    """Return the user record if credentials are valid, else None."""
    data = storage.read_users()
    user = next((u for u in data["users"] if u["username"] == username), None)
    if user is None:
        # Burn comparable time to avoid a username-existence timing oracle.
        check_password(password, hash_password("timing-equalizer"))
        return None
    if not check_password(password, user["password_hash"]):
        return None
    return user


def get_user_by_id(storage: Storage, user_id: str) -> dict[str, Any] | None:
    data = storage.read_users()
    return next((u for u in data["users"] if u["id"] == user_id), None)

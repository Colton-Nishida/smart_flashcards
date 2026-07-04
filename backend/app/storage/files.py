"""JSON-file backed storage with atomic write-then-rename."""

import contextlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class StorageIdError(ValueError):
    """Raised when a user/deck id is not filesystem-safe."""


def _check_id(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.match(value):
        raise StorageIdError(f"unsafe id: {value!r}")
    return value


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


class Storage:
    """File-backed persistence for users and decks."""

    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)

    # -- users ------------------------------------------------------------

    @property
    def _users_path(self) -> Path:
        return self.data_dir / "users.json"

    def read_users(self) -> dict[str, Any]:
        return _read_json(self._users_path) or {"users": []}

    def write_users(self, data: dict[str, Any]) -> None:
        _atomic_write_json(self._users_path, data)

    # -- decks ------------------------------------------------------------

    def _deck_dir(self, user_id: str) -> Path:
        return self.data_dir / "decks" / _check_id(user_id)

    def _deck_path(self, user_id: str, deck_id: str) -> Path:
        return self._deck_dir(user_id) / f"{_check_id(deck_id)}.json"

    def read_deck(self, user_id: str, deck_id: str) -> dict[str, Any] | None:
        return _read_json(self._deck_path(user_id, deck_id))

    def write_deck(self, user_id: str, deck: dict[str, Any]) -> None:
        _atomic_write_json(self._deck_path(user_id, deck["id"]), deck)

    def list_decks(self, user_id: str) -> list[dict[str, Any]]:
        deck_dir = self._deck_dir(user_id)
        if not deck_dir.is_dir():
            return []
        decks = []
        for path in sorted(deck_dir.glob("*.json")):
            deck = _read_json(path)
            if deck is not None:
                decks.append(deck)
        return decks

    def delete_deck(self, user_id: str, deck_id: str) -> bool:
        path = self._deck_path(user_id, deck_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

"""File persistence layer.

ALL disk access goes through this module (it is the future DB seam).

Layout under ``data_dir``:
    users.json
    decks/<user_id>/<deck_id>.json

Every write is atomic: write to a temp file in the same directory, then
``os.replace`` onto the final path.
"""

from app.storage.files import Storage, StorageIdError

__all__ = ["Storage", "StorageIdError"]

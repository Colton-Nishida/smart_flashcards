"""Tests for app.storage — file persistence layer."""

import json
import threading

import pytest

from app.storage import Storage, StorageIdError


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "data")


class TestUsers:
    def test_read_users_empty(self, storage):
        assert storage.read_users() == {"users": []}

    def test_users_roundtrip(self, storage):
        data = {"users": [{"id": "u_1", "username": "cole", "password_hash": "x"}]}
        storage.write_users(data)
        assert storage.read_users() == data

    def test_users_file_is_valid_json_on_disk(self, storage, tmp_path):
        storage.write_users({"users": []})
        raw = (tmp_path / "data" / "users.json").read_text()
        assert json.loads(raw) == {"users": []}


class TestDecks:
    DECK = {
        "id": "d_abc",
        "name": "Bio",
        "description": "Cells",
        "created_at": "2026-07-04T00:00:00Z",
        "source_filename": "bio.pdf",
        "cards": [{"id": "c_1", "front": "Q", "back": "A", "tags": ["bio"]}],
    }

    def test_read_missing_deck_returns_none(self, storage):
        assert storage.read_deck("u_1", "d_missing") is None

    def test_deck_roundtrip(self, storage):
        storage.write_deck("u_1", self.DECK)
        assert storage.read_deck("u_1", "d_abc") == self.DECK

    def test_list_decks_empty_for_unknown_user(self, storage):
        assert storage.list_decks("u_nobody") == []

    def test_list_decks_returns_all_user_decks(self, storage):
        storage.write_deck("u_1", self.DECK)
        other = dict(self.DECK, id="d_xyz", name="Chem")
        storage.write_deck("u_1", other)
        decks = storage.list_decks("u_1")
        assert {d["id"] for d in decks} == {"d_abc", "d_xyz"}

    def test_decks_are_isolated_per_user(self, storage):
        storage.write_deck("u_1", self.DECK)
        assert storage.read_deck("u_2", "d_abc") is None
        assert storage.list_decks("u_2") == []

    def test_delete_deck(self, storage):
        storage.write_deck("u_1", self.DECK)
        assert storage.delete_deck("u_1", "d_abc") is True
        assert storage.read_deck("u_1", "d_abc") is None

    def test_delete_missing_deck_returns_false(self, storage):
        assert storage.delete_deck("u_1", "d_missing") is False

    def test_overwrite_deck_replaces_content(self, storage):
        storage.write_deck("u_1", self.DECK)
        updated = dict(self.DECK, name="Bio 2")
        storage.write_deck("u_1", updated)
        assert storage.read_deck("u_1", "d_abc")["name"] == "Bio 2"


class TestSafety:
    @pytest.mark.parametrize("bad_id", ["../evil", "a/b", "", ".", "d_x\x00", "d x"])
    def test_rejects_unsafe_ids(self, storage, bad_id):
        with pytest.raises(StorageIdError):
            storage.read_deck(bad_id, "d_abc")
        with pytest.raises(StorageIdError):
            storage.read_deck("u_1", bad_id)

    def test_atomic_write_no_partial_files_left(self, storage, tmp_path):
        storage.write_users({"users": []})
        deck_dirs = tmp_path / "data"
        leftovers = [p for p in deck_dirs.rglob("*") if p.suffix == ".tmp"]
        assert leftovers == []

    def test_concurrent_writes_leave_valid_json(self, storage, tmp_path):
        def writer(n):
            for i in range(20):
                storage.write_users({"users": [{"id": f"u_{n}_{i}"}]})

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # File must always be complete, parseable JSON (write-then-rename)
        raw = (tmp_path / "data" / "users.json").read_text()
        data = json.loads(raw)
        assert "users" in data

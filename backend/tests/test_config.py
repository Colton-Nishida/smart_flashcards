"""Tests for app.config — env-driven settings."""

import logging
from pathlib import Path

from app.config import BACKEND_DIR, DEFAULT_SESSION_SECRET, Settings


def _clean_env(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "SESSION_SECRET", "DATA_DIR"):
        monkeypatch.delenv(var, raising=False)


def test_defaults(monkeypatch):
    _clean_env(monkeypatch)
    settings = Settings(_env_file=None)
    assert settings.anthropic_api_key == ""
    assert settings.anthropic_model == "claude-sonnet-5"
    assert settings.session_secret == DEFAULT_SESSION_SECRET
    assert settings.data_dir == (BACKEND_DIR.parent / "data").resolve()
    assert settings.data_dir.is_absolute()


def test_env_overrides(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("SESSION_SECRET", "super-secret")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "mydata"))
    settings = Settings(_env_file=None)
    assert settings.anthropic_api_key == "sk-test-123"
    assert settings.anthropic_model == "claude-haiku-4-5"
    assert settings.session_secret == "super-secret"
    assert settings.data_dir == (tmp_path / "mydata").resolve()


def test_relative_data_dir_resolved_to_absolute(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("DATA_DIR", "relative/dir")
    settings = Settings(_env_file=None)
    assert settings.data_dir.is_absolute()
    assert settings.data_dir == (Path.cwd() / "relative" / "dir").resolve()


def test_default_session_secret_logs_warning(monkeypatch, caplog):
    _clean_env(monkeypatch)
    with caplog.at_level(logging.WARNING, logger="app.config"):
        Settings(_env_file=None)
    assert any("SESSION_SECRET" in record.message for record in caplog.records)


def test_explicit_session_secret_no_warning(monkeypatch, caplog):
    _clean_env(monkeypatch)
    monkeypatch.setenv("SESSION_SECRET", "explicit")
    with caplog.at_level(logging.WARNING, logger="app.config"):
        Settings(_env_file=None)
    assert not any("SESSION_SECRET" in record.message for record in caplog.records)

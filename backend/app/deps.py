"""Shared FastAPI dependencies (app-state accessors)."""

from fastapi import Request

from app.config import Settings
from app.storage import Storage


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> Storage:
    return request.app.state.storage

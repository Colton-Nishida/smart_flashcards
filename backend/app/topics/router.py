"""Topic routes: /api/topics/*. Every route requires an authenticated user."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status

from app.auth.deps import CurrentUser
from app.config import Settings
from app.deps import get_settings, get_storage
from app.generation import service as generation
from app.generation.deps import AnthropicClient
from app.generation.errors import InvalidPdfError, PdfTooLargeError
from app.generation.http import llm_errors
from app.quiz import agent
from app.storage import Storage, StorageIdError
from app.topics import service
from app.topics.models import Topic, TopicSummary, TopicUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/topics", tags=["topics"])

StorageDep = Annotated[Storage, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_NOT_FOUND = (service.TopicNotFoundError, StorageIdError)


def _404() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Topic not found")


@router.post("", response_model=Topic, status_code=status.HTTP_201_CREATED)
def create_topic(
    user: CurrentUser,
    storage: StorageDep,
    settings: SettingsDep,
    client: AnthropicClient,
    file: UploadFile,
    name: Annotated[str, Form(min_length=1, max_length=200)],
    description: Annotated[str, Form(max_length=2000)] = "",
    instructions: Annotated[str, Form(max_length=4000)] = "",
) -> Topic:
    """Upload a PDF, extract the study-notes doc synchronously, persist the topic."""
    pdf_bytes = file.file.read()
    try:
        generation.validate_pdf(pdf_bytes)
    except InvalidPdfError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Upload must be a PDF file"
        ) from None
    except PdfTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from None

    with llm_errors("notes extraction"):
        extracted = agent.extract_topic_notes(
            client,
            pdf_bytes=pdf_bytes,
            topic_name=name,
            description=description,
            instructions=instructions,
            model=settings.anthropic_model,
        )

    topic = service.create_topic(
        storage,
        user["id"],
        name=name,
        description=description,
        instructions=instructions,
        source_filename=file.filename or "upload.pdf",
        notes_md=extracted.notes_md,
        pdf_bytes=pdf_bytes,
    )
    return Topic(**topic)


@router.get("", response_model=list[TopicSummary])
def list_topics(user: CurrentUser, storage: StorageDep) -> list[TopicSummary]:
    return [TopicSummary(**s) for s in service.list_topic_summaries(storage, user["id"])]


@router.get("/{topic_id}", response_model=Topic)
def get_topic(topic_id: str, user: CurrentUser, storage: StorageDep) -> Topic:
    try:
        return Topic(**service.get_topic(storage, user["id"], topic_id))
    except _NOT_FOUND:
        raise _404() from None


@router.patch("/{topic_id}", response_model=Topic)
def update_topic(
    topic_id: str, update: TopicUpdate, user: CurrentUser, storage: StorageDep
) -> Topic:
    try:
        topic = service.update_topic(
            storage,
            user["id"],
            topic_id,
            name=update.name,
            description=update.description,
            instructions=update.instructions,
        )
        return Topic(**topic)
    except _NOT_FOUND:
        raise _404() from None


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: str, user: CurrentUser, storage: StorageDep) -> None:
    try:
        service.delete_topic(storage, user["id"], topic_id)
    except _NOT_FOUND:
        raise _404() from None


@router.get("/{topic_id}/pdf")
def download_pdf(topic_id: str, user: CurrentUser, storage: StorageDep) -> Response:
    try:
        pdf = storage.read_topic_pdf(user["id"], topic_id)
    except StorageIdError:
        raise _404() from None
    if pdf is None:
        raise _404()
    return Response(content=pdf, media_type="application/pdf")

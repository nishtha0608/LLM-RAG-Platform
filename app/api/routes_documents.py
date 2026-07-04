"""Document upload, listing, and deletion endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.deps import (
    CurrentUser,
    get_document_repository,
    get_ingestion_service,
    get_vector_store,
)
from app.config import get_settings
from app.models import Document, DocumentStatus
from app.repositories import DocumentRepository
from app.schemas import DocumentList, DocumentRead
from app.services.ingestion import IngestionService
from app.vectorstore import VectorStore

router = APIRouter(prefix="/documents", tags=["documents"])

_ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain", "text/markdown"}


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: CurrentUser,
    file: UploadFile,
    documents: Annotated[DocumentRepository, Depends(get_document_repository)],
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> DocumentRead:
    settings = get_settings()
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {file.content_type}",
        )

    raw_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )

    document = Document(
        owner_id=current_user.id,
        filename=file.filename or "untitled",
        content_type=file.content_type,
        size_bytes=len(raw_bytes),
        status=DocumentStatus.PROCESSING,
    )
    document = await documents.create(document)

    try:
        chunk_count = await ingestion.ingest(
            document.id, current_user.id, document.filename, raw_bytes, document.content_type
        )
        document.status = DocumentStatus.READY
        document.chunk_count = chunk_count
    except Exception as exc:
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)[:1000]

    return DocumentRead.model_validate(document)


@router.get("", response_model=DocumentList)
async def list_documents(
    current_user: CurrentUser,
    documents: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> DocumentList:
    items = await documents.list_for_owner(current_user.id)
    return DocumentList(
        items=[DocumentRead.model_validate(item) for item in items], total=len(items)
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: CurrentUser,
    documents: Annotated[DocumentRepository, Depends(get_document_repository)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
) -> None:
    import uuid as uuid_module

    document = await documents.get_by_id(uuid_module.UUID(document_id), current_user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    await vector_store.delete_document(str(document.id))
    await documents.delete(document)

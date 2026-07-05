"""Pydantic request/response schemas (API contract layer)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DocumentStatus, MessageRole, UserRole

# --- Auth ---


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 -- OAuth2 scheme name, not a secret


class RefreshRequest(BaseModel):
    refresh_token: str


# --- Documents ---


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    chunk_count: int
    created_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int


# --- Chat ---


class ChatSessionCreate(BaseModel):
    title: str = Field(default="New chat", max_length=255)


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    document_ids: list[str] | None = Field(
        default=None, description="Restrict retrieval to these document IDs, if provided."
    )


class SourceCitation(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    chunk_text: str
    score: float


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    sources: list[SourceCitation] | None
    created_at: datetime


class ChatQueryResponse(BaseModel):
    message: ChatMessageRead
    citations: list[SourceCitation]


class QueryHistoryItem(BaseModel):
    session_id: uuid.UUID
    content: str
    created_at: datetime


# --- Health ---


class HealthStatus(BaseModel):
    status: str
    version: str
    environment: str


class ReadinessStatus(BaseModel):
    status: str
    checks: dict[str, bool]

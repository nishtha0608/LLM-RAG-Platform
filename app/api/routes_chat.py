"""Chat session and RAG query endpoints."""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, get_chat_repository, get_rag_service
from app.models import ChatMessage, ChatSession, MessageRole
from app.repositories import ChatRepository
from app.schemas import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
    QueryHistoryItem,
)
from app.services.rag import RagService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: ChatSessionCreate,
    current_user: CurrentUser,
    chat: Annotated[ChatRepository, Depends(get_chat_repository)],
) -> ChatSessionRead:
    session = await chat.create_session(ChatSession(owner_id=current_user.id, title=payload.title))
    return ChatSessionRead.model_validate(session)


@router.get("/sessions", response_model=list[ChatSessionRead])
async def list_sessions(
    current_user: CurrentUser, chat: Annotated[ChatRepository, Depends(get_chat_repository)]
) -> list[ChatSessionRead]:
    sessions = await chat.list_sessions(current_user.id)
    return [ChatSessionRead.model_validate(session) for session in sessions]


@router.get("/history", response_model=list[QueryHistoryItem])
async def list_history(
    current_user: CurrentUser, chat: Annotated[ChatRepository, Depends(get_chat_repository)]
) -> list[QueryHistoryItem]:
    messages = await chat.list_user_queries(current_user.id)
    return [
        QueryHistoryItem(session_id=m.session_id, content=m.content, created_at=m.created_at)
        for m in messages
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageRead])
async def list_messages(
    session_id: str,
    current_user: CurrentUser,
    chat: Annotated[ChatRepository, Depends(get_chat_repository)],
) -> list[ChatMessageRead]:
    session = await chat.get_session(uuid.UUID(session_id), current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    messages = await chat.list_messages(session.id)
    return [ChatMessageRead.model_validate(message) for message in messages]


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    payload: ChatMessageCreate,
    current_user: CurrentUser,
    chat: Annotated[ChatRepository, Depends(get_chat_repository)],
    rag: Annotated[RagService, Depends(get_rag_service)],
) -> StreamingResponse:
    session = await chat.get_session(uuid.UUID(session_id), current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    history_messages = await chat.list_messages(session.id)
    history = [{"role": str(m.role), "content": m.content} for m in history_messages]

    await chat.add_message(
        ChatMessage(session_id=session.id, role=MessageRole.USER, content=payload.content)
    )

    stream, citations = await rag.answer(
        payload.content, current_user.id, history, payload.document_ids
    )

    async def event_stream() -> AsyncIterator[str]:
        collected: list[str] = []
        async for token in stream:
            collected.append(token)
            yield token
        full_text = "".join(collected)
        sources = [
            {
                "document_id": c.document_id,
                "filename": c.filename,
                "chunk_index": c.chunk_index,
                "chunk_text": c.chunk_text[:500],
                "score": round(c.score, 4),
            }
            for c in citations
        ]
        await chat.add_message(
            ChatMessage(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                content=full_text,
                sources=sources,
            )
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")

"""Data access layer: thin, testable wrappers around SQLAlchemy queries."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, ChatSession, Document, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document: Document) -> Document:
        self._session.add(document)
        await self._session.flush()
        return document

    async def get_by_id(self, document_id: uuid.UUID, owner_id: uuid.UUID) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.id == document_id, Document.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_id: uuid.UUID) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .where(Document.owner_id == owner_id)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(self, chat_session: ChatSession) -> ChatSession:
        self._session.add(chat_session)
        await self._session.flush()
        return chat_session

    async def get_session(self, session_id: uuid.UUID, owner_id: uuid.UUID) -> ChatSession | None:
        result = await self._session.execute(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.owner_id == owner_id
            )
        )
        return result.scalar_one_or_none()

    async def list_sessions(self, owner_id: uuid.UUID) -> list[ChatSession]:
        result = await self._session.execute(
            select(ChatSession)
            .where(ChatSession.owner_id == owner_id)
            .order_by(ChatSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def add_message(self, message: ChatMessage) -> ChatMessage:
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_messages(self, session_id: uuid.UUID) -> list[ChatMessage]:
        result = await self._session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars().all())

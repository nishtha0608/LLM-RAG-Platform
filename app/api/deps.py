"""FastAPI dependency providers: DB session, repositories, services, and
the authenticated-user dependency used to protect routes."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import User
from app.repositories import ChatRepository, DocumentRepository, UserRepository
from app.security import InvalidTokenError, TokenType, decode_token
from app.services.auth import AuthService
from app.services.embedding import EmbeddingProvider, get_embedding_provider
from app.services.ingestion import IngestionService
from app.services.llm import LLMNotConfiguredError, LLMProvider, get_llm_provider
from app.services.rag import RagService
from app.vectorstore import QdrantVectorStore, VectorStore

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_user_repository(session: DbSession) -> UserRepository:
    return UserRepository(session)


def get_document_repository(session: DbSession) -> DocumentRepository:
    return DocumentRepository(session)


def get_chat_repository(session: DbSession) -> ChatRepository:
    return ChatRepository(session)


def get_auth_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(user_repository)


def get_vector_store() -> VectorStore:
    return QdrantVectorStore()


def get_embeddings() -> EmbeddingProvider:
    return get_embedding_provider()


def get_ingestion_service(
    embeddings: Annotated[EmbeddingProvider, Depends(get_embeddings)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
) -> IngestionService:
    return IngestionService(embeddings, vector_store)


def get_llm() -> LLMProvider:
    try:
        return get_llm_provider()
    except LLMNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


def get_rag_service(
    embeddings: Annotated[EmbeddingProvider, Depends(get_embeddings)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
) -> RagService:
    return RagService(embeddings, vector_store, llm)


async def get_current_user(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error

    try:
        user_id = decode_token(token, TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise credentials_error from exc

    user = await user_repository.get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

"""Embedding generation service. Local sentence-transformers by default;
swap the class to call a hosted embeddings API without touching callers."""

import asyncio
from functools import lru_cache
from typing import Protocol, cast

from sentence_transformers import SentenceTransformer

from app.config import get_settings


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


@lru_cache
def _load_model(model_name: str) -> SentenceTransformer:
    return cast(SentenceTransformer, SentenceTransformer(model_name))


class LocalEmbeddingProvider:
    """Runs a sentence-transformers model on CPU/GPU in a worker thread
    so it doesn't block the async event loop."""

    def __init__(self) -> None:
        settings = get_settings()
        self._model_name = settings.embedding_model
        self._batch_size = settings.embedding_batch_size

    def _encode(self, texts: list[str]) -> list[list[float]]:
        model = _load_model(self._model_name)
        vectors = model.encode(texts, batch_size=self._batch_size, normalize_embeddings=True)
        return [cast(list[float], vector.tolist()) for vector in vectors]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._encode, texts)

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]


def get_embedding_provider() -> EmbeddingProvider:
    return LocalEmbeddingProvider()

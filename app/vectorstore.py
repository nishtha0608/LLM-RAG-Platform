"""Qdrant vector store client wrapper. Abstracted behind a small protocol
so the backing vector database can be swapped without touching services."""

import uuid
from dataclasses import dataclass
from typing import Protocol

from qdrant_client import AsyncQdrantClient, models

from app.config import get_settings


@dataclass(frozen=True, slots=True)
class VectorRecord:
    id: str
    document_id: str
    owner_id: str
    filename: str
    chunk_text: str
    chunk_index: int


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    document_id: str
    filename: str
    chunk_text: str
    chunk_index: int
    score: float


class VectorStore(Protocol):
    async def ensure_collection(self) -> None: ...

    async def upsert_chunks(
        self, records: list[VectorRecord], embeddings: list[list[float]]
    ) -> None: ...

    async def search(
        self,
        query_embedding: list[float],
        owner_id: str,
        top_k: int,
        score_threshold: float,
        document_ids: list[str] | None = None,
    ) -> list[ScoredChunk]: ...

    async def delete_document(self, document_id: str) -> None: ...

    async def scroll_documents(
        self, owner_id: str, document_ids: list[str], limit: int
    ) -> list[ScoredChunk]: ...


class QdrantVectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        )
        self._collection = settings.qdrant_collection
        self._dimension = settings.vector_dimension

    async def ensure_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=models.VectorParams(
                    size=self._dimension, distance=models.Distance.COSINE
                ),
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="owner_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="document_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    async def upsert_chunks(
        self, records: list[VectorRecord], embeddings: list[list[float]]
    ) -> None:
        if len(records) != len(embeddings):
            raise ValueError("records and embeddings must be the same length")

        points = [
            models.PointStruct(
                id=record.id,
                vector=vector,
                payload={
                    "document_id": record.document_id,
                    "owner_id": record.owner_id,
                    "filename": record.filename,
                    "chunk_text": record.chunk_text,
                    "chunk_index": record.chunk_index,
                },
            )
            for record, vector in zip(records, embeddings, strict=True)
        ]
        await self._client.upsert(collection_name=self._collection, points=points)

    async def search(
        self,
        query_embedding: list[float],
        owner_id: str,
        top_k: int,
        score_threshold: float,
        document_ids: list[str] | None = None,
    ) -> list[ScoredChunk]:
        must_conditions: list[models.FieldCondition] = [
            models.FieldCondition(key="owner_id", match=models.MatchValue(value=owner_id))
        ]
        if document_ids:
            must_conditions.append(
                models.FieldCondition(key="document_id", match=models.MatchAny(any=document_ids))
            )

        results = await self._client.query_points(
            collection_name=self._collection,
            query=query_embedding,
            query_filter=models.Filter(must=must_conditions),
            limit=top_k,
            score_threshold=score_threshold,
        )
        return [
            ScoredChunk(
                document_id=point.payload["document_id"],
                filename=point.payload["filename"],
                chunk_text=point.payload["chunk_text"],
                chunk_index=point.payload["chunk_index"],
                score=point.score,
            )
            for point in results.points
            if point.payload is not None
        ]

    async def scroll_documents(
        self, owner_id: str, document_ids: list[str], limit: int
    ) -> list[ScoredChunk]:
        points, _ = await self._client.scroll(
            collection_name=self._collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(key="owner_id", match=models.MatchValue(value=owner_id)),
                    models.FieldCondition(
                        key="document_id", match=models.MatchAny(any=document_ids)
                    ),
                ]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        chunks = [
            ScoredChunk(
                document_id=point.payload["document_id"],
                filename=point.payload["filename"],
                chunk_text=point.payload["chunk_text"],
                chunk_index=point.payload["chunk_index"],
                score=1.0,
            )
            for point in points
            if point.payload is not None
        ]
        chunks.sort(key=lambda c: (c.document_id, c.chunk_index))
        return chunks

    async def delete_document(self, document_id: str) -> None:
        await self._client.delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=document_id)
                        )
                    ]
                )
            ),
        )


def new_chunk_id() -> str:
    return str(uuid.uuid4())

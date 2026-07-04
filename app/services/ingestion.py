"""Document ingestion: extract text, chunk it, embed it, and index it."""

import uuid
from dataclasses import dataclass

from app.config import get_settings
from app.services.embedding import EmbeddingProvider
from app.vectorstore import VectorRecord, VectorStore, new_chunk_id


@dataclass(frozen=True, slots=True)
class TextChunk:
    text: str
    index: int


def extract_text(raw_bytes: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw_bytes))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    if content_type in ("text/plain", "text/markdown"):
        return raw_bytes.decode("utf-8", errors="replace")

    raise ValueError(f"Unsupported content type: {content_type}")


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    if overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[TextChunk] = []
    start = 0
    index = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(TextChunk(text=normalized[start:end], index=index))
        if end == len(normalized):
            break
        start = end - overlap
        index += 1
    return chunks


class IngestionService:
    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: VectorStore) -> None:
        self._embeddings = embedding_provider
        self._vector_store = vector_store
        self._settings = get_settings()

    async def ingest(
        self,
        document_id: uuid.UUID,
        owner_id: uuid.UUID,
        filename: str,
        raw_bytes: bytes,
        content_type: str,
    ) -> int:
        text = extract_text(raw_bytes, content_type)
        chunks = chunk_text(text, self._settings.chunk_size, self._settings.chunk_overlap)
        if not chunks:
            return 0

        vectors = await self._embeddings.embed([chunk.text for chunk in chunks])
        records = [
            VectorRecord(
                id=new_chunk_id(),
                document_id=str(document_id),
                owner_id=str(owner_id),
                filename=filename,
                chunk_text=chunk.text,
                chunk_index=chunk.index,
            )
            for chunk in chunks
        ]
        await self._vector_store.ensure_collection()
        await self._vector_store.upsert_chunks(records, vectors)
        return len(chunks)

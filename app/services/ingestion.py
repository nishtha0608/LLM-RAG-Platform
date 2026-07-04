"""Document ingestion: extract text, chunk it, embed it, and index it."""

import re
import uuid
from dataclasses import dataclass

from app.config import get_settings
from app.services.embedding import EmbeddingProvider
from app.vectorstore import VectorRecord, VectorStore, new_chunk_id

# PDF extraction sometimes glues two sentences together with no whitespace at all
# (e.g. "...Act, 1996.Disputes shall..."), which otherwise defeats sentence splitting.
_GLUED_SENTENCE_RE = re.compile(r"(?<=[.!?])(?=[A-Z0-9])")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


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


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        pieces.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return pieces


def _split_into_units(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into sentence-level units, preserving line breaks as sentence
    boundaries too, so unrelated clauses/sections don't get silently fused
    together the way a blind whitespace collapse would."""
    units: list[str] = []
    for line in text.splitlines():
        deglued = _GLUED_SENTENCE_RE.sub(" ", line)
        normalized = " ".join(deglued.split())
        if not normalized:
            continue
        for sentence in _SENTENCE_SPLIT_RE.split(normalized):
            if not sentence:
                continue
            if len(sentence) > chunk_size:
                units.extend(_hard_split(sentence, chunk_size, overlap))
            else:
                units.append(sentence)
    return units


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    if overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    units = _split_into_units(text, chunk_size, overlap)
    if not units:
        return []

    chunks: list[TextChunk] = []
    index = 0
    current = ""
    for unit in units:
        candidate = f"{current} {unit}".strip() if current else unit
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        chunks.append(TextChunk(text=current, index=index))
        index += 1
        tail = current[-overlap:] if overlap else ""
        current = f"{tail} {unit}".strip() if tail else unit
        if len(current) > chunk_size:
            current = unit

    if current:
        chunks.append(TextChunk(text=current, index=index))
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

"""RAG query orchestration: retrieve relevant chunks, then generate a
grounded answer with citations."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.config import get_settings
from app.services.embedding import EmbeddingProvider
from app.services.llm import LLMProvider
from app.vectorstore import ScoredChunk, VectorStore

SYSTEM_PROMPT = """Answer the user's question using ONLY the context below.

Rules:
1. Base your answer strictly on the context. Do not use outside knowledge, and do not \
guess, infer, or speculate about anything the context does not explicitly state.
2. If the context does not contain the answer, reply exactly: \
"The provided documents don't contain enough information to answer that."
3. Be concise and directly answer the question first, then add supporting detail.
4. When you use a fact from the context, name the source file in parentheses.
5. If different parts of the context conflict or overlap, prefer the most specific, \
directly relevant statement over a general one."""


@dataclass(frozen=True, slots=True)
class RagAnswer:
    citations: list[ScoredChunk]


def _build_context(chunks: list[ScoredChunk]) -> str:
    if not chunks:
        return "No relevant documents were found."
    blocks = [
        f"[Source: {chunk.filename}, chunk {chunk.chunk_index}]\n{chunk.chunk_text}"
        for chunk in chunks
    ]
    return "\n\n---\n\n".join(blocks)


class RagService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        llm_provider: LLMProvider,
    ) -> None:
        self._embeddings = embedding_provider
        self._vector_store = vector_store
        self._llm = llm_provider
        self._settings = get_settings()

    async def retrieve(
        self, query: str, owner_id: uuid.UUID, document_ids: list[str] | None = None
    ) -> list[ScoredChunk]:
        query_vector = await self._embeddings.embed_query(query)
        return await self._vector_store.search(
            query_embedding=query_vector,
            owner_id=str(owner_id),
            top_k=self._settings.retrieval_top_k,
            score_threshold=self._settings.retrieval_score_threshold,
            document_ids=document_ids,
        )

    async def answer(
        self,
        query: str,
        owner_id: uuid.UUID,
        history: list[dict[str, str]],
        document_ids: list[str] | None = None,
    ) -> tuple[AsyncIterator[str], list[ScoredChunk]]:
        citations = await self.retrieve(query, owner_id, document_ids)
        context = _build_context(citations)
        system_prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}"
        stream = self._llm.stream_completion(
            system_prompt, [*history, {"role": "user", "content": query}]
        )
        return stream, citations

"""Unit tests for the text chunking logic used during document ingestion."""

import pytest

from app.services.ingestion import chunk_text


def test_chunk_text_splits_long_text_with_overlap() -> None:
    text = "word " * 500
    chunks = chunk_text(text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 100 for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_chunk_text_empty_input_returns_no_chunks() -> None:
    assert chunk_text("   ", chunk_size=100, overlap=10) == []


def test_chunk_text_rejects_overlap_greater_than_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        chunk_text("some text", chunk_size=50, overlap=50)


def test_chunk_text_short_text_returns_single_chunk() -> None:
    chunks = chunk_text("short text", chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].text == "short text"

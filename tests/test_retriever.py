import json
from pathlib import Path
from types import SimpleNamespace

import faiss
import numpy as np
import pytest

from src.indexing import FaqDocument, save_index_bundle
from src.retrieval import FaissRetriever, build_retriever


class FakeEmbedder:
    def embed(self, texts: list[str], role: str = "passage") -> np.ndarray:
        assert texts == ["환불 가능한가요?"]
        assert role == "query"
        return np.array([[1.0, 0.0]], dtype=np.float32)


def test_retriever_returns_top_results_in_score_order() -> None:
    index = faiss.IndexFlatIP(2)
    index.add(np.array([[1.0, 0.0], [0.8, 0.6], [0.0, 1.0]], dtype=np.float32))
    documents = [
        FaqDocument(1, "환불", "환불 기준", chunk_id="row-1", source_row_id=1),
        FaqDocument(2, "취소", "취소 기준", chunk_id="row-2", source_row_id=2),
        FaqDocument(3, "장소", "장소 안내", chunk_id="row-3", source_row_id=3),
    ]
    retriever = FaissRetriever(index=index, documents=documents, embedder=FakeEmbedder())

    results = retriever.search("환불 가능한가요?", top_k=2)

    assert [result.document.row_id for result in results] == [1, 2]
    assert results[0].score == pytest.approx(1.0)
    assert results[0].score >= results[1].score


def test_retriever_rejects_blank_question() -> None:
    retriever = FaissRetriever(
        index=faiss.IndexFlatIP(2),
        documents=[],
        embedder=SimpleNamespace(),
    )

    with pytest.raises(ValueError, match="질문"):
        retriever.search(" ")


def test_retriever_caps_top_k_to_document_count() -> None:
    index = faiss.IndexFlatIP(2)
    index.add(np.array([[1.0, 0.0]], dtype=np.float32))
    retriever = FaissRetriever(
        index=index,
        documents=[FaqDocument(1, "환불", "본문", chunk_id="row-1", source_row_id=1)],
        embedder=FakeEmbedder(),
    )

    assert len(retriever.search("환불 가능한가요?", top_k=3)) == 1


def test_build_retriever_loads_index_and_metadata(tmp_path: Path) -> None:
    documents = [
        FaqDocument(row_id=1, title="환불", body="환불 기준", chunk_id="row-1", source_row_id=1),
        FaqDocument(row_id=2, title="취소", body="취소 기준", chunk_id="row-2", source_row_id=2),
    ]
    index = faiss.IndexFlatIP(2)
    index.add(np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
    index_path = tmp_path / "faq.faiss"
    metadata_path = tmp_path / "metadata.json"
    save_index_bundle(index, documents, index_path, metadata_path)

    retriever = build_retriever(index_path, metadata_path, FakeEmbedder())

    results = retriever.search("환불 가능한가요?", top_k=2)
    assert [result.document.row_id for result in results] == [1, 2]

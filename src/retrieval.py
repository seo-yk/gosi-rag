"""질문 벡터와 FAQ 벡터를 비교해 관련 FAQ 검색."""

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol, Sequence

import faiss
import numpy as np

from src.indexing import EmbeddingRole, FaqDocument, load_documents


class Embedder(Protocol):
    def embed(self, texts: Sequence[str], role: EmbeddingRole = "passage") -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class SearchResult:
    """검색 문서와 유사도 점수 보관"""
    document: FaqDocument
    score: float


@dataclass(frozen=True, slots=True)
class SearchMetrics:
    """질문 임베딩과 벡터 검색 시간 보관"""

    embedding_latency_seconds: float
    search_latency_seconds: float


class FaissRetriever:
    """정규화된 질문 벡터로 FAISS Top K 검색 수행"""

    def __init__(
        self,
        index: faiss.Index,
        documents: Sequence[FaqDocument],
        embedder: Embedder,
    ) -> None:
        if index.ntotal != len(documents):
            raise ValueError("FAISS 벡터 개수와 문서 개수가 다릅니다.")
        self._index = index
        self._documents = list(documents)
        self._embedder = embedder

    def search(self, question: str, top_k: int = 3) -> list[SearchResult]:
        """질문 벡터화 후 Top K 검색 실행."""
        return self.search_with_metrics(question, top_k)[0]

    def search_with_metrics(
        self,
        question: str,
        top_k: int = 3,
    ) -> tuple[list[SearchResult], SearchMetrics]:
        """질문 임베딩 시간과 FAISS 검색 시간을 분리해 반환."""
        if not question.strip():
            raise ValueError("질문을 입력해야 합니다.")
        if top_k < 1:
            raise ValueError("top_k는 1 이상이어야 합니다.")
        if not self._documents:
            return [], SearchMetrics(embedding_latency_seconds=0.0, search_latency_seconds=0.0)

        embedding_started_at = perf_counter()
        query_vector = np.asarray(self._embedder.embed([question], role="query"), dtype=np.float32).copy()
        embedding_latency_seconds = perf_counter() - embedding_started_at
        faiss.normalize_L2(query_vector)

        search_started_at = perf_counter()
        scores, positions = self._index.search(query_vector, min(top_k, len(self._documents)))
        search_latency_seconds = perf_counter() - search_started_at
        results = [
            SearchResult(self._documents[int(position)], float(score))
            for score, position in zip(scores[0], positions[0], strict=True)
            if position >= 0
        ]
        return results, SearchMetrics(
            embedding_latency_seconds=embedding_latency_seconds,
            search_latency_seconds=search_latency_seconds,
        )


def build_retriever(index_path: str | Path, metadata_path: str | Path, embedder: Embedder) -> FaissRetriever:
    """인덱스와 메타데이터 로드 후 검색기 생성"""
    return FaissRetriever(
        index=faiss.read_index(str(index_path)),
        documents=load_documents(metadata_path),
        embedder=embedder,
    )

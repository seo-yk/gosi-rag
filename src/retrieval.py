"""질문 벡터와 FAQ 벡터를 비교해 관련 FAQ 검색"""

from dataclasses import dataclass
from typing import Protocol, Sequence

import faiss
import numpy as np

from src.indexing import EmbeddingRole, FaqDocument


class Embedder(Protocol):
    def embed(self, texts: Sequence[str], role: EmbeddingRole = "passage") -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class SearchResult:
    """검색 문서와 유사도 점수 보관"""
    document: FaqDocument
    score: float


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
        if not question.strip():
            raise ValueError("질문을 입력해야 합니다.")
        if top_k < 1:
            raise ValueError("top_k는 1 이상이어야 합니다.")
        if not self._documents:
            return []

        query_vector = np.asarray(self._embedder.embed([question], role="query"), dtype=np.float32).copy()
        faiss.normalize_L2(query_vector)
        scores, positions = self._index.search(query_vector, min(top_k, len(self._documents)))
        return [
            SearchResult(self._documents[int(position)], float(score))
            for score, position in zip(scores[0], positions[0], strict=True)
            if position >= 0
        ]

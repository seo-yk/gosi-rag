"""검색 실험을 실행하고 청킹, Top K, 임베딩 입력 필드 비교"""

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import faiss
from dotenv import load_dotenv


def _load_project_env() -> None:
    """환경 변수 파일 우선순위 로드"""
    env_file = os.environ.get("FAQ_ENV_FILE", "").strip()
    if env_file:
        load_dotenv(env_file, override=True)
        return
    load_dotenv(".env.local", override=True)
    load_dotenv(".env", override=False)


from src.indexing import (
    ChunkingMode,
    EmbeddingMode,
    EmbeddingProvider,
    build_embedder,
    index_bundle_paths,
    load_documents,
)
from src.retrieval import FaissRetriever


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """검색 성능 지표와 실패 FAQ 목록 보관"""
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    failed_expected_ids: tuple[int, ...]


def evaluate_rankings(rankings: Sequence[tuple[int, Sequence[int]]]) -> EvaluationResult:
    """정답 순위 목록을 Hit@K와 MRR로 집계"""

    if not rankings:
        raise ValueError("평가 결과가 비어 있습니다.")
    hit_1 = 0
    hit_3 = 0
    hit_5 = 0
    reciprocal_rank_sum = 0.0
    failed: list[int] = []
    for expected_id, retrieved_ids in rankings:
        ids = list(retrieved_ids)
        hit_1 += int(bool(ids) and ids[0] == expected_id)
        hit_3 += int(expected_id in ids[:3])
        hit_5 += int(expected_id in ids[:5])
        if expected_id in ids:
            reciprocal_rank_sum += 1 / (ids.index(expected_id) + 1)
        else:
            failed.append(expected_id)
    total = len(rankings)
    return EvaluationResult(hit_1 / total, hit_3 / total, hit_5 / total, reciprocal_rank_sum / total, tuple(failed))


def read_questions(path: Path) -> list[tuple[str, int]]:
    """평가 질문셋 로드"""
    with path.open(encoding="utf-8-sig", newline="") as file:
        return [
            (row["question"].strip(), int(row["expected_row_id"]))
            for row in csv.DictReader(file)
        ]


def evaluate_index(
    index_path: Path,
    metadata_path: Path,
    questions: list[tuple[str, int]],
    embedder,
    top_k: int,
) -> EvaluationResult:
    """단일 인덱스 기준 검색 성능 평가 실행"""
    retriever = FaissRetriever(
        index=faiss.read_index(str(index_path)),
        documents=load_documents(metadata_path),
        embedder=embedder,
    )
    rankings = [
        (
            expected_id,
            [result.document.resolved_row_id for result in retriever.search(question, top_k=top_k)],
        )
        for question, expected_id in questions
    ]
    return evaluate_rankings(rankings)


def _experiment_rows(
    index_dir: Path,
    questions: list[tuple[str, int]],
    embedders: dict[EmbeddingProvider, object],
    chunking_modes: Sequence[ChunkingMode],
    embedding_modes: Sequence[EmbeddingMode],
    top_ks: Sequence[int],
) -> list[dict[str, object]]:
    """실험 조합별 평가 결과 행 생성"""
    rows: list[dict[str, object]] = []
    for chunking_mode in chunking_modes:
        for embedding_provider, embedder in embedders.items():
            for embedding_mode in embedding_modes:
                index_path, metadata_path = index_bundle_paths(index_dir, chunking_mode, embedding_provider, embedding_mode)
                for top_k in top_ks:
                    result = evaluate_index(index_path, metadata_path, questions, embedder, top_k)
                    rows.append(
                        {
                            "chunking_mode": chunking_mode,
                            "embedding_provider": embedding_provider,
                            "embedding_mode": embedding_mode,
                            "top_k": top_k,
                            "hit_at_1": result.hit_at_1,
                            "hit_at_3": result.hit_at_3,
                            "hit_at_5": result.hit_at_5,
                            "mrr": result.mrr,
                            "failed_expected_ids": "|".join(map(str, result.failed_expected_ids)),
                        }
                    )
    return rows


def main() -> None:
    """검색 성능 평가 CLI 실행"""
    parser = argparse.ArgumentParser(description="청킹, Top K, 임베딩 입력 필드의 검색 성능을 평가합니다.")
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--index-dir", type=Path, default=Path("index"))
    parser.add_argument("--output", type=Path, default=Path("output/evaluation_summary.csv"))
    parser.add_argument("--providers", nargs="+", default=["openai", "local"])
    parser.add_argument("--chunking-modes", nargs="+", default=["row", "paragraph", "file"])
    parser.add_argument("--embedding-modes", nargs="+", default=["title", "title_body"])
    parser.add_argument("--top-ks", nargs="+", type=int, default=[3, 5])
    args = parser.parse_args()

    _load_project_env()
    embedders = {provider: build_embedder(provider, os.environ) for provider in args.providers}
    questions = read_questions(args.questions)
    rows = _experiment_rows(
        args.index_dir,
        questions,
        embedders,
        tuple(args.chunking_modes),
        tuple(args.embedding_modes),
        tuple(args.top_ks),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

"""검색 실험을 실행하고 청킹, Top K, 임베딩 입력 필드 비교"""

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.config import load_project_env

from src.indexing import (
    ChunkingMode,
    EmbeddingMode,
    EmbeddingProvider,
    build_embedder,
    index_bundle_paths,
)
from src.retrieval import build_retriever


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """검색 성능 지표와 실패 FAQ 목록 보관"""
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    all_hit_at_1: float
    all_hit_at_3: float
    all_hit_at_5: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    failed_expected_ids: tuple[str, ...]


def evaluate_rankings(rankings: Sequence[tuple[int | Sequence[int], Sequence[int]]]) -> EvaluationResult:
    """정답 순위 목록을 any-hit, all-hit, recall, MRR로 집계한다."""

    if not rankings:
        raise ValueError("평가 결과가 비어 있습니다.")
    hit_1 = 0
    hit_3 = 0
    hit_5 = 0
    all_hit_1 = 0
    all_hit_3 = 0
    all_hit_5 = 0
    recall_1 = 0.0
    recall_3 = 0.0
    recall_5 = 0.0
    reciprocal_rank_sum = 0.0
    failed: list[str] = []
    for expected, retrieved_ids in rankings:
        expected_ids = {expected} if isinstance(expected, int) else set(expected)
        if not expected_ids:
            raise ValueError("정답 ID가 비어 있습니다.")
        ids = list(retrieved_ids)
        retrieved_1 = set(ids[:1])
        retrieved_3 = set(ids[:3])
        retrieved_5 = set(ids[:5])
        hit_1 += int(bool(expected_ids & retrieved_1))
        hit_3 += int(bool(expected_ids & retrieved_3))
        hit_5 += int(bool(expected_ids & retrieved_5))
        all_hit_1 += int(expected_ids <= retrieved_1)
        all_hit_3 += int(expected_ids <= retrieved_3)
        all_hit_5 += int(expected_ids <= retrieved_5)
        recall_1 += len(expected_ids & retrieved_1) / len(expected_ids)
        recall_3 += len(expected_ids & retrieved_3) / len(expected_ids)
        recall_5 += len(expected_ids & retrieved_5) / len(expected_ids)
        relevant_ranks = [ids.index(expected_id) + 1 for expected_id in expected_ids if expected_id in ids]
        if relevant_ranks:
            reciprocal_rank_sum += 1 / min(relevant_ranks)
        else:
            failed.append("|".join(map(str, sorted(expected_ids))))
    total = len(rankings)
    return EvaluationResult(
        hit_1 / total,
        hit_3 / total,
        hit_5 / total,
        reciprocal_rank_sum / total,
        all_hit_1 / total,
        all_hit_3 / total,
        all_hit_5 / total,
        recall_1 / total,
        recall_3 / total,
        recall_5 / total,
        tuple(failed),
    )


def read_questions(path: Path) -> list[tuple[str, tuple[int, ...]]]:
    """평가 질문셋 로드"""
    with path.open(encoding="utf-8-sig", newline="") as file:
        return [
            (
                row["question"].strip(),
                tuple(int(value.strip()) for value in row["target_answer_no"].split(",")),
            )
            for row in csv.DictReader(file)
        ]


def evaluate_index(
    index_path: Path,
    metadata_path: Path,
    questions: list[tuple[str, tuple[int, ...]]],
    embedder,
    top_k: int,
) -> EvaluationResult:
    """단일 인덱스 기준 검색 성능 평가 실행"""
    retriever = build_retriever(index_path, metadata_path, embedder)
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
    questions: list[tuple[str, tuple[int, ...]]],
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
                            "all_hit_at_1": result.all_hit_at_1,
                            "all_hit_at_3": result.all_hit_at_3,
                            "all_hit_at_5": result.all_hit_at_5,
                            "recall_at_1": result.recall_at_1,
                            "recall_at_3": result.recall_at_3,
                            "recall_at_5": result.recall_at_5,
                            "failed_expected_ids": ";".join(result.failed_expected_ids),
                        }
                    )
    return rows


def main() -> None:
    """검색 성능 평가 CLI 실행"""
    parser = argparse.ArgumentParser(description="청킹, Top K, 임베딩 입력 필드의 검색 성능을 평가합니다.")
    parser.add_argument("--questions", type=Path, default=Path("evaluation/inputs/retrieval_question.csv"))
    parser.add_argument("--index-dir", type=Path, default=Path("index"))
    parser.add_argument("--output", type=Path, default=Path("output/evaluation_summary.csv"))
    parser.add_argument("--providers", nargs="+", default=["openai", "local"])
    parser.add_argument("--chunking-modes", nargs="+", default=["row", "paragraph", "file"])
    parser.add_argument("--embedding-modes", nargs="+", default=["title", "title_body"])
    parser.add_argument("--top-ks", nargs="+", type=int, default=[3, 5])
    args = parser.parse_args()

    load_project_env()
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

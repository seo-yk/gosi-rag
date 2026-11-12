"""검색 실험을 실행하고 청킹, 임베딩 모델, 임베딩 입력 필드 비교 (평가셋 v1.3)

지표 (evaluation/inputs/README.md "채점 규칙")
- Hit@K: 모든 필수 그룹에서 FAQ가 1개 이상 Top-K 안에 있으면 1
- Group Recall@K: 충족된 그룹 수 ÷ 전체 그룹 수
- MRR: 필수 그룹이 1개인 문항만. 그룹 내 FAQ 중 가장 높은 순위의 역수
- 범위 밖 문항: 지표에 넣지 않고 Top-1 유사도와 검색된 FAQ 번호만 기록(임곗값 없음)

검색 깊이(--depth, 기본 5)만큼 한 번 검색해 @1, @3, @5를 함께 계산한다.
"""

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from evaluation.scripts.evalset import (
    EvalQuestion,
    OutOfScopeQuestion,
    format_groups,
    group_recall,
    is_hit,
    read_evalset,
    read_out_of_scope,
    reciprocal_rank,
)
from src.config import load_project_env
from src.indexing import (
    ChunkingMode,
    EmbeddingMode,
    EmbeddingProvider,
    build_embedder,
    index_bundle_paths,
)
from src.retrieval import build_retriever

KS = (1, 3, 5)
ALL_TYPES = "전체"


@dataclass(frozen=True, slots=True)
class GroupEvaluationResult:
    """문항 묶음 하나의 검색 지표"""

    questions: int
    single_questions: int
    hit_at: dict[int, float]
    group_recall_at: dict[int, float]
    mrr: float | None  # 단일 그룹 문항이 없으면 None
    failed_ids: tuple[int, ...]  # Hit@max(K) 실패 문항


def evaluate_groups(
    rankings: Sequence[tuple[EvalQuestion, Sequence[int]]],
    ks: Sequence[int] = KS,
) -> GroupEvaluationResult:
    """문항별 검색 결과(FAQ 연번 순위)를 그룹 기준으로 집계"""
    if not rankings:
        raise ValueError("평가 결과가 비어 있습니다.")
    total = len(rankings)
    hit_at = {k: sum(is_hit(q.required_faqs, ids, k) for q, ids in rankings) / total for k in ks}
    recall_at = {k: sum(group_recall(q.required_faqs, ids, k) for q, ids in rankings) / total for k in ks}
    singles = [(q, ids) for q, ids in rankings if q.is_single]
    mrr = sum(reciprocal_rank(q.required_faqs, ids) for q, ids in singles) / len(singles) if singles else None
    failed = tuple(q.id for q, ids in rankings if not is_hit(q.required_faqs, ids, max(ks)))
    return GroupEvaluationResult(total, len(singles), hit_at, recall_at, mrr, failed)


def evaluate_by_type(
    rankings: Sequence[tuple[EvalQuestion, Sequence[int]]],
    ks: Sequence[int] = KS,
) -> dict[str, GroupEvaluationResult]:
    """전체와 유형별(type) 지표"""
    results = {ALL_TYPES: evaluate_groups(rankings, ks)}
    for question_type in sorted({q.type for q, _ in rankings}):
        results[question_type] = evaluate_groups([(q, ids) for q, ids in rankings if q.type == question_type], ks)
    return results


def summary_row(config: dict[str, object], question_type: str, result: GroupEvaluationResult) -> dict[str, object]:
    """결과 CSV 한 행"""
    row: dict[str, object] = dict(config)
    row["type"] = question_type
    row["questions"] = result.questions
    row["single_questions"] = result.single_questions
    for k, value in result.hit_at.items():
        row[f"hit_at_{k}"] = round(value, 4)
    for k, value in result.group_recall_at.items():
        row[f"group_recall_at_{k}"] = round(value, 4)
    row["mrr_single"] = "" if result.mrr is None else round(result.mrr, 4)
    row["failed_ids"] = ";".join(map(str, result.failed_ids))
    return row


def embedding_model_name(embedder: object) -> str:
    """결과 기록용 임베딩 모델 이름"""
    return str(getattr(embedder, "model", None) or getattr(embedder, "model_name", ""))


def run_experiments(
    index_dir: Path,
    eval_set_name: str,
    questions: Sequence[EvalQuestion],
    out_of_scope: Sequence[OutOfScopeQuestion],
    embedders: dict[EmbeddingProvider, object],
    chunking_modes: Sequence[ChunkingMode],
    embedding_modes: Sequence[EmbeddingMode],
    depth: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """조합별 요약, 문항별 상세, 범위 밖 기록 행 생성"""
    summary, details, oos_rows = [], [], []
    for chunking_mode in chunking_modes:
        for provider, embedder in embedders.items():
            for embedding_mode in embedding_modes:
                index_path, metadata_path = index_bundle_paths(index_dir, chunking_mode, provider, embedding_mode)
                retriever = build_retriever(index_path, metadata_path, embedder)
                config = {
                    "eval_set": eval_set_name,
                    "index_dir": str(index_dir),
                    "chunking_mode": chunking_mode,
                    "embedding_provider": provider,
                    "embedding_model": embedding_model_name(embedder),
                    "embedding_mode": embedding_mode,
                    "depth": depth,
                }

                rankings = []
                for question in questions:
                    results = retriever.search(question.question, top_k=depth)
                    ids = [result.document.resolved_row_id for result in results]
                    rankings.append((question, ids))
                    details.append({
                        **config,
                        "id": question.id,
                        "type": question.type,
                        "required_faqs": format_groups(question.required_faqs),
                        "retrieved_ids": "|".join(map(str, ids)),
                        **{f"hit_at_{k}": int(is_hit(question.required_faqs, ids, k)) for k in KS},
                    })
                for question_type, result in evaluate_by_type(rankings).items():
                    summary.append(summary_row(config, question_type, result))

                for question in out_of_scope:
                    results = retriever.search(question.question, top_k=depth)
                    oos_rows.append({
                        **config,
                        "id": question.id,
                        "difficulty": question.difficulty,
                        "top1_id": results[0].document.resolved_row_id if results else "",
                        "top1_score": round(results[0].score, 4) if results else "",
                        "retrieved_ids": "|".join(str(r.document.resolved_row_id) for r in results),
                        "retrieved_scores": "|".join(f"{r.score:.4f}" for r in results),
                        "similar_faqs": "|".join(map(str, question.similar_faqs)),
                    })
    return summary, details, oos_rows


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """검색 성능 평가 CLI 실행"""
    parser = argparse.ArgumentParser(description="평가셋 v1.3으로 청킹, 임베딩 모델, 임베딩 입력 필드의 검색 성능을 평가합니다.")
    parser.add_argument("--questions", type=Path, default=Path("evaluation/inputs/evalset_v1.3.jsonl"))
    parser.add_argument("--out-of-scope", type=Path, default=Path("evaluation/inputs/evalset_out_of_scope_v1.3.jsonl"))
    parser.add_argument("--index-dir", type=Path, default=Path("index/faq_v2"),
                        help="src/indexing.py --output 으로 만든 인덱스 폴더")
    parser.add_argument("--output", type=Path, default=Path("output/retrieval_summary.csv"))
    parser.add_argument("--details-output", type=Path, default=Path("output/retrieval_details.csv"))
    parser.add_argument("--out-of-scope-output", type=Path, default=Path("output/retrieval_out_of_scope.csv"))
    parser.add_argument("--providers", nargs="+", default=["openai", "local"])
    parser.add_argument("--chunking-modes", nargs="+", default=["row", "paragraph", "file"])
    parser.add_argument("--embedding-modes", nargs="+", default=["title", "title_body"])
    parser.add_argument("--depth", type=int, default=max(KS), help="문항당 검색 개수(최소 5)")
    args = parser.parse_args()
    if args.depth < max(KS):
        parser.error(f"--depth는 {max(KS)} 이상이어야 합니다.")

    load_project_env()
    questions = read_evalset(args.questions)
    out_of_scope = read_out_of_scope(args.out_of_scope) if args.out_of_scope else []
    embedders = {provider: build_embedder(provider, os.environ) for provider in args.providers}
    summary, details, oos_rows = run_experiments(
        args.index_dir,
        args.questions.stem,
        questions,
        out_of_scope,
        embedders,
        tuple(args.chunking_modes),
        tuple(args.embedding_modes),
        args.depth,
    )
    write_csv(args.output, summary)
    write_csv(args.details_output, details)
    write_csv(args.out_of_scope_output, oos_rows)
    combinations = len(details) // len(questions)
    print(f"{args.questions.stem}: {len(questions)}문항, 범위 밖 {len(out_of_scope)}문항, 조합 {combinations}개 → {args.output}")


if __name__ == "__main__":
    main()

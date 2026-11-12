"""검색 실험을 실행하고 청킹, 임베딩 모델, 임베딩 입력 필드 비교 (평가셋 v1.3)

지표 (evaluation/evalset/README.md "채점 규칙")
- Hit@K: 모든 필수 그룹에서 FAQ가 1개 이상 Top-K 안에 있으면 1
- Group Recall@K: 충족된 그룹 수 ÷ 전체 그룹 수
- MRR: 필수 그룹이 1개인 문항만. 그룹 내 FAQ 중 가장 높은 순위의 역수
- 범위 밖 문항: 지표에 넣지 않고 Top-1 유사도와 검색된 FAQ 번호만 기록(임곗값 없음)

검색 깊이(--depth, 기본 5)만큼 서로 다른 FAQ를 한 번에 구해 @1, @3, @5를 함께 계산한다.
청크는 FAQ 연번 기준으로 중복을 제거한다(문장 청킹 등).
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
    default_index_dir,
    embedder_model_name,
    index_bundle_paths,
    is_supported_combination,
    load_documents,
    load_index_manifest,
    model_slug,
    resolve_provider,
)
from src.retrieval import build_retriever

KS = (1, 3, 5)
ALL_TYPES = "전체"
SINGLE_ONLY = "단일 그룹 전체"  # 필수 그룹이 1개인 문항(복수근거 제외)
CHUNK_OVERSAMPLE = 10  # FAQ 중복 제거 전에 depth × 10개 청크를 검색


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


def evaluate_subsets(
    rankings: Sequence[tuple[EvalQuestion, Sequence[int]]],
    ks: Sequence[int] = KS,
) -> dict[str, GroupEvaluationResult]:
    """전체, 단일 그룹 전체, 유형별, 작성자별 지표

    - 복수근거 문항은 Hit@1이 구조적으로 0이므로 단일 그룹 문항만 모은 행을 따로 낸다.
    - 작성자별(본인/Claude) 행은 질문 작성 방식에 따른 편향을 점검하는 용도다.
    """
    results = {ALL_TYPES: evaluate_groups(rankings, ks)}
    singles = [(q, ids) for q, ids in rankings if q.is_single]
    if singles:
        results[SINGLE_ONLY] = evaluate_groups(singles, ks)
    for question_type in sorted({q.type for q, _ in rankings}):
        results[f"유형: {question_type}"] = evaluate_groups([(q, ids) for q, ids in rankings if q.type == question_type], ks)
    for author in sorted({q.written_by for q, _ in rankings if q.written_by}):
        results[f"작성: {author}"] = evaluate_groups([(q, ids) for q, ids in rankings if q.written_by == author], ks)
    return results


def summary_row(config: dict[str, object], subset: str, result: GroupEvaluationResult) -> dict[str, object]:
    """결과 CSV 한 행"""
    row: dict[str, object] = dict(config)
    row["subset"] = subset
    row["questions"] = result.questions
    row["single_questions"] = result.single_questions
    for k, value in result.hit_at.items():
        row[f"hit_at_{k}"] = round(value, 4)
    for k, value in result.group_recall_at.items():
        row[f"group_recall_at_{k}"] = round(value, 4)
    row["mrr_single"] = "" if result.mrr is None else round(result.mrr, 4)
    row["failed_ids"] = ";".join(map(str, result.failed_ids))
    return row


def unique_faq_ranking(results: Sequence[object], depth: int) -> list[tuple[int, float]]:
    """청크 검색 결과를 FAQ 연번 기준으로 중복 제거해 상위 depth개 (연번, 점수) 반환

    문장·문단 청킹에서는 같은 FAQ의 청크가 여러 개 검색된다. FAQ마다 가장 높은 순위의 청크만 남긴다.
    row 청킹에서는 결과가 바뀌지 않는다.
    """
    ranked: list[tuple[int, float]] = []
    seen: set[int] = set()
    for result in results:
        faq_id = result.document.resolved_row_id
        if faq_id in seen:
            continue
        seen.add(faq_id)
        ranked.append((faq_id, float(result.score)))
        if len(ranked) == depth:
            break
    return ranked


class QueryCachingEmbedder:
    """질문 임베딩을 캐시하는 래퍼. 같은 모델의 여러 인덱스(청킹·임베딩 입력 조합)에서 질문 벡터를 한 번만 만든다.

    조합마다 질문 벡터가 완전히 같아지고(비교 공정성), API 호출 수도 줄어든다.
    """

    def __init__(self, embedder: object) -> None:
        self._embedder = embedder
        self._cache: dict[str, object] = {}
        self.query_calls = 0

    def __getattr__(self, name: str) -> object:
        return getattr(self._embedder, name)

    def embed(self, texts: Sequence[str], role: str = "passage"):
        if role != "query" or len(texts) != 1:
            return self._embedder.embed(texts, role=role)
        text = texts[0]
        if text not in self._cache:
            self._cache[text] = self._embedder.embed([text], role="query")
            self.query_calls += 1
        return self._cache[text]


def check_index(index_path: Path, metadata_path: Path, embedder: object, embedding_mode: str,
                questions: Sequence[EvalQuestion]) -> dict[str, object]:
    """인덱스가 지금 임베딩 모델로 만들어졌는지, 정답 FAQ가 모두 들어 있는지 확인하고 manifest 반환"""
    manifest = load_index_manifest(index_path)
    model = embedder_model_name(embedder)
    if manifest["embedding_model"] != model:
        raise SystemExit(f"{index_path}: 인덱스 모델({manifest['embedding_model']})과 질문 임베딩 모델({model})이 다릅니다.")
    if embedding_mode not in manifest["embedding_modes"]:
        raise SystemExit(f"{index_path}: manifest에 {embedding_mode} 인덱스 기록이 없습니다.")
    indexed = {document.resolved_row_id for document in load_documents(metadata_path)}
    missing = sorted({faq_id for q in questions for group in q.required_faqs for faq_id in group} - indexed)
    if missing:
        raise SystemExit(f"{index_path}: 정답 FAQ가 인덱스에 없습니다: {missing}")
    return manifest


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
                if not is_supported_combination(chunking_mode, embedding_mode):
                    continue
                index_path, metadata_path = index_bundle_paths(index_dir, chunking_mode, provider, embedding_mode)
                manifest = check_index(index_path, metadata_path, embedder, embedding_mode, questions)
                retriever = build_retriever(index_path, metadata_path, embedder)
                config = {
                    "eval_set": eval_set_name,
                    "source_csv": manifest["source_csv"],
                    "source_sha256": str(manifest["source_sha256"])[:12],
                    "index_dir": str(index_dir),
                    "chunking_mode": chunking_mode,
                    "chunks": manifest["chunks"],
                    "embedding_provider": provider,
                    "embedding_model": manifest["embedding_model"],
                    "embedding_mode": embedding_mode,
                    "depth": depth,
                }

                rankings = []
                short_rankings: list[int] = []
                for question in questions:
                    ranked = unique_faq_ranking(retriever.search(question.question, top_k=depth * CHUNK_OVERSAMPLE), depth)
                    ids = [faq_id for faq_id, _ in ranked]
                    if len(ids) < depth:
                        short_rankings.append(question.id)
                    rankings.append((question, ids))
                    details.append({
                        **config,
                        "id": question.id,
                        "type": question.type,
                        "written_by": question.written_by,
                        "required_faqs": format_groups(question.required_faqs),
                        "retrieved_ids": "|".join(map(str, ids)),
                        **{f"hit_at_{k}": int(is_hit(question.required_faqs, ids, k)) for k in KS},
                    })
                if short_rankings:
                    print(f"경고: {chunking_mode}/{embedding_mode}에서 서로 다른 FAQ가 {depth}개 미만인 문항 {short_rankings}")
                for subset, result in evaluate_subsets(rankings).items():
                    summary.append(summary_row(config, subset, result))

                for question in out_of_scope:
                    ranked = unique_faq_ranking(retriever.search(question.question, top_k=depth * CHUNK_OVERSAMPLE), depth)
                    oos_rows.append({
                        **config,
                        "id": question.id,
                        "difficulty": question.difficulty,
                        "top1_id": ranked[0][0] if ranked else "",
                        "top1_score": round(ranked[0][1], 4) if ranked else "",
                        "retrieved_ids": "|".join(str(faq_id) for faq_id, _ in ranked),
                        "retrieved_scores": "|".join(f"{score:.4f}" for _, score in ranked),
                        "similar_faqs": "|".join(map(str, question.similar_faqs)),
                    })
    return summary, details, oos_rows


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Excel·Numbers에서 한글이 깨지지 않도록 BOM 포함 UTF-8
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """검색 성능 평가 CLI 실행"""
    parser = argparse.ArgumentParser(description="평가셋 v1.3으로 청킹, 임베딩 모델, 임베딩 입력 필드의 검색 성능을 평가합니다.")
    parser.add_argument("--questions", type=Path, default=Path("evaluation/evalset/evalset_v1.3.jsonl"))
    parser.add_argument("--out-of-scope", type=Path, default=Path("evaluation/evalset/evalset_out_of_scope_v1.3.jsonl"))
    parser.add_argument("--index-dir", type=Path, default=None, help="기본값 index/faq_v2/<모델 이름>")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--run-name", default=None,
                        help="결과 파일 이름 뒤에 붙일 이름. 기본값은 모델 이름(예: kure-v1)")
    parser.add_argument("--provider", choices=["openai", "local"], default=None, help="기본값 EMBEDDING_PROVIDER")
    parser.add_argument("--chunking-modes", nargs="+", default=["row", "sentence"])
    parser.add_argument("--embedding-modes", nargs="+", default=["title", "title_body"])
    parser.add_argument("--depth", type=int, default=max(KS), help="문항당 검색 개수(최소 5)")
    args = parser.parse_args()
    if args.depth < max(KS):
        parser.error(f"--depth는 {max(KS)} 이상이어야 합니다.")

    load_project_env()
    questions = read_evalset(args.questions)
    out_of_scope = read_out_of_scope(args.out_of_scope) if args.out_of_scope else []
    provider = resolve_provider(args.provider, os.environ)
    embedder = QueryCachingEmbedder(build_embedder(provider, os.environ))
    model_name = embedder_model_name(embedder)
    index_dir = args.index_dir or default_index_dir(model_name)
    run_name = model_slug(model_name) if args.run_name is None else args.run_name
    print(f"{model_name} ({provider}), 인덱스 {index_dir}")
    summary, details, oos_rows = run_experiments(
        index_dir,
        args.questions.stem,
        questions,
        out_of_scope,
        {provider: embedder},
        tuple(args.chunking_modes),
        tuple(args.embedding_modes),
        args.depth,
    )
    suffix = f"_{run_name}" if run_name else ""
    summary_path = args.output_dir / f"retrieval_summary{suffix}.csv"
    write_csv(summary_path, summary)
    write_csv(args.output_dir / f"retrieval_details{suffix}.csv", details)
    write_csv(args.output_dir / f"retrieval_out_of_scope{suffix}.csv", oos_rows)
    combinations = len(details) // len(questions)
    print(f"{args.questions.stem}: {len(questions)}문항, 범위 밖 {len(out_of_scope)}문항, 조합 {combinations}개 → {summary_path}")


if __name__ == "__main__":
    main()

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import faiss
from dotenv import load_dotenv
from openai import OpenAI

from src.indexing import OpenAIEmbedder, load_documents
from src.retrieval import FaissRetriever


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    hit_at_1: float
    hit_at_3: float
    mrr: float
    failed_expected_ids: tuple[int, ...]


def evaluate_rankings(rankings: Sequence[tuple[int, Sequence[int]]]) -> EvaluationResult:
    """정답 FAQ 순위를 Hit@1, Hit@3, MRR로 요약한다."""

    if not rankings:
        raise ValueError("평가 결과가 비어 있습니다.")
    hit_1 = 0
    hit_3 = 0
    reciprocal_rank_sum = 0.0
    failed: list[int] = []
    for expected_id, retrieved_ids in rankings:
        ids = list(retrieved_ids)
        hit_1 += int(bool(ids) and ids[0] == expected_id)
        hit_3 += int(expected_id in ids[:3])
        if expected_id in ids:
            reciprocal_rank_sum += 1 / (ids.index(expected_id) + 1)
        else:
            failed.append(expected_id)
    total = len(rankings)
    return EvaluationResult(hit_1 / total, hit_3 / total, reciprocal_rank_sum / total, tuple(failed))


def read_questions(path: Path) -> list[tuple[str, int]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return [
            (row["question"].strip(), int(row["expected_row_id"]))
            for row in csv.DictReader(file)
        ]


def evaluate_index(
    index_path: Path,
    metadata_path: Path,
    questions: list[tuple[str, int]],
    embedder: OpenAIEmbedder,
) -> tuple[float, float, float, tuple[int, ...]]:
    retriever = FaissRetriever(
        index=faiss.read_index(str(index_path)),
        documents=load_documents(metadata_path),
        embedder=embedder,
    )
    rankings = [
        (
            expected_id,
            [result.document.row_id for result in retriever.search(question, top_k=3)],
        )
        for question, expected_id in questions
    ]
    result = evaluate_rankings(rankings)
    return result.hit_at_1, result.hit_at_3, result.mrr, result.failed_expected_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="제목/제목+본문 검색 성능을 평가합니다.")
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--index-dir", type=Path, default=Path("index"))
    parser.add_argument("--output", type=Path, default=Path("output/evaluation_summary.csv"))
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY 환경변수가 필요합니다.")
    embedder = OpenAIEmbedder(
        OpenAI(api_key=api_key),
        os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
    )
    questions = read_questions(args.questions)
    rows = []
    for mode in ("title", "title_body"):
        hit_1, hit_3, mrr, failed = evaluate_index(
            args.index_dir / f"{mode}.faiss",
            args.index_dir / "metadata.json",
            questions,
            embedder,
        )
        rows.append(
            {
                "method": mode,
                "hit_at_1": hit_1,
                "hit_at_3": hit_3,
                "mrr": mrr,
                "failed_expected_ids": "|".join(map(str, failed)),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

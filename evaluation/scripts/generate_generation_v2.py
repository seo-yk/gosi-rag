"""고유 50문항 기준 Generation v2 답변 생성."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from time import perf_counter
from typing import Any


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from app import Settings, build_services
from src.config import load_project_env


OUTPUT_FIELDS = [
    "question_id",
    "question",
    "question_type",
    "evaluation_intent",
    "reference_answer",
    "relevant_answer_nos",
    "required_facts_json",
    "generation_provider",
    "generation_model",
    "retrieval_config",
    "retrieved_answer_nos",
    "retrieved_contexts",
    "generated_answer",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def render_contexts(results: list[Any]) -> str:
    return "\n\n".join(
        "[FAQ {row_id}]\n제목: {title}\n본문: {body}".format(
            row_id=result.document.resolved_row_id,
            title=result.document.title,
            body=result.document.body,
        )
        for result in results
    )


def append_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as file:
        return {
            row["question_id"].strip()
            for row in csv.DictReader(file)
            if row.get("question_id", "").strip()
        }


def generate(questions_path: Path, output_path: Path, settings: Settings) -> None:
    questions = read_jsonl(questions_path)
    done = completed_ids(output_path)
    retriever, generator = build_services(settings)
    retrieval_config = (
        f"{settings.chunking_mode}|{settings.embedding_provider}|"
        f"{settings.embedding_model}|{settings.embedding_mode}|top{settings.top_k}"
    )

    for index, item in enumerate(questions, start=1):
        question_id = str(item["question_id"])
        if question_id in done:
            print(f"[{index}/{len(questions)}] {question_id} already generated")
            continue

        started_at = perf_counter()
        results = retriever.search(str(item["question"]), top_k=settings.top_k)
        answer = generator.generate(str(item["question"]), results)
        append_row(
            output_path,
            {
                "question_id": question_id,
                "question": item["question"],
                "question_type": item["question_type"],
                "evaluation_intent": item["evaluation_intent"],
                "reference_answer": item["reference_answer"],
                "relevant_answer_nos": "|".join(map(str, item["relevant_answer_nos"])),
                "required_facts_json": json.dumps(item["required_facts"], ensure_ascii=False),
                "generation_provider": settings.generation_provider,
                "generation_model": settings.generation_model,
                "retrieval_config": retrieval_config,
                "retrieved_answer_nos": "|".join(
                    str(result.document.resolved_row_id) for result in results
                ),
                "retrieved_contexts": render_contexts(results),
                "generated_answer": answer.text,
            },
        )
        print(
            f"[{index}/{len(questions)}] {question_id} generated "
            f"({perf_counter() - started_at:.2f}s)"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path("evaluation/inputs/question_generation_v2.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/v2/gen_50_gpt-5.4-mini.csv"),
    )
    args = parser.parse_args()

    load_project_env()
    settings = Settings.from_mapping(os.environ)
    generate(args.questions, args.output, settings)


if __name__ == "__main__":
    main()

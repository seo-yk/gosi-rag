"""질문셋 기준으로 생성 답변만 저장, 모델별 CSV 생성을 위한 스크립트"""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from app import build_services
from app import Settings
from evaluation.scripts.evaluate_generation import GenerationQuestion, read_generation_questions, render_contexts
from src.config import load_project_env


def output_fieldnames() -> list[str]:
    """생성 결과 CSV 헤더 반환"""
    return [
        "question_id",
        "question",
        "question_type",
        "evaluation_intent",
        "target_answer_no",
        "target_answer",
        "supporting_answer_nos",
        "generation_provider",
        "generation_model",
        "retrieved_answer_nos",
        "retrieved_contexts",
        "generated_answer",
        "notes",
    ]


def build_output_row(
    item: GenerationQuestion,
    generation_provider: str,
    generation_model: str,
    retrieved_answer_nos: str,
    retrieved_contexts: str,
    generated_answer: str,
) -> dict[str, Any]:
    """질문과 생성 결과를 CSV 행으로 변환"""
    return {
        "question_id": item.question_id,
        "question": item.question,
        "question_type": item.question_type,
        "evaluation_intent": item.evaluation_intent,
        "target_answer_no": item.target_answer_no,
        "target_answer": item.target_answer,
        "supporting_answer_nos": item.supporting_answer_nos,
        "generation_provider": generation_provider,
        "generation_model": generation_model,
        "retrieved_answer_nos": retrieved_answer_nos,
        "retrieved_contexts": retrieved_contexts,
        "generated_answer": generated_answer,
        "notes": item.notes,
    }


def generate_answers(
    questions_path: Path,
    output_path: Path,
    settings: Settings,
) -> None:
    """질문셋 기준 생성 답변과 검색 컨텍스트만 저장"""
    questions = read_generation_questions(questions_path)
    retriever, generator = build_services(settings)

    total = len(questions)
    print(f"총 {total}개의 질문에 대해 답변 생성을 시작합니다. (모델: {settings.generation_model})")

    rows: list[dict[str, Any]] = []
    for i, item in enumerate(questions, 1):
        print(f"[{i}/{total}] '{item.question[:25]}...' 답변 생성 중...", end="", flush=True)
        from time import perf_counter
        start = perf_counter()
        
        results = retriever.search(item.question, top_k=settings.top_k)
        answer = generator.generate(item.question, results)
        
        elapsed = perf_counter() - start
        print(f" 완료! ({elapsed:.2f}초)")
        
        rows.append(
            build_output_row(
                item=item,
                generation_provider=settings.generation_provider,
                generation_model=settings.generation_model,
                retrieved_answer_nos="|".join(str(source.document.resolved_row_id) for source in answer.sources),
                retrieved_contexts=render_contexts(answer.sources),
                generated_answer=answer.text,
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=output_fieldnames())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """생성 답변 CSV 생성 CLI 실행"""
    parser = argparse.ArgumentParser(description="FAQ 생성 답변을 저장합니다.")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path("evaluation/inputs/evalset_v1.3.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/generated_answers.csv"),
    )
    args = parser.parse_args()

    load_project_env()
    settings = Settings.from_mapping(os.environ)
    generate_answers(args.questions, args.output, settings)


if __name__ == "__main__":
    main()

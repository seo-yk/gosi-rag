"""질문셋 기준으로 생성 답변만 저장, 모델별 CSV 생성을 위한 스크립트"""

import argparse
import csv
import os
import re
import sys
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Any


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from app import build_services
from app import Settings
from evaluation.scripts.evaluate_generation import GenerationQuestion, read_generation_questions, render_contexts
from src.config import load_project_env
from src.indexing import FaqDocument, load_faq_csv
from src.retrieval import SearchResult


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


def oracle_sources(item: GenerationQuestion, faqs: dict[int, FaqDocument]) -> list[SearchResult]:
    """정답 FAQ를 검색 결과 대신 근거로 쓰는 오라클 입력. 필수 그룹의 FAQ 전부(대체 정답 포함)를 순서대로 넣는다"""
    ids = list(dict.fromkeys(int(x) for x in re.findall(r"\d+", item.target_answer_no)))
    if not ids:
        raise ValueError(f"{item.question_id}: 정답 FAQ가 없어 오라클 입력을 만들 수 없습니다(범위 밖 문항은 제외).")
    return [SearchResult(faqs[faq_id], 1.0) for faq_id in ids]


def load_done_ids(path: Path) -> set[str]:
    """이미 생성한 문항(재실행 시 건너뜀)"""
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as file:
        return {row["question_id"] for row in csv.DictReader(file)}


def append_row(path: Path, row: dict[str, Any]) -> None:
    """한 문항씩 바로 저장해 중간에 실패해도 이어서 실행할 수 있게 한다"""
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=output_fieldnames())
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def generate_answers(
    questions_path: Path,
    output_path: Path,
    settings: Settings,
    oracle: bool = False,
    faq_path: Path = Path("data/faq_v2.csv"),
) -> None:
    """질문셋 기준 생성 답변과 근거 컨텍스트 저장

    oracle=False: 검색 결과 Top-K를 근거로 생성(실제 파이프라인)
    oracle=True: 정답 FAQ를 근거로 생성(검색 오류를 뺀 생성 품질의 상한)
    """
    questions = read_generation_questions(questions_path)
    retriever, generator = build_services(settings)
    faqs = {doc.resolved_row_id: doc for doc in load_faq_csv(faq_path)} if oracle else {}
    context_note = (
        f"context=oracle({faq_path})" if oracle else
        f"context=retrieval({settings.embedding_model}, {settings.chunking_mode}, {settings.embedding_mode}, top_k={settings.top_k})"
    )
    done = load_done_ids(output_path)

    total = len(questions)
    print(f"총 {total}개 질문 (이미 생성 {len(done)}개). 모델: {settings.generation_model}, {context_note}")

    for i, item in enumerate(questions, 1):
        if item.question_id in done:
            continue
        print(f"[{i}/{total}] '{item.question[:25]}...' 답변 생성 중...", end="", flush=True)
        start = perf_counter()

        sources = oracle_sources(item, faqs) if oracle else retriever.search(item.question, top_k=settings.top_k)
        answer = generator.generate(item.question, sources)

        print(f" 완료! ({perf_counter() - start:.2f}초)")
        item_with_note = replace(item, notes="; ".join(x for x in (item.notes, context_note) if x))
        append_row(
            output_path,
            build_output_row(
                item=item_with_note,
                generation_provider=settings.generation_provider,
                generation_model=settings.generation_model,
                retrieved_answer_nos="|".join(str(source.document.resolved_row_id) for source in answer.sources),
                retrieved_contexts=render_contexts(answer.sources),
                generated_answer=answer.text,
            ),
        )


def main() -> None:
    """생성 답변 CSV 생성 CLI 실행"""
    parser = argparse.ArgumentParser(description="FAQ 생성 답변을 저장합니다. 같은 출력 파일로 다시 실행하면 남은 문항만 생성합니다.")
    parser.add_argument("--questions", type=Path, default=Path("evaluation/evalset/evalset_v1.3.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("output/generated_answers.csv"))
    parser.add_argument("--oracle", action="store_true", help="검색 대신 정답 FAQ를 근거로 생성")
    args = parser.parse_args()

    load_project_env()
    settings = Settings.from_mapping(os.environ)
    generate_answers(args.questions, args.output, settings, oracle=args.oracle)


if __name__ == "__main__":
    main()

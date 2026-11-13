"""질문셋 기준으로 생성 답변만 저장, 모델별 CSV 생성을 위한 스크립트"""

import argparse
import csv
import os
import re
import sys
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
    """생성 결과 CSV 헤더 (평가셋 v1.3과 같은 이름 규칙)"""
    return [
        "id",               # 문항 번호
        "type",             # 문항 유형
        "question",         # 질문
        "required_faqs",    # 정답 FAQ (예: 78 & 272|251)
        "reference_answer", # 기준 답변
        "model",            # 생성 모델
        "context_setup",    # 근거 구성 (retrieval: 검색 모델·청킹·입력·Top-K / oracle: 정답 FAQ)
        "context_faqs",     # 모델에 근거로 준 FAQ 번호
        "context_text",     # 모델에 근거로 준 FAQ 제목·본문
        "answer",           # 생성 답변
    ]


def build_output_row(
    item: GenerationQuestion,
    model: str,
    context_setup: str,
    context_faqs: str,
    context_text: str,
    answer: str,
) -> dict[str, Any]:
    """질문과 생성 결과를 CSV 행으로 변환"""
    return {
        "id": item.question_id,
        "type": item.question_type,
        "question": item.question,
        "required_faqs": item.target_answer_no,
        "reference_answer": item.target_answer,
        "model": model,
        "context_setup": context_setup,
        "context_faqs": context_faqs,
        "context_text": context_text,
        "answer": answer,
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
        return {row.get("id") or row.get("question_id", "") for row in csv.DictReader(file)}


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
    context_setup = (
        f"oracle: {faq_path}" if oracle else
        f"retrieval: {settings.embedding_model}, {settings.chunking_mode}, {settings.embedding_mode}, top_k={settings.top_k}"
    )
    done = load_done_ids(output_path)

    total = len(questions)
    print(f"총 {total}개 질문 (이미 생성 {len(done)}개). 모델: {settings.generation_model}, {context_setup}")

    for i, item in enumerate(questions, 1):
        if item.question_id in done:
            continue
        print(f"[{i}/{total}] '{item.question[:25]}...' 답변 생성 중...", end="", flush=True)
        start = perf_counter()

        sources = oracle_sources(item, faqs) if oracle else retriever.search(item.question, top_k=settings.top_k)
        answer = generator.generate(item.question, sources)

        print(f" 완료! ({perf_counter() - start:.2f}초)")
        append_row(
            output_path,
            build_output_row(
                item=item,
                model=settings.generation_model,
                context_setup=context_setup,
                context_faqs="|".join(str(source.document.resolved_row_id) for source in answer.sources),
                context_text=render_contexts(answer.sources),
                answer=answer.text,
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

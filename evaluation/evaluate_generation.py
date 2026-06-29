"""생성 답변과 OpenRouter/Gemini judge를 이용한 FAQ 답변 품질 평가."""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from openai import OpenAI


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import Settings, build_services
from src.config import load_project_env
from src.generation import GeneratedAnswer
from src.retrieval import SearchResult


BATCH_JUDGE_SYSTEM_PROMPT = (
    "You are a strict evaluation judge. "
    "Analyze the candidate answer based on the question, reference answer, and retrieved contexts. "
    "You must return ONLY a valid JSON object matching the requested schema, without any markdown formatting or extra text."
)

BATCH_JUDGE_PROMPT = """Evaluate the candidate answer on 5 metrics.

Question:
{question}

Reference answer (Ground Truth):
{target_answer}

Retrieved FAQ contexts (for groundedness):
{contexts}

Candidate answer to evaluate:
{generated_answer}

Evaluation criteria:
1. similarity (integer 0 to 5):
   5 = essentially the same meaning
   4 = mostly the same meaning with only minor differences
   3 = partially correct but important details differ or are missing
   2 = limited overlap
   1 = mostly different
   0 = incorrect or unrelated

2. groundedness (integer 0 to 2):
   2 = fully grounded in the retrieved FAQ contexts (all claims supported)
   1 = partially grounded, but some claims are weakly supported or vague
   0 = not grounded in the retrieved contexts at all

3. correctness (integer 0 or 1):
   Does the candidate answer correctly answer the question according to the reference answer?
   1 = correct, 0 = incorrect.

4. completeness (integer 0 or 1):
   Does the candidate answer cover the essential information required by the question without important omissions?
   1 = yes, 0 = no.

5. hallucination (integer 0 or 1):
   Does the candidate answer avoid unsupported or invented claims beyond the reference answer?
   1 = yes (no hallucination), 0 = no (contains hallucination).

Return a JSON object in this exact format (no markdown blocks, no leading/trailing text):
{{
  "similarity": <integer>,
  "groundedness": <integer>,
  "correctness": <integer>,
  "completeness": <integer>,
  "hallucination": <integer>
}}
"""


@dataclass(frozen=True, slots=True)
class GenerationQuestion:
    """생성 평가용 질문 한 건."""

    question_id: str
    question: str
    question_type: str
    evaluation_intent: str
    target_answer_no: int
    target_answer: str
    supporting_answer_nos: str
    notes: str


@dataclass(frozen=True, slots=True)
class JudgeScores:
    """judge 원시 점수와 최종 판정."""

    similarity: int
    groundedness: int
    correctness: int
    completeness: int
    hallucination: int
    overall: str


@dataclass(frozen=True, slots=True)
class GenerationEvaluationSettings:
    """생성 평가 실행 설정."""

    app_settings: Settings
    openrouter_api_key: str
    gemini_api_key: str
    judge_provider: str
    judge_model: str

    @classmethod
    def from_mapping(cls, values: dict[str, str]) -> "GenerationEvaluationSettings":
        app_settings = Settings.from_mapping(values)
        judge_provider = values.get("FAQ_JUDGE_PROVIDER", "openrouter").strip().lower()
        gemini_api_key = values.get("GEMINI_API_KEY", "").strip()
        openrouter_api_key = values.get("OPENROUTER_API_KEY", "").strip()

        if judge_provider == "openrouter":
            if not openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY 환경변수가 필요합니다.")
            judge_model = values.get("OPENROUTER_JUDGE_MODEL", "meta-llama/llama-3.3-70b-instruct:free").strip()
            if not judge_model:
                judge_model = "meta-llama/llama-3.3-70b-instruct:free"
        elif judge_provider == "gemini":
            if not gemini_api_key:
                raise ValueError("GEMINI_API_KEY 환경변수가 필요합니다.")
            judge_model = values.get("GEMINI_JUDGE_MODEL", "gemini-2.5-flash").strip()
            if not judge_model:
                judge_model = "gemini-2.5-flash"
        else:
            raise ValueError(f"지원하지 않는 judge provider 입니다: {judge_provider}")

        return cls(
            app_settings=app_settings,
            openrouter_api_key=openrouter_api_key,
            gemini_api_key=gemini_api_key,
            judge_provider=judge_provider,
            judge_model=judge_model,
        )


class OpenRouterJudge:
    """OpenRouter 호환 judge 호출기."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=30.0,
            max_retries=1,
        )
        self.model = model

    def evaluate(self, question: str, target_answer: str, generated_answer: str, contexts: str) -> str:
        prompt = BATCH_JUDGE_PROMPT.format(
            question=question,
            target_answer=target_answer,
            generated_answer=generated_answer,
            contexts=contexts or "No retrieved FAQ context.",
        )
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": BATCH_JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return (response.choices[0].message.content or "").strip()


class GeminiJudge:
    """Gemini 호환 judge 호출기."""

    def __init__(self, api_key: str, model: str) -> None:
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self.model = model

    def evaluate(self, question: str, target_answer: str, generated_answer: str, contexts: str) -> str:
        prompt = BATCH_JUDGE_PROMPT.format(
            question=question,
            target_answer=target_answer,
            generated_answer=generated_answer,
            contexts=contexts or "No retrieved FAQ context.",
        )
        response = self._client.models.generate_content(
            model=self.model,
            contents=[
                BATCH_JUDGE_SYSTEM_PROMPT,
                prompt
            ]
        )
        return (response.text or "").strip()


def read_generation_questions(path: Path) -> list[GenerationQuestion]:
    """생성 평가 질문셋 로드."""
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows: list[GenerationQuestion] = []
        for row in csv.DictReader(file):
            rows.append(
                GenerationQuestion(
                    question_id=row["question_id"].strip(),
                    question=row["question"].strip(),
                    question_type=row["question_type"].strip(),
                    evaluation_intent=row["evaluation_intent"].strip(),
                    target_answer_no=int(row["target_answer_no"]),
                    target_answer=row["target_answer"].strip(),
                    supporting_answer_nos=row.get("supporting_answer_nos", "").strip(),
                    notes=row.get("notes", "").strip(),
                )
            )
        return rows


def render_contexts(results: Sequence[SearchResult]) -> str:
    """judge용 검색 컨텍스트 문자열 생성."""
    if not results:
        return "No retrieved FAQ context."
    return "\n\n".join(
        "[FAQ {row_id}]\n제목: {title}\n본문: {body}".format(
            row_id=result.document.resolved_row_id,
            title=result.document.title,
            body=result.document.body,
        )
        for result in results
    )


def similarity_to_ox(score: int) -> str:
    """유사도 점수를 O/X로 변환."""
    return "O" if score >= 4 else "X"


def binary_to_ox(score: int) -> str:
    """이진 점수를 O/X로 변환."""
    return "O" if score == 1 else "X"


def most_frequent_element(result: Sequence[str]) -> str:
    """동률 시 X를 우선하는 최빈값 선택."""
    count = Counter(result)
    most_common = count.most_common()
    if not most_common:
        return "X"
    if count.get("X", 0) == most_common[0][1]:
        return "X"
    return "O"


def parse_judge_json(text: str) -> JudgeScores:
    """JSON 결과 파싱하여 점수 및 최종 판정 구조화."""
    clean_text = text.strip()
    if clean_text.startswith("```"):
        lines = clean_text.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```"):
            clean_text = "\n".join(lines[1:-1]).strip()

    start = clean_text.find("{")
    end = clean_text.rfind("}")
    if start != -1 and end != -1:
        clean_text = clean_text[start:end+1]

    try:
        data = json.loads(clean_text)
        similarity = int(data.get("similarity", -1))
        groundedness = int(data.get("groundedness", -1))
        correctness = int(data.get("correctness", -1))
        completeness = int(data.get("completeness", -1))
        hallucination = int(data.get("hallucination", -1))
    except Exception:
        return JudgeScores(-1, -1, -1, -1, -1, "fail")

    if similarity not in range(6): similarity = -1
    if groundedness not in range(3): groundedness = -1
    if correctness not in {0, 1}: correctness = -1
    if completeness not in {0, 1}: completeness = -1
    if hallucination not in {0, 1}: hallucination = -1

    overall = most_frequent_element(
        [
            similarity_to_ox(similarity),
            binary_to_ox(correctness),
            binary_to_ox(completeness),
            binary_to_ox(hallucination),
        ]
    )
    return JudgeScores(
        similarity=similarity,
        groundedness=groundedness,
        correctness=correctness,
        completeness=completeness,
        hallucination=hallucination,
        overall="pass" if overall == "O" else "fail",
    )


def build_row_note(
    answer: GeneratedAnswer,
    judge_scores: JudgeScores,
    question_note: str,
) -> str:
    """디버깅용 note 생성."""
    parts: list[str] = []
    if question_note:
        parts.append(question_note)
    parts.append(f"overall={judge_scores.overall}")
    parts.append(
        "similarity={similarity}, groundedness={groundedness}, correctness={correctness}, "
        "completeness={completeness}, hallucination={hallucination}".format(
            similarity=judge_scores.similarity,
            groundedness=judge_scores.groundedness,
            correctness=judge_scores.correctness,
            completeness=judge_scores.completeness,
            hallucination=judge_scores.hallucination,
        )
    )
    if answer.sources:
        source_ids = "|".join(str(source.document.resolved_row_id) for source in answer.sources)
        parts.append(f"retrieved_answer_nos={source_ids}")
    return " | ".join(parts)


def output_fieldnames() -> list[str]:
    """결과 CSV 헤더 반환."""
    return [
        "question_id",
        "question",
        "question_type",
        "evaluation_intent",
        "target_answer_no",
        "target_answer",
        "supporting_answer_nos",
        "generated_answer",
        "retrieved_answer_nos",
        "similarity_score",
        "groundedness",
        "correctness",
        "completeness",
        "hallucination",
        "overall",
        "notes",
    ]


def evaluate_generation(
    questions_path: Path,
    output_path: Path,
    settings: GenerationEvaluationSettings,
) -> None:
    """질문셋 기준 생성+judge 평가 실행."""
    questions = read_generation_questions(questions_path)
    retriever, generator = build_services(settings.app_settings)
    
    if settings.judge_provider == "gemini":
        judge = GeminiJudge(settings.gemini_api_key, settings.judge_model)
    else:
        judge = OpenRouterJudge(settings.openrouter_api_key, settings.judge_model)

    rows: list[dict[str, Any]] = []
    for item in questions:
        results = retriever.search(item.question, top_k=settings.app_settings.top_k)
        answer = generator.generate(item.question, results)
        contexts = render_contexts(results)
        
        raw_judge_text = judge.evaluate(item.question, item.target_answer, answer.text, contexts)
        judge_scores = parse_judge_json(raw_judge_text)
        
        rows.append(
            {
                "question_id": item.question_id,
                "question": item.question,
                "question_type": item.question_type,
                "evaluation_intent": item.evaluation_intent,
                "target_answer_no": item.target_answer_no,
                "target_answer": item.target_answer,
                "supporting_answer_nos": item.supporting_answer_nos,
                "generated_answer": answer.text,
                "retrieved_answer_nos": "|".join(str(source.document.resolved_row_id) for source in answer.sources),
                "similarity_score": judge_scores.similarity,
                "groundedness": judge_scores.groundedness,
                "correctness": judge_scores.correctness,
                "completeness": judge_scores.completeness,
                "hallucination": judge_scores.hallucination,
                "overall": judge_scores.overall,
                "notes": build_row_note(answer, judge_scores, item.notes),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=output_fieldnames())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """생성 평가 CLI 실행."""
    parser = argparse.ArgumentParser(description="FAQ 생성 답변을 평가합니다.")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path("evaluation/generation_questions.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/generation_evaluation.csv"),
    )
    args = parser.parse_args()

    load_project_env()
    settings = GenerationEvaluationSettings.from_mapping(dict(os.environ))
    evaluate_generation(args.questions, args.output, settings)


if __name__ == "__main__":
    main()

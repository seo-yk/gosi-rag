"""생성 답변 결과 자동 평가 스크립트"""

import argparse
import csv
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, TypeVar

from openai import OpenAI


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from app import Settings, build_services
from evaluation.scripts.evalset import format_groups, read_evalset, read_out_of_scope
from src.config import load_project_env
from src.generation import GeneratedAnswer, check_not_truncated, ollama_context_length
from src.retrieval import SearchResult


BATCH_EVALUATION_SYSTEM_PROMPT = (
    "You are a strict evaluation judge. "
    "Analyze the candidate answer based on the question, reference answer, and retrieved contexts. "
    "You must return ONLY a valid JSON object matching the requested schema, without any markdown formatting or extra text."
)

BATCH_EVALUATION_PROMPT = """Evaluate the candidate answer on 3 metrics.

Question:
{question}

Reference answer (Ground Truth):
{target_answer}

Retrieved FAQ contexts (for groundedness):
{contexts}

Candidate answer to evaluate:
{generated_answer}

Evaluation criteria:
1. groundedness (integer 0 to 2):
   2 = fully grounded in the retrieved FAQ contexts (all claims supported)
   1 = partially grounded, but some claims are weakly supported or vague
   0 = not grounded in the retrieved contexts at all

2. correctness (integer 0 or 1):
   Does the candidate answer correctly answer the question according to the reference answer?
   1 = correct, 0 = incorrect.

3. completeness (integer 0 or 1):
   Does the candidate answer cover the essential information required by the question without important omissions?
   1 = yes, 0 = no.

Return a JSON object in this exact format (no markdown blocks, no leading/trailing text):
{{
  "groundedness": <integer>,
  "correctness": <integer>,
  "completeness": <integer>
}}
"""

BATCH_MULTI_EVALUATION_PROMPT_TEMPLATE = """Evaluate each candidate answer item on the same 3 metrics.

Return a JSON array only. Each array item must match this exact format:
[
  {{
    "question_id": "<question_id>",
    "groundedness": <integer>,
    "correctness": <integer>,
    "completeness": <integer>
  }}
]

Items to evaluate:
{items}
"""

GEMINI_REQUEST_INTERVAL_SECONDS = 12.0
GEMINI_MAX_RETRIES = 6
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class GenerationQuestion:
    """생성 평가용 질문 한 건"""

    question_id: str
    question: str
    question_type: str
    evaluation_intent: str
    target_answer_no: str
    target_answer: str
    supporting_answer_nos: str
    notes: str


@dataclass(frozen=True, slots=True)
class GeneratedAnswerRow:
    """생성 완료된 답변 한 건"""

    question_id: str
    question: str
    question_type: str
    evaluation_intent: str
    target_answer_no: str
    target_answer: str
    supporting_answer_nos: str
    generation_provider: str
    generation_model: str
    retrieved_answer_nos: str
    retrieved_contexts: str
    generated_answer: str
    notes: str


@dataclass(frozen=True, slots=True)
class EvaluationScores:
    """자동 평가 원시 점수와 최종 판정"""

    similarity: int
    groundedness: int
    correctness: int
    completeness: int
    unsupported_claims: int
    overall: str


@dataclass(frozen=True, slots=True)
class GenerationEvaluationSettings:
    """생성 평가 실행 설정"""

    app_settings: Settings
    evaluation_provider: str
    evaluation_model: str

    @classmethod
    def from_mapping(cls, values: dict[str, str]) -> "GenerationEvaluationSettings":
        app_settings = Settings.from_mapping(values)
        evaluation_provider = values.get("EVALUATION_PROVIDER", "ollama").strip().lower()

        if evaluation_provider != "ollama":
            raise ValueError(f"지원하지 않는 evaluation provider 입니다: {evaluation_provider}")
        if not app_settings.ollama_base_url:
            raise ValueError("OLLAMA_BASE_URL 환경변수가 필요합니다.")
        evaluation_model = values.get("EVALUATION_MODEL", "gemma3:4b").strip()
        if not evaluation_model:
            evaluation_model = "gemma3:4b"

        return cls(
            app_settings=app_settings,
            evaluation_provider=evaluation_provider,
            evaluation_model=evaluation_model,
        )


class OllamaEvaluator:
    """Ollama 기반 자동 평가 호출기"""

    def __init__(self, base_url: str, model: str) -> None:
        self._client = OpenAI(
            base_url=base_url,
            api_key="ollama",
            timeout=300.0,
            max_retries=1,
        )
        self.model = model
        self.context_limit = ollama_context_length(base_url, model)

    def evaluate(self, question: str, target_answer: str, generated_answer: str, contexts: str) -> str:
        prompt = BATCH_EVALUATION_PROMPT.format(
            question=question,
            target_answer=target_answer,
            generated_answer=generated_answer,
            contexts=contexts or "No retrieved FAQ context.",
        )
        return self._complete(prompt)

    def evaluate_batch(self, payload: str) -> str:
        return self._complete(payload)

    def _complete(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": BATCH_EVALUATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        check_not_truncated(response, self.context_limit, f"채점 모델 {self.model}")
        return (response.choices[0].message.content or "").strip()


OUT_OF_SCOPE_TYPE = "범위 밖"


def _is_out_of_scope_file(path: Path) -> bool:
    with path.open(encoding="utf-8") as file:
        first = next((line for line in file if line.strip()), "{}")
    return "required_faqs" not in json.loads(first)


PARSE_RETRIES = 2


def evaluate_with_retry(evaluator, question: str, target_answer: str, generated_answer: str, contexts: str,
                        retries: int = PARSE_RETRIES) -> EvaluationScores:
    """채점 결과 JSON을 읽지 못하면 다시 요청한다. 끝내 실패하면 overall='error'로 남긴다

    파싱 실패를 'fail'(오답)로 세면 채점기 오류가 답변 품질로 잘못 집계된다.
    """
    for _ in range(retries + 1):
        scores = parse_evaluation_json(evaluator.evaluate(question, target_answer, generated_answer, contexts))
        if min(scores.groundedness, scores.correctness, scores.completeness) >= 0:
            return scores
    return EvaluationScores(scores.similarity, scores.groundedness, scores.correctness, scores.completeness,
                            scores.unsupported_claims, "error")


def skip_out_of_scope(items: list[T]) -> list[T]:
    """범위 밖 문항은 자동 평가에서 뺀다(사람이 pass_rule로 판정)"""
    kept = [item for item in items if getattr(item, "question_type", "") != OUT_OF_SCOPE_TYPE]
    if len(kept) != len(items):
        print(f"범위 밖 {len(items) - len(kept)}문항은 자동 평가에서 제외합니다. 직접 판정하세요.")
    if not kept:
        raise SystemExit("자동 평가할 문항이 없습니다.")
    return kept


def read_generation_questions(path: Path) -> list[GenerationQuestion]:
    """생성 평가 질문셋 로드. .jsonl은 평가셋 v1.3(본 평가셋 또는 범위 밖), .csv는 1차 실험 형식

    범위 밖 문항은 기준 답변이 없다. 자동 평가 대상이 아니며, pass_rule에 따라 사람이 판정한다.
    """
    if path.suffix == ".jsonl" and _is_out_of_scope_file(path):
        return [
            GenerationQuestion(
                question_id=str(item.id),
                question=item.question,
                question_type=OUT_OF_SCOPE_TYPE,
                evaluation_intent="FAQ에 근거가 없음을 밝히는지",
                target_answer_no="",
                target_answer="",
                supporting_answer_nos="",
                notes=f"difficulty={item.difficulty}; similar_faqs={'|'.join(map(str, item.similar_faqs))}",
            )
            for item in read_out_of_scope(path)
        ]
    if path.suffix == ".jsonl":
        return [
            GenerationQuestion(
                question_id=str(item.id),
                question=item.question,
                question_type=item.type,
                evaluation_intent=item.intent,
                target_answer_no=format_groups(item.required_faqs),
                target_answer=item.reference_answer,
                supporting_answer_nos="|".join(map(str, item.supporting_faqs)),
                notes="",
            )
            for item in read_evalset(path)
        ]
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows: list[GenerationQuestion] = []
        for row in csv.DictReader(file):
            rows.append(
                GenerationQuestion(
                    question_id=row["question_id"].strip(),
                    question=row["question"].strip(),
                    question_type=row["question_type"].strip(),
                    evaluation_intent=row["evaluation_intent"].strip(),
                    target_answer_no=row["target_answer_no"].strip(),
                    target_answer=row["target_answer"].strip(),
                    supporting_answer_nos=row.get("supporting_answer_nos", "").strip(),
                    notes=row.get("notes", "").strip(),
                )
            )
        return rows


def read_generated_answers(path: Path) -> list[GeneratedAnswerRow]:
    """생성 결과 CSV 로드"""
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows: list[GeneratedAnswerRow] = []
        for row in csv.DictReader(file):
            rows.append(
                GeneratedAnswerRow(
                    question_id=row["question_id"].strip(),
                    question=row["question"].strip(),
                    question_type=row["question_type"].strip(),
                    evaluation_intent=row["evaluation_intent"].strip(),
                    target_answer_no=row["target_answer_no"].strip(),
                    target_answer=row["target_answer"].strip(),
                    supporting_answer_nos=row.get("supporting_answer_nos", "").strip(),
                    generation_provider=row.get("generation_provider", "").strip(),
                    generation_model=row.get("generation_model", "").strip(),
                    retrieved_answer_nos=row.get("retrieved_answer_nos", "").strip(),
                    retrieved_contexts=row.get("retrieved_contexts", "").strip(),
                    generated_answer=row["generated_answer"].strip(),
                    notes=row.get("notes", "").strip(),
                )
            )
        return rows


def render_contexts(results: Sequence[SearchResult]) -> str:
    """자동 평가용 검색 컨텍스트 문자열 생성"""
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
    """유사도 점수를 O/X로 변환"""
    return "O" if score >= 4 else "X"


def binary_to_ox(score: int) -> str:
    """이진 점수를 O/X로 변환"""
    return "O" if score == 1 else "X"


def unsupported_claims_to_ox(score: int) -> str:
    """지원되지 않은 주장 여부를 O/X로 변환"""
    return "X" if score == 1 else "O" if score == 0 else "X"


def most_frequent_element(result: Sequence[str]) -> str:
    """동률 시 X를 우선하는 최빈값 선택"""
    count = Counter(result)
    most_common = count.most_common()
    if not most_common:
        return "X"
    if count.get("X", 0) == most_common[0][1]:
        return "X"
    return "O"


def parse_evaluation_json(text: str) -> EvaluationScores:
    """JSON 결과 파싱하여 점수 및 최종 판정 구조화"""
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
        unsupported_claims = int(data.get("unsupported_claims", -1))
    except Exception:
        return EvaluationScores(-1, -1, -1, -1, -1, "fail")

    if similarity not in range(6):
        if 0 <= similarity <= 100:
            if similarity >= 90:
                similarity = 5
            elif similarity >= 70:
                similarity = 4
            elif similarity >= 50:
                similarity = 3
            elif similarity >= 30:
                similarity = 2
            elif similarity > 0:
                similarity = 1
            else:
                similarity = 0
        else:
            similarity = -1
    if groundedness not in range(3):
        if 0 <= groundedness <= 100:
            groundedness = 2 if groundedness >= 67 else 1 if groundedness > 0 else 0
        else:
            groundedness = -1
    if correctness not in {0, 1}:
        if 0 <= correctness <= 100:
            correctness = 1 if correctness >= 50 else 0
        else:
            correctness = -1
    if completeness not in {0, 1}:
        if 0 <= completeness <= 100:
            completeness = 1 if completeness >= 50 else 0
        else:
            completeness = -1
    if unsupported_claims not in {0, 1}:
        if 0 <= unsupported_claims <= 100:
            unsupported_claims = 1 if unsupported_claims >= 50 else 0
        else:
            unsupported_claims = -1

    # 3대 지표 엄격 AND 조건 판정 (groundedness >= 1, correctness == 1, completeness == 1)
    is_pass = (groundedness in {1, 2}) and (correctness == 1) and (completeness == 1)
    overall_str = "pass" if is_pass else "fail"
    return EvaluationScores(
        similarity=similarity,
        groundedness=groundedness,
        correctness=correctness,
        completeness=completeness,
        unsupported_claims=unsupported_claims,
        overall=overall_str,
    )


def parse_evaluation_json_array(text: str) -> dict[str, EvaluationScores]:
    """배치 평가 JSON 배열을 question_id 기준 점수 맵으로 변환"""
    clean_text = text.strip()
    if clean_text.startswith("```"):
        lines = clean_text.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```"):
            clean_text = "\n".join(lines[1:-1]).strip()

    start = clean_text.find("[")
    end = clean_text.rfind("]")
    if start != -1 and end != -1:
        clean_text = clean_text[start:end+1]

    try:
        data = json.loads(clean_text)
    except Exception:
        return {}

    if not isinstance(data, list):
        return {}

    parsed: dict[str, EvaluationScores] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        question_id = str(item.get("question_id", "")).strip()
        if not question_id:
            continue
        parsed[question_id] = parse_evaluation_json(json.dumps(item, ensure_ascii=False))
    return parsed


def chunk_items(items: Sequence[T], size: int) -> list[list[T]]:
    """고정 크기 배치로 분할"""
    if size <= 0:
        raise ValueError("batch size must be positive")
    return [list(items[index:index + size]) for index in range(0, len(items), size)]


def build_batch_evaluation_prompt(items: Sequence[GeneratedAnswerRow]) -> str:
    """여러 문항을 한 번에 평가하기 위한 프롬프트 생성"""
    rendered_items: list[str] = []
    for item in items:
        rendered_items.append(
            "\n".join(
                [
                    f"question_id: {item.question_id}",
                    f"question: {item.question}",
                    f"reference_answer: {item.target_answer}",
                    f"retrieved_contexts: {item.retrieved_contexts or 'No retrieved FAQ context.'}",
                    f"candidate_answer: {item.generated_answer}",
                ]
            )
        )
    return BATCH_MULTI_EVALUATION_PROMPT_TEMPLATE.format(items="\n\n---\n\n".join(rendered_items))


def build_row_note(
    generated_answer: str,
    retrieved_answer_nos: str,
    generation_provider: str,
    generation_model: str,
    evaluation_model: str,
    evaluation_scores: EvaluationScores,
    question_note: str,
) -> str:
    """디버깅용 note 생성"""
    parts: list[str] = []
    if question_note:
        parts.append(question_note)
    parts.append(f"overall={evaluation_scores.overall}")
    parts.append(
        "similarity={similarity}, groundedness={groundedness}, correctness={correctness}, "
        "completeness={completeness}, unsupported_claims={unsupported_claims}".format(
            similarity=evaluation_scores.similarity,
            groundedness=evaluation_scores.groundedness,
            correctness=evaluation_scores.correctness,
            completeness=evaluation_scores.completeness,
            unsupported_claims=evaluation_scores.unsupported_claims,
        )
    )
    if generation_provider:
        parts.append(f"generation_provider={generation_provider}")
    if generation_model:
        parts.append(f"generation_model={generation_model}")
    parts.append(f"evaluation_model={evaluation_model}")
    if retrieved_answer_nos:
        parts.append(f"retrieved_answer_nos={retrieved_answer_nos}")
    if generated_answer:
        parts.append(f"generated_chars={len(generated_answer)}")
    return " | ".join(parts)


def output_fieldnames() -> list[str]:
    """결과 CSV 헤더 반환"""
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
        "evaluation_model",
        "generated_answer",
        "retrieved_answer_nos",
        "similarity_score",
        "groundedness",
        "correctness",
        "completeness",
        "unsupported_claims",
        "overall",
        "notes",
    ]


def load_existing_output_rows(path: Path) -> list[dict[str, str]]:
    """기존 평가 결과가 있으면 재개용으로 로드"""
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def append_output_row(path: Path, row: dict[str, Any]) -> None:
    """평가 결과 한 건을 즉시 저장해 중간 실패에도 재개 가능하게 유지"""
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=output_fieldnames())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def build_evaluator(
    settings: GenerationEvaluationSettings,
) -> OllamaEvaluator:
    """평가 provider 설정에 맞는 호출기 생성"""
    return OllamaEvaluator(settings.app_settings.ollama_base_url, settings.evaluation_model)


def build_answer_output_row(
    item: GeneratedAnswerRow,
    evaluation_model: str,
    evaluation_scores: EvaluationScores,
) -> dict[str, Any]:
    """저장용 평가 결과 행 구성"""
    return {
        "question_id": item.question_id,
        "question": item.question,
        "question_type": item.question_type,
        "evaluation_intent": item.evaluation_intent,
        "target_answer_no": item.target_answer_no,
        "target_answer": item.target_answer,
        "supporting_answer_nos": item.supporting_answer_nos,
        "generation_provider": item.generation_provider,
        "generation_model": item.generation_model,
        "evaluation_model": evaluation_model,
        "generated_answer": item.generated_answer,
        "retrieved_answer_nos": item.retrieved_answer_nos,
        "similarity_score": evaluation_scores.similarity,
        "groundedness": evaluation_scores.groundedness,
        "correctness": evaluation_scores.correctness,
        "completeness": evaluation_scores.completeness,
        "unsupported_claims": evaluation_scores.unsupported_claims,
        "overall": evaluation_scores.overall,
        "notes": build_row_note(
            generated_answer=item.generated_answer,
            retrieved_answer_nos=item.retrieved_answer_nos,
            generation_provider=item.generation_provider,
            generation_model=item.generation_model,
            evaluation_model=evaluation_model,
            evaluation_scores=evaluation_scores,
            question_note=item.notes,
        ),
    }


def evaluate_generation(
    questions_path: Path,
    output_path: Path,
    settings: GenerationEvaluationSettings,
) -> None:
    """질문셋 기준 생성 + 자동 평가 실행"""
    questions = skip_out_of_scope(read_generation_questions(questions_path))
    retriever, generator = build_services(settings.app_settings)
    
    evaluator = build_evaluator(settings)

    total = len(questions)
    print(f"총 {total}개의 질문에 대해 생성 및 평가를 시작합니다. (모델: {settings.app_settings.generation_model}, 평가기: {settings.evaluation_model})")

    rows: list[dict[str, Any]] = []
    for i, item in enumerate(questions, 1):
        print(f"[{i}/{total}] '{item.question[:25]}...' 처리 중...", end="", flush=True)
        from time import perf_counter
        start = perf_counter()
        
        results = retriever.search(item.question, top_k=settings.app_settings.top_k)
        answer = generator.generate(item.question, results)
        contexts = render_contexts(results)
        
        evaluation_scores = evaluate_with_retry(evaluator, item.question, item.target_answer, answer.text, contexts)
        
        elapsed = perf_counter() - start
        print(f" 완료! ({elapsed:.2f}초 | 판정: {evaluation_scores.overall})")
        
        rows.append(
            {
                "question_id": item.question_id,
                "question": item.question,
                "question_type": item.question_type,
                "evaluation_intent": item.evaluation_intent,
                "target_answer_no": item.target_answer_no,
                "target_answer": item.target_answer,
                "supporting_answer_nos": item.supporting_answer_nos,
                "generation_provider": settings.app_settings.generation_provider,
                "generation_model": settings.app_settings.generation_model,
                "evaluation_model": settings.evaluation_model,
                "generated_answer": answer.text,
                "retrieved_answer_nos": "|".join(str(source.document.resolved_row_id) for source in answer.sources),
                "similarity_score": evaluation_scores.similarity,
                "groundedness": evaluation_scores.groundedness,
                "correctness": evaluation_scores.correctness,
                "completeness": evaluation_scores.completeness,
                "unsupported_claims": evaluation_scores.unsupported_claims,
                "overall": evaluation_scores.overall,
                "notes": build_row_note(
                    generated_answer=answer.text,
                    retrieved_answer_nos="|".join(str(source.document.resolved_row_id) for source in answer.sources),
                    generation_provider=settings.app_settings.generation_provider,
                    generation_model=settings.app_settings.generation_model,
                    evaluation_model=settings.evaluation_model,
                    evaluation_scores=evaluation_scores,
                    question_note=item.notes,
                ),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=output_fieldnames())
        writer.writeheader()
        writer.writerows(rows)


def evaluate_generated_answers(
    answers_path: Path,
    output_path: Path,
    settings: GenerationEvaluationSettings,
    batch_size: int = 1,
) -> None:
    """생성 완료된 답변 CSV를 자동 평가만 실행"""
    answers = skip_out_of_scope(read_generated_answers(answers_path))
    existing_rows = load_existing_output_rows(output_path)
    completed_question_ids = {
        row["question_id"].strip()
        for row in existing_rows
        if row.get("question_id", "").strip()
    }

    evaluator = build_evaluator(settings)

    total = len(answers)
    print(f"총 {total}개의 저장된 답변에 대해 평가만 진행합니다. (평가기: {settings.evaluation_model})")

    if batch_size > 1:
        pending_answers = [item for item in answers if item.question_id not in completed_question_ids]
        batches = chunk_items(pending_answers, batch_size)
        total_batches = len(batches)
        for index, batch in enumerate(batches, 1):
            question_preview = ", ".join(item.question_id for item in batch)
            print(f"[batch {index}/{total_batches}] '{question_preview}' 배치 평가 중...", end="", flush=True)
            from time import perf_counter
            start = perf_counter()

            raw_evaluation_text = evaluator.evaluate_batch(build_batch_evaluation_prompt(batch))
            parsed_scores = parse_evaluation_json_array(raw_evaluation_text)

            elapsed = perf_counter() - start
            print(f" 완료! ({elapsed:.2f}초)")

            for item in batch:
                evaluation_scores = parsed_scores.get(item.question_id, EvaluationScores(-1, -1, -1, -1, -1, "fail"))
                append_output_row(
                    output_path,
                    build_answer_output_row(item, settings.evaluation_model, evaluation_scores),
                )
                completed_question_ids.add(item.question_id)
        return

    for i, item in enumerate(answers, 1):
        if item.question_id in completed_question_ids:
            print(f"[{i}/{total}] '{item.question[:25]}...' 이미 평가되어 건너뜁니다.")
            continue
        print(f"[{i}/{total}] '{item.question[:25]}...' 평가 중...", end="", flush=True)
        from time import perf_counter
        start = perf_counter()
        
        evaluation_scores = evaluate_with_retry(
            evaluator,
            item.question,
            item.target_answer,
            item.generated_answer,
            item.retrieved_contexts or "No retrieved FAQ context.",
        )
        
        elapsed = perf_counter() - start
        print(f" 완료! ({elapsed:.2f}초 | 판정: {evaluation_scores.overall})")

        append_output_row(output_path, build_answer_output_row(item, settings.evaluation_model, evaluation_scores))
        completed_question_ids.add(item.question_id)


def main() -> None:
    """생성 결과 평가 CLI 실행"""
    parser = argparse.ArgumentParser(description="FAQ 생성 답변 결과를 평가합니다.")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path("evaluation/evalset/evalset_v1.3.jsonl"),
    )
    parser.add_argument(
        "--answers",
        type=Path,
        help="생성 전용 단계에서 저장한 답변 CSV 경로",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/generation_evaluation.csv"),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="평가 시 한 번에 묶어 보낼 문항 수. 기본값 1은 단건 평가.",
    )
    args = parser.parse_args()

    load_project_env()
    settings = GenerationEvaluationSettings.from_mapping(dict(os.environ))
    if args.answers is not None:
        evaluate_generated_answers(args.answers, args.output, settings, batch_size=args.batch_size)
    else:
        evaluate_generation(args.questions, args.output, settings)


if __name__ == "__main__":
    main()

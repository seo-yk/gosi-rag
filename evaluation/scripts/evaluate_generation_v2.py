"""LLM-as-a-Judge v2 단건 평가와 Human Escalation 목록 생성."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from openai import OpenAI


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.config import load_project_env


SYSTEM_PROMPT = (
    "You are a strict RAG answer evaluator. "
    "Evaluate exactly one item. Return JSON only."
)

PROMPT_TEMPLATE = """Evaluate the candidate answer.

Question:
{question}

Reference answer:
{reference_answer}

Required facts:
{required_facts}

Retrieved contexts:
{retrieved_contexts}

Candidate answer:
{candidate_answer}

Rules:
1. groundedness checks whether candidate claims are supported by retrieved contexts.
2. correctness checks whether the candidate actually gives the correct answer according to the reference answer.
3. Check every required fact individually. Copy every missing fact exactly into missing_required_facts.
4. If the reference contains an answer but the candidate refuses or says it cannot be confirmed:
   - correctness must be fail
   - answer_status must be false_refusal
5. A hallucination-free refusal is not automatically a correct answer.
6. Return JSON only.

Output schema:
{{
  "groundedness": "pass | partial | fail",
  "correctness": "pass | fail",
  "missing_required_facts": ["exact missing required fact"],
  "answer_status": "answered | valid_refusal | false_refusal",
  "reason": "brief reason in at most two sentences"
}}
"""

OUTPUT_FIELDS = [
    "question_id",
    "evaluation_model",
    "groundedness",
    "correctness",
    "missing_required_facts_json",
    "answer_status",
    "overall",
    "reason",
    "raw_evaluation",
]

ESCALATION_FIELDS = [
    "question_id",
    "escalation_reasons",
    "question",
    "reference_answer",
    "required_facts_json",
    "relevant_answer_nos",
    "retrieved_answer_nos",
    "generated_answer",
    "judge_overall",
    "judge_reason",
    "human_overall",
    "human_notes",
]


def parse_json_object(text: str) -> dict[str, Any]:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        clean = "\n".join(lines[1:-1]).strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start < 0 or end < start:
        raise ValueError("evaluation response does not contain a JSON object")
    data = json.loads(clean[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("evaluation response must be a JSON object")
    return data


def normalize_evaluation(data: dict[str, Any]) -> dict[str, Any]:
    groundedness = str(data.get("groundedness", "")).strip().lower()
    correctness = str(data.get("correctness", "")).strip().lower()
    answer_status = str(data.get("answer_status", "")).strip().lower()
    missing = data.get("missing_required_facts", [])
    reason = str(data.get("reason", "")).strip()

    if groundedness not in {"pass", "partial", "fail"}:
        raise ValueError(f"invalid groundedness: {groundedness}")
    if correctness not in {"pass", "fail"}:
        raise ValueError(f"invalid correctness: {correctness}")
    if answer_status not in {"answered", "valid_refusal", "false_refusal"}:
        raise ValueError(f"invalid answer_status: {answer_status}")
    if not isinstance(missing, list) or not all(isinstance(item, str) for item in missing):
        raise ValueError("missing_required_facts must be a string list")

    normalized_missing = [item.strip() for item in missing if item.strip()]
    overall = (
        "pass"
        if groundedness != "fail"
        and correctness == "pass"
        and not normalized_missing
        and answer_status != "false_refusal"
        else "fail"
    )
    return {
        "groundedness": groundedness,
        "correctness": correctness,
        "missing_required_facts": normalized_missing,
        "answer_status": answer_status,
        "overall": overall,
        "reason": reason,
    }


def apply_deterministic_rules(
    evaluation: dict[str, Any],
    reference_answer: str,
    candidate_answer: str,
) -> dict[str, Any]:
    """명시적 핵심 답변 유보는 모델 판정과 무관하게 false refusal로 처리."""
    normalized = dict(evaluation)
    leading_answer = candidate_answer.strip()[:160]
    refusal_prefixes = (
        "제공된 FAQ만으로는",
        "검색된 FAQ만으로는",
        "제공된 정보만으로는",
    )
    if reference_answer.strip() and leading_answer.startswith(refusal_prefixes):
        normalized["correctness"] = "fail"
        normalized["answer_status"] = "false_refusal"
        normalized["overall"] = "fail"
        marker = "deterministic_false_refusal"
        reason = str(normalized.get("reason", "")).strip()
        normalized["reason"] = f"{reason} | {marker}" if reason else marker
    return normalized


def completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as file:
        return {
            row["question_id"].strip()
            for row in csv.DictReader(file)
            if row.get("question_id", "").strip()
        }


def append_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def stable_pass_sample(question_id: str) -> int:
    return int(hashlib.sha256(question_id.encode()).hexdigest()[:8], 16)


def write_escalations(
    answers_path: Path,
    evaluations_path: Path,
    escalation_path: Path,
    pass_sample_size: int = 10,
) -> None:
    with answers_path.open(encoding="utf-8-sig", newline="") as file:
        answers = {row["question_id"]: row for row in csv.DictReader(file)}
    with evaluations_path.open(encoding="utf-8-sig", newline="") as file:
        evaluations = {row["question_id"]: row for row in csv.DictReader(file)}

    pass_candidates = [
        question_id
        for question_id, evaluation in evaluations.items()
        if evaluation["overall"] == "pass"
    ]
    sampled_passes = set(
        sorted(pass_candidates, key=stable_pass_sample)[:pass_sample_size]
    )

    rows: list[dict[str, str]] = []
    for question_id, answer in answers.items():
        evaluation = evaluations[question_id]
        reasons: list[str] = []
        if evaluation["overall"] == "fail":
            reasons.append("judge_fail")
        if evaluation["answer_status"] == "false_refusal":
            reasons.append("false_refusal")
        if len([item for item in answer["relevant_answer_nos"].split("|") if item]) > 1:
            reasons.append("multi_document")
        if question_id in sampled_passes:
            reasons.append("pass_sample")
        if not reasons:
            continue
        rows.append(
            {
                "question_id": question_id,
                "escalation_reasons": "|".join(reasons),
                "question": answer["question"],
                "reference_answer": answer["reference_answer"],
                "required_facts_json": answer["required_facts_json"],
                "relevant_answer_nos": answer["relevant_answer_nos"],
                "retrieved_answer_nos": answer["retrieved_answer_nos"],
                "generated_answer": answer["generated_answer"],
                "judge_overall": evaluation["overall"],
                "judge_reason": evaluation["reason"],
                "human_overall": "",
                "human_notes": "",
            }
        )

    escalation_path.parent.mkdir(parents=True, exist_ok=True)
    with escalation_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=ESCALATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def evaluate(
    answers_path: Path,
    output_path: Path,
    escalation_path: Path,
    base_url: str,
    model: str,
) -> None:
    with answers_path.open(encoding="utf-8-sig", newline="") as file:
        answers = list(csv.DictReader(file))
    done = completed_ids(output_path)
    client = OpenAI(base_url=base_url, api_key="ollama", timeout=300.0, max_retries=1)

    for index, answer in enumerate(answers, start=1):
        question_id = answer["question_id"]
        if question_id in done:
            print(f"[{index}/{len(answers)}] {question_id} already evaluated")
            continue

        prompt = PROMPT_TEMPLATE.format(
            question=answer["question"],
            reference_answer=answer["reference_answer"],
            required_facts=answer["required_facts_json"],
            retrieved_contexts=answer["retrieved_contexts"],
            candidate_answer=answer["generated_answer"],
        )
        started_at = perf_counter()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        raw = (response.choices[0].message.content or "").strip()
        try:
            normalized = apply_deterministic_rules(
                normalize_evaluation(parse_json_object(raw)),
                reference_answer=answer["reference_answer"],
                candidate_answer=answer["generated_answer"],
            )
        except Exception as error:
            normalized = {
                "groundedness": "fail",
                "correctness": "fail",
                "missing_required_facts": [],
                "answer_status": "answered",
                "overall": "fail",
                "reason": f"parse_error: {error}",
            }
        append_row(
            output_path,
            {
                "question_id": question_id,
                "evaluation_model": model,
                "groundedness": normalized["groundedness"],
                "correctness": normalized["correctness"],
                "missing_required_facts_json": json.dumps(
                    normalized["missing_required_facts"], ensure_ascii=False
                ),
                "answer_status": normalized["answer_status"],
                "overall": normalized["overall"],
                "reason": normalized["reason"],
                "raw_evaluation": raw,
            },
        )
        print(
            f"[{index}/{len(answers)}] {question_id} {normalized['overall']} "
            f"({perf_counter() - started_at:.2f}s)"
        )

    write_escalations(answers_path, output_path, escalation_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--answers",
        type=Path,
        default=Path("output/v2/gen_50_gpt-5.4-mini.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/v2/eval_50_gpt-5.4-mini-gemma3-4b_single.csv"),
    )
    parser.add_argument(
        "--escalations",
        type=Path,
        default=Path("output/v2/human_escalation_50.csv"),
    )
    args = parser.parse_args()

    load_project_env()
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model = os.environ.get("EVALUATION_MODEL", "gemma3:4b")
    evaluate(args.answers, args.output, args.escalations, base_url, model)


if __name__ == "__main__":
    main()

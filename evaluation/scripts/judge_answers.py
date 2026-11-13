"""생성 답변 자동 채점 (루브릭 v2)

- 입력: generate_answers.py가 만든 생성 결과 CSV
- 채점 모델: Ollama(기본 gemma3-4b-ctx8k, num_ctx 8192. evaluation/ollama/*.Modelfile)
- 출력: id, model, context_setup, judge_model, groundedness, correctness, groups_covered,
        completeness, unjustified_refusal, verdict, reason
- 범위 밖 문항은 채점하지 않는다(사람이 판정)
- 1차 실험의 루브릭 v1은 evaluate_generation.py에 그대로 있다

루브릭 v2.1 요약 (자세한 설명: evaluation/judge_calibration/README.md)
- 채점 모델은 판단 근거(reason)를 먼저 쓰고 점수를 낸다
- 완결성은 평가셋의 필수 근거 그룹별로 판단한다
- 길이·서식·말투는 무시하고, 같은 뜻의 다른 표현과 근거 FAQ에 뒷받침되는 대체 답을 인정한다
- 정확성은 답변에 실제로 쓴 내용이 맞는지만 본다(빠뜨림은 그룹 충족, 회피는 회피 항목에서 본다)
- 근거에 답이 있는 부분을 하나라도 피하면 unjustified_refusal = 1. 답을 준 뒤 덧붙인 안내는 회피가 아니다
- v2 → v2.1(2026-11-13): "회피면 정확성 0" 규칙을 없애 세 항목이 각각 하나만 보게 했다
- verdict(파이썬에서 계산): groundedness 2, correctness 1, 모든 그룹 충족, unjustified_refusal 0이면 pass
"""

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from openai import OpenAI

from evaluation.scripts.evaluate_generation import GeneratedAnswerRow, OUT_OF_SCOPE_TYPE, read_generated_answers
from src.config import load_project_env
from src.generation import check_not_truncated, ollama_context_length

RUBRIC_VERSION = "v2.1"
DEFAULT_JUDGE_MODEL = "gemma3-4b-ctx8k"
PARSE_RETRIES = 2

SYSTEM_PROMPT = (
    "You are a strict, impartial grader for a Korean FAQ question-answering system. "
    "Return ONLY one JSON object. Do not use markdown."
)

USER_PROMPT = """Grade the candidate answer.

## Question
<<question>>

## Reference answer (one correct answer; different wording can also be correct)
<<reference>>

## Required evidence groups
The answer must address every group below. A group is satisfied if the answer covers the information of ANY one FAQ in that group.
<<groups>>

## FAQ contexts given to the answering system
<<contexts>>

## Candidate answer
<<answer>>

## Rules
- Judge content only. Ignore length, formatting (bold, lists), and tone.
- Paraphrases count as correct.
- If the FAQ contexts disagree with each other, an answer that follows one of them is correct.
- Extra information is fine if it is supported by the FAQ contexts.
- If the FAQ contexts contain the answer to ANY part of the question but the candidate says it cannot confirm that part or does not answer it, set unjustified_refusal = 1. Judge correctness only on what the candidate actually stated.
- Giving the answer and then adding a pointer such as "check the official notice for details" is NOT a refusal.
- If the FAQ contexts do not contain the needed information and the candidate says it cannot confirm, set unjustified_refusal = 0 and correctness = 0.

## Scores
- groundedness: 2 = every claim is supported by the FAQ contexts; 1 = a minor detail is not supported; 0 = a key claim is unsupported or contradicts the contexts
- correctness: 1 = everything the candidate stated in answer to the question is correct (consistent with the reference answer, or supported by the FAQ contexts) and nothing stated is wrong; 0 = something stated is wrong, or the candidate gave no answer at all. Missing parts are judged by groups_covered, not here.
- groups_covered: a list with one 0 or 1 per required group, in the order above
- unjustified_refusal: 1 if the candidate refused or said it cannot confirm any part whose answer is in the FAQ contexts; otherwise 0

Write a short reason first (1-3 sentences), then the scores. Return exactly this JSON shape:
{"reason": "...", "groundedness": 0, "correctness": 0, "groups_covered": [0], "unjustified_refusal": 0}
"""


@dataclass(frozen=True, slots=True)
class JudgeScores:
    """채점 모델의 원 점수와 파이썬에서 계산한 판정"""

    groundedness: int
    correctness: int
    groups_covered: tuple[int, ...]
    unjustified_refusal: int
    reason: str

    @property
    def completeness(self) -> int:
        return int(bool(self.groups_covered) and all(self.groups_covered))

    @property
    def verdict(self) -> str:
        ok = (self.groundedness == 2 and self.correctness == 1
              and self.completeness == 1 and self.unjustified_refusal == 0)
        return "pass" if ok else "fail"


def parse_groups(required_faqs: str) -> list[list[int]]:
    """'78 & 272|251' → [[78], [272, 251]]"""
    return [[int(x) for x in re.findall(r"\d+", part)] for part in required_faqs.split("&") if re.search(r"\d", part)]


def format_groups(groups: Sequence[Sequence[int]], titles: dict[int, str]) -> str:
    """채점 프롬프트용 필수 근거 그룹. 예: 'Group 1: FAQ 78 [신분증 미지참] ...'"""
    lines = []
    for index, group in enumerate(groups, 1):
        options = " OR ".join(f"FAQ {faq_id} {titles.get(faq_id, '')}".strip() for faq_id in group)
        lines.append(f"Group {index}: {options}")
    return "\n".join(lines)


def build_prompt(item: GeneratedAnswerRow, groups_text: str) -> str:
    replacements = {
        "<<question>>": item.question,
        "<<reference>>": item.target_answer,
        "<<groups>>": groups_text,
        "<<contexts>>": item.retrieved_contexts or "No FAQ context.",
        "<<answer>>": item.generated_answer,
    }
    prompt = USER_PROMPT
    for key, value in replacements.items():
        prompt = prompt.replace(key, value)
    return prompt


def parse_judge_json(text: str, group_count: int) -> JudgeScores | None:
    """채점 결과 JSON을 읽는다. 형식이 틀리면 None(다시 요청)"""
    clean = text.strip()
    start, end = clean.find("{"), clean.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(clean[start:end + 1])
        groundedness = int(data["groundedness"])
        correctness = int(data["correctness"])
        covered = tuple(int(x) for x in data["groups_covered"])
        refusal = int(data["unjustified_refusal"])
        reason = str(data.get("reason", "")).strip()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
    if groundedness not in (0, 1, 2) or correctness not in (0, 1) or refusal not in (0, 1):
        return None
    if len(covered) != group_count or any(x not in (0, 1) for x in covered):
        return None
    return JudgeScores(groundedness, correctness, covered, refusal, reason)


def response_schema(group_count: int) -> dict[str, Any]:
    """출력 형식을 JSON 스키마로 강제(Ollama 구조화 출력). 소형 모델의 형식 오류를 막는다"""
    return {"type": "json_schema", "json_schema": {"name": "grade", "schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string"},
            "groundedness": {"type": "integer", "enum": [0, 1, 2]},
            "correctness": {"type": "integer", "enum": [0, 1]},
            "groups_covered": {"type": "array", "items": {"type": "integer", "enum": [0, 1]},
                               "minItems": group_count, "maxItems": group_count},
            "unjustified_refusal": {"type": "integer", "enum": [0, 1]},
        },
        "required": ["reason", "groundedness", "correctness", "groups_covered", "unjustified_refusal"],
    }}}


class OllamaJudge:
    """Ollama(OpenAI 호환) 채점 모델. 입력이 컨텍스트 한도에 닿으면 중단한다"""

    def __init__(self, base_url: str, model: str) -> None:
        self._client = OpenAI(base_url=base_url, api_key="ollama", timeout=600.0, max_retries=1)
        self.model = model
        self.context_limit = ollama_context_length(base_url, model)

    def complete(self, prompt: str, group_count: int | None = None) -> str:
        extra = {"response_format": response_schema(group_count)} if group_count else {}
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0,
            **extra,
        )
        check_not_truncated(response, self.context_limit, f"채점 모델 {self.model}")
        return (response.choices[0].message.content or "").strip()


def judge_one(judge, item: GeneratedAnswerRow, titles: dict[int, str], retries: int = PARSE_RETRIES) -> JudgeScores | None:
    """채점하고, JSON을 읽지 못하면 다시 요청한다. 끝내 실패하면 None(verdict=error)"""
    groups = parse_groups(item.target_answer_no)
    prompt = build_prompt(item, format_groups(groups, titles))
    for _ in range(retries + 1):
        scores = parse_judge_json(judge.complete(prompt, len(groups)), len(groups))
        if scores is not None:
            return scores
    return None


def output_fieldnames() -> list[str]:
    return ["id", "model", "context_setup", "judge_model", "groundedness", "correctness", "groups_covered",
            "completeness", "unjustified_refusal", "verdict", "reason"]


def output_row(item: GeneratedAnswerRow, judge_model: str, scores: JudgeScores | None) -> dict[str, Any]:
    base = {"id": item.question_id, "model": item.generation_model, "context_setup": item.notes,
            "judge_model": f"{judge_model} (rubric {RUBRIC_VERSION})"}
    if scores is None:
        return base | {k: "" for k in output_fieldnames()[4:-2]} | {"verdict": "error", "reason": "채점 결과를 읽지 못함"}
    return base | {
        "groundedness": scores.groundedness,
        "correctness": scores.correctness,
        "groups_covered": "|".join(map(str, scores.groups_covered)),
        "completeness": scores.completeness,
        "unjustified_refusal": scores.unjustified_refusal,
        "verdict": scores.verdict,
        "reason": scores.reason,
    }


def load_titles(path: Path) -> dict[int, str]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return {int(row["연번"]): row["제목"].strip() for row in csv.DictReader(file)}


def judge_answers(answers_path: Path, output_path: Path, judge, faq_path: Path = Path("data/faq_v2.csv"),
                  only_ids: set[str] | None = None) -> None:
    """생성 결과 전체를 채점. 같은 출력 파일로 다시 실행하면 남은 문항만 채점한다"""
    titles = load_titles(faq_path)
    items = [item for item in read_generated_answers(answers_path) if item.question_type != OUT_OF_SCOPE_TYPE]
    if only_ids is not None:
        items = [item for item in items if item.question_id in only_ids]
    done = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8-sig", newline="") as file:
            done = {row["id"] for row in csv.DictReader(file)}
    print(f"{answers_path.name}: {len(items)}문항 (이미 채점 {len(done)}), 채점 모델 {judge.model}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(items, 1):
        if item.question_id in done:
            continue
        start = perf_counter()
        scores = judge_one(judge, item, titles)
        row = output_row(item, judge.model, scores)
        new_file = not output_path.exists()
        with output_path.open("a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=output_fieldnames())
            if new_file:
                writer.writeheader()
            writer.writerow(row)
        print(f"[{index}/{len(items)}] id {item.question_id}: {row['verdict']} ({perf_counter() - start:.1f}초)")


def main() -> None:
    parser = argparse.ArgumentParser(description="생성 답변을 루브릭 v2로 자동 채점합니다.")
    parser.add_argument("answers", type=Path, help="generate_answers.py 결과 CSV")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-model", default=None, help=f"기본값 JUDGE_MODEL 또는 {DEFAULT_JUDGE_MODEL}")
    parser.add_argument("--ids", default=None, help="일부 문항만 채점(쉼표 구분). 반복 채점 확인용")
    args = parser.parse_args()

    load_project_env()
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip()
    judge = OllamaJudge(base_url, args.judge_model or os.environ.get("JUDGE_MODEL") or DEFAULT_JUDGE_MODEL)
    only_ids = set(args.ids.split(",")) if args.ids else None
    judge_answers(args.answers, args.output, judge, only_ids=only_ids)


if __name__ == "__main__":
    main()

import json

import pytest

from evaluation.scripts.evaluate_generation_v2 import (
    apply_deterministic_rules,
    normalize_evaluation,
    parse_json_object,
)


def test_false_refusal_is_always_fail() -> None:
    result = normalize_evaluation(
        {
            "groundedness": "pass",
            "correctness": "fail",
            "missing_required_facts": ["재입실 가능 여부"],
            "answer_status": "false_refusal",
            "reason": "답을 유보했다.",
        }
    )

    assert result["overall"] == "fail"


def test_pass_requires_no_missing_facts() -> None:
    result = normalize_evaluation(
        {
            "groundedness": "pass",
            "correctness": "pass",
            "missing_required_facts": [],
            "answer_status": "answered",
            "reason": "필수 사실을 포함했다.",
        }
    )

    assert result["overall"] == "pass"


def test_missing_fact_overrides_correctness_pass() -> None:
    result = normalize_evaluation(
        {
            "groundedness": "pass",
            "correctness": "pass",
            "missing_required_facts": ["9급은 재입실할 수 없다."],
            "answer_status": "answered",
            "reason": "예외 조건을 누락했다.",
        }
    )

    assert result["overall"] == "fail"


def test_parse_json_object_accepts_markdown_fence() -> None:
    payload = {"groundedness": "pass"}
    assert parse_json_object(f"```json\n{json.dumps(payload)}\n```") == payload


def test_normalize_rejects_invalid_labels() -> None:
    with pytest.raises(ValueError, match="groundedness"):
        normalize_evaluation(
            {
                "groundedness": "yes",
                "correctness": "pass",
                "missing_required_facts": [],
                "answer_status": "answered",
            }
        )


def test_leading_refusal_is_deterministically_false_refusal() -> None:
    result = apply_deterministic_rules(
        {
            "groundedness": "pass",
            "correctness": "pass",
            "missing_required_facts": [],
            "answer_status": "answered",
            "overall": "pass",
            "reason": "judge considered it safe",
        },
        reference_answer="7급은 재입실할 수 있고 9급은 재입실할 수 없다.",
        candidate_answer="제공된 FAQ만으로는 재입실 가능 여부를 확인할 수 없습니다.",
    )

    assert result["correctness"] == "fail"
    assert result["answer_status"] == "false_refusal"
    assert result["overall"] == "fail"


def test_trailing_caveat_does_not_override_answered_response() -> None:
    result = apply_deterministic_rules(
        {
            "groundedness": "pass",
            "correctness": "pass",
            "missing_required_facts": [],
            "answer_status": "answered",
            "overall": "pass",
            "reason": "answered",
        },
        reference_answer="응시할 수 있다.",
        candidate_answer="응시할 수 있습니다. 더 구체적인 예외는 FAQ만으로 확인할 수 없습니다.",
    )

    assert result["answer_status"] == "answered"
    assert result["overall"] == "pass"

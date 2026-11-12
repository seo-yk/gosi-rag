import json
from pathlib import Path

import pytest

from evaluation.scripts.evalset import (
    EvalQuestion,
    format_groups,
    group_recall,
    is_hit,
    read_evalset,
    read_out_of_scope,
    reciprocal_rank,
)
from evaluation.scripts.evaluate_retrieval import ALL_TYPES, evaluate_by_type, evaluate_groups

ROOT = Path(__file__).resolve().parents[1]


def question(qid: int, groups, supporting=(), question_type="일상표현") -> EvalQuestion:
    return EvalQuestion(
        id=qid,
        question=f"질문 {qid}",
        intent="",
        type=question_type,
        required_faqs=tuple(tuple(g) for g in groups),
        supporting_faqs=tuple(supporting),
        reference_answer="",
    )


# 그룹 채점: 인수인계서 작업 3의 최소 사례


def test_single_group_hit_depends_on_rank() -> None:
    groups = ((12,),)
    retrieved = [3, 12, 8, 1, 2]

    assert not is_hit(groups, retrieved, 1)
    assert is_hit(groups, retrieved, 3)
    assert reciprocal_rank(groups, retrieved) == 1 / 2


def test_alternative_answer_in_group_counts_as_hit() -> None:
    groups = ((4, 252),)  # 4 또는 252
    retrieved = [252, 9, 10]

    assert is_hit(groups, retrieved, 1)
    assert reciprocal_rank(groups, retrieved) == 1.0


def test_partial_groups_miss_hit_but_count_in_group_recall() -> None:
    groups = ((78,), (272, 251))  # 78 그리고 (272 또는 251)
    retrieved = [78, 5, 6, 251, 7]

    assert not is_hit(groups, retrieved, 3)
    assert group_recall(groups, retrieved, 3) == 1 / 2
    assert is_hit(groups, retrieved, 5)
    assert group_recall(groups, retrieved, 5) == 1.0


def test_supporting_faq_alone_is_a_miss() -> None:
    item = question(1, [[79]], supporting=[64])
    retrieved = [64, 2, 3, 4, 5]

    result = evaluate_groups([(item, retrieved)])

    assert result.hit_at == {1: 0.0, 3: 0.0, 5: 0.0}
    assert result.group_recall_at[5] == 0.0
    assert result.mrr == 0.0
    assert result.failed_ids == (1,)


# 집계


def test_mrr_uses_only_single_group_questions() -> None:
    single = question(1, [[12]])
    multi = question(2, [[1], [2]], question_type="복수근거")

    result = evaluate_groups([(single, [9, 12]), (multi, [1, 2])])

    assert result.questions == 2
    assert result.single_questions == 1
    assert result.mrr == 1 / 2  # 복수근거 문항은 MRR에서 빠짐
    assert result.hit_at[1] == 0.0  # 단일: 12가 2위, 복수: 2가 Top-1 밖
    assert result.hit_at[3] == 1.0


def test_hit_rates_average_over_questions() -> None:
    rankings = [
        (question(1, [[12]]), [12, 3, 8]),
        (question(2, [[5]]), [9, 5, 2]),
        (question(3, [[7]]), [1, 2, 3]),
    ]

    result = evaluate_groups(rankings)

    assert result.hit_at[1] == 1 / 3
    assert result.hit_at[3] == 2 / 3
    assert result.mrr == (1 + 1 / 2 + 0) / 3
    assert result.failed_ids == (3,)


def test_mrr_is_none_when_no_single_questions() -> None:
    result = evaluate_groups([(question(1, [[1], [2]], question_type="복수근거"), [1, 2])])

    assert result.mrr is None


def test_reciprocal_rank_rejects_multi_group() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank(((1,), (2,)), [1, 2])


def test_evaluate_groups_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="평가"):
        evaluate_groups([])


def test_evaluate_by_type_includes_total_and_each_type() -> None:
    rankings = [
        (question(1, [[1]], question_type="원문유사"), [1]),
        (question(2, [[2]], question_type="조건형"), [9]),
    ]

    results = evaluate_by_type(rankings)

    assert set(results) == {ALL_TYPES, "원문유사", "조건형"}
    assert results[ALL_TYPES].hit_at[1] == 1 / 2
    assert results["원문유사"].hit_at[1] == 1.0
    assert results["조건형"].hit_at[1] == 0.0


def test_format_groups() -> None:
    assert format_groups(((78,), (272, 251))) == "78 & 272|251"


# 로더


def test_read_evalset_keeps_only_keep_rows(tmp_path: Path) -> None:
    path = tmp_path / "evalset.jsonl"
    rows = [
        {"id": 1, "status": "keep", "question": "질문", "intent": "의도", "type": "복수근거",
         "required_faqs": [[78], [272, 251]], "supporting_faqs": [77], "reference_answer": "답",
         "written_by": "본인", "reviewed": True},
        {"id": 2, "status": "exclude", "question": "제외", "intent": "", "type": "일상표현",
         "required_faqs": [[1]], "supporting_faqs": [], "reference_answer": "",
         "written_by": "Claude", "reviewed": False},
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    items = read_evalset(path)

    assert [item.id for item in items] == [1]
    assert items[0].required_faqs == ((78,), (272, 251))
    assert not items[0].is_single


def test_committed_evalset_v1_3_has_expected_counts() -> None:
    items = read_evalset(ROOT / "evaluation/inputs/evalset_v1.3.jsonl")
    out_of_scope = read_out_of_scope(ROOT / "evaluation/inputs/evalset_out_of_scope_v1.3.jsonl")

    assert len(items) == 148
    assert sum(item.is_single for item in items) == 111
    assert len(out_of_scope) == 10
    assert not {item.id for item in items} & {item.id for item in out_of_scope}

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
from types import SimpleNamespace

from evaluation.scripts.evaluate_retrieval import (
    ALL_TYPES,
    SINGLE_ONLY,
    evaluate_subsets,
    evaluate_groups,
    unique_faq_ranking,
)

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


def test_evaluate_subsets_includes_total_and_each_type() -> None:
    rankings = [
        (question(1, [[1]], question_type="원문유사"), [1]),
        (question(2, [[2]], question_type="조건형"), [9]),
    ]

    results = evaluate_subsets(rankings)

    assert set(results) == {ALL_TYPES, SINGLE_ONLY, "유형: 원문유사", "유형: 조건형"}
    assert results[ALL_TYPES].hit_at[1] == 1 / 2
    assert results["유형: 원문유사"].hit_at[1] == 1.0
    assert results["유형: 조건형"].hit_at[1] == 0.0


def test_unique_faq_ranking_keeps_best_chunk_per_faq() -> None:
    def chunk(faq_id: int, score: float) -> SimpleNamespace:
        return SimpleNamespace(document=SimpleNamespace(resolved_row_id=faq_id), score=score)

    results = [chunk(12, 0.9), chunk(12, 0.8), chunk(5, 0.7), chunk(12, 0.6), chunk(3, 0.5), chunk(9, 0.4)]

    assert unique_faq_ranking(results, 3) == [(12, 0.9), (5, 0.7), (3, 0.5)]


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
    items = read_evalset(ROOT / "evaluation/evalset/evalset_v1.3.jsonl")
    out_of_scope = read_out_of_scope(ROOT / "evaluation/evalset/evalset_out_of_scope_v1.3.jsonl")

    assert len(items) == 148
    assert sum(item.is_single for item in items) == 111
    assert len(out_of_scope) == 10
    assert not {item.id for item in items} & {item.id for item in out_of_scope}


# 파이프라인 무결성: 인덱스 생성 → 검색 평가


class KeywordEmbedder:
    """테스트용 임베더: 단어 사전 기준 bag-of-words 벡터"""

    VOCAB = ("환불", "시험장", "신분증", "가산점", "취소")

    def __init__(self, model_name: str = "fake-model") -> None:
        self.model_name = model_name
        self.calls: list[tuple[str, int]] = []

    def embed(self, texts, role="passage"):
        import numpy as np

        self.calls.append((role, len(texts)))
        vectors = [[float(text.count(word)) + 0.01 for word in self.VOCAB] for text in texts]
        return np.asarray(vectors, dtype=np.float32)


def _build_tiny_index(tmp_path: Path, embedder) -> Path:
    from src.indexing import build_indexes

    csv_path = tmp_path / "faq.csv"
    csv_path.write_text(
        "연번,제목,본문\n"
        "1,환불은 언제 되나요?,접수 취소 후 환불은 5일 안에 됩니다. 중복 결제 환불은 더 걸릴 수 있습니다.\n"
        "2,시험장은 어떻게 정하나요?,시험장은 응시번호 순으로 배정합니다. 수험생이 고를 수 없습니다.\n"
        "3,신분증이 없으면?,신분증이 없어도 본인확인 절차를 거쳐 응시할 수 있습니다.\n",
        encoding="utf-8",
    )
    index_dir = tmp_path / "index"
    build_indexes(csv_path, index_dir, {"local": embedder}, chunking_modes=("row", "sentence"))
    return index_dir


def test_run_experiments_end_to_end_with_manifest(tmp_path: Path) -> None:
    from evaluation.scripts.evaluate_retrieval import QueryCachingEmbedder, run_experiments

    index_dir = _build_tiny_index(tmp_path, KeywordEmbedder())
    questions = [question(1, [[1]]), question(2, [[2]]), question(3, [[1], [3]], question_type="복수근거")]
    questions = [
        EvalQuestion(q.id, text, "", q.type, q.required_faqs, (), "", written_by=author)
        for q, text, author in zip(questions, ["환불 언제 돼요", "시험장 고를 수 있나요", "환불이랑 신분증"], ["본인", "Claude", "본인"])
    ]
    embedder = QueryCachingEmbedder(KeywordEmbedder())

    summary, details, oos = run_experiments(
        index_dir, "tiny", questions, [], {"local": embedder}, ("row", "sentence"), ("title", "title_body"), 5
    )

    combos = {(row["chunking_mode"], row["embedding_mode"]) for row in summary}
    assert combos == {("row", "title"), ("row", "title_body"), ("sentence", "title_body")}
    assert len(details) == 3 * len(questions)
    assert {row["source_sha256"] for row in summary} != {""}
    assert {row["subset"] for row in summary} >= {"전체", "단일 그룹 전체", "작성: 본인", "작성: Claude"}
    # 질문 벡터는 조합이 바뀌어도 질문당 한 번만 만든다
    assert embedder.query_calls == len(questions)
    # 문장 청킹이어도 같은 FAQ는 순위에 한 번만 나온다
    for row in details:
        ids = row["retrieved_ids"].split("|")
        assert len(ids) == len(set(ids))


def test_check_index_rejects_model_mismatch(tmp_path: Path) -> None:
    from evaluation.scripts.evaluate_retrieval import check_index
    from src.indexing import index_bundle_paths

    index_dir = _build_tiny_index(tmp_path, KeywordEmbedder("model-a"))
    index_path, metadata_path = index_bundle_paths(index_dir, "row", "local", "title")

    with pytest.raises(SystemExit, match="모델"):
        check_index(index_path, metadata_path, KeywordEmbedder("model-b"), "title", [question(1, [[1]])])


def test_check_index_rejects_missing_gold_faq(tmp_path: Path) -> None:
    from evaluation.scripts.evaluate_retrieval import check_index
    from src.indexing import index_bundle_paths

    index_dir = _build_tiny_index(tmp_path, KeywordEmbedder())
    index_path, metadata_path = index_bundle_paths(index_dir, "row", "local", "title")

    with pytest.raises(SystemExit, match="정답 FAQ"):
        check_index(index_path, metadata_path, KeywordEmbedder(), "title", [question(1, [[99]])])

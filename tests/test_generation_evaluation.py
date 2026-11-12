from evaluation.scripts.evaluate_generation import (
    binary_to_ox,
    build_row_note,
    most_frequent_element,
    output_fieldnames,
    similarity_to_ox,
    unsupported_claims_to_ox,
)


def test_similarity_to_ox_uses_threshold_four() -> None:
    assert similarity_to_ox(4) == "O"
    assert similarity_to_ox(5) == "O"
    assert similarity_to_ox(3) == "X"


def test_binary_to_ox_accepts_only_one() -> None:
    assert binary_to_ox(1) == "O"
    assert binary_to_ox(0) == "X"
    assert binary_to_ox(-1) == "X"


def test_unsupported_claims_to_ox_treats_zero_as_clean() -> None:
    assert unsupported_claims_to_ox(0) == "O"
    assert unsupported_claims_to_ox(1) == "X"
    assert unsupported_claims_to_ox(-1) == "X"


def test_most_frequent_element_prefers_x_on_tie() -> None:
    assert most_frequent_element(["O", "X"]) == "X"
    assert most_frequent_element(["O", "O", "X", "X"]) == "X"
    assert most_frequent_element(["O", "O", "X"]) == "O"


def test_output_fieldnames_include_generation_and_evaluation_models() -> None:
    fields = output_fieldnames()
    assert "generation_provider" in fields
    assert "generation_model" in fields
    assert "evaluation_model" in fields


def test_build_row_note_includes_models_and_retrieved_ids() -> None:
    note = build_row_note(
        generated_answer="응시수수료는 기준에 따라 반환됩니다.",
        retrieved_answer_nos="12|15",
        generation_provider="gemini",
        generation_model="gemini-3.5-flash",
        evaluation_model="gemma3:4b",
        evaluation_scores=type("EvaluationScoresStub", (), {
            "similarity": 5,
            "groundedness": 2,
            "correctness": 1,
            "completeness": 1,
            "unsupported_claims": 0,
            "overall": "pass",
        })(),
        question_note="sample",
    )
    assert "generation_provider=gemini" in note
    assert "generation_model=gemini-3.5-flash" in note
    assert "evaluation_model=gemma3:4b" in note
    assert "retrieved_answer_nos=12|15" in note


def test_read_generation_questions_reads_evalset_v1_3() -> None:
    from pathlib import Path

    from evaluation.scripts.evaluate_generation import read_generation_questions

    root = Path(__file__).resolve().parents[1]
    items = read_generation_questions(root / "evaluation/evalset/evalset_v1.3.jsonl")
    by_id = {item.question_id: item for item in items}

    assert len(items) == 148
    assert "12" not in by_id  # exclude 문항
    assert by_id["52"].target_answer_no == "78 & 272|251"
    assert by_id["52"].target_answer.startswith("기한이 만료된 여권은")


def test_read_generation_questions_reads_out_of_scope_v1_3() -> None:
    from pathlib import Path

    from evaluation.scripts.evaluate_generation import OUT_OF_SCOPE_TYPE, read_generation_questions

    root = Path(__file__).resolve().parents[1]
    items = read_generation_questions(root / "evaluation/evalset/evalset_out_of_scope_v1.3.jsonl")

    assert [item.question_id for item in items] == [str(i) for i in range(154, 164)]
    assert {item.question_type for item in items} == {OUT_OF_SCOPE_TYPE}
    assert all(item.target_answer == "" for item in items)


def test_skip_out_of_scope_removes_out_of_scope_rows() -> None:
    from types import SimpleNamespace

    from evaluation.scripts.evaluate_generation import OUT_OF_SCOPE_TYPE, skip_out_of_scope

    items = [SimpleNamespace(question_type="일상표현"), SimpleNamespace(question_type=OUT_OF_SCOPE_TYPE)]

    assert skip_out_of_scope(items) == items[:1]


def test_oracle_sources_uses_all_gold_faqs_in_order() -> None:
    from evaluation.scripts.evaluate_generation import GenerationQuestion
    from evaluation.scripts.generate_answers import oracle_sources
    from src.indexing import FaqDocument

    faqs = {i: FaqDocument(i, f"제목{i}", f"본문{i}", source_row_id=i) for i in (78, 251, 272)}
    item = GenerationQuestion("52", "질문", "복수근거", "", "78 & 272|251", "답", "", "")

    sources = oracle_sources(item, faqs)

    assert [s.document.resolved_row_id for s in sources] == [78, 272, 251]


def test_generation_output_resumes_from_existing_rows(tmp_path) -> None:
    from evaluation.scripts.generate_answers import append_row, load_done_ids, output_fieldnames

    path = tmp_path / "answers.csv"
    append_row(path, {name: "" for name in output_fieldnames()} | {"question_id": "1"})
    append_row(path, {name: "" for name in output_fieldnames()} | {"question_id": "2"})

    assert load_done_ids(path) == {"1", "2"}
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM은 파일 맨 앞에 한 번만
    assert path.read_bytes().count(b"\xef\xbb\xbf") == 1

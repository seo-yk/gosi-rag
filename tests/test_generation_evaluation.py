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
    items = read_generation_questions(root / "evaluation/inputs/evalset_v1.3.jsonl")
    by_id = {item.question_id: item for item in items}

    assert len(items) == 148
    assert "12" not in by_id  # exclude 문항
    assert by_id["52"].target_answer_no == "78 & 272|251"
    assert by_id["52"].target_answer.startswith("기한이 만료된 여권은")

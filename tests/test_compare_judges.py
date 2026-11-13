from evaluation.scripts.compare_judges import cohen_kappa, compare


def test_cohen_kappa_perfect_and_chance() -> None:
    assert cohen_kappa([("pass", "pass"), ("fail", "fail")]) == 1.0
    # 사람 pass 3·fail 1, 채점기는 전부 pass → 일치율 75%지만 kappa 0
    assert cohen_kappa([("pass", "pass")] * 3 + [("fail", "pass")]) == 0.0


def test_compare_counts_fail_detection_and_errors() -> None:
    human = [
        {"condition": "A", "id": "1", "verdict": "pass", "groundedness": "2", "correctness": "1", "groups_covered": "1", "unjustified_refusal": "0"},
        {"condition": "A", "id": "2", "verdict": "fail", "groundedness": "2", "correctness": "0", "groups_covered": "1|0", "unjustified_refusal": "0"},
        {"condition": "B", "id": "3", "verdict": "pass", "groundedness": "2", "correctness": "1", "groups_covered": "1", "unjustified_refusal": "0"},
    ]
    judged = [
        {"condition": "A", "id": "1", "verdict": "pass", "groundedness": "2", "correctness": "1", "groups_covered": "1", "unjustified_refusal": "0"},
        {"condition": "A", "id": "2", "verdict": "pass", "groundedness": "2", "correctness": "1", "groups_covered": "1|1", "unjustified_refusal": "0"},
        {"condition": "B", "id": "3", "verdict": "error", "groundedness": "", "correctness": "", "groups_covered": "", "unjustified_refusal": ""},
    ]

    result = compare(human, judged)

    assert result["errors"] == 1
    assert result["fail_caught"] == (0, 1)
    assert result["verdict_agreement"] == 0.5
    assert result["groups_covered"] == 2 / 3
    assert result["disagreements"] == [("A", "2", "fail", "pass")]

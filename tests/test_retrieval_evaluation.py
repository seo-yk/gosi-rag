from evaluation.scripts.evaluate_retrieval import evaluate_rankings


def test_evaluate_rankings_calculates_hit_rates_and_mrr() -> None:
    rankings = [
        (12, [12, 3, 8]),
        (5, [9, 5, 2]),
        (7, [1, 2, 3]),
    ]

    result = evaluate_rankings(rankings)

    assert result.hit_at_1 == 1 / 3
    assert result.hit_at_3 == 2 / 3
    assert result.hit_at_5 == 2 / 3
    assert result.mrr == (1 + 1 / 2 + 0) / 3
    assert result.all_hit_at_3 == 2 / 3
    assert result.recall_at_3 == 2 / 3
    assert result.failed_expected_ids == ("7",)


def test_evaluate_rankings_supports_multiple_required_answers() -> None:
    rankings = [
        ((64, 79), [79, 10, 64]),
        ((64, 79), [79, 10, 11]),
    ]

    result = evaluate_rankings(rankings)

    assert result.hit_at_1 == 1
    assert result.mrr == 1
    assert result.all_hit_at_1 == 0
    assert result.all_hit_at_3 == 1 / 2
    assert result.recall_at_3 == 3 / 4


def test_evaluate_rankings_rejects_empty_input() -> None:
    try:
        evaluate_rankings([])
    except ValueError as error:
        assert "평가" in str(error)
    else:
        raise AssertionError("Expected ValueError")

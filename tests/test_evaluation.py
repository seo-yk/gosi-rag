from evaluation.evaluate import evaluate_rankings


def test_evaluate_rankings_calculates_hit_rates_and_mrr() -> None:
    rankings = [
        (12, [12, 3, 8]),
        (5, [9, 5, 2]),
        (7, [1, 2, 3]),
    ]

    result = evaluate_rankings(rankings)

    assert result.hit_at_1 == 1 / 3
    assert result.hit_at_3 == 2 / 3
    assert result.mrr == (1 + 1 / 2 + 0) / 3
    assert result.failed_expected_ids == (7,)


def test_evaluate_rankings_rejects_empty_input() -> None:
    try:
        evaluate_rankings([])
    except ValueError as error:
        assert "평가" in str(error)
    else:
        raise AssertionError("Expected ValueError")

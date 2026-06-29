from evaluation.evaluate_generation import (
    binary_to_ox,
    most_frequent_element,
    similarity_to_ox,
)


def test_similarity_to_ox_uses_threshold_four() -> None:
    assert similarity_to_ox(4) == "O"
    assert similarity_to_ox(5) == "O"
    assert similarity_to_ox(3) == "X"


def test_binary_to_ox_accepts_only_one() -> None:
    assert binary_to_ox(1) == "O"
    assert binary_to_ox(0) == "X"
    assert binary_to_ox(-1) == "X"


def test_most_frequent_element_prefers_x_on_tie() -> None:
    assert most_frequent_element(["O", "X"]) == "X"
    assert most_frequent_element(["O", "O", "X", "X"]) == "X"
    assert most_frequent_element(["O", "O", "X"]) == "O"

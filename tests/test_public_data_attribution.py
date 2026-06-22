from pathlib import Path

from src.indexing import load_faq_csv


ROOT = Path(__file__).parents[1]


def test_public_dataset_is_included_with_expected_schema_and_rows() -> None:
    documents = load_faq_csv(ROOT / "data" / "faq.csv")

    assert len(documents) == 289
    assert all(document.title and document.body for document in documents)


def test_readme_contains_required_public_data_attribution() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "인사혁신처" in readme
    assert "https://www.data.go.kr/data/15120427/fileData.do" in readme
    assert "공공누리 제1유형" in readme
    assert "출처표시" in readme
    assert "즉시 반영되지 않을 수" in readme

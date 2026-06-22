from pathlib import Path

import pytest

from src.indexing import load_faq_csv


FIXTURE = Path(__file__).parent / "fixtures" / "faq.csv"


def test_load_faq_csv_returns_documents() -> None:
    documents = load_faq_csv(FIXTURE)

    assert [document.row_id for document in documents] == [1, 2]
    assert documents[0].title == "응시수수료 반환"


def test_load_faq_csv_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "missing.csv"
    path.write_text("연번,제목\n1,제목\n", encoding="utf-8")

    with pytest.raises(ValueError, match="필수 컬럼"):
        load_faq_csv(path)


def test_load_faq_csv_rejects_blank_fields(tmp_path: Path) -> None:
    path = tmp_path / "blank.csv"
    path.write_text("연번,제목,본문\n1,제목,\n", encoding="utf-8")

    with pytest.raises(ValueError, match="빈 제목 또는 본문"):
        load_faq_csv(path)


def test_load_faq_csv_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.csv"
    path.write_text("연번,제목,본문\n1,A,B\n1,C,D\n", encoding="utf-8")

    with pytest.raises(ValueError, match="중복 연번"):
        load_faq_csv(path)

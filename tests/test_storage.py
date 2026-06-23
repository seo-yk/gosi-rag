from pathlib import Path

from src.indexing import load_documents


def test_load_documents_reads_saved_metadata(tmp_path: Path) -> None:
    path = tmp_path / "metadata.json"
    path.write_text(
        '[{"row_id": 1, "title": "제목", "body": "본문", "chunk_id": "row-1", "chunking_mode": "row", "source_row_id": 1}]',
        encoding="utf-8",
    )

    documents = load_documents(path)

    assert documents[0].row_id == 1
    assert documents[0].title == "제목"
    assert documents[0].resolved_row_id == 1

import json
from pathlib import Path

import faiss
import numpy as np
import pytest

from src.indexing import FaqDocument, build_chunked_documents, build_faiss_index, save_index_bundle


def test_build_faiss_index_normalizes_vectors_for_inner_product() -> None:
    vectors = np.array([[3.0, 4.0], [0.0, 2.0]], dtype=np.float32)

    index = build_faiss_index(vectors)
    scores, positions = index.search(np.array([[0.6, 0.8]], dtype=np.float32), 2)

    assert positions[0, 0] == 0
    assert scores[0, 0] == pytest.approx(1.0)


def test_save_index_bundle_writes_faiss_and_metadata(tmp_path: Path) -> None:
    documents = [
        FaqDocument(row_id=1, title="A", body="B", chunk_id="row-1", source_row_id=1),
        FaqDocument(row_id=2, title="C", body="D", chunk_id="row-2", source_row_id=2),
    ]
    index = faiss.IndexFlatIP(2)
    index.add(np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
    index_path = tmp_path / "faq.faiss"
    metadata_path = tmp_path / "metadata.json"

    save_index_bundle(index, documents, index_path, metadata_path)

    assert faiss.read_index(str(index_path)).ntotal == 2
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata[1]["row_id"] == 2
    assert metadata[1]["chunk_id"] == "row-2"


def test_save_index_bundle_rejects_count_mismatch(tmp_path: Path) -> None:
    index = faiss.IndexFlatIP(2)
    index.add(np.array([[1.0, 0.0]], dtype=np.float32))

    with pytest.raises(ValueError, match="개수"):
        save_index_bundle(
            index,
            [],
            tmp_path / "faq.faiss",
            tmp_path / "metadata.json",
        )


def test_build_chunked_documents_supports_row_paragraph_and_file_modes() -> None:
    documents = [
        FaqDocument(1, "제목", """첫째 문단.

둘째 문단.""", chunk_id="row-1", source_row_id=1),
        FaqDocument(2, "다른 제목", "본문", chunk_id="row-2", source_row_id=2),
    ]

    row_documents = build_chunked_documents(documents, "row")
    paragraph_documents = build_chunked_documents(documents, "paragraph")
    file_documents = build_chunked_documents(documents, "file")

    assert len(row_documents) == 2
    assert len(paragraph_documents) == 3
    assert paragraph_documents[0].chunking_mode == "paragraph"
    assert file_documents[0].chunking_mode == "file"
    assert file_documents[0].resolved_row_id == 0

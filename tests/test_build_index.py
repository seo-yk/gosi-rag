from pathlib import Path

import faiss
import numpy as np

from src.indexing import build_indexes


class FakeEmbedder:
    def embed(self, texts: list[str]) -> np.ndarray:
        return np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)


def test_build_indexes_creates_both_experiment_indexes(tmp_path: Path) -> None:
    csv_path = tmp_path / "faq.csv"
    csv_path.write_text("연번,제목,본문\n1,A,B\n2,C,D\n", encoding="utf-8")

    build_indexes(csv_path, tmp_path / "index", FakeEmbedder())

    assert faiss.read_index(str(tmp_path / "index" / "title.faiss")).ntotal == 2
    assert faiss.read_index(str(tmp_path / "index" / "title_body.faiss")).ntotal == 2
    assert (tmp_path / "index" / "metadata.json").exists()

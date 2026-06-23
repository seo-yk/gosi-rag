from pathlib import Path

import faiss
import numpy as np

from src.indexing import build_indexes


class FakeEmbedder:
    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for index, _text in enumerate(texts):
            if index % 2 == 0:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return np.asarray(vectors, dtype=np.float32)


def test_build_indexes_creates_chunking_and_embedding_indexes(tmp_path: Path) -> None:
    csv_path = tmp_path / "faq.csv"
    csv_path.write_text(
        """연번,제목,본문
1,A,"첫째 문단.

둘째 문단."
2,C,D
""",
        encoding="utf-8",
    )

    build_indexes(csv_path, tmp_path / "index", FakeEmbedder())

    assert faiss.read_index(str(tmp_path / "index" / "row" / "title.faiss")).ntotal == 2
    assert faiss.read_index(str(tmp_path / "index" / "paragraph" / "title_body.faiss")).ntotal == 3
    assert faiss.read_index(str(tmp_path / "index" / "file" / "title.faiss")).ntotal == 1
    assert (tmp_path / "index" / "row" / "metadata.json").exists()
    assert (tmp_path / "index" / "paragraph" / "metadata.json").exists()
    assert (tmp_path / "index" / "file" / "metadata.json").exists()

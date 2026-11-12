from pathlib import Path

import faiss
import numpy as np

import json

from src.indexing import build_indexes, load_index_manifest


class FakeEmbedder:
    def __init__(self, offset: float) -> None:
        self.offset = offset

    def embed(self, texts: list[str], role: str = "passage") -> np.ndarray:
        vectors = []
        for index, _text in enumerate(texts):
            base = 1.0 + self.offset + index
            if role == "query":
                vectors.append([base, base])
            elif index % 2 == 0:
                vectors.append([base, 0.0])
            else:
                vectors.append([0.0, base])
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

    build_indexes(
        csv_path,
        tmp_path / "index",
        {
            "openai": FakeEmbedder(0.0),
            "local": FakeEmbedder(10.0),
        },
        chunking_modes=("row", "paragraph", "sentence", "file"),
    )

    assert faiss.read_index(str(tmp_path / "index" / "row" / "openai" / "title.faiss")).ntotal == 2
    assert faiss.read_index(str(tmp_path / "index" / "paragraph" / "local" / "title_body.faiss")).ntotal == 3
    assert faiss.read_index(str(tmp_path / "index" / "file" / "openai" / "title.faiss")).ntotal == 1
    assert (tmp_path / "index" / "row" / "openai" / "metadata.json").exists()
    assert (tmp_path / "index" / "paragraph" / "local" / "metadata.json").exists()
    assert (tmp_path / "index" / "file" / "openai" / "metadata.json").exists()
    # 문장 청킹은 title_body만 만든다
    assert (tmp_path / "index" / "sentence" / "local" / "title_body.faiss").exists()
    assert not (tmp_path / "index" / "sentence" / "local" / "title.faiss").exists()

    manifest = load_index_manifest(tmp_path / "index" / "row" / "openai" / "title.faiss")
    assert manifest["source_rows"] == 2
    assert manifest["chunks"] == 2
    assert manifest["embedding_modes"] == ["title", "title_body"]
    assert len(manifest["source_sha256"]) == 64
    sentence_manifest = json.loads((tmp_path / "index" / "sentence" / "local" / "manifest.json").read_text(encoding="utf-8"))
    assert sentence_manifest["embedding_modes"] == ["title_body"]


def test_check_index_model_and_default_dir(tmp_path: Path) -> None:
    import pytest

    from src.indexing import check_index_model, default_index_dir, model_slug, resolve_provider

    assert model_slug("nlpai-lab/KURE-v1") == "kure-v1"
    assert str(default_index_dir("BAAI/bge-m3")) == "index/faq_v2/bge-m3"
    assert resolve_provider(None, {"EMBEDDING_PROVIDER": "OpenAI"}) == "openai"
    assert resolve_provider(None, {}) == "local"

    csv_path = tmp_path / "faq.csv"
    csv_path.write_text("연번,제목,본문\n1,A,B\n", encoding="utf-8")
    embedder = FakeEmbedder(0.0)
    embedder.model_name = "model-a"
    build_indexes(csv_path, tmp_path / "index", {"local": embedder}, chunking_modes=("row",))
    index_path = tmp_path / "index" / "row" / "local" / "title.faiss"

    assert check_index_model(index_path, "model-a")["chunks"] == 1
    with pytest.raises(ValueError, match="다릅니다"):
        check_index_model(index_path, "model-b")

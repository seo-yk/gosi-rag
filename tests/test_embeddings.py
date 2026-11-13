from types import SimpleNamespace

import numpy as np
import pytest

from src.indexing import LocalEmbedder, OpenAIEmbedder


class FakeEmbeddings:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0.0, 1.0]),
                SimpleNamespace(index=0, embedding=[1.0, 0.0]),
            ]
        )


class FakeSentenceTransformer:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def encode(self, sentences, **kwargs):
        self.calls.append((list(sentences), kwargs))
        return np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)


def test_openai_embedder_batches_text_and_orders_response_by_index() -> None:
    embeddings = FakeEmbeddings()
    client = SimpleNamespace(embeddings=embeddings)
    embedder = OpenAIEmbedder(client=client, model="text-embedding-3-small")

    vectors = embedder.embed(["첫 번째", "두 번째"])

    assert np.array_equal(vectors, np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
    assert embeddings.kwargs == {
        "model": "text-embedding-3-small",
        "input": ["첫 번째", "두 번째"],
        "encoding_format": "float",
    }


def test_openai_embedder_rejects_empty_input() -> None:
    embedder = OpenAIEmbedder(client=SimpleNamespace(), model="model")

    with pytest.raises(ValueError, match="비어"):
        embedder.embed([])


def test_local_embedder_prefixes_inputs_by_role_for_e5() -> None:
    model = FakeSentenceTransformer()
    embedder = LocalEmbedder(model_name="intfloat/multilingual-e5-small", model=model)

    vectors = embedder.embed(["질문입니다"], role="query")

    assert vectors.shape == (2, 2)
    sentences, kwargs = model.calls[0]
    assert sentences == ["query: 질문입니다"]
    assert kwargs == {
        "convert_to_numpy": True,
        "normalize_embeddings": False,
        "show_progress_bar": False,
    }


def test_local_embedder_does_not_prefix_non_e5_models() -> None:
    model = FakeSentenceTransformer()
    embedder = LocalEmbedder(model_name="nlpai-lab/KURE-v1", model=model)

    embedder.embed(["질문입니다"], role="query")
    embedder.embed(["본문입니다"], role="passage")

    assert [call[0] for call in model.calls] == [["질문입니다"], ["본문입니다"]]


def test_local_embedder_rejects_empty_input() -> None:
    embedder = LocalEmbedder(model_name="fake-model", model=FakeSentenceTransformer())

    with pytest.raises(ValueError, match="비어"):
        embedder.embed([])

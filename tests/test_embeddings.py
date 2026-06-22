from types import SimpleNamespace

import numpy as np
import pytest

from src.indexing import OpenAIEmbedder


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


def test_embedder_batches_text_and_orders_response_by_index() -> None:
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


def test_embedder_rejects_empty_input() -> None:
    embedder = OpenAIEmbedder(client=SimpleNamespace(), model="model")

    with pytest.raises(ValueError, match="비어"):
        embedder.embed([])

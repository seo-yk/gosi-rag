from types import SimpleNamespace

from src.generation import GeminiAnswerGenerator
from src.indexing import FaqDocument
from src.retrieval import SearchResult


class FakeModels:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(text="응시수수료는 기준에 따라 반환됩니다.")


def test_generator_uses_only_retrieved_context_and_preserves_sources() -> None:
    models = FakeModels()
    client = SimpleNamespace(models=models)
    source = SearchResult(
        document=FaqDocument(12, "응시수수료 반환", "접수 취소 시 반환 기준입니다.", chunk_id="row-12", source_row_id=12),
        score=0.91,
    )
    generator = GeminiAnswerGenerator(client=client, model="gemini-test")

    answer = generator.generate("환불 가능한가요?", [source])

    assert answer.text == "응시수수료는 기준에 따라 반환됩니다."
    assert answer.sources == (source,)
    assert models.kwargs["model"] == "gemini-test"
    prompt = str(models.kwargs["contents"])
    assert "제공된 FAQ만 근거" in prompt
    assert "[FAQ 12]" in prompt
    assert "응시수수료 반환" in prompt


def test_generator_returns_fallback_without_calling_model() -> None:
    client = SimpleNamespace(models=FakeModels())
    generator = GeminiAnswerGenerator(client=client, model="gemini-test")

    answer = generator.generate("없는 질문", [])

    assert answer.text == "검색된 FAQ에서 답변 근거를 찾을 수 없습니다."
    assert answer.sources == ()
    assert client.models.kwargs == {}

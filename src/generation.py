"""검색된 FAQ만 근거로 생성 모델 답변 생성"""

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from src.retrieval import SearchResult


class GeminiClient(Protocol):
    models: Any


class OpenRouterClient(Protocol):
    chat: Any


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    """생성 답변과 출처 묶음 보관"""
    text: str
    sources: tuple[SearchResult, ...]


def build_prompt(question: str, sources: Sequence[SearchResult]) -> str:
    """생성 모델에 전달할 공통 프롬프트 생성."""
    contexts = "\n\n".join(
        "[FAQ {row_id}]\n제목: {title}\n본문: {body}".format(
            row_id=result.document.resolved_row_id,
            title=result.document.title,
            body=result.document.body,
        )
        for result in sources
    )
    return (
        "다음 규칙을 반드시 지켜 답변하세요.\n"
        "1. 제공된 FAQ만 근거로 답변합니다.\n"
        "2. FAQ에 없는 내용을 추측하지 않습니다.\n"
        "3. 근거가 부족하면 확인할 수 없다고 답변합니다.\n\n"
        f"사용자 질문: {question}\n\n검색된 FAQ:\n{contexts}"
    )


class GeminiAnswerGenerator:
    """모델에는 FAQ 컨텍스트만 전달하고 출처는 애플리케이션이 보존"""

    def __init__(self, client: GeminiClient, model: str) -> None:
        self._client = client
        self.model = model

    def generate(self, question: str, search_results: Sequence[SearchResult]) -> GeneratedAnswer:
        """검색 결과 기반 Gemini 답변 생성"""
        sources = tuple(search_results)
        if not sources:
            return GeneratedAnswer("검색된 FAQ에서 답변 근거를 찾을 수 없습니다.", ())

        prompt = build_prompt(question, sources)
        response = self._client.models.generate_content(model=self.model, contents=prompt)
        text = (response.text or "").strip() or "답변을 생성하지 못했습니다."
        return GeneratedAnswer(text, sources)


class OpenRouterAnswerGenerator:
    """OpenRouter 호환 OpenAI API로 FAQ 기반 답변 생성"""

    def __init__(self, client: OpenRouterClient, model: str) -> None:
        self._client = client
        self.model = model

    def generate(self, question: str, search_results: Sequence[SearchResult]) -> GeneratedAnswer:
        """검색 결과 기반 OpenRouter 답변 생성"""
        sources = tuple(search_results)
        if not sources:
            return GeneratedAnswer("검색된 FAQ에서 답변 근거를 찾을 수 없습니다.", ())

        prompt = build_prompt(question, sources)
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "당신은 FAQ 기반 답변 도우미입니다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = (response.choices[0].message.content or "").strip() or "답변을 생성하지 못했습니다."
        return GeneratedAnswer(text, sources)

"""검색된 FAQ 근거로 생성 모델 답변 생성"""

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from src.retrieval import SearchResult


class GeminiClient(Protocol):
    models: Any


class OpenAIChatClient(Protocol):
    chat: Any


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    """생성 답변과 출처 묶음 보관"""
    text: str
    sources: tuple[SearchResult, ...]


def build_prompt(question: str, sources: Sequence[SearchResult]) -> str:
    """생성 모델에 전달할 공통 프롬프트 생성"""
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


OLLAMA_DEFAULT_CONTEXT = 2048  # num_ctx를 지정하지 않은 모델에 Ollama 서버가 쓰는 값(0.31 기준 실측)
TRUNCATION_MARGIN = 16


def ollama_context_length(base_url: str, model: str) -> int:
    """Ollama 모델의 실제 컨텍스트 길이(num_ctx). 모델에 없으면 서버 기본값"""
    root = re.sub(r"/v1/?$", "", base_url.rstrip("/"))
    request = urllib.request.Request(
        f"{root}/api/show", data=json.dumps({"model": model}).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        info = json.loads(response.read())
    match = re.search(r"num_ctx\s+(\d+)", info.get("parameters") or "")
    if match:
        return int(match.group(1))
    return int(os.environ.get("OLLAMA_CONTEXT_LENGTH") or OLLAMA_DEFAULT_CONTEXT)


def check_not_truncated(response: Any, context_limit: int | None, label: str) -> None:
    """Ollama는 컨텍스트를 넘는 프롬프트의 앞부분을 조용히 잘라 버린다. 입력 토큰이 한도에 닿으면 멈춘다"""
    if context_limit is None:
        return
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    if prompt_tokens is not None and prompt_tokens >= context_limit - TRUNCATION_MARGIN:
        raise RuntimeError(
            f"{label}: 입력 {prompt_tokens}토큰이 컨텍스트 한도({context_limit})에 닿아 앞부분이 잘렸을 수 있습니다. "
            "num_ctx를 늘린 모델을 쓰세요(evaluation/ollama/*.Modelfile)."
        )


class GeminiAnswerGenerator:

    def __init__(self, client: GeminiClient, model: str) -> None:
        self._client = client
        self.model = model

    def generate(self, question: str, search_results: Sequence[SearchResult]) -> GeneratedAnswer:
        sources = tuple(search_results)
        if not sources:
            return GeneratedAnswer("검색된 FAQ에서 답변 근거를 찾을 수 없습니다.", ())

        prompt = build_prompt(question, sources)
        response = self._client.models.generate_content(model=self.model, contents=prompt)
        text = (response.text or "").strip() or "답변을 생성하지 못했습니다."
        return GeneratedAnswer(text, sources)


class OpenAIAnswerGenerator:
    """OpenAI API와 Ollama(OpenAI 호환) 공용. Ollama면 context_limit을 넘겨 잘림을 검사한다"""

    def __init__(self, client: OpenAIChatClient, model: str, context_limit: int | None = None) -> None:
        self._client = client
        self.model = model
        self.context_limit = context_limit

    def generate(self, question: str, search_results: Sequence[SearchResult]) -> GeneratedAnswer:
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
        check_not_truncated(response, self.context_limit, f"생성 모델 {self.model}")
        text = (response.choices[0].message.content or "").strip() or "답변을 생성하지 못했습니다."
        return GeneratedAnswer(text, sources)

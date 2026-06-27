import os
from math import ceil
from time import perf_counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import streamlit as st
from google import genai

from src.config import load_project_env
from src.generation import GeminiAnswerGenerator, GeneratedAnswer
from src.indexing import build_embedder, index_bundle_paths
from src.retrieval import FaissRetriever, SearchMetrics, build_retriever

OPENAI_EMBEDDING_COST_PER_1M_TOKENS = 0.02
GEMINI_FLASH_INPUT_COST_PER_1M_TOKENS = 0.30
GEMINI_FLASH_OUTPUT_COST_PER_1M_TOKENS = 2.50
SERVICES_CACHE_VERSION = "2026-06-27-search-metrics-v1"


@dataclass(frozen=True, slots=True)
class MetricsData:
    """질문 처리 결과 기반 메트릭"""

    total_latency_seconds: float
    embedding_latency_seconds: float
    search_latency_seconds: float
    generation_latency_seconds: float
    estimated_cost_usd: float
    sources_used: int
    sources_limit: int
    embedding_model: str
    generation_model: str
    embedding_tokens_estimate: int
    generation_input_tokens_estimate: int
    generation_output_tokens_estimate: int
    embedding_cost_estimate_usd: float
    generation_cost_estimate_usd: float


@dataclass(frozen=True, slots=True)
class Settings:
    """앱 실행 설정 생성"""

    openai_api_key: str
    gemini_api_key: str
    embedding_provider: str
    embedding_model: str
    gemini_model: str
    chunking_mode: str
    embedding_mode: str
    top_k: int
    index_path: Path
    metadata_path: Path

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "Settings":
        """환경변수 매핑에서 앱 설정 생성"""
        gemini_api_key = values.get("GEMINI_API_KEY", "").strip()
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY 환경변수가 필요합니다.")

        embedding_provider = values.get("FAQ_EMBEDDING_PROVIDER", "openai")
        openai_api_key = values.get("OPENAI_API_KEY", "").strip()
        if embedding_provider == "openai" and not openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 필요합니다.")
        chunking_mode = values.get("FAQ_CHUNKING_MODE", "row")
        embedding_mode = values.get("FAQ_EMBEDDING_MODE", "title_body")
        top_k = int(values.get("FAQ_TOP_K", "3"))
        index_path, metadata_path = index_bundle_paths(
            values.get("FAQ_INDEX_DIR", "index"),
            chunking_mode,  # type: ignore[arg-type]
            embedding_provider,  # type: ignore[arg-type]
            embedding_mode,  # type: ignore[arg-type]
        )
        return cls(
            openai_api_key=openai_api_key,
            gemini_api_key=gemini_api_key,
            embedding_provider=embedding_provider,
            embedding_model=values.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            if embedding_provider == "openai"
            else values.get("LOCAL_EMBEDDING_MODEL", "intfloat/multilingual-e5-small"),
            gemini_model=values.get("GEMINI_MODEL", "gemini-3.5-flash"),
            chunking_mode=chunking_mode,
            embedding_mode=embedding_mode,
            top_k=top_k,
            index_path=index_path,
            metadata_path=metadata_path,
        )


@st.cache_resource
def build_services(
    settings: Settings,
    cache_version: str = SERVICES_CACHE_VERSION,
) -> tuple[FaissRetriever, GeminiAnswerGenerator]:
    """검색기와 답변 생성기 초기화 실행"""
    del cache_version
    embedder = build_embedder(
        settings.embedding_provider,
        {
            "OPENAI_API_KEY": settings.openai_api_key,
            "OPENAI_EMBEDDING_MODEL": settings.embedding_model,
            "LOCAL_EMBEDDING_MODEL": settings.embedding_model,
        },
    )
    retriever = build_retriever(settings.index_path, settings.metadata_path, embedder)
    generator = GeminiAnswerGenerator(
        client=genai.Client(api_key=settings.gemini_api_key),
        model=settings.gemini_model,
    )
    return retriever, generator


def build_generation_prompt(question: str, answer: GeneratedAnswer) -> str:
    """생성 모델에 전달한 프롬프트와 같은 구조의 텍스트 생성"""
    if not answer.sources:
        return ""

    contexts = "\n\n".join(
        "[FAQ {row_id}]\n제목: {title}\n본문: {body}".format(
            row_id=source.document.resolved_row_id,
            title=source.document.title,
            body=source.document.body,
        )
        for source in answer.sources
    )
    return (
        "다음 규칙을 반드시 지켜 답변하세요.\n"
        "1. 제공된 FAQ만 근거로 답변합니다.\n"
        "2. FAQ에 없는 내용을 추측하지 않습니다.\n"
        "3. 근거가 부족하면 확인할 수 없다고 답변합니다.\n\n"
        f"사용자 질문: {question}\n\n검색된 FAQ:\n{contexts}"
    )


def estimate_tokens(text: str) -> int:
    """한국어 FAQ 텍스트 기준의 단순 토큰 추정"""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, ceil(len(stripped) / 1.5))


def estimate_embedding_cost(provider: str, tokens: int) -> float:
    """임베딩 제공자별 요청 비용 추정"""
    if provider != "openai" or tokens <= 0:
        return 0.0
    return (tokens / 1_000_000) * OPENAI_EMBEDDING_COST_PER_1M_TOKENS


def estimate_generation_cost(input_tokens: int, output_tokens: int) -> float:
    """Gemini Flash 계열 생성 비용 추정"""
    input_cost = (input_tokens / 1_000_000) * GEMINI_FLASH_INPUT_COST_PER_1M_TOKENS
    output_cost = (output_tokens / 1_000_000) * GEMINI_FLASH_OUTPUT_COST_PER_1M_TOKENS
    return input_cost + output_cost


def build_metrics_data(
    settings: Settings,
    question: str,
    answer: GeneratedAnswer,
    embedding_latency_seconds: float,
    search_latency_seconds: float,
    generation_latency_seconds: float,
) -> MetricsData:
    """실제 요청 결과와 설정을 바탕으로 메트릭 계산"""
    embedding_tokens_estimate = estimate_tokens(question)
    prompt = build_generation_prompt(question, answer)
    generation_input_tokens_estimate = estimate_tokens(prompt)
    generation_output_tokens_estimate = estimate_tokens(answer.text) if prompt else 0
    embedding_cost_estimate_usd = estimate_embedding_cost(
        settings.embedding_provider,
        embedding_tokens_estimate,
    )
    generation_cost_estimate_usd = estimate_generation_cost(
        generation_input_tokens_estimate,
        generation_output_tokens_estimate,
    )
    return MetricsData(
        total_latency_seconds=embedding_latency_seconds + search_latency_seconds + generation_latency_seconds,
        embedding_latency_seconds=embedding_latency_seconds,
        search_latency_seconds=search_latency_seconds,
        generation_latency_seconds=generation_latency_seconds,
        estimated_cost_usd=embedding_cost_estimate_usd + generation_cost_estimate_usd,
        sources_used=len(answer.sources),
        sources_limit=settings.top_k,
        embedding_model=settings.embedding_model,
        generation_model=settings.gemini_model,
        embedding_tokens_estimate=embedding_tokens_estimate,
        generation_input_tokens_estimate=generation_input_tokens_estimate,
        generation_output_tokens_estimate=generation_output_tokens_estimate,
        embedding_cost_estimate_usd=embedding_cost_estimate_usd,
        generation_cost_estimate_usd=generation_cost_estimate_usd,
    )


def render_metrics(metrics: MetricsData) -> None:
    """답변별 메트릭 표시"""
    columns = st.columns(5)
    columns[0].metric("Latency", f"{metrics.total_latency_seconds:.2f}s")
    columns[1].metric("Embedding", f"{metrics.embedding_latency_seconds:.2f}s")
    columns[2].metric("Generation", f"{metrics.generation_latency_seconds:.2f}s")
    columns[3].metric("Cost", f"${metrics.estimated_cost_usd:.4f}")
    columns[4].metric("Sources", f"{metrics.sources_used}/{metrics.sources_limit}")

    with st.expander("자세히 보기"):
        if metrics.search_latency_seconds * 1000 < 0.01:
            search_latency_display = "< 0.01ms"
        else:
            search_latency_display = f"{metrics.search_latency_seconds * 1000:.2f}ms"

        st.write(f"검색 시간: `{search_latency_display}`")
        st.write(f"임베딩 모델: `{metrics.embedding_model}`")
        st.write(f"생성 모델: `{metrics.generation_model}`")

        token_col, cost_col = st.columns(2)

        with token_col:
            st.write("토큰")
            st.write(f"- 임베딩: `{metrics.embedding_tokens_estimate}`")
            st.write(f"- 생성 입력: `{metrics.generation_input_tokens_estimate}`")
            st.write(f"- 생성 출력: `{metrics.generation_output_tokens_estimate}`")

        with cost_col:
            st.write("비용")
            st.write(f"- 임베딩: `${metrics.embedding_cost_estimate_usd:.6f}`")
            st.write(f"- 생성: `${metrics.generation_cost_estimate_usd:.6f}`")
            st.write(f"- 총비용: `${metrics.estimated_cost_usd:.4f}`")

        st.caption("(토큰 수와 비용은 FAQ 텍스트 기준 단순 추정치이며 실제와 다를 수 있습니다)")


def main() -> None:
    """Streamlit FAQ RAG 앱 실행"""
    st.set_page_config(page_title="국가공무원 채용시험 FAQ RAG", page_icon="🔎")
    st.title("국가공무원 채용시험 FAQ RAG")
    st.caption("국가공무원 채용시험 FAQ를 검색하고 근거 기반 답변을 생성합니다.")

    load_project_env()
    try:
        settings = Settings.from_mapping(os.environ)
        retriever, generator = build_services(settings, SERVICES_CACHE_VERSION)
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        st.error(str(error))
        st.stop()

    st.sidebar.caption(
        f"provider={settings.embedding_provider}, chunking={settings.chunking_mode}, embedding={settings.embedding_mode}, top_k={settings.top_k}"
    )

    question = st.text_input("질문을 입력하세요")
    action_col, status_col = st.columns([1, 3])
    ask_clicked = action_col.button("질문하기", type="primary")
    if ask_clicked:
        if not question.strip():
            st.warning("질문을 입력하세요.")
            return

        generation_error_detail: str | None = None
        try:
            if hasattr(retriever, "search_with_metrics"):
                results, search_metrics = retriever.search_with_metrics(
                    question,
                    top_k=settings.top_k,
                )
            else:
                fallback_started_at = perf_counter()
                results = retriever.search(question, top_k=settings.top_k)
                fallback_latency_seconds = perf_counter() - fallback_started_at
                search_metrics = SearchMetrics(
                    embedding_latency_seconds=fallback_latency_seconds,
                    search_latency_seconds=0.0,
                )
        except Exception as error:
            st.error(f"검색 중 오류가 발생했습니다: {error}")
            return

        try:
            generation_started_at = perf_counter()
            generated = generator.generate(question, results)
            generation_latency_seconds = perf_counter() - generation_started_at
            answer = generated
            generation_notice = None
        except Exception as error:
            generation_latency_seconds = perf_counter() - generation_started_at
            answer = GeneratedAnswer("", tuple(results))
            generation_notice = "답변 생성 중 오류가 발생해 검색 결과만 표시됩니다. 잠시 후 다시 시도해 주세요."
            generation_error_detail = str(error)

        render_metrics(
            build_metrics_data(
                settings,
                question,
                answer,
                search_metrics.embedding_latency_seconds,
                search_metrics.search_latency_seconds,
                generation_latency_seconds,
            )
        )

        st.subheader("답변")
        if answer.text:
            st.write(answer.text)
        if generation_notice:
            st.warning(generation_notice)
        if generation_error_detail:
            with st.expander("자세히 보기"):
                st.code(generation_error_detail)
        st.subheader("출처")
        for source in answer.sources:
            document = source.document
            with st.expander(
                f"FAQ {document.resolved_row_id} · {document.title} · 유사도 {source.score:.3f}"
            ):
                st.write(document.body)


if __name__ == "__main__":
    main()

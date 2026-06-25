import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import streamlit as st
from google import genai

from src.config import load_project_env
from src.generation import GeminiAnswerGenerator, GeneratedAnswer
from src.indexing import build_embedder, index_bundle_paths
from src.retrieval import FaissRetriever, build_retriever


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
def build_services(settings: Settings) -> tuple[FaissRetriever, GeminiAnswerGenerator]:
    """검색기와 답변 생성기 초기화 실행"""
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


def main() -> None:
    """Streamlit FAQ RAG 앱 실행"""
    st.set_page_config(page_title="국가공무원 채용시험 FAQ RAG", page_icon="🔎")
    st.title("국가공무원 채용시험 FAQ RAG")
    st.caption("국가공무원 채용시험 FAQ를 검색하고 근거 기반 답변을 생성합니다.")

    load_project_env()
    try:
        settings = Settings.from_mapping(os.environ)
        retriever, generator = build_services(settings)
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        st.error(str(error))
        st.stop()

    st.sidebar.caption(
        f"provider={settings.embedding_provider}, chunking={settings.chunking_mode}, embedding={settings.embedding_mode}, top_k={settings.top_k}"
    )

    question = st.text_input("질문을 입력하세요")
    if st.button("질문하기", type="primary"):
        if not question.strip():
            st.warning("질문을 입력하세요.")
            return

        try:
            results = retriever.search(question, top_k=settings.top_k)
        except Exception as error:
            st.error(f"검색 중 오류가 발생했습니다: {error}")
            return

        try:
            generated = generator.generate(question, results)
            answer = generated
            generation_notice = None
        except Exception as error:
            answer = GeneratedAnswer(
                "Gemini 응답이 지연되어 검색 결과만 먼저 보여드립니다.\n잠시 후 다시 시도하면 답변을 받을 수 있습니다.",
                tuple(results),
            )
            generation_notice = f"답변 생성은 건너뛰고 검색 결과만 표시했어요: {error}"

        if generation_notice:
            st.warning(generation_notice)

        st.subheader("답변")
        st.write(answer.text)
        st.subheader("출처")
        for source in answer.sources:
            document = source.document
            with st.expander(
                f"FAQ {document.resolved_row_id} · {document.title} · 유사도 {source.score:.3f}"
            ):
                st.write(document.body)


if __name__ == "__main__":
    main()

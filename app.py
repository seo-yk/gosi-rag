import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import faiss
import streamlit as st
from dotenv import load_dotenv
from google import genai
from openai import OpenAI

from src.generation import GeminiAnswerGenerator
from src.indexing import OpenAIEmbedder, index_bundle_paths, load_documents
from src.retrieval import FaissRetriever


@dataclass(frozen=True, slots=True)
class Settings:
    """환경변수를 앱 실행에 필요한 설정으로 변환한다."""

    openai_api_key: str
    gemini_api_key: str
    embedding_model: str
    gemini_model: str
    chunking_mode: str
    embedding_mode: str
    top_k: int
    index_path: Path
    metadata_path: Path

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "Settings":
        openai_api_key = values.get("OPENAI_API_KEY", "").strip()
        gemini_api_key = values.get("GEMINI_API_KEY", "").strip()
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 필요합니다.")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY 환경변수가 필요합니다.")

        chunking_mode = values.get("FAQ_CHUNKING_MODE", "row")
        embedding_mode = values.get("FAQ_EMBEDDING_MODE", "title_body")
        top_k = int(values.get("FAQ_TOP_K", "3"))
        index_path, metadata_path = index_bundle_paths(
            values.get("FAQ_INDEX_DIR", "index"),
            chunking_mode,  # type: ignore[arg-type]
            embedding_mode,  # type: ignore[arg-type]
        )
        return cls(
            openai_api_key=openai_api_key,
            gemini_api_key=gemini_api_key,
            embedding_model=values.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            gemini_model=values.get("GEMINI_MODEL", "gemini-3.5-flash"),
            chunking_mode=chunking_mode,
            embedding_mode=embedding_mode,
            top_k=top_k,
            index_path=index_path,
            metadata_path=metadata_path,
        )


@st.cache_resource
def build_services(settings: Settings) -> tuple[FaissRetriever, GeminiAnswerGenerator]:
    retriever = FaissRetriever(
        index=faiss.read_index(str(settings.index_path)),
        documents=load_documents(settings.metadata_path),
        embedder=OpenAIEmbedder(
            OpenAI(api_key=settings.openai_api_key),
            settings.embedding_model,
        ),
    )
    generator = GeminiAnswerGenerator(
        client=genai.Client(api_key=settings.gemini_api_key),
        model=settings.gemini_model,
    )
    return retriever, generator


def main() -> None:
    st.set_page_config(page_title="국가공무원 채용시험 FAQ RAG", page_icon="🔎")
    st.title("국가공무원 채용시험 FAQ RAG")
    st.caption("국가공무원 채용시험 FAQ를 검색하고 근거 기반 답변을 생성합니다.")

    load_dotenv()
    try:
        settings = Settings.from_mapping(os.environ)
        retriever, generator = build_services(settings)
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        st.error(str(error))
        st.stop()

    st.sidebar.caption(
        f"chunking={settings.chunking_mode}, embedding={settings.embedding_mode}, top_k={settings.top_k}"
    )

    question = st.text_input("질문을 입력하세요")
    if st.button("질문하기", type="primary"):
        if not question.strip():
            st.warning("질문을 입력하세요.")
            return

        try:
            results = retriever.search(question, top_k=settings.top_k)
            generated = generator.generate(question, results)
        except Exception as error:
            st.error(f"질의 처리 중 오류가 발생했습니다: {error}")
            return

        st.subheader("답변")
        st.write(generated.text)
        st.subheader("출처")
        for source in generated.sources:
            document = source.document
            with st.expander(
                f"FAQ {document.resolved_row_id} · {document.title} · 유사도 {source.score:.3f}"
            ):
                st.write(document.body)


if __name__ == "__main__":
    main()

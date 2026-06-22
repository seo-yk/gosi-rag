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
from src.indexing import OpenAIEmbedder, load_documents
from src.retrieval import FaissRetriever


@dataclass(frozen=True, slots=True)
class Settings:
    """환경변수를 앱 실행에 필요한 설정으로 변환한다."""

    openai_api_key: str
    gemini_api_key: str
    embedding_model: str
    gemini_model: str
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
        return cls(
            openai_api_key=openai_api_key,
            gemini_api_key=gemini_api_key,
            embedding_model=values.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            gemini_model=values.get("GEMINI_MODEL", "gemini-3.5-flash"),
            index_path=Path(values.get("FAQ_INDEX_PATH", "index/title_body.faiss")),
            metadata_path=Path(values.get("FAQ_METADATA_PATH", "index/metadata.json")),
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

    question = st.text_input("질문을 입력하세요")
    if st.button("질문하기", type="primary"):
        if not question.strip():
            st.warning("질문을 입력하세요.")
            return

        try:
            results = retriever.search(question, top_k=3)
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
                f"FAQ {document.row_id} · {document.title} · 유사도 {source.score:.3f}"
            ):
                st.write(document.body)


if __name__ == "__main__":
    main()

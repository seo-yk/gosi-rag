"""FAISS 인덱스 저장"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

import faiss
import numpy as np
import pandas as pd
from openai import OpenAI


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config import load_project_env

EmbeddingMode = Literal["title", "title_body"]
EmbeddingProvider = Literal["openai", "local"]
EmbeddingRole = Literal["query", "passage"]
ChunkingMode = Literal["row", "paragraph", "sentence", "file"]
REQUIRED_COLUMNS = {"연번", "제목", "본문"}
ENCODINGS = ("utf-8-sig", "utf-8", "cp949")
LOCAL_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"


@dataclass(frozen=True, slots=True)
class FaqDocument:
    """검색과 출처 표시에 사용하는 하나의 FAQ 또는 청크 레코드"""

    row_id: int
    title: str
    body: str
    chunk_id: str | None = None
    chunking_mode: ChunkingMode = "row"
    source_row_id: int | None = None
    paragraph_index: int | None = None

    @property
    def resolved_row_id(self) -> int:
        """출처 표시용 FAQ 연번 반환"""
        return self.source_row_id if self.source_row_id is not None else self.row_id

    def embedding_text(self, mode: EmbeddingMode) -> str:
        """임베딩 입력 텍스트 생성"""
        if mode == "title":
            return self.title
        if mode == "title_body":
            return f"제목: {self.title}\n본문: {self.body}"
        raise ValueError(f"Unsupported embedding mode: {mode}")


class EmbeddingClient(Protocol):
    embeddings: Any


class LocalEmbeddingModel(Protocol):
    def encode(self, sentences: Sequence[str], **kwargs: Any) -> Any: ...


class Embedder(Protocol):
    def embed(self, texts: Sequence[str], role: EmbeddingRole = "passage") -> np.ndarray: ...


class OpenAIEmbedder:

    def __init__(self, client: EmbeddingClient, model: str = "text-embedding-3-small") -> None:
        self._client = client
        self.model = model

    def embed(self, texts: Sequence[str], role: EmbeddingRole = "passage") -> np.ndarray:
        del role
        if not texts:
            raise ValueError("임베딩할 텍스트 목록이 비어 있습니다.")

        response = self._client.embeddings.create(
            model=self.model,
            input=list(texts),
            encoding_format="float",
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return np.asarray([item.embedding for item in ordered], dtype=np.float32)


class LocalEmbedder:

    def __init__(self, model_name: str = LOCAL_EMBEDDING_MODEL, model: LocalEmbeddingModel | None = None) -> None:
        self.model_name = model_name
        self._model = model

    def _load_model(self) -> LocalEmbeddingModel:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:  # pragma: no cover - exercised only when dependency missing
            raise RuntimeError(
                "local embeddings require the 'sentence-transformers' package"
            ) from error
        self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: Sequence[str], role: EmbeddingRole = "passage") -> np.ndarray:
        if not texts:
            raise ValueError("임베딩할 텍스트 목록이 비어 있습니다.")

        prefix = "query: " if role == "query" else "passage: "
        payload = [f"{prefix}{text}" for text in texts]
        model = self._load_model()
        vectors = model.encode(
            payload,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: UnicodeDecodeError | None = None
    for encoding in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=encoding, dtype={"연번": "Int64"})
        except UnicodeDecodeError as error:
            last_error = error
    raise ValueError("지원하는 인코딩으로 CSV를 읽을 수 없습니다.") from last_error


def _split_paragraphs(body: str) -> list[str]:
    stripped = body.strip()
    if not stripped:
        return []

    parts = [part.strip() for part in re.split(r"\n\s*\n+", stripped) if part.strip()]
    if parts:
        return parts

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    return lines if lines else [stripped]


# 한글·닫는 괄호/따옴표 뒤의 마침표·물음표·느낌표에서만 자른다("2007.12.31." 같은 날짜는 자르지 않음)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[가-힣)\]」』\"'][.?!])\s+")
MIN_SENTENCE_CHARS = 20  # 이보다 짧은 조각은 앞 문장에 붙인다


def _split_sentences(body: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE_BOUNDARY.split(body.strip()) if part.strip()]
    sentences: list[str] = []
    for part in parts:
        if sentences and len(part) < MIN_SENTENCE_CHARS:
            sentences[-1] = f"{sentences[-1]} {part}"
        else:
            sentences.append(part)
    return sentences


def _chunk_label(row_id: int, chunking_mode: ChunkingMode, paragraph_index: int | None = None) -> str:
    if chunking_mode == "file":
        return "file-0"
    if chunking_mode in ("paragraph", "sentence"):
        suffix = paragraph_index if paragraph_index is not None else 1
        marker = "p" if chunking_mode == "paragraph" else "s"
        return f"row-{row_id}-{marker}{suffix}"
    return f"row-{row_id}"


def load_faq_csv(path: str | Path) -> list[FaqDocument]:
    frame = _read_csv(Path(path))
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing))}")
    if frame["연번"].isna().any():
        raise ValueError("빈 연번이 있습니다.")

    titles = frame["제목"].fillna("").astype(str).str.strip()
    bodies = frame["본문"].fillna("").astype(str).str.strip()
    if titles.eq("").any() or bodies.eq("").any():
        raise ValueError("빈 제목 또는 본문이 있습니다.")

    row_ids = frame["연번"].astype(int)
    if row_ids.duplicated().any():
        raise ValueError("중복 연번이 있습니다.")

    return [
        FaqDocument(
            int(row_id),
            title,
            body,
            chunk_id=_chunk_label(int(row_id), "row"),
            chunking_mode="row",
            source_row_id=int(row_id),
        )
        for row_id, title, body in zip(row_ids, titles, bodies, strict=True)
    ]


def build_chunked_documents(documents: Sequence[FaqDocument], chunking_mode: ChunkingMode) -> list[FaqDocument]:
    """행/문단/문장/파일 전체 기준으로 검색용 청크 생성

    sentence: 본문을 문장 단위로 자르고 청크마다 FAQ 제목을 유지한다(title_body 임베딩 시 제목이 문맥 머리말 역할).
    """

    if chunking_mode == "sentence":
        return [
            FaqDocument(
                document.row_id,
                document.title,
                sentence,
                chunk_id=_chunk_label(document.row_id, "sentence", index),
                chunking_mode="sentence",
                source_row_id=document.resolved_row_id,
                paragraph_index=index,
            )
            for document in documents
            for index, sentence in enumerate(_split_sentences(document.body) or [document.body], start=1)
        ]

    if chunking_mode == "row":
        return [
            FaqDocument(
                document.row_id,
                document.title,
                document.body,
                chunk_id=_chunk_label(document.row_id, "row"),
                chunking_mode="row",
                source_row_id=document.resolved_row_id,
            )
            for document in documents
        ]

    if chunking_mode == "paragraph":
        chunks: list[FaqDocument] = []
        for document in documents:
            paragraphs = _split_paragraphs(document.body)
            if not paragraphs:
                paragraphs = [document.body]
            for index, paragraph in enumerate(paragraphs, start=1):
                chunks.append(
                    FaqDocument(
                        document.row_id,
                        document.title,
                        paragraph,
                        chunk_id=_chunk_label(document.row_id, "paragraph", index),
                        chunking_mode="paragraph",
                        source_row_id=document.resolved_row_id,
                        paragraph_index=index,
                    )
                )
        return chunks

    if chunking_mode == "file":
        body = "\n\n".join(
            f"[FAQ {document.row_id}] {document.title}\n{document.body}" for document in documents
        )
        return [
            FaqDocument(
                0,
                "전체 FAQ",
                body,
                chunk_id=_chunk_label(0, "file"),
                chunking_mode="file",
                source_row_id=None,
            )
        ]

    raise ValueError(f"Unsupported chunking mode: {chunking_mode}")


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    """코사인 유사도(cosine similarity) 계산용 L2 정규화 실행"""
    normalized = np.asarray(vectors, dtype=np.float32).copy()
    if normalized.ndim != 2 or normalized.shape[0] == 0:
        raise ValueError("임베딩 벡터는 비어 있지 않은 2차원 배열이어야 합니다.")
    faiss.normalize_L2(normalized)
    return normalized


def build_faiss_index(vectors: np.ndarray) -> faiss.IndexFlatIP:
    """L2 정규화 후 내적 검색을 사용해 cosine similarity 인덱스 생성"""

    normalized = normalize_vectors(vectors)
    index = faiss.IndexFlatIP(normalized.shape[1])
    index.add(normalized)
    return index


def index_bundle_paths(
    output_dir: str | Path,
    chunking_mode: ChunkingMode,
    embedding_provider: EmbeddingProvider,
    embedding_mode: EmbeddingMode,
) -> tuple[Path, Path]:
    """인덱스와 메타데이터 저장 경로 생성"""
    mode_dir = Path(output_dir) / chunking_mode / embedding_provider
    return mode_dir / f"{embedding_mode}.faiss", mode_dir / "metadata.json"


def save_index_bundle(
    index: faiss.Index,
    documents: Sequence[FaqDocument],
    index_path: str | Path,
    metadata_path: str | Path,
) -> None:
    """FAISS 인덱스와 FAQ 메타데이터 저장"""
    if index.ntotal != len(documents):
        raise ValueError("FAISS 벡터 개수와 메타데이터 개수가 다릅니다.")

    faiss_path = Path(index_path)
    json_path = Path(metadata_path)
    faiss_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(faiss_path))
    json_path.write_text(
        json.dumps([asdict(document) for document in documents], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_documents(path: str | Path) -> list[FaqDocument]:
    """저장된 FAQ 메타데이터 로드"""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    documents: list[FaqDocument] = []
    for row in rows:
        documents.append(
            FaqDocument(
                int(row["row_id"]),
                str(row["title"]),
                str(row["body"]),
                chunk_id=row.get("chunk_id"),
                chunking_mode=row.get("chunking_mode", "row"),
                source_row_id=row.get("source_row_id"),
                paragraph_index=row.get("paragraph_index"),
            )
        )
    return documents


def is_supported_combination(chunking_mode: ChunkingMode, embedding_mode: EmbeddingMode) -> bool:
    """문장 청크는 FAQ마다 제목이 같아 title만 임베딩하면 같은 벡터가 반복되므로 만들지 않는다"""
    return not (chunking_mode == "sentence" and embedding_mode == "title")


def build_indexes(
    csv_path: Path,
    output_dir: Path,
    embedders: dict[EmbeddingProvider, Embedder],
    chunking_modes: Sequence[ChunkingMode] = ("row", "paragraph", "file"),
    embedding_modes: Sequence[EmbeddingMode] = ("title", "title_body"),
) -> None:
    """청킹 방식과 임베딩 입력 필드를 조합해 실험용 인덱스 생성"""

    source_documents = load_faq_csv(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    for chunking_mode in chunking_modes:
        chunked_documents = build_chunked_documents(source_documents, chunking_mode)
        for embedding_provider, embedder in embedders.items():
            mode_dir = output_dir / chunking_mode / embedding_provider
            mode_dir.mkdir(parents=True, exist_ok=True)
            metadata_path = mode_dir / "metadata.json"

            for embedding_mode in embedding_modes:
                if not is_supported_combination(chunking_mode, embedding_mode):
                    continue
                vectors = embedder.embed(
                    [document.embedding_text(embedding_mode) for document in chunked_documents],
                    role="passage",
                )
                index_path = mode_dir / f"{embedding_mode}.faiss"
                save_index_bundle(build_faiss_index(vectors), chunked_documents, index_path, metadata_path)


def build_embedder(provider: EmbeddingProvider, values: Mapping[str, str]) -> Embedder:
    """임베딩 제공자별 Embedder 생성"""
    if provider == "openai":
        api_key = values.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 필요합니다.")
        model = values.get("EMBEDDING_MODEL", "text-embedding-3-small")
        return OpenAIEmbedder(OpenAI(api_key=api_key), model)
    if provider == "local":
        model_name = values.get("EMBEDDING_MODEL", LOCAL_EMBEDDING_MODEL)
        return LocalEmbedder(model_name=model_name)
    raise ValueError(f"Unsupported embedding provider: {provider}")


def main() -> None:
    """FAQ 인덱스 생성 CLI 실행"""
    parser = argparse.ArgumentParser(description="FAQ CSV에서 FAISS 인덱스를 생성합니다.")
    parser.add_argument("--csv", type=Path, default=Path("data/faq_v2.csv"), help="원본 재현은 data/faq.csv")
    parser.add_argument("--output", type=Path, default=Path("index/faq_v2"))
    parser.add_argument("--providers", nargs="+", default=["openai", "local"])
    parser.add_argument("--chunking-modes", nargs="+", default=["row", "sentence"])
    parser.add_argument("--embedding-modes", nargs="+", default=["title", "title_body"])
    args = parser.parse_args()

    load_project_env()
    embedders = {provider: build_embedder(provider, os.environ) for provider in args.providers}
    build_indexes(
        args.csv,
        args.output,
        embedders,
        tuple(args.chunking_modes),
        tuple(args.embedding_modes),
    )


if __name__ == "__main__":
    main()

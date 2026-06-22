"""FAQ CSV를 검증하고 임베딩하여 FAISS 인덱스로 저장한다."""

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence

import faiss
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


EmbeddingMode = Literal["title", "title_body"]
REQUIRED_COLUMNS = {"연번", "제목", "본문"}
ENCODINGS = ("utf-8-sig", "utf-8", "cp949")


@dataclass(frozen=True, slots=True)
class FaqDocument:
    """검색과 출처 표시에 사용하는 하나의 FAQ 레코드."""

    row_id: int
    title: str
    body: str

    def embedding_text(self, mode: EmbeddingMode) -> str:
        if mode == "title":
            return self.title
        if mode == "title_body":
            return f"제목: {self.title}\n본문: {self.body}"
        raise ValueError(f"Unsupported embedding mode: {mode}")


class EmbeddingClient(Protocol):
    embeddings: Any


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


class OpenAIEmbedder:
    """OpenAI Embeddings API 응답을 FAISS가 사용할 float32 배열로 변환한다."""

    def __init__(self, client: EmbeddingClient, model: str = "text-embedding-3-small") -> None:
        self._client = client
        self.model = model

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            raise ValueError("임베딩할 텍스트 목록이 비어 있습니다.")

        response = self._client.embeddings.create(
            model=self.model,
            input=list(texts),
            encoding_format="float",
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return np.asarray([item.embedding for item in ordered], dtype=np.float32)


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: UnicodeDecodeError | None = None
    for encoding in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=encoding, dtype={"연번": "Int64"})
        except UnicodeDecodeError as error:
            last_error = error
    raise ValueError("지원하는 인코딩으로 CSV를 읽을 수 없습니다.") from last_error


def load_faq_csv(path: str | Path) -> list[FaqDocument]:
    """CSV 필수 컬럼과 값의 무결성을 검사한 뒤 FAQ 목록을 반환한다."""

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
        FaqDocument(int(row_id), title, body)
        for row_id, title, body in zip(row_ids, titles, bodies, strict=True)
    ]


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    normalized = np.asarray(vectors, dtype=np.float32).copy()
    if normalized.ndim != 2 or normalized.shape[0] == 0:
        raise ValueError("임베딩 벡터는 비어 있지 않은 2차원 배열이어야 합니다.")
    faiss.normalize_L2(normalized)
    return normalized


def build_faiss_index(vectors: np.ndarray) -> faiss.IndexFlatIP:
    """L2 정규화 후 내적 검색을 사용해 cosine similarity 인덱스를 만든다."""

    normalized = normalize_vectors(vectors)
    index = faiss.IndexFlatIP(normalized.shape[1])
    index.add(normalized)
    return index


def save_index_bundle(
    index: faiss.Index,
    documents: Sequence[FaqDocument],
    index_path: str | Path,
    metadata_path: str | Path,
) -> None:
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
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        FaqDocument(int(row["row_id"]), str(row["title"]), str(row["body"]))
        for row in rows
    ]


def build_indexes(csv_path: Path, output_dir: Path, embedder: Embedder) -> None:
    """제목 전용과 제목+본문 비교 실험용 인덱스를 함께 생성한다."""

    documents = load_faq_csv(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    for mode in ("title", "title_body"):
        vectors = embedder.embed([document.embedding_text(mode) for document in documents])
        save_index_bundle(
            build_faiss_index(vectors),
            documents,
            output_dir / f"{mode}.faiss",
            output_dir / "metadata.json",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="FAQ CSV에서 FAISS 인덱스를 생성합니다.")
    parser.add_argument("--csv", type=Path, default=Path("data/faq.csv"))
    parser.add_argument("--output", type=Path, default=Path("index"))
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY 환경변수가 필요합니다.")
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    build_indexes(args.csv, args.output, OpenAIEmbedder(OpenAI(api_key=api_key), model))


if __name__ == "__main__":
    main()

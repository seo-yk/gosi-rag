# 국가공무원 채용시험 FAQ RAG

인사혁신처 사이버국가고시센터의 국가공무원 채용시험 FAQ를 검색하고, 검색 문서만 근거로 답변과 출처를 제공하는 RAG 프로젝트입니다.

## 주요 기능

- CSV의 `FAQ 1행 = 청크 1개` 전처리
- OpenAI `text-embedding-3-small` 임베딩
- FAISS와 cosine similarity 기반 Top 3 검색
- Gemini 기반 근거 제한 답변 생성
- FAQ 연번·제목·본문·유사도 출처 표시
- 제목 임베딩과 제목+본문 임베딩의 Hit@1·Hit@3·MRR 비교

## 기술 스택

Python, Pandas, NumPy, OpenAI API, FAISS, Google Gen AI SDK, Gemini, Streamlit, Pytest

## 처리 흐름

```text
CSV 로드 및 검증
→ 제목 / 제목+본문 임베딩
→ L2 정규화 및 FAISS IndexFlatIP 저장
→ 질문 임베딩 및 cosine similarity 검색
→ Top 3 FAQ를 Gemini에 전달
→ 답변과 애플리케이션 검증 출처 표시
```

## 설치

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 `OPENAI_API_KEY`와 `GEMINI_API_KEY`를 설정합니다.

## 데이터 준비

공공데이터포털에서 제공하는 CSV가 `data/faq.csv`에 포함되어 있습니다. 데이터는 `연번`, `제목`, `본문` 컬럼과 289개 FAQ로 구성됩니다.

## 인덱스 생성

```bash
python src/indexing.py --csv data/faq.csv --output index
```

다음 파일이 생성됩니다.

```text
index/
├── title.faiss
├── title_body.faiss
└── metadata.json
```

## 실행

```bash
python -m streamlit run app.py
```

## 검색 평가

`evaluation/questions.csv`에 실제 평가 질문과 정답 FAQ 연번을 작성합니다.

```bash
python evaluation/evaluate.py \
  --questions evaluation/questions.csv \
  --index-dir index \
  --output output/evaluation_summary.csv
```

평가 지표:

- Hit@1
- Hit@3
- MRR
- 정답 FAQ 미검색 사례

## 프로젝트 구조

```text
.
├── app.py
├── src/
│   ├── indexing.py
│   ├── retrieval.py
│   └── generation.py
├── evaluation/
│   ├── questions.csv
│   └── evaluate.py
├── tests/
├── data/
├── .env.example
├── requirements.txt
└── README.md
```

## 핵심 설계 결정

- CSV 행이 독립된 FAQ이므로 행 단위 청킹을 사용합니다.
- 임베딩 생성과 벡터 비교를 분리합니다.
- 벡터를 L2 정규화한 뒤 FAISS 내적 검색을 사용해 cosine similarity 순위를 구합니다.
- 생성 모델이 출처를 만들게 하지 않고 검색 메타데이터를 애플리케이션이 표시합니다.
- 기본 검색 성능을 먼저 평가하고, 정답 후보의 순위 문제가 반복될 때 reranker를 검토합니다.

## 데이터 출처

- 제공기관: 인사혁신처
- 데이터명: 인사혁신처_사이버국가고시센터 국가공무원 채용시험 종합안내(FAQ)_20260320
- 기준일: 2026-03-20
- 출처: [공공데이터포털](https://www.data.go.kr/data/15120427/fileData.do)
- 이용허락: 공공누리 제1유형(출처표시)

이 저장소는 위 출처와 이용허락 조건을 명시하고 원본 CSV를 활용합니다. 공무원 채용 제도가 변경된 경우 데이터에 즉시 반영되지 않을 수 있으므로 실제 지원 전 최신 공고와 제도를 별도로 확인해야 합니다.

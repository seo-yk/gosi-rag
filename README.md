# 국가공무원 채용시험 FAQ RAG

인사혁신처 사이버국가고시센터의 국가공무원 채용시험 FAQ 데이터를 근거로 답변을 제공하는 RAG(Retrieval-Augmented Generation) 프로젝트.

## 개요 및 목표

이 프로젝트는 국가공무원 채용시험 FAQ 데이터를 기반으로 RAG 질의응답 시스템을 구현하고, 현재 데이터셋에 가장 적합한 검색 구조를 찾기 위한 비교 실험을 수행하는 것을 목표로 합니다.

구체적으로는 다음 네 가지 비교를 수행하고, Hit@K, MRR 평가를 통해 설계 결정을 검증합니다.

- 청킹 방식 비교: 행 단위 / 문단 단위 / 파일 전체 단위
- 임베딩 방식 비교: OpenAI 임베딩 / Local 임베딩
- 임베딩 입력 필드 비교: 제목 / 제목 + 본문
- 검색 범위 비교: Top 3 / Top 5

실제 실험 결과는 문서 하단의 평가 결과 섹션에 정리했습니다.

## 기술 스택

| 영역     | 기술                                                                                                   | 비고                       |
| ------ | ---------------------------------------------------------------------------------------------------- | ------------------------ |
| 언어     | Python                                                                                               | 데이터 처리 및 AI API 연동       |
| 데이터 처리 | Pandas, NumPy                                                                                        | CSV 탐색 및 전처리             |
| 임베딩    | OpenAI: `text-embedding-3-small`<br>Local: `intfloat/multilingual-e5-small`(`sentence-transformers`) | 텍스트 → 벡터 변환,<br>성능 비교 실험 |
| 벡터 검색  | FAISS(IndexFlatIP), cosine similarity                                                                | 텍스트 임베딩 의미 비교            |
| 답변 생성  | Gemini API                                                                                           | 자연어 답변 생성                |
| UI     | Streamlit                                                                                            | 데모 UI                    |
|        |                                                                                                      |                          |

## 디렉터리 구조

```text
gosi-rag/
├── app.py               # 질의응답 데모 앱(UI)
├── src/
│   ├── indexing.py      # 데이터 전처리, 청킹, 임베딩, FAISS 인덱스 생성
│   ├── retrieval.py     # 질문 임베딩과 Top K 유사 문서 검색
│   └── generation.py    # 검색 결과 기반 최종 답변 생성
├── evaluation/
│   ├── questions.csv    # 검색 성능 평가용 질문셋 및 정답 FAQ ID
│   └── evaluate.py      # Hit@K, MRR 기반 검색 성능 평가 스크립트
├── tests/               # 핵심 로직 테스트
├── data/                # 원본 데이터
├── .env.openai.example  # 환경 변수 예시 파일(openai 임베딩)
├── .env.local.example   # 환경 변수 예시 파일(local 임베딩)
├── requirements.txt     # 의존성 목록
└── README.md
```


## 데이터셋

- 출처: [인사혁신처 사이버국가고시센터의 국가공무원 채용시험 FAQ, 2026-03-20 기준](https://www.data.go.kr/data/15120427/fileData.do)
- 형식: CSV
- 주요 컬럼: `연번`, `제목`, `본문`
- 레코드 수: 289개
- 데이터 크기: 약 232KB

## 설치

- 권장: Python 3.11 이상

```bash
# 저장소 클론
git clone <repository-url>
cd gosi-rag

# 가상환경 생성
python -m venv .venv

# 활성화 (MacOS, Linux)
source .venv/bin/activate

# 활성화 (Windows)
.venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

## 환경변수 설정

| 기능          | 방식                               | 비용  | 설정 방법                                                                  | 비고                                                           |
| ----------- | -------------------------------- | --- | ---------------------------------------------------------------------- | ------------------------------------------------------------ |
| 답변 생성 (필수)  | Gemini API                       | 무료  | `.env.local.example` 또는 `.env.openai.example`를 복사해 `GEMINI_API_KEY` 설정 | 발급: [Google AI Studio](https://aistudio.google.com/)         |
| 임베딩(Local)  | `intfloat/multilingual-e5-small` | 무료  | `.env.local.example`를 기준으로 `.env.local` 작성                             | 로컬 모델 기반 임베딩                                                 |
| 임베딩(OpenAI) | `text-embedding-3-small`         | 유료  | `.env.openai.example`를 기준으로 `.env.openai` 작성 후 `OPENAI_API_KEY` 설정     | 발급: [OpenAI API Platform](https://platform.openai.com/login) |

## 실행 방식

```bash
# 로컬 임베딩 실행
cp .env.local.example .env.local
FAQ_ENV_FILE=.env.local python3 src/indexing.py --csv data/faq.csv --output index --providers local
FAQ_ENV_FILE=.env.local python3 -m streamlit run app.py

# OpenAI 임베딩 실행
cp .env.openai.example .env.openai
FAQ_ENV_FILE=.env.openai python3 src/indexing.py --csv data/faq.csv --output index --providers openai
FAQ_ENV_FILE=.env.openai python3 -m streamlit run app.py
```

## 파이프라인 실행 순서

### Step 1. 인덱스 생성

FAQ 데이터를 청킹하고 임베딩한 뒤 FAISS 인덱스를 생성합니다.

```bash
FAQ_ENV_FILE=.env.local python3 src/indexing.py --csv data/faq.csv --output index --providers local
```

- `data/faq.csv`를 읽어 청킹(row / paragraph / file)별 문서를 생성합니다.
- 각 문서를 임베딩하고 FAISS 인덱스를 저장합니다.
- 결과:
    - `index/{chunking}/{provider}/{embedding_mode}.faiss`
    - `index/{chunking}/{provider}/metadata.json`

### Step 2. 질의응답 앱 실행

Streamlit 앱을 실행해 직접 질문을 입력하고 검색 결과와 답변을 확인합니다.

```bash
FAQ_ENV_FILE=.env.local python3 -m streamlit run app.py
```

- 질문을 입력하면 FAQ 검색 후 Gemini 기반 답변을 생성합니다.
- Gemini 응답이 실패하면 검색 결과를 우선 표시합니다.

### Step 3. 검색 성능 평가

평가 질문셋을 기준으로 Hit@K와 MRR를 계산합니다.

```bash
FAQ_ENV_FILE=.env.local python3 -m evaluation.evaluate --questions evaluation/questions.csv --index-dir index --output output/evaluation_summary.csv --providers local
```

- `evaluation/questions.csv`를 기준으로 검색 성능을 측정합니다.
- 결과:
    - `output/evaluation_summary.csv`

## 평가 결과

| 청킹        | 입력 필드      | Top K | Hit@1 | Hit@3 | Hit@5 |   MRR | 비고             |
| --------- | ---------- | ----: | ----: | ----: | ----: | ----: | -------------- |
| row       | title      |     3 | 90.2% | 96.1% | 96.1% | 0.928 | 가장 좋은 조합 중 하나  |
| row       | title_body |     3 | 86.3% | 96.1% | 96.1% | 0.905 | title 대비 소폭 하락 |
| paragraph | title      |     3 | 90.2% | 96.1% | 96.1% | 0.928 | row와 동일        |
| paragraph | title_body |     3 | 86.3% | 96.1% | 96.1% | 0.905 | row와 동일        |
| file      | title      |     3 |  0.0% |  0.0% |  0.0% | 0.000 | 단일 파일 청킹은 부적합  |

평가 지표는 다음과 같습니다.

- Hit@1: 정답 FAQ가 첫 번째 결과인지 측정
- Hit@3: 정답 FAQ가 상위 3개에 포함되는지 측정
- Hit@5: 정답 FAQ가 상위 5개에 포함되는지 측정
- MRR: 정답 FAQ의 평균적인 순위 품질 측정
- 실패 사례 분석: 유의어, 일상 표현, 복합 질문에서 놓친 문서 확인

Top K를 비교한 결과 현재 질문셋에서는 성능 차이가 없어, 컨텍스트 길이와 토큰 비용을 고려해 기본 검색 범위를 `Top 3`로 두었습니다.

실제 수치는 다음과 같은 방향성을 보여줍니다.

- 행 단위와 문단 단위는 현재 데이터셋에서 거의 동일하게 동작함
- 제목만 임베딩한 설정이 제목+본문보다 약간 더 안정적임
- 파일 전체 단위 청킹은 검색 후보를 너무 크게 뭉쳐 성능이 크게 떨어짐

## 개선 검토

- FAQ 내용이 변경될 때 증분 색인 기능 필요
- 키워드가 중요한 질문에서는 BM25 기반 하이브리드 검색 검토
- 검색 후보의 순위 품질이 부족할 경우 reranker 검토
- 데이터 규모 증가 시 Qdrant 또는 pgvector 등의 벡터 DB 도입 검토

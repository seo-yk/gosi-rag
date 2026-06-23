# 국가공무원 채용시험 FAQ RAG

인사혁신처 사이버국가고시센터의 국가공무원 채용시험 FAQ를 검색하고, 검색된 문서를 근거로 답변과 출처를 제공하는 RAG(Retrieval-Augmented Generation) 프로젝트입니다.

## 프로젝트 소개

FAQ 문서는 정확한 답변을 포함하고 있어도 사용자의 표현과 문서 제목이 다르면 원하는 정보를 찾기 어렵습니다. 이 프로젝트는 사용자 질문과 의미적으로 가까운 FAQ를 검색하고, 검색된 문서만 생성 모델에 전달하여 근거가 명확한 답변을 제공하는 것을 목표로 합니다.

핵심 흐름은 다음과 같습니다.

```text
FAQ 색인
→ 사용자 질문 임베딩
→ 유사 FAQ 검색
→ 검색 결과를 컨텍스트로 전달
→ 답변과 출처 반환
```

## 주요 기능

- CSV FAQ 데이터 로드 및 전처리
- FAQ 한 행 단위 청킹을 기본 가설로 두고 행/문단/파일 전체를 비교
- 로컬 임베딩과 OpenAI 임베딩 방식 비교
- cosine similarity를 이용한 Top 3 및 Top 5 FAQ 검색
- 검색된 FAQ만 활용한 Gemini 답변 생성
- Gemini 응답이 지연될 때 검색 결과 우선 표시 fallback
- 답변에 사용된 FAQ 연번과 제목 표시
- 제목 임베딩과 제목·본문 임베딩의 검색 성능 비교

## 기술 스택

| 영역 | 기술 | 선택 이유 |
|---|---|---|
| 언어 | Python | 데이터 처리와 AI API 연동 생태계가 풍부함 |
| 데이터 처리 | Pandas | CSV 탐색과 행 단위 전처리가 간단함 |
| 임베딩 | OpenAI `text-embedding-3-small`, 로컬 `sentence-transformers` | 두 임베딩 방식을 비교하고, 로컬 실행도 가능하게 하기 위함 |
| 벡터 검색 | FAISS, cosine similarity | 현재 데이터 규모에서 단순하고 빠르게 검색 가능 |
| 답변 생성 | Gemini API | 검색 문서를 기반으로 자연어 답변 생성 |
| UI | Streamlit | 검색 결과와 출처를 빠르게 시각화 가능 |
| 설정 관리 | `.env` 분리 | 로컬 / OpenAI 실행 환경을 분리 관리 |

## 시스템 구조와 처리 흐름

```text
[색인 단계]
FAQ CSV
→ 청킹 방식 선택(행/문단/파일 전체)
→ "제목" 또는 "제목 + 본문" 구성
→ 로컬 또는 OpenAI 임베딩 생성
→ 벡터와 FAQ 메타데이터 저장

[질의 단계]
사용자 질문
→ 질문 임베딩 생성
→ 질문 벡터와 FAQ 벡터의 cosine similarity 계산
→ 유사도 기준 Top 3 또는 Top 5 선택
→ 검색된 FAQ를 Gemini에 전달
→ 답변과 검증된 출처 반환
```

임베딩 모델은 텍스트를 벡터로 변환합니다. cosine similarity는 임베딩 생성 이후의 검색 단계에서 질문 벡터와 FAQ 벡터를 비교하는 데 사용합니다.

## 데이터셋

- 출처: 인사혁신처 사이버국가고시센터의 국가공무원 채용시험 FAQ
- 형식: CSV
- 주요 컬럼: `연번`, `제목`, `본문`
- 레코드 수: 289개
- 데이터 크기: 약 232KB

각 행은 하나의 질문과 답변으로 완결되어 있어 `FAQ 1행 = 청크 1개`를 기본 가설로 둡니다. 실제 설계에서는 행/문단/파일 전체 청킹을 비교해 최종 방식을 결정합니다.

## 설치 및 실행 방법

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

실행 환경은 `.env.local`과 `.env.openai`로 분리합니다.

## 환경변수 설정

공통으로 `GEMINI_API_KEY`가 필요합니다. 이 키는 질문에 대한 최종 답변 생성에 사용됩니다.

OpenAI 임베딩을 사용할 경우에는 추가로 `OPENAI_API_KEY`가 필요합니다. 이 키는 `.env.openai`에 설정합니다.

로컬 임베딩을 사용할 경우에는 `OPENAI_API_KEY` 없이도 실행할 수 있습니다. 이 경우 `.env.local`을 사용합니다.

`.env`와 실제 키 파일은 Git에 커밋하지 않습니다. 공개 저장소에는 키 이름만 포함한 `.env.example`을 제공합니다.

## 실행 방식

이 프로젝트는 로컬 임베딩과 OpenAI 임베딩 방식 모두로 테스트할 수 있습니다.

로컬 임베딩 실행:

```bash
FAQ_ENV_FILE=.env.local python3 src/indexing.py --csv data/faq.csv --output index --providers local
FAQ_ENV_FILE=.env.local python3 -m streamlit run app.py
```

OpenAI 임베딩 실행:

```bash
FAQ_ENV_FILE=.env.openai python3 src/indexing.py --csv data/faq.csv --output index --providers openai
FAQ_ENV_FILE=.env.openai python3 -m streamlit run app.py
```

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

### FAQ 한 행 단위 청킹

각 행이 독립적으로 완결된 FAQ이므로 행 단위를 기본값으로 둡니다. 다만 설계 검증에서는 문단 단위와 파일 전체 단위도 비교해, FAQ 데이터에 어떤 청킹이 실제로 유리한지 확인합니다.

### 제목과 본문을 함께 임베딩

사용자 질문의 표현이 FAQ 제목과 다르더라도 본문에 관련 내용이 포함될 수 있습니다. 제목만 사용한 방식과 제목·본문을 함께 사용한 방식을 동일한 평가 질문으로 비교합니다. 청킹과 Top K를 먼저 정리한 뒤, 가장 유리한 검색 설정에서 이 비교를 수행합니다.

### Cosine similarity 기반 검색

텍스트 임베딩에서는 벡터 크기보다 의미적 방향의 유사성을 비교하는 것이 적합합니다. 현재 289개 FAQ는 전체 벡터 비교의 계산 부담이 작으며, 구현과 결과 해석도 단순합니다.

### Reranker는 초기 범위에서 제외

먼저 기본 임베딩 검색의 성능을 측정합니다. 정답 FAQ가 검색 후보에는 포함되지만 낮은 순위에 반복적으로 배치될 때 reranker 도입을 검토합니다.

## 검색 성능 평가

평가를 세 단계로 나눕니다.

1. 청킹 방식 비교
   - 행 단위
   - 문단 단위
   - 파일 전체 단위
2. 임베딩 방식 비교
   - OpenAI
   - Local
3. 임베딩 입력 필드 비교
   - 제목만 임베딩
   - 제목과 본문을 함께 임베딩
4. Top K 비교
   - Top 3
   - Top 5

평가 지표는 다음과 같습니다.

- Hit@1: 정답 FAQ가 첫 번째 결과인지 측정
- Hit@3: 정답 FAQ가 상위 3개에 포함되는지 측정
- Hit@5: 정답 FAQ가 상위 5개에 포함되는지 측정
- MRR: 정답 FAQ의 평균적인 순위 품질 측정
- 실패 사례 분석: 유의어, 일상 표현, 복합 질문에서 놓친 문서 확인

실제 수치는 평가 질문셋을 확정하고 실험을 실행한 뒤 공개합니다.

## 한계와 개선 계획

- 평가 질문셋과 검색 성능 수치가 아직 확정되지 않음
- FAQ 내용이 변경될 때 증분 색인 기능 필요
- 키워드가 중요한 질문에서 BM25 기반 하이브리드 검색 검토
- 검색 후보의 순위 품질이 부족할 경우 reranker 검토
- 데이터 규모 증가 시 Qdrant 또는 pgvector 등의 벡터 DB 검토

## 데이터 출처

- 인사혁신처 사이버국가고시센터, 국가공무원 채용시험 종합안내 FAQ, 2026-03-20 기준
- 공공데이터포털: https://www.data.go.kr/data/15120427/fileData.do
- 이용허락: 공공누리 제1유형(출처표시)

데이터 공개 및 재배포 조건은 GitHub 저장소 공개 전에 원문 제공처의 이용 조건을 확인하여 반영합니다.

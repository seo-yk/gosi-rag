# 국가공무원 채용시험 FAQ RAG 평가 파이프라인

인사혁신처 사이버국가고시센터 FAQ 데이터로 만든 RAG 프로젝트입니다. 검색과 생성을 분리해 답변 품질 저하의 원인을 추적하고, 자동 평가가 어디까지 유효한지 함께 검증했습니다.

## 1. 프로젝트 목적

사이버국가고시센터 FAQ 289건으로 RAG 파이프라인을 만들었습니다. 답변 품질이 떨어질 때 원인이 검색 누락인지, 생성 모델의 응답 문제인지 따로 확인할 수 있도록 평가 구조를 분리했습니다.

- 검색 단계와 생성 단계를 분리해 품질 저하 구간을 추적했습니다.
- 청킹 방식, 임베딩 모델, 입력 필드, 검색 범위를 같은 질문셋으로 비교했습니다.
- 자동 평가를 도입하고, 인간 평가를 얼마나 대체할 수 있는지 따로 검증했습니다.

---

## 2. 핵심 성과

- 검색/생성 분리 평가로 품질 저하 원인 추적
- 자동 평가 프롬프트의 편향과 한계 확인
- Batch 평가를 검토하고, 소형 로컬 평가기에서는 단건 평가가 더 안정적임을 확인

---

## 3. 기술 스택

| 분류 | 기술 스택 | 비고 |
|---|---|---|
| **언어** | Python3 | 데이터 처리 및 파이프라인 |
| **데이터 처리** | Pandas, NumPy | CSV 탐색 및 전처리 |
| **임베딩 모델** | `intfloat/multilingual-e5-small` (오픈소스)<br>OpenAI `text-embedding-3-small`, `text-embedding-3-large` | 임베딩 성능 비교 |
| **벡터 검색** | FAISS (IndexFlatIP), Cosine Similarity | 의미 기반 검색 |
| **답변 생성** | OpenAI `gpt-5.4-mini`<br>Gemini `gemini-3.5-flash`<br>Ollama `qwen2.5:3b` | 검색 결과를 바탕으로 답변 생성 |
| **평가 모델** | Ollama `gemma3:4b` | 자동 평가 |
| **데모 UI** | Streamlit | 데모 UI |

---

## 4. 디렉터리 구조

```text
gosi-rag/
├── app.py
├── src/
│   ├── config.py
│   ├── indexing.py
│   ├── retrieval.py
│   └── generation.py
├── evaluation/
│   ├── inputs/
│   │   ├── question_retrieval.csv
│   │   └── question_generation.csv
│   └── scripts/
│       ├── evaluate_retrieval.py
│       ├── generate_generation.py
│       └── evaluate_generation.py
├── tests/
├── data/
├── output/
├── .env.example
├── requirements.txt
└── README.md
```

---

## 5. 설치 및 실행

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

# 환경변수 파일 생성
cp .env.example .env
```

### 로컬 모델로 빠르게 실행

OpenAI API 키 없이 로컬 임베딩 모델로 벡터 인덱스를 먼저 만들 수 있습니다.

```bash
python src/indexing.py --providers local --chunking-modes row --embedding-modes title
```

`.env`에서 아래 값을 사용하면 로컬 인덱스를 기준으로 데모 앱을 실행할 수 있습니다.

```dotenv
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=intfloat/multilingual-e5-small
CHUNKING_MODE=row
EMBEDDING_MODE=title
TOP_K=3
GENERATION_PROVIDER=ollama
GENERATION_MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

Ollama 대신 Gemini 또는 OpenAI로 답변 생성을 실행하려면 `.env.example`의 주석에 맞춰 `GENERATION_PROVIDER`, `GENERATION_MODEL`, API 키를 변경합니다.

```bash
python -m streamlit run app.py
```

### 전체 실험용 인덱스 생성

OpenAI 임베딩까지 함께 비교하려면 `OPENAI_API_KEY`를 설정한 뒤 전체 조합을 생성합니다.

```bash
python src/indexing.py
```

---

## 6. 실험 설계

검색 성능과 생성 품질을 한 번에 보지 않고 단계별로 나눠 확인했습니다. Retrieval과 Generation을 분리하고, 같은 질문셋에서 조건별 결과를 비교했습니다.

| 단계 | 실험 변수 | 비교 항목 | 평가지표 |
|---|---|---|---|
| **검색** | 청킹 방식 | `row` vs `paragraph` vs `file` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| | 임베딩 프로바이더 | `sentence-transformers` vs `openai` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| | 임베딩 모델 | `intfloat/multilingual-e5-small` vs `text-embedding-3-small` vs `text-embedding-3-large` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| | 임베딩 대상 필드 | `title` vs `title_body` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| | 검색 범위 | `Top 3` vs `Top 5` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| **생성** | 생성 모델 | OpenAI `gpt-5.4-mini` | - |
| **평가** | 평가 모델 | Ollama `gemma3:4b` | `groundedness`, `correctness`, `completeness`, `unsupported_claims`, `overall` |

---

## 7. 결과

### 7-1. 검색(Retrieval)

- **최종 조합:** `row` + `E5-Small` + `title` + `Top 3`

| Hit@1 | Hit@3 | Hit@5 | MRR |
|---:|---:|---:|---:|
| 90.2% | 96.1% | 96.1% | 0.928 |

**주요 결과**

- Retrieval 기준선은 `row + E5-Small + title + Top 3`입니다.
- FAQ 질문만 임베딩한 `title` 구성이 본문까지 포함한 `title_body` 구성보다 더 안정적으로 정답을 찾았습니다.
- 이 데이터셋에서는 OpenAI `text-embedding-3-small`보다 경량 오픈소스 모델인 `E5-Small`이 더 높은 검색 성능을 보였습니다.
- `text-embedding-3-large`까지 비교했지만 여전히 `E5-Small`이 검색 성능이 더 높았습니다.

**해석**

- 원본 FAQ 제목이 실제 사용자 질문과 가까워, 본문 설명까지 넣는 것보다 질문 문장만 임베딩하는 편이 더 잘 맞았습니다.
- 다만 일부 답변의 세부 키워드는 본문에만 있어 충분히 회수되지 않았습니다.
- 이 한계를 통해 의미 기반 벡터 검색만으로는 부족한 케이스가 있으며, 키워드 검색을 함께 쓰는 **하이브리드 서치**가 필요하다는 점을 확인했습니다.

> **산출물**
> - `E5-small` 결과: `output/retr_e5-small.csv`
> - `text-embedding-3-small` 결과: `output/retr_openai-3-small.csv`
> - `text-embedding-3-large` 결과: `output/retr_openai-3-large.csv`

### 7-2. 생성 및 자동 평가(Generation & Evaluation)

- **최종 조합:** `gpt-5.4-mini` 생성 + `gemma3:4b` 단건 평가
- **평가 결과:**
  - 수동 평가 Overall Pass: **55/60**
  - 자동 평가 Overall Pass: **60/60**

**평가 일치도**

- 생성 결과의 최신 기준선은 `gpt-5.4-mini` 60문항 결과 파일입니다.
- 수동 평가와 자동 평가의 일치율은 `91.67%`로, 인간 평가자 간 평균 일치도(`80~90%`)보다 높았습니다.
- 불일치 사례는 주로 근거가 충분한데도 답변을 회피한 응답에서 발생했습니다.
- 따라서 자동 평가에는 답변 회피와 핵심 정보 누락을 감지하는 규칙 기반 가드레일이 필요합니다.
- 다만 모든 엣지 케이스를 규칙만으로 커버하기는 어려워 최종 품질 판단에는 수동 평가를 병행해야 합니다.

**평가 방식 점검**

**오버헤드 최소화**

- 비용과 오버헤드를 줄이기 위해 Batch 평가를 검토했습니다.
- 하지만 작은 배치(`batch_size=3`)에서도 11문항 오차가 발생했습니다.
- `gemma3:4b`처럼 로컬에서 돌리는 소형 평가기에서는 단건 평가가 더 안정적이었습니다.

**필드명 조정**

- 초기 평가 프롬프트에서는 `hallucination` 필드명이 판정을 흔들었습니다. 프롬프트에 1(환각 없음)이라고 명시했음에도 필드명을 기준으로 0(환각 없음)으로 평가했습니다.
- 따라서 필드명을 `unsupported_claims`로 바꾼 뒤 판정이 더 안정적으로 유지됐습니다.

> **생성 및 평가 산출물**
> - 답변 생성 원본: `output/gen_60_gpt-5.4-mini.csv`
> - 단건 채점 결과: `output/eval_60_gpt-5.4-mini-gemma3-4b_single.csv`
> - 배치 채점 비교군: `output/eval_60_gpt-5.4-mini-gemma3-4b_b3.csv`

### 7-3. 이 프로젝트로 확인한 것

- 답변 품질 문제는 검색과 생성을 먼저 분리해서 봐야 합니다.
- 검색 단계에서는 더 큰 모델보다 데이터 구조에 맞는 입력과 검색 범위가 중요했습니다.
- 평가 단계에서는 자동화 자체보다 평가 편향을 확인하고 보완 규칙을 설계하는 일이 더 중요했습니다.

---

## 8. 데이터셋 및 출처

- **데이터 제공처:** 인사혁신처 (사이버국가고시센터)
- **데이터셋명:** `인사혁신처_사이버국가고시센터 국가공무원 채용시험 종합안내(FAQ)_20260320`
- **데이터 구성:** 289개 레코드, CSV 형식 (`연번`, `제목`, `본문`)
- **수집 출처:** [공공데이터포털](https://www.data.go.kr/data/15120427/fileData.do)
- **이용 조건:** 공공누리 제1유형 (출처 표시 조건 하에 자유로운 상업적 이용 및 변경 가능)
- **주의사항:** 실제 공무원 채용 시험 응시 시에는 사이버국가고시센터의 최신 공고문을 교차 검증해야 합니다.

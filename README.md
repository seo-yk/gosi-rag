# 국가공무원 채용시험 FAQ 답변

인사혁신처 사이버국가고시센터 FAQ 데이터로 질의응답 시스템(RAG)을 구현하고, 품질 저하 문제를 명확히 분석할 수 있는 구조를 만드는 데 집중한 프로젝트입니다.

## 🎯 프로젝트 목적

사이버국가고시센터 FAQ 289건으로 RAG 파이프라인을 구현했습니다. 답변 품질이 떨어질 때 원인이 검색 누락인지 생성 문제인지 나눠서 볼 수 있도록 평가 구조를 따로 설계했습니다. RAG 시스템의 품질을 높이는 것이 무엇인지 정확하게 판정하기 위해 실험 조건과 평가 방식을 설계했습니다.

- 검색 단계와 생성 단계를 분리해 문제가 발생한 구간을 따로 확인할 수 있게 했습니다.
- 청킹 방식, 임베딩 모델, 입력 필드, 검색 범위를 변수로 두고 같은 조건에서 반복 비교할 수 있게 구성했습니다.
- 평가의 일관성을 주기 위해 자동 평가를 도입했고, 실제 인간 평가 대체로 유효한지 검증했습니다.

---

## 2. 핵심 성과

- 검색/생성 분리 평가 구조를 설계해 품질 저하 원인 추적
- 자동 평가 프롬프트 편향 검증
- 비용, 오버헤드 절약을 위한 Batch 도입이 품질에 영향을 주지 않을지 여부 검증

---

## 3. 기술 스택

| 분류 | 기술 스택 | 비고 |
|---|---|---|
| **언어** | Python3 | 데이터 처리 및 파이프라인 |
| **데이터 처리** | Pandas, NumPy | CSV 탐색 및 전처리 |
| **임베딩 모델** | `intfloat/multilingual-e5-small` (오픈소스)<br>OpenAI `text-embedding-3-small` | 임베딩 성능 비교 |
| **벡터 검색** | FAISS (IndexFlatIP), Cosine Similarity | 의미 기반 검색 |
| **답변 생성** | OpenAI `gpt-5.4-mini`<br>Gemini `gemini-3.5-flash` | 검색 결과를 바탕으로 답변 생성 |
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

# 벡터 인덱스 빌드
python src/indexing.py

# 데모 웹 실행
python -m streamlit run app.py
```

---

## 6. 실험 설계

검색 성능과 생성 품질을 한 번에 보지 않고 단계별로 나눠 확인했습니다. Retrieval과 Generation을 분리해 독립 변수를 두고 같은 질문셋으로 결과를 비교했습니다.

| 단계 | 실험 변수 | 비교 항목 | 평가지표 |
|---|---|---|---|
| **검색** | 청킹 방식 | `row` vs `paragraph` vs `file` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| | 임베딩 프로바이더 | `sentence-transformers (오픈소스)` vs `openai` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| | 임베딩 모델 | `intfloat/multilingual-e5-small` vs `text-embedding-3-small` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| | 임베딩 대상 필드 | `title` vs `title_body` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| | 검색 범위 | `Top 3` vs `Top 5` | `Hit@1`, `Hit@3`, `Hit@5`, `MRR` |
| **생성** | 생성 모델 | OpenAI `gpt-5.4-mini` | - |
| **평가** | 평가 모델 | Ollama `gemma3:4b` | `groundedness`, `correctness`, `completeness`, `overall` |

---

## 7. 결과

### 7-1. 검색(Retrieval)
- **최종 조합:** `row` + `E5-Small` + `title` + `Top 3`

| Hit@1 | Hit@3 | Hit@5 | MRR |
|---:|---:|---:|---:|
| 90.2% | 96.1% | 96.1% | 0.928 |

**주요 결과**

- Retrieval 기준선은 `row + E5-Small + title + Top 3` 조합으로 정했습니다.
- `title` 단독 임베딩이 `title + body`보다 검색 성능이 높았습니다.
- OpenAI `text-embedding-3-small`보다 `E5-Small`이 검색 성능이 높았습니다.
- `text-embedding-3-large`까지 비교했지만 여전히 `E5-Small`가 검색 성능이 더 높았습니다.

**해석**

- 원본 데이터셋 자체가 질문이 명확하고 깔끔해 `title` 단독 임베딩이 우세했습니다.
- 하지만 일부 답변에서 본문에만 있는 세부 키워드는 충분히 회수되지 않았습니다.
- 따라서 이후에는 의미 검색과 키워드 검색을 함께 붙이는 하이브리드 검색 도입이 필요하다고 봤습니다.

> [!files] 산출물
> 자세한 실험 결과는 아래 산출물 파일에서 확인할 수 있습니다.
> - `E5-small` 결과: `output/retr_e5-small.csv`
> - `text-embedding-3-small` 결과: `output/retr_openai-3-small.csv`
> - `text-embedding-3-large` 결과: `output/retr_openai-3-large.csv`

### 7-2. 생성 및 자동 평가(Generation & Evaluation)
- **최종 조합:** `gpt-5.4-mini` 생성 + `gemma3:4b` 단건 평가
- **평가 결과:**
  - 수동 평가 Overall Pass: **46/50**
  - 자동 평가 Overall Pass: **50/50**

**검증 결과**

- 생성 결과의 최신 기준선은 `gpt-5.4-mini` 50문항 결과 파일입니다.
- 수동 평가와 자동 평가의 일치율은 91.67%로 Auto Evaluation의 유효성을 검증했습니다. (인간 평가자 채점 일치도 평균: 80%)
- 자동 평가와 수동 평가 오차의 원인은 정답이 있는데 답을 유보한 응답을 Pass로 처리해서인 것으로 확인됐습니다.
- 평가 rubric을 `groundedness`, `correctness`, `completeness`로 간소화했지만, 정답이 있는데 답을 유보한 경우까지 구분하지는 못했습니다.
- 자동 평가는 보조 지표로 두고, 답변 유보나 핵심 정보 누락은 별도 규칙(가드레일)으로 걸러내는 쪽이 맞다고 판단했습니다.
- 결과적으로 자동 평가는 유효하지만 여전히 수동 평가가 필요하다고 판단했습니다.

**추가 검증**
</br>
[오버헤드 최소화]
- 평가 시 비용과 오버헤드를 줄이기 위해 배치 도입을 검토했습니다.
- 하지만 배치 사이즈를 소규모(`batch_size=3`)으로 설정해도 평가에서 11문항 오차가 있었습니다.
- `gemma3:4b`처럼 로컬에서 돌리는 소형 평가기에서는 배치 처리보다 단건 평가가 더 안정적이어서 최종 기준도 단건 평가로 잡았습니다.

[필드명 조정]
- 초기 평가 프롬프트에서는 `hallucination` 필드명이 판정을 흔들었습니다. 프롬프트에 1(환각 없음)이라고 명시했음에도 필드명을 기준으로 0(환각없음)으로 평가했습니다.
- 따라서 필드명을 `unsupported_claims`로 바꾼 뒤 판정이 더 안정적으로 유지됐습니다.


### 7-3. 이 프로젝트로 확인한 것

- 답변 품질 문제를 다룰 때는 검색과 생성을 먼저 분리해서 봐야 합니다.
- 검색 단계에서는 더 큰 모델보다 데이터 구조에 맞는 임베딩 입력과 검색 범위를 고르는 일이 더 중요했습니다.
- 평가 단계에서는 자동화를 붙이는 일보다 자동 평가의 편향을 확인하고 보완 규칙을 정하는 일이 더 중요했습니다.

> [!files] 생성 및 평가 산출물
> - 답변 생성 원본: `output/gen_60_gpt-5.4-mini.csv`
> - 단건 채점 결과: `output/eval_60_gpt-5.4-mini-gemma3-4b_single.csv`
> - 배치 채점 비교군: `output/eval_60_gpt-5.4-mini-gemma3-4b_b3.csv`

---

## 8. 데이터셋 및 출처

- **데이터 제공처:** 인사혁신처 (사이버국가고시센터)
- **데이터셋명:** `인사혁신처_사이버국가고시센터 국가공무원 채용시험 종합안내(FAQ)_20260320`
- **데이터 구성:** 289개 레코드, CSV 형식 (`연번`, `제목`, `본문`)
- **수집 출처:** [공공데이터포털](https://www.data.go.kr/data/15120427/fileData.do)
- **이용 조건:** 공공누리 제1유형 (출처 표시 조건 하에 자유로운 상업적 이용 및 변경 가능)
- **주의사항:** 실제 공무원 채용 시험 응시 시에는 사이버국가고시센터의 최신 공고문을 교차 검증해야 합니다.

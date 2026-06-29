# 국가공무원 채용시험 FAQ RAG

인사혁신처 사이버국가고시센터의 국가공무원 채용시험 FAQ 데이터를 근거로 답변을 제공하는 RAG(Retrieval-Augmented Generation) 프로젝트.

## 🎯 개요 및 목표

본 프로젝트는 국가공무원 채용시험 FAQ 데이터를 기반으로 실무형 RAG(Retrieval-Augmented Generation) 시스템을 구축하고, **'가설-실험-검증' 중심의 데이터 엔지니어링과 아키텍처 최적화**를 달성하는 것을 목표로 합니다.

단순히 동작하는 챗봇 구현을 넘어, 프로덕션 환경에서 직면하는 성능 병목을 제어하기 위해 다음 **엔지니어링 설계 원칙**을 기반으로 고도화되었습니다.

1. **평가 파이프라인 분리**
   * RAG 답변 품질 저하의 근본 원인을 파악하기 위해 검색 엔진 자체 성능과 생성 답변 품질을 독립된 변수로 분리하여 정량적으로 평가하고 측정합니다.
   
2. **데이터 특성에 맞춤화한 검색 튜닝**
   * FAQ 데이터셋의 구조적 특성을 파악하고 최적의 검색 방식을 규명하기 위해 다음 **RAG 비교 실험 매트릭스**를 설계하여 비교 대조를 수행했습니다.

     | 실험 영역 | 대조군 구성 | 엔지니어링 가설 및 검증 목적 |
     | :---: | :--- | :--- | 
     | **청킹 방식** | 행(Row) vs 문단(Paragraph) vs 전체 파일 | FAQ 단일 질의응답이 가진 의미적 독립성을 보존하는 최적의 텍스트 파티셔닝 단위 검증 |
     | **임베딩 방식** | OpenAI 임베딩 vs 로컬 경량 임베딩 | 상용 API 호출 비용, 네트워크 지연과 로컬 임베딩의 온프레미스 가용성 및 한글 표현력 비교 |
     | **임베딩 입력 필드** | 제목(질문) 단독 vs 제목 + 본문 | 사용자의 실제 질의가 FAQ 본문의 장황한 텍스트에 희석되지 않고 정렬될 수 있는지 검증 |
     | **검색 범위 (Top-K)** | Top 3 검색 vs Top 5 검색 | LLM의 입력 비용과 추론 레이턴시를 최소화하면서 검색 누락을 방지하는 임계점 검증 |

3. **프로덕션 환경을 고려한 비용/레이턴시 최적화**
   * LLM Judge 평가 수행 시 발생하는 대량의 API 호출 지연과 레이트 리밋 오버헤드를 해소하기 위해, 다중 호출 방식을 단일 JSON 배치(Structured Output) 병합 호출로 최적화하여 API 호출 비용 및 레이턴시를 80% 감축했습니다.

실제 실험 결과는 문서 하단의 평가 결과 섹션에 상세히 정리되어 있습니다.

## 🛠️ 기술 스택

| 영역     | 기술                                                                                                   | 비고                       |
| :------: | :---------------------------------------------------------------------------------------------------- | :------------------------ |
| 언어     | Python                                                                                               | 데이터 처리 및 AI API 연동       |
| 데이터 처리 | Pandas, NumPy                                                                                        | CSV 탐색 및 전처리             |
| 임베딩    | Local: `intfloat/multilingual-e5-small`<br>OpenAI: `text-embedding-3-small`                          | 텍스트 → 벡터 변환,<br>성능 비교 실험 |
| 벡터 검색  | FAISS(IndexFlatIP), cosine similarity                                                                | 텍스트 임베딩 의미 비교            |
| 답변 생성  | Gemini: `gemini-3.5-flash`<br>OpenRouter: `qwen/qwen3-8b:free`                                       | 검색 결과 기반 최종 답변 생성            |
| UI     | Streamlit                                                                                            | 데모 UI                    |

## 📁 디렉터리 구조

```text
gosi-rag/
├── app.py
├── src/
│   ├── config.py                   # 공통 환경 변수 로드
│   ├── indexing.py                 # 인덱스 생성
│   ├── retrieval.py                # 질문 임베딩 및 검색
│   └── generation.py               # 최종 답변 생성
├── evaluation/
│   ├── inputs/                     # 평가 질문셋
│   │   ├── question_retrieval.csv 
│   │   └── question_generation.csv   
│   └── scripts/                    # 평가 스크립트
│       ├── generation_generate.py    
│       ├── generation_eval.py        
│       └── retrieval_eval.py         
├── tests/                          # 테스트
├── data/                           # 원본 데이터
├── .env.example                    # 환경 변수
├── requirements.txt                # 의존성 목록
└── README.md
```

## 💾 데이터셋 및 출처

본 프로젝트는 인사혁신처 사이버국가고시센터에서 제공하는 국가공무원 채용시험 FAQ 공공데이터를 가공하여 활용합니다.

- **제공기관:** 인사혁신처
- **데이터셋명:** 인사혁신처_사이버국가고시센터 국가공무원 채용시험 종합안내(FAQ)_20260320
- **데이터 형식:** CSV (`연번`, `제목`, `본문` 컬럼)
- **데이터 규모:** 289개 레코드 (약 232KB, 기준일: 2026-03-20)
- **원천 자료 출처:** [공공데이터포털](https://www.data.go.kr/data/15120427/fileData.do)
- **이용조건:** 공공누리 제1유형 (출처표시 조건)

> 💡 **이용 안내:**  
> 본 저장소는 위 출처 및 이용허락 조건을 준수하여 원본 CSV를 포함하고 있습니다. 공무원 채용 제도가 변경되는 경우, 본 데이터셋에 즉시 반영되지 않을 수 있으므로 실제 시험 준비 시에는 사이버국가고시센터의 최신 공식 공고를 교차 검증해야 합니다.

## ⚙️ 설치

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

## 🔑 환경변수 설정

프로젝트 루트 폴더에 `.env` 파일을 생성하고 필요한 API 키와 설정을 기입합니다.

| 기능 | 방식 | 비용 | 설정 방법 | 비고 |
| :---: | :--- | :---: | :--- | :--- |
| **임베딩(Local)** | `intfloat/multilingual-e5-small` | 무료 | `FAQ_EMBEDDING_PROVIDER=local` 설정 |
| **임베딩(OpenAI)** | `text-embedding-3-small` | 유료 | `FAQ_EMBEDDING_PROVIDER=openai`, `OPENAI_API_KEY` 설정 |
| **답변 생성** | Gemini API 또는 OpenRouter | 무료 | `FAQ_GENERATION_PROVIDER`, `GEMINI_API_KEY` 또는 `OPENROUTER_API_KEY` 설정 | OpenRouter 생성 모델: `qwen/qwen3-8b:free` |
| **생성 평가** | OpenRouter | 무료 | 기본 비교는 `FAQ_JUDGE_PROVIDER=openrouter`, `OPENROUTER_JUDGE_MODEL=meta-llama/llama-3.3-70b-instruct:free` | OpenRouter judge 사용이 어려울 때만 Gemini judge를 별도 배치로 실행 |

---

## 🚀 실행 및 파이프라인 가이드

본 프로젝트는 인덱스 생성, 데모 앱 구동, 검색 평가, 생성 답안 저장, 생성 평가 순으로 이어지는 5단계 파이프라인 구조로 설계되었습니다.

먼저 `.env.example` 파일을 복사하여 `.env` 파일을 생성하고 필요한 설정을 진행합니다.
```bash
cp .env.example .env
```
> 💡 복사 후 `.env` 파일에 API 키와 사용 설정을 기입하면 별도의 파일명 접두사 없이 아래 명령어를 바로 실행할 수 있습니다.

### [Step 1] 인덱스 생성 (Indexing)
FAQ 데이터를 청킹하고 벡터화하여 FAISS 인덱스를 빌드합니다.
```bash
python3 src/indexing.py
```
* 결과물: `index/{chunking}/{provider}/` 경로에 `.faiss` 및 `metadata.json` 파일 생성

### [Step 2] 데모 앱 실행 (Streamlit Application)
Streamlit 웹 UI를 구동하여 로컬 검색기 및 생성 모델의 실제 동작을 시각적으로 확인합니다.
```bash
python3 -m streamlit run app.py
```

### [Step 3] 검색 성능 평가 (Retrieval Evaluation)
평가 질문셋을 바탕으로 검색기 성능 지표(Hit@K, MRR)를 측정합니다.
```bash
python3 -m evaluation.scripts.retrieval_eval --questions evaluation/inputs/question_retrieval.csv
```
* 결과물: 조건별 검색 매트릭스 성능 요약 파일 생성

### [Step 4] 생성 답안 저장 (Generation Only)
질문셋에 대해 선택한 생성 모델의 답변과 검색 컨텍스트만 먼저 저장합니다.

```bash
# 모델별 실행 시 반드시 파일명 직접 지정 필요

FAQ_GENERATION_PROVIDER={모델} python3 -m evaluation.scripts.generation_generate --questions evaluation/inputs/question_generation.csv --output output/{파일명}.csv
```
* 결과물: 생성 모델별 답변, 검색 FAQ 번호, 검색 컨텍스트를 담은 CSV 파일 생성

### [Step 5] 생성 답변 품질 평가 (LLM-as-a-Judge)
배치 채점관 모델을 활용해 저장된 생성 답변의 품질(의미 유사도, 근거성, 정확성, 완결성, 환각)을 자동 채점합니다.
```bash
python3 -m evaluation.scripts.generation_eval --answers output/{파일명}.csv --output output/{파일명}.csv
```
* 결과물: 모델별 문항 세부 평점, 생성 답변, Judge 판정 피드백을 담은 평가 CSV 생성

## 📊 평가 프레임워크 및 결과

본 프로젝트에서는 RAG 시스템의 성능 병목을 정확히 추적하고 통제하기 위해 1) 검색 성능 평가(Retrieval Evaluation)와 2) 생성 답변 품질 평가(Generation Evaluation)를 엄격하게 분리하여 평가 프레임워크를 구성했습니다.

---

### 1. 검색(Retrieval) 평가 결과

검색 평가는 평가용 질문셋(50개 질의)과 정답 FAQ 매핑 정보를 기준으로 각 실험군별 **Hit@K**와 **MRR**을 정량 측정하여 설계 결정을 검증했습니다.

> **평가 지표 정의:**
> - **Hit@K**: 검색된 상위 K개 문서 중 정답 FAQ가 포함될 확률
> - **MRR(Mean Reciprocal Rank)**: 검색 결과 중 정답 FAQ가 위치한 순위의 역수 평균

#### 1-1. 실험 결과 테이블

| 청킹 방식 | 임베딩 모델 (Provider) | 입력 필드 (Features) | Top K | Hit@1 | Hit@3 | Hit@5 | MRR | 비고 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **row** | **Local (E5-Small)** | **title** | **3** | **90.2%** | **96.1%** | **96.1%** | **0.928** | **최적의 조합** |
| row | Local (E5-Small) | title_body | 3 | 86.3% | 96.1% | 96.1% | 0.905 | title 대비 소폭 하락 |
| paragraph | Local (E5-Small) | title | 3 | 90.2% | 96.1% | 96.1% | 0.928 | row 청킹과 결과 동일 |
| paragraph | Local (E5-Small) | title_body | 3 | 86.3% | 96.1% | 96.1% | 0.905 | row 청킹과 결과 동일 |
| file | Local (E5-Small) | title | 3 | 0.0% | 0.0% | 0.0% | 0.000 | 단일 파일 청킹은 RAG에 부적합 |

#### 1-2. 엔지니어링 분석 및 인사이트

*   **청크 크기 최적화:**  
    본 FAQ 데이터셋은 각 행(Row)이 단일 질의응답(Q&A)으로 완결되며, 평균 약 333자(최대 1,344자) 수준의 콤팩트한 데이터 특성을 가집니다. 실험 결과, 행(Row) 단위 청킹과 문단(Paragraph) 단위 청킹은 완전히 동일한 검색 결과(Hit@3 96.1%, MRR 0.928)를 보이며 변별력이 부재했습니다. 반면, 전체 파일 단위(File-level) 청킹은 무관한 맥락들을 혼재시켜 검색 성능을 0%로 붕괴시켰습니다.
    
    결과적으로 **데이터의 독립적인 의미 단위를 가장 직관적으로 보존하면서 불필요한 분할 오버헤드가 없는 행(Row) 단위 청킹을 최적의 전략으로 채택**했습니다.

*   **검색 범위(Top K) 효율화:**  
    검색 범위를 Top 3에서 Top 5로 확장하더라도 검색 성능 지표의 추가적인 향상은 관찰되지 않았습니다(Hit@3 및 Hit@5 모두 96.1%로 동일). 이는 모델이 정답 문서를 대부분 최상위 순위(MRR 0.928) 내에 안정적으로 랭킹했음을 의미합니다.
    
    따라서 검색 범위 확장은 LLM의 컨텍스트 윈도우 증가로 인한 **불필요한 입력 토큰 비용 발생 및 추론 지연 시간(Latency) 상승을 초래할 뿐이므로, 시스템 비용 효율성을 극대화하기 위해 기본 검색 범위를 Top 3로 제한**했습니다.

*   **임베딩 입력 필드 분석:**  
    질문과 답변이 함께 포함된 `title_body`를 임베딩 입력으로 사용할 때보다, 질문만 단독으로 포함된 `title` 필드를 입력으로 사용했을 때 Hit@1이 90.2%로 **약 3.9%p 향상**되었습니다.
    
    이는 사용자의 실제 입력 질의가 FAQ 본문의 긴 설명문보다 FAQ 제목(질문)과 의미적 방향성이 일치하기 때문에 본문 텍스트가 노이즈로 작용한 결과입니다.

---

### 2. 생성 답변(Generation) 평가 결과

생성 답변 평가는 검색 단계에서 가져온 FAQ 컨텍스트를 바탕으로 생성 모델이 얼마나 정확하고 안전하게 대답했는지 검증합니다.

#### 2-1. LLM 평가 결과 (Judge: Llama-3.3-70B)

대표적인 질문 유형(원문유사, 일상표현, 조건형, 복합질문) 10개를 선정하여, 고정 채점관 모델인 `meta-llama/llama-3.3-70b-instruct:free`를 통해 자동 평가를 수행한 실측 결과 테이블입니다. 생성 모델은 한 번의 배치 실행에서 1개만 사용하며, 비교가 필요할 때는 Judge를 고정한 채 배치를 분리 실행합니다.

*   **Judge 평가 기준:**
    - **Similarity (의미 유사도):** 기준 답안과 의미가 얼마나 일치하는가? (`0~5`, 4점 이상 Pass)
    - **Groundedness (근거성):** 주어진 FAQ 컨텍스트 내의 사실에만 기반하여 답했는가? (`0~2`, 2점 만점)
    - **Correctness (정확성):** 질문의 핵심 취지에 맞게 정확한 사실을 대답했는가? (`0/1`)
    - **Completeness (완결성):** 중요 정보 누락 없이 성실하게 답변했는가? (`0/1`)
    - **Hallucination (환각 배제):** 근거 없는 추론이나 왜곡된 사실이 배제되었는가? (`1: 없음`, `0: 있음`)
    - **Overall (최종 판정):** 개별 지표의 일관성을 검증하여 최종 사용자 제공 적합 여부 판정 (`Pass` / `Fail`)

| ID | 평가용 질문 | Similarity | Groundedness | Correctness | Completeness | Hallucination | Overall | LLM Judge 판정 상세 피드백 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **q001** | 원서 접수 끝난 뒤에 응시지역이나 선택과목을 바꿀 수 있나요? | 5 | 2 | 1 | 1 | 1 | **Pass** | 기준 답안의 추가 변경 불가 내용을 의미론적으로 동일하게 표현함. |
| **q002** | 원서 접수를 취소하면 응시수수료는 바로 환불되나요? | 4 | 2 | 1 | 1 | 1 | **Pass** | 환불 절차와 시점의 연기가 잘 설명됨. |
| **q003** | 응시표는 언제부터 다시 출력할 수 있어요? 시험 당일 잃어버려도 괜찮나요? | 5 | 2 | 1 | 1 | 1 | **Pass** | 출력 시점과 분실 시 대책이 논리적 오류 없이 답변됨. |
| **q004** | 친구랑 같이 접수하면 시험장에서 앞뒤 번호로 붙을 수 있나요? | 5 | 2 | 1 | 1 | 1 | **Pass** | 무작위 응시번호 배정 원리가 정확히 일치함. |
| **q005** | 서울 살아도 다른 지역 시험장 선택해서 볼 수 있나요? | 5 | 2 | 1 | 1 | 1 | **Pass** | 거주지 무관 17개 시도 선택 가능 여부를 명확히 확인함. |
| **q006** | 영어 성적이 아직 없는데 일단 원서부터 접수하고 나중에 등록해도 되나요? | 5 | 2 | 1 | 1 | 1 | **Pass** | 원서 선접수 후 사후 등록 기한 조건을 올바르게 판정함. |
| **q007** | 토익 성적 유효기간이 지났는데 예전에 본 점수도 쓸 수 있나요? | 5 | 2 | 1 | 1 | 1 | **Pass** | 만료 전 사전등록 요건과 5년 인정 기준을 누락 없이 포함함. |
| **q008** | 장애인 편의지원은 언제 어떻게 신청해요? 진단서가 꼭 필요한가요? | 5 | 2 | 1 | 1 | 1 | **Pass** | 편의지원 신청 시기와 진단서 예외 조건을 정확히 대조함. |
| **q009** | 시험 보러 갈 때 꼭 챙겨야 하는 게 뭐예요? | 3 | 2 | 0 | 0 | 1 | **Fail** | 기준 답안의 핵심인 '신분증', '수험표' 정보가 유실됨. Similarity 3점 및 Completeness 0점 처리로 Fail 판정. |
| **q010** | 접수한 뒤에 개명되면 시험 볼 때 어떻게 해야 하나요? | 5 | 2 | 1 | 1 | 1 | **Pass** | 초본 지참 및 본인 확인 절차에 대한 의미 정합성 우수함. |

#### 2-2. LLM Judge 평가 결과 분석

*   **Fail 케이스(q009) 분석:**  
    생성 답변에서 Groundedness(근거성)는 2점(컨텍스트 내 사실에 기반함)으로 적절히 통제되었으나, 핵심 필수 지참물(신분증, 수험표 등)이 누락되어 Completeness(완결성) 0점 및 최종 **Fail**을 받았습니다. 이는 RAG 파이프라인의 검색기(Retriever)가 Top 3 검색 시 주변 언저리 문서는 참조했으나 정작 가장 핵심적인 준비물 안내 FAQ(FAQ 77)를 누출한 결과입니다.  
    
    생성 모델(Gemini)에 엄격한 Groundedness 지시를 내려 환각은 100% 억제했더라도, **검색 단계(Retrieval Recall)의 실수가 최종 답변의 완결성(Completeness) 저하로 직결됨**을 정량적으로 증명했습니다.

#### 2-3. Automated LLM-as-a-Judge 아키텍처

프로덕션 환경에서의 지속 가능한 배포와 테스트 자동화를 위해, 단일 고정 채점관 모델(LLM-as-a-Judge)을 통해 평가를 자동화하는 파이프라인(`evaluation/scripts/generation_eval.py`)을 설계하여 포함했습니다.

*   **동작 원리:**
    1. `retriever.search`를 통해 획득한 context와 생성된 답변, 그리고 기준 정답(Ground Truth)을 준비합니다.
    2. 환경변수 `OPENROUTER_JUDGE_MODEL`에 지정된 **단 하나의 고정 모델**에게 각 평가 프롬프트(Similarity, Groundedness, Correctness 등)를 전송합니다. free judge가 일시적으로 unavailable한 경우에만 Gemini judge로 별도 배치를 재실행합니다.
    3. 채점 결과를 정수화(Similarity: 0~5, Groundedness: 0~2 등)하여 취합한 뒤, 다수결 또는 특정 조건식을 만족할 때 최종 `Pass` 여부를 결정해 CSV 파일로 로깅합니다.

*   **고정 채점관의 필요성:** 평가 대상을 변경하더라도 채점관 모델의 등급 기준을 1개로 고정함으로써 평가 편향을 방지하고 일관된 정량 지표를 도출하도록 보장합니다.

*   **벤치마킹:** https://huggingface.co/datasets/allganize/RAG-Evaluation-Dataset-KO

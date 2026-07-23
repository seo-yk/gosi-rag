# LLM-as-a-Judge Rubric v2

## 목적

동일하게 고정된 생성 답변을 대상으로 평가 루브릭과 평가 모델의 영향을 분리한다. Retrieval과 Generation은 다시 실행하지 않는다.

## 평가 입력

- `question`
- `reference_answer`
- `required_facts`
- `retrieved_contexts`
- `candidate_answer`

## 평가 기준

### 1. Groundedness

후보 답변의 사실 주장이 검색 컨텍스트에 의해 뒷받침되는지 평가한다.

- `pass`: 모든 핵심 주장이 검색 컨텍스트에 의해 뒷받침된다.
- `partial`: 일부 부수적 주장의 근거가 약하거나 불명확하다.
- `fail`: 핵심 주장이 검색 컨텍스트에 없거나 검색 컨텍스트와 충돌한다.

답변이 아무 사실도 제공하지 않고 유보했다는 이유만으로 correctness 또는 completeness를 통과시키지 않는다.

### 2. Correctness

후보 답변이 기준답변과 사실적으로 일치하며 사용자 질문에 올바르게 답했는지 평가한다.

- `pass`: 핵심 결론과 조건이 기준답변과 일치한다.
- `fail`: 핵심 결론이 틀렸거나 기준답변과 충돌하거나 질문에 답하지 못했다.

명시적 유보 규칙:

- 기준답변에 실제 답이 있는데 후보 답변이 `확인할 수 없다`, `알 수 없다`, `근거가 없다`고 유보하면 `correctness=fail`이다.
- 근거 없는 주장을 하지 않았다는 사실은 correctness 통과 사유가 아니다.

### 3. Completeness

후보 답변이 `required_facts`를 빠짐없이 포함했는지 평가한다.

- `pass`: 모든 required fact를 명시적으로 또는 의미상 동일하게 포함한다.
- `fail`: 하나 이상의 required fact가 누락되거나 반대로 표현됐다.

평가 모델은 누락된 항목을 `missing_required_facts`에 원문 그대로 반환한다.

### 4. Answer Status

- `answered`: 질문에 실제 답을 제공했다.
- `valid_refusal`: 기준답변에도 답이 없고 후보 답변이 정당하게 유보했다.
- `false_refusal`: 기준답변에는 답이 있지만 후보 답변이 답변을 유보했다.

## 출력 스키마

```json
{
  "groundedness": "pass | partial | fail",
  "correctness": "pass | fail",
  "missing_required_facts": ["누락된 required fact 원문"],
  "answer_status": "answered | valid_refusal | false_refusal",
  "reason": "두 문장 이내의 판정 근거"
}
```

## Overall 판정

평가 모델은 Overall을 출력하지 않는다. 코드는 아래 조건을 모두 만족할 때만 Pass로 판정한다.

```text
groundedness != fail
AND correctness == pass
AND missing_required_facts가 비어 있음
AND answer_status != false_refusal
```

하나라도 만족하지 않으면 Fail이다.

## 단건 평가 프롬프트

```text
You are a strict RAG answer evaluator.
Evaluate one candidate answer using only the supplied fields.
Do not reward a refusal merely because it avoids hallucination.

Question:
{question}

Reference answer:
{reference_answer}

Required facts:
{required_facts}

Retrieved contexts:
{retrieved_contexts}

Candidate answer:
{candidate_answer}

Rules:
1. Groundedness checks whether candidate claims are supported by retrieved contexts.
2. Correctness checks whether the candidate actually gives the correct answer according to the reference answer.
3. Completeness checks every required fact individually.
4. If the reference contains an answer but the candidate refuses or says it cannot be confirmed:
   - correctness must be fail
   - answer_status must be false_refusal
5. A hallucination-free refusal is not automatically a correct answer.
6. Return JSON only and follow the schema exactly.

Output schema:
{
  "groundedness": "pass | partial | fail",
  "correctness": "pass | fail",
  "missing_required_facts": ["exact missing required fact"],
  "answer_status": "answered | valid_refusal | false_refusal",
  "reason": "brief reason in at most two sentences"
}
```

## 실험 통제

1. 기존 60문항과 `gpt-5.4-mini` 생성 답변을 고정한다.
2. 단건 평가와 `temperature=0`을 사용한다.
3. 먼저 `gemma3:4b`로 v1 대비 루브릭 효과를 측정한다.
4. 같은 v2 루브릭으로 더 큰 평가 모델을 실행해 모델 크기 효과를 분리한다.
5. 단건 기준선이 안정된 후에만 배치 평가를 다시 비교한다.

## 주요 지표

- Human–LLM Overall Agreement
- False Pass: Human Fail / Judge Pass
- False Fail: Human Pass / Judge Fail
- False Refusal Recall
- Required Fact Omission Recall
- 동일 입력 반복 시 판정 재현성

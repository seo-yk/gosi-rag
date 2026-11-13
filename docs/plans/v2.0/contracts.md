# gosi-rag 2차 이터레이션 계약

이 문서는 [`spec.md`](./spec.md)의 요구사항을 구현 가능한 데이터 계약으로 구체화한다. 필드명과 상태 코드는 애플리케이션, 로그, 저장 데이터, 평가기 사이에서 공통으로 사용한다.

## 1. 공통 규칙

- 모델은 답변 본문만 생성하고 애플리케이션이 최종 `RagResponse`를 조립한다.
- 상태는 모델의 자기 보고가 아니라 실제 파이프라인 실행 결과로 결정한다.
- 입력 검사는 첫 실패에서 종료하며 복합 오류 목록을 만들지 않는다.
- 사용자 응답에는 안전한 메시지만 포함한다. 원본 예외와 공급자 오류 본문은 로그에만 기록한다.
- 모든 시각은 UTC ISO 8601, 소요 시간은 밀리초 정수로 기록한다.
- 필드에 의미가 없으면 생략하고, 계약에서 지정한 필드만 `null`을 허용한다.

## 2. 식별자

| 필드 | 의미 | 생성 시점 |
|---|---|---|
| `request_id` | 사용자 질문 한 건의 전체 처리 | 입력 수신 직후 |
| `generation_id` | 실제 LLM 호출 한 건 | LLM 호출 직전 |
| `evaluation_id` | 생성 결과 평가 한 건 | 평가 시작 직전 |
| `question_id` | 평가 데이터셋 질문 | 데이터셋 작성 시 |

LLM 호출 전에 종료되면 `generation_id`를 생성하지 않는다. 대체 모델 호출은 같은 `request_id` 아래에서 새로운 `generation_id`를 사용한다.

## 3. 공통 열거형

### 응답 상태

| 값 | 의미 |
|---|---|
| `answered` | 근거와 실행 조건을 통과해 답변을 반환함 |
| `abstained` | 검색 근거 부족 등 정책상 답변을 유보함 |
| `rejected` | 입력 계약을 만족하지 않아 처리 전에 거부함 |
| `failed` | 검색, 호출, 출력 처리, 저장 등 시스템 처리에 실패함 |

### 처리 단계

```text
input_validation
input_normalization
embedding
retrieval
retrieval_gate
context_assembly
prompt_building
llm_call
output_processing
persistence
completed
```

### 세부 원인 코드

```text
answer_generated
fallback_answer_generated
retrieval_no_results
retrieval_below_threshold
context_budget_exceeded
input_empty
input_not_text
input_too_long
input_unsupported_url
input_encoding_failed
embedding_failed
retrieval_failed
prompt_build_failed
llm_authentication_failed
llm_bad_request
llm_rate_limited
llm_provider_failed
llm_timeout
request_deadline_exceeded
output_empty
output_parse_failed
output_schema_mismatch
persistence_failed
fallback_provider_failed
```

한 응답에는 `reason_code` 하나만 사용한다. 복구 전의 실패 이력은 `attempts`로 표현한다.

## 4. 외부 응답 계약

### RagResponse

```json
{
  "schema_version": "2.0",
  "request_id": "req_001",
  "status": "answered",
  "reason_code": "answer_generated",
  "stage": "completed",
  "answer": "답변 본문",
  "message": null,
  "citations": [],
  "retrieval": null,
  "error": null
}
```

| 필드 | 타입 | 규칙 |
|---|---|---|
| `schema_version` | string | 응답 스키마 버전 |
| `request_id` | string | 항상 필요 |
| `status` | enum | 항상 필요 |
| `reason_code` | enum | 항상 하나만 필요 |
| `stage` | enum | 항상 필요 |
| `answer` | string \| null | `answered`일 때만 비어 있지 않은 문자열 |
| `message` | string \| null | `answered`가 아닐 때 사용자 안내 문장 |
| `citations` | Citation[] | 인용이 없으면 빈 배열 |
| `retrieval` | RetrievalSummary \| null | 검색 단계에 도달하지 않았으면 `null` |
| `error` | ErrorInfo \| null | `failed`일 때만 사용 |
| `attempts` | Attempt[] | 실제 LLM 호출이 두 번 이상일 때만 포함 |

상태별 불변 조건:

| 상태 | `answer` | `message` | `error` | `stage` |
|---|---|---|---|---|
| `answered` | 필수 | `null` | `null` | `completed` |
| `abstained` | `null` | 필수 | `null` | 유보를 결정한 단계 |
| `rejected` | `null` | 필수 | `null` | 입력 처리 단계 |
| `failed` | `null` | 필수 | 필수 | 실패한 단계 |

### Citation

```json
{
  "source_document_id": "faq-12",
  "chunk_id": "faq-12#001",
  "label": "FAQ 12"
}
```

`citations`는 답변이 실제로 인용한 출처다. 검색된 출처 전체나 모델에 전달된 출처를 대신하지 않는다.

### RetrievalSummary

```json
{
  "decision": "generate",
  "top_similarity_score": 0.86,
  "accepted_chunk_ids": ["faq-12#001"],
  "delivered_chunk_ids": ["faq-12#001"]
}
```

`decision`은 `generate` 또는 `abstain`이다. `top_similarity_score`는 검색 결과가 없으면 `null`이며 정답 확률이나 생성 모델의 확신도로 해석하지 않는다.

### ErrorInfo

```json
{
  "retryable": false,
  "provider": "gemini"
}
```

`provider`는 공급자 관련 실패일 때만 포함한다. 내부 예외 클래스명, API 키, 공급자 원문 오류는 포함하지 않는다.

### Attempt

```json
{
  "generation_id": "gen_001",
  "provider": "gemini",
  "model": "configured-model",
  "outcome": "rate_limited",
  "duration_ms": 820
}
```

`outcome`은 `succeeded`, `rate_limited`, `provider_failed`, `timeout`, `authentication_failed`, `bad_request` 중 하나다. `attempts`에는 실제 LLM 호출만 담고, 단일 호출이면 필드를 생략한다.

### 예시: 입력 거부

```json
{
  "schema_version": "2.0",
  "request_id": "req_002",
  "status": "rejected",
  "reason_code": "input_unsupported_url",
  "stage": "input_validation",
  "answer": null,
  "message": "이미지나 파일 URL 대신 텍스트로 질문해 주세요.",
  "citations": [],
  "retrieval": null,
  "error": null
}
```

### 예시: 근거 부족

```json
{
  "schema_version": "2.0",
  "request_id": "req_003",
  "status": "abstained",
  "reason_code": "retrieval_below_threshold",
  "stage": "retrieval_gate",
  "answer": null,
  "message": "확인할 수 있는 근거가 부족합니다. 질문을 구체적으로 작성해 주세요.",
  "citations": [],
  "retrieval": {
    "decision": "abstain",
    "top_similarity_score": 0.31,
    "accepted_chunk_ids": [],
    "delivered_chunk_ids": []
  },
  "error": null
}
```

### 예시: 대체 모델까지 실패

```json
{
  "schema_version": "2.0",
  "request_id": "req_004",
  "status": "failed",
  "reason_code": "fallback_provider_failed",
  "stage": "llm_call",
  "answer": null,
  "message": "답변 생성 중 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
  "citations": [],
  "retrieval": {
    "decision": "generate",
    "top_similarity_score": 0.84,
    "accepted_chunk_ids": ["faq-20#001"],
    "delivered_chunk_ids": ["faq-20#001"]
  },
  "error": {"retryable": true, "provider": "openai"},
  "attempts": [
    {
      "generation_id": "gen_004a",
      "provider": "gemini",
      "model": "configured-gemini-model",
      "outcome": "rate_limited",
      "duration_ms": 820
    },
    {
      "generation_id": "gen_004b",
      "provider": "openai",
      "model": "configured-openai-model",
      "outcome": "provider_failed",
      "duration_ms": 1140
    }
  ]
}
```

## 5. 입력 처리 계약

입력 검증기는 다음 순서로 한 항목씩 검사하고 첫 실패에서 반환한다.

1. 문자열 타입
2. 설정된 최대 문자 수
3. 감지 가능한 비텍스트 URL 또는 데이터 URI
4. NFC, 줄바꿈, 앞뒤 공백 정규화
5. UTF-8 strict 인코딩 가능 여부
6. 정규화 후 빈 문자열 여부

일반 웹 URL은 허용하며 네트워크 요청으로 MIME 타입을 확인하지 않는다. 검증을 통과한 객체만 임베딩과 검색으로 전달한다.

```json
{
  "request_id": "req_001",
  "text": "정규화된 질문",
  "character_count": 8,
  "utf8_byte_count": 22
}
```

## 6. 검색과 컨텍스트 계약

### RetrievedChunk

```json
{
  "chunk_id": "faq-12#001",
  "source_document_id": "faq-12",
  "text": "청크 본문",
  "retrieval_rank": 1,
  "similarity_score": 0.86,
  "dataset_version": "faq-2026-09-01",
  "index_version": "idx-2026-09-01"
}
```

`retrieval_rank`는 1부터 시작한다. `similarity_score`는 같은 `index_version`에 연결된 임곗값과만 비교한다.

### ContextChunk

```json
{
  "chunk_id": "faq-12#001",
  "source_document_id": "faq-12",
  "retrieval_rank": 1,
  "context_position": 1,
  "text": "모델에 실제 전달한 본문"
}
```

제외 사유는 `below_similarity_threshold` 또는 `input_budget_exceeded`로 기록한다. 청크 내부 절단, 요약, 재정렬은 하지 않는다.

## 7. 프롬프트 계약

```json
{
  "system_instructions": "답변 규칙",
  "retrieved_context": [
    {
      "chunk_id": "faq-12#001",
      "source_document_id": "faq-12",
      "text": "근거 본문"
    }
  ],
  "user_input": "사용자 질문"
}
```

세 영역은 논리적으로 분리한다. 예시와 배경 섹션은 두지 않는다. 검색, 임곗값 판단, 모델 호출은 프롬프트 구성기의 책임이 아니다. 필수 영역 누락이나 렌더링 실패는 `prompt_build_failed`로 종료하며 단순화된 프롬프트로 폴백하지 않는다.

## 8. LLM 호출 계약

공통 호출기는 공급자 독립 요청을 받고 어댑터가 SDK 요청으로 변환한다.

```json
{
  "request_id": "req_001",
  "generation_id": "gen_001",
  "model": "configured-model",
  "prompt": {},
  "max_output_tokens": 512,
  "timeout_ms": 10000
}
```

호출 결과는 공급자와 관계없이 다음 형태로 정규화한다.

```json
{
  "generation_id": "gen_001",
  "provider": "gemini",
  "model": "configured-model",
  "text": "모델 원문",
  "finish_reason": "stop",
  "input_tokens": 850,
  "output_tokens": 120,
  "duration_ms": 930
}
```

호출 정책:

- 1차 호출은 Gemini를 사용한다.
- 일시적 서버 오류 또는 속도 제한에만 OpenAI 호출을 한 번 허용한다.
- 타임아웃, 인증 실패, 잘못된 요청, 미지원 옵션에는 대체 호출하지 않는다.
- 전체 요청 마감 시간을 넘길 수 있으면 대체 호출을 시작하지 않는다.
- SDK 자동 재시도는 비활성화한다.
- 타임아웃이 발생하면 출력 처리기로 데이터를 넘기지 않는다.

## 9. 출력 처리 계약

일반 답변은 텍스트 추출, 줄바꿈·공백 정규화, 전체 답변을 감싼 코드 펜스 제거, 허용된 서두 제거, 빈 답변 검증 순으로 처리한다. 본문의 Markdown은 보존한다. 빈 결과는 `output_empty`다.

평가기 출력만 JSON으로 파싱한다. 전체 JSON을 감싼 코드 펜스를 제거한 뒤 파싱하고 다음 스키마를 검증한다.

```json
{
  "groundedness": 0.0,
  "correctness": 0.0,
  "overall": 0.0,
  "rationale": "평가 근거"
}
```

파싱 실패는 `output_parse_failed`, 필드 누락·타입·범위 오류는 `output_schema_mismatch`다. 출력 처리기는 LLM을 다시 호출하지 않는다.

## 10. 오류 정책 계약

오류 정책은 예외와 현재 실행 상태를 받아 다음 결정만 반환하는 순수 함수다.

```json
{
  "action": "stop",
  "status": "failed",
  "reason_code": "llm_timeout",
  "message": "답변 생성 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
  "retryable": true
}
```

`action`은 `stop` 또는 `use_fallback`이다. 재호출과 시간 제한 집행은 오케스트레이터와 LLM 호출기가 담당한다.

| 원인 | 최종 상태 | 단계 | 대체 호출 |
|---|---|---|---|
| 입력 형식·길이·URL·인코딩 | `rejected` | 입력 처리 | 금지 |
| 검색 결과 없음·임곗값 미달 | `abstained` | 검색 게이트 | 금지 |
| 컨텍스트 예산 부족 | `abstained` | 컨텍스트 조합 | 금지 |
| 프롬프트 구성 실패 | `failed` | 프롬프트 구성 | 금지 |
| 인증·잘못된 요청·타임아웃 | `failed` | LLM 호출 | 금지 |
| 속도 제한·일시적 서버 오류 | 미정 | LLM 호출 | 1회 허용 |
| 출력 파싱·스키마 오류 | `failed` | 출력 처리 | MVP에서 금지 |

## 11. 관측 이벤트 계약

모든 이벤트는 JSON Lines로 기록한다.

```json
{
  "timestamp": "2026-09-17T00:00:00Z",
  "request_id": "req_001",
  "stage": "retrieval",
  "event": "retrieval_completed",
  "status": "succeeded",
  "duration_ms": 42
}
```

공통 필드는 `timestamp`, `request_id`, `stage`, `event`, `status`다. 종료 이벤트에는 `duration_ms`, 실패 이벤트에는 내부 분류용 `error_type`을 추가한다.

필수 이벤트:

```text
request_received
input_validated
input_rejected
input_normalized
retrieval_completed
retrieval_gate_decided
context_assembled
prompt_built
llm_call_started
llm_call_completed
llm_call_failed
fallback_selected
output_processed
record_persisted
request_finished
```

`request_received`는 첫 이벤트이고 `request_finished`는 모든 종료 경로에서 정확히 한 번 기록한다. 입력 원문과 전체 컨텍스트는 일반 로그에 반복 저장하지 않는다.

## 12. 생성 기록 계약

생성 기록은 JSON Lines를 정본으로 사용한다.

```json
{
  "schema_version": "2.0",
  "request_id": "req_001",
  "generation_id": "gen_001",
  "created_at": "2026-09-17T00:00:01Z",
  "provider": "gemini",
  "model": "configured-model",
  "dataset_version": "faq-2026-09-01",
  "index_version": "idx-2026-09-01",
  "normalized_question": "정규화된 질문",
  "retrieved_chunks": [],
  "delivered_context": [],
  "raw_model_text": "모델 원문",
  "processed_answer": "정규화된 답변",
  "response_status": "answered",
  "response_reason_code": "answer_generated",
  "model_reported_status": null,
  "cited_chunk_ids": []
}
```

- `retrieved_chunks`에는 점수와 검색 순위를 저장한다.
- `delivered_context`에는 모델에 실제 전달한 본문과 순서를 저장한다.
- `model_reported_status`는 저장만 하며 최종 상태 판정에 사용하지 않는다.
- CSV는 분석용 파생 산출물이며 정본이 아니다.

## 13. 평가 기록 계약

```json
{
  "schema_version": "2.0",
  "evaluation_id": "eval_001",
  "generation_id": "gen_001",
  "question_id": "q_001",
  "evaluation_status": "succeeded",
  "groundedness": 0.92,
  "correctness": 0.88,
  "overall": 0.90,
  "rationale": "전달된 근거와 답변이 일치함",
  "evaluator_provider": "openai",
  "evaluator_model": "configured-judge-model",
  "created_at": "2026-09-17T00:01:00Z"
}
```

`evaluation_status`는 `succeeded` 또는 `failed`다. 실패 시 품질 점수와 `rationale`은 `null`이며 `evaluation_error_type`을 기록한다. 평가 실패를 낮은 품질 점수로 변환하지 않는다. 평가기는 현재 인덱스를 다시 검색하지 않고 `generation_id`에 저장된 `delivered_context`를 사용한다.

## 14. 버전 매니페스트 계약

### DatasetManifest

```json
{
  "schema_version": "2.0",
  "dataset_version": "faq-2026-09-01",
  "created_at": "2026-09-01T00:00:00Z",
  "source_hash": "sha256:...",
  "document_count": 100,
  "chunk_count": 100
}
```

### IndexManifest

```json
{
  "schema_version": "2.0",
  "index_version": "idx-2026-09-01",
  "dataset_version": "faq-2026-09-01",
  "created_at": "2026-09-01T00:05:00Z",
  "embedding_provider": "configured-provider",
  "embedding_model": "configured-model",
  "chunking_policy": "faq-row-v1",
  "similarity_metric": "cosine",
  "artifact_hash": "sha256:..."
}
```

데이터셋과 인덱스 버전은 불변이다. 같은 버전 이름으로 내용을 덮어쓰지 않는다. 검색 임곗값 설정에는 적용 대상 `index_version`을 함께 기록한다.

## 15. 요구사항 추적

| 계약 | 관련 요구사항 |
|---|---|
| 입력 처리 | INP-001~004 |
| 검색·컨텍스트 | RET-001~003, CTX-001~002 |
| 프롬프트 | PRM-001~002 |
| LLM 호출·어댑터 | LLM-001~004 |
| 외부 응답·출력 처리 | OUT-001~003 |
| 오류 정책 | ERR-001 |
| 로그 | OBS-001~002 |
| 생성·평가 기록 | REC-001~002, EVAL-001~002 |
| 버전 매니페스트 | VER-001~003 |

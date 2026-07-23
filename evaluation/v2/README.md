# Generation Evaluation v2

## 목표

고유 50문항을 대상으로 현재 Retrieval 기준선과 `gpt-5.4-mini` 생성 결과를 새로 만들고, 명시적인 필수 사실과 False Refusal 규칙을 적용해 `gemma3:4b` 단건 평가를 다시 수행한다.

## 고정 조건

- Dataset: q001~q050
- Retrieval: `row + intfloat/multilingual-e5-small + title + Top 3`
- Generation: `gpt-5.4-mini`
- Judge: `gemma3:4b`
- Evaluation unit: single item
- Temperature: 0

## 파일

- `evaluation/inputs/question_generation_v2.jsonl`: 관련 FAQ와 필수 사실을 포함한 고유 50문항
- `evaluation/v2/llm_judge_v2_rubric.md`: v2 루브릭
- `evaluation/scripts/generate_generation_v2.py`: 신규 답변 생성
- `evaluation/scripts/evaluate_generation_v2.py`: 단건 자동평가 및 Human Escalation 목록 생성
- `output/v2/`: 신규 실행 결과

## Overall Pass

아래 조건을 모두 만족해야 한다.

```text
groundedness != fail
AND correctness == pass
AND missing_required_facts가 비어 있음
AND answer_status != false_refusal
```

## Human Escalation

다음 항목을 사람이 우선 검토한다.

- 자동평가 Fail 전체
- `false_refusal`
- 복수 관련 FAQ 문항
- 자동평가 Pass 중 고정 시드로 추출한 10건

## 실행

```bash
EMBEDDING_PROVIDER=local \
EMBEDDING_MODEL=intfloat/multilingual-e5-small \
CHUNKING_MODE=row \
EMBEDDING_MODE=title \
TOP_K=3 \
GENERATION_PROVIDER=openai \
GENERATION_MODEL=gpt-5.4-mini \
.venv/bin/python evaluation/scripts/generate_generation_v2.py

.venv/bin/python evaluation/scripts/evaluate_generation_v2.py
```

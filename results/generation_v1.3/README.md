# 생성 실험 결과 (평가셋 v1.3)

2026-11-13 생성. 자동 채점(루브릭 v2)과 사람 검증 결과는 채점이 끝나면 이 폴더에 추가한다.

| 조건 | 생성 모델 | 근거 | 파일 |
|---|---|---|---|
| A | `gpt-5.4-mini` (OpenAI) | 검색 결과 Top-3 (bge-m3, row, title_body) | `generated_answers_A_gpt-5.4-mini.csv`, `…_out_of_scope.csv` |
| B | `gpt-5.4-mini` (OpenAI) | 정답 FAQ(오라클). 검색 오류를 뺀 생성 품질의 상한 | `generated_answers_B_gpt-5.4-mini_oracle.csv` |
| C | `exaone3.5:7.8b` (Ollama, num_ctx 8192) | A와 같은 검색 설정 | `generated_answers_C_exaone3.5-7.8b.csv`, `…_out_of_scope.csv` |

- 문항: 본 평가셋 148문항(A·B·C), 범위 밖 10문항(A·C)
- 생성 프롬프트는 세 조건 공통(`src/generation.py`의 `build_prompt`), temperature 0
- 칼럼: `id`, `type`, `question`, `required_faqs`, `reference_answer`, `model`, `context_setup`, `context_faqs`, `context_text`, `answer`
- 답변 길이 평균: A 258자, B 235자, C 366자

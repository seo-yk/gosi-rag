# 생성 실험 결과 (평가셋 v1.3)

2026-11-13 생성·채점. 채점 모델 선정과 사람 검증은 `evaluation/judge_calibration/`, 설계와 해석은 `docs/experiment_log.md`에 있다.

| 조건 | 생성 모델 | 근거 | 파일 |
|---|---|---|---|
| A | `gpt-5.4-mini` (OpenAI) | 검색 결과 Top-3 (bge-m3, row, title_body) | `generated_answers_A_gpt-5.4-mini.csv`, `…_out_of_scope.csv` |
| B | `gpt-5.4-mini` (OpenAI) | 정답 FAQ(오라클). 검색 오류를 뺀 생성 품질의 상한 | `generated_answers_B_gpt-5.4-mini_oracle.csv` |
| C | `exaone3.5:7.8b` (Ollama, num_ctx 8192) | A와 같은 검색 설정 | `generated_answers_C_exaone3.5-7.8b.csv`, `…_out_of_scope.csv` |

- 문항: 본 평가셋 148문항(A·B·C), 범위 밖 10문항(A·C)
- 생성 프롬프트는 세 조건 공통(`src/generation.py`의 `build_prompt`), temperature 0
- 칼럼: `id`, `type`, `question`, `required_faqs`, `reference_answer`, `model`, `context_setup`, `context_faqs`, `context_text`, `answer`
- 답변 길이 평균: A 258자, B 235자, C 366자

## 자동 채점 (gemini-3.8-flash, 루브릭 v2.1)

| 조건 | pass | 근거성 2 | 정확성 1 | 완결성 1 | 근거 있는데 회피 |
|---|---:|---:|---:|---:|---:|
| A (gpt-5.4-mini + 검색) | 138/148 (93.2%) | 98.0% | 93.9% | 93.9% | 1 |
| B (gpt-5.4-mini + 정답 근거) | 145/148 (98.0%) | 99.3% | 98.6% | 98.0% | 1 |
| C (EXAONE 3.5 7.8B + 검색) | 103/148 (69.6%) | 75.7% | 83.1% | 84.5% | 8 |

- 파일: `judged_<조건>__gemini-3.8-flash.csv` (칼럼: id, model, context_setup, judge_model, groundedness, correctness, groups_covered, completeness, unjustified_refusal, verdict, reason)
- 반복 채점(조건별 무작위 10문항, 30문항): 판정 29/30 같음, 모든 점수 28/30 같음(`rejudge_*.csv`)
- 채점기 신뢰도(사람 기준): A·B 40문항 판정 일치 90.0%(kappa 0.45) → 불일치 재검토 후 95.0%(kappa 0.64). C 15문항 8/15(kappa 0.12) → 재검토 후 14/15(kappa 0.87). C 보정 추정 합격률 약 73.4%(채점기 69.6%와 차이 확인 안 됨)
- 토큰 사용(444문항): 입력 약 61.8만, 출력 약 4.1만, 생각 약 12.6만

## 범위 밖 질문 차단 (사람 판정)

| 조건 | 차단 |
|---|---|
| A gpt-5.4-mini | 10/10 |
| C EXAONE 3.5 7.8B | 10/10 |

기준: FAQ에 근거가 없음을 밝히면 통과, 안내처 언급은 허용, 근거 없는 수치·사실을 답하면 실패. 판정 원본은 `evaluation/judge_calibration/oos_human_labels.csv`.


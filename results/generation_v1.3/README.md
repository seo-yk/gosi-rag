# 생성 실험 결과 (평가셋 v1.3)

2026-11-13 생성·채점. 결과 해석은 `docs/2_generation.md`, 채점기 검증은 `docs/3_judge_validation.md`에 있다.

| 조건 | 생성 모델 | 근거 |
|---|---|---|
| A | `gpt-5.4-mini` (OpenAI) | 검색 결과 상위 3개 (bge-m3, row, title_body) |
| B | `gpt-5.4-mini` (OpenAI) | 정답 FAQ (검색 오류를 뺀 조건) |
| C | `exaone3.5:7.8b` (Ollama, 컨텍스트 8K) | A와 같은 검색 결과 |

| 파일 | 내용 |
|---|---|
| `answers_A.csv`, `answers_B.csv`, `answers_C.csv` | 생성 답변 148문항 |
| `answers_A_out_of_scope.csv`, `answers_C_out_of_scope.csv` | 범위 밖 질문 10문항 답변(사람 판정: `evaluation/human_review/5_oos_review/`) |
| `judged_A.csv`, `judged_B.csv`, `judged_C.csv` | 자동 채점 결과(gemini-3.8-flash, 루브릭 v2.1)와 판단 근거 |
| `rejudged_A.csv`, `rejudged_B.csv`, `rejudged_C.csv` | 반복 채점 확인(조건별 무작위 10문항) |

열 설명은 `docs/2_generation.md` 9장에 있다. CSV는 UTF-8(BOM 포함)이다.

스크립트가 `output/`에 만드는 원래 파일 이름과의 대응: `generated_answers_<조건>_<모델>.csv` → `answers_<조건>.csv`, `judged_<조건>_<모델>__gemini-3.8-flash.csv` → `judged_<조건>.csv`, `rejudge_…` → `rejudged_<조건>.csv`.

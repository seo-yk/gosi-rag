# 1차 실험 기록 (2026.06~07)

이 폴더는 1차 실험의 질문셋과 결과 파일을 보관한다. 2026-11-12에 `evaluation/inputs/`와 `output/`에서 옮겨 왔다(`git mv`, 내용 변경 없음). 재실험(평가셋 v1.2 이후)의 파일과 섞이지 않게 분리했다.

1차 실험 당시의 저장소 전체는 태그 `experiment-v1`(커밋 `3292007`)로 볼 수 있다.

## 파일

| 파일 | 행 수 | 내용 |
|---|---|---|
| `inputs/question_retrieval.csv` | 50 | 검색 평가 질문셋. 정답 FAQ 1개(`target_answer_no`) |
| `inputs/question_generation.csv` | 60 | 생성 평가 질문셋. 기준 답변과 보조 FAQ 포함 |
| `output/retr_e5-small.csv` | 12 | `intfloat/multilingual-e5-small` 검색 조합별 Hit@1·3·5, MRR |
| `output/retr_openai-3-small.csv` | 12 | `text-embedding-3-small` 검색 조합별 결과 |
| `output/retr_openai-3-large.csv` | 4 | `text-embedding-3-large` 검색 조합별 결과 |
| `output/gen_60_gpt-5.4-mini.csv` | 60 | `gpt-5.4-mini` 생성 답변과 검색된 FAQ |
| `output/eval_60_gpt-5.4-mini-gemma3-4b_single.csv` | 60 | `gemma3:4b` 단건 채점 결과 |
| `output/eval_60_gpt-5.4-mini-gemma3-4b_b3.csv` | 60 | `gemma3:4b` 배치(3문항) 채점 비교군 |

검색 대상 데이터는 `data/faq.csv`(교정 전 원본 289건)다. 이 파일은 원본 공공데이터라서 옮기지 않았다.

## 주요 수치 (루트 README 7장)

- 검색: `row` + `e5-small` + `title` + Top 3 조합에서 Hit@1 90.2%, Hit@3 96.1%, Hit@5 96.1%, MRR 0.928
- 생성: 수동 평가 Overall Pass 55/60, 자동 평가 60/60, 수동·자동 일치율 91.67%

## 이 결과를 다시 쓰지 않는 이유

1. **원본 FAQ의 제목과 본문이 어긋나 있었다.** 연번 100~200(101건)의 본문이 한 칸씩 밀려, 각 행의 본문이 앞 연번 질문의 답이었다. 자세한 내용은 `data/CHANGES_faq.md`에 있다. 최종 검색 조합은 제목만 임베딩해서 이 영향이 작았을 수 있다. 하지만 `title + body` 조합과 생성 단계(검색된 본문을 근거로 답변)는 직접 영향을 받았다.
2. **검색 평가 문항 수가 모델마다 달랐다.** 인수인계 기록에 따르면 e5는 51문항, OpenAI는 50문항이었다. 현재 남은 질문셋 파일은 50행이다.
3. **검색용(50)과 생성용(60) 평가셋이 따로 있었다.** 그래서 두 단계 결과를 같은 문항 기준으로 비교할 수 없었다.

재실험은 교정본 FAQ(`data/faq_v2.csv`)와 단일 평가셋(`evaluation/inputs/evalset_v1.2.jsonl` 이후 버전)으로 진행한다.

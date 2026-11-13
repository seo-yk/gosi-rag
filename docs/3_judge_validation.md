# 3. 자동 채점기 검증 (사람 채점)

생성 답변 444개(A·B·C 각 148)는 LLM 채점기로 채점했다. 채점기를 쓰기 전에, 사람이 블라인드로 채점한 결과와 비교해 채점기를 고르고 신뢰도를 확인했다. 사람 채점자는 1명(프로젝트 작성자)이다.

- 사람 채점 파일: `evaluation/human_review/` (단계별 폴더, 파일 설명은 그 폴더의 README)
- 채점 코드: `evaluation/scripts/judge_answers.py`(루브릭 v2.1), 비교: `evaluation/scripts/compare_judges.py`
- 결정 과정과 이유: `docs/experiment_log.md` 8-3 ~ 8-10

## 3-1. 진행 순서

| 단계 | 폴더 | 문항 | 목적 |
|---|---|---|---|
| 1 | `1_ab_review/` | 40 (A 20 + B 20) | 사람 기준 만들기, 채점기 후보 6개 비교 |
| 2 | `2_ab_rereview/` | 8 (불일치 4 + 일치 4) | 1단계 불일치가 사람 실수인지 채점기 실수인지 블라인드로 다시 보기 |
| 3 | `3_c_review/` | 15 (C) | EXAONE 답변에도 채점기가 맞게 판정하는지 확인 |
| 4 | `4_c_adjudication/` | 7 (3단계 불일치) | 채점기의 판단 근거를 보고 근거 FAQ와 대조해 최종 판단 |
| 5 | `5_oos_review/` | 20 (A 10 + C 10) | 범위 밖 질문 답변 판정(자동 채점하지 않음) |

## 3-2. 채점 기준 (루브릭 v2.1, 사람·채점기 공통)

각 답변을 **질문 → 필수 근거 → 기준 답변 → 제공된 근거 FAQ → 생성 답변** 순서로 읽고 네 항목을 매긴다.

| 항목 | 값 | 기준 |
|---|---|---|
| 근거성 | 0/1/2 | 답변 내용이 **제공된 근거 FAQ에 있는가**. 2 = 모두 있음, 1 = 근거에 없는 세부 내용이 조금 섞임, 0 = 핵심 내용이 근거에 없거나 근거와 모순 |
| 정확성 | 0/1 | 답변에 **쓴 내용이 맞는가**. 빠뜨린 부분은 보지 않는다. 아무것도 답하지 않았으면 0 |
| 그룹별 충족 | 그룹마다 0/1 (예: `1\|0`) | 필수 근거 그룹마다 그 내용에 답했는가. "또는"으로 묶인 FAQ는 하나만 다뤄도 충족 |
| 근거 있는데 회피 | 0/1 | 근거 FAQ에 답이 있는 부분을 하나라도 "확인할 수 없다"는 식으로 피했으면 1 |

- **합격(pass):** 근거성 2, 정확성 1, 모든 그룹 충족, 회피 0. 입력값으로 자동 계산한다.
- 길이, 서식(굵게·목록), 말투는 점수에 넣지 않는다.
- 근거 FAQ끼리 내용이 다르면(예: 사전등록 경로) 그중 하나에 근거한 답은 맞는 것으로 본다.
- 근거 FAQ에 있는 정보라면 질문 범위를 넘는 내용을 덧붙여도 감점하지 않는다.
- 근거 FAQ에 답이 없어 "확인할 수 없다"고 답했다면 회피 0, 정확성 0이다.
- 예: 두 가지를 물었는데 하나는 맞게 답하고 다른 하나는 근거가 있는데 피했으면 정확성 1, 그룹 `1|0`, 회피 1.
- **범위 밖 질문(5단계):** FAQ에 근거가 없음을 밝히면 통과, 안내처 언급은 허용, 근거 없는 수치·사실을 답하면 실패.

규칙 이력: v2 → **v2.1(2026-11-13)**. v2의 "회피면 정확성 0" 규칙을 없앴다. 일부만 피한 답변에서 맞게 답한 부분까지 정확성 0이 되어 같은 결함이 두 항목에서 깎였기 때문이다.

## 3-3. 1단계: 채점기 선정 (A·B 40문항)

**표본:** A(gpt-5.4-mini + 검색) 20 + B(gpt-5.4-mini + 정답 FAQ) 20, 서로 다른 문항. 조건마다 유형별로 층화했다(복수근거 6, 원문유사 4, 일상표현 5, 조건형 5). 사전등록 경로가 FAQ마다 다른 문항(38, 49, 50, 55)을 포함했다. 모델 이름, 근거 구성, 자동 점수는 숨기고 순서를 섞었다(시드 고정).

**결과:** 사람 판정 pass 35, fail 5. pass가 많아 판정 일치율보다 kappa와 fail 검출을 함께 봤다.

| 채점기 후보 | 판정 일치 | kappa | 사람 fail 검출 | 사람 pass 유지 | 채점기 pass율 | 근거성 | 정확성 | 그룹 충족 | 회피 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma3-4b (로컬, 8K) | 40.0% | 0.10 | 5/5 | 11/35 | 27.5% | 52.5% | 82.5% | 50.9% | 97.5% |
| qwen2.5-7b (로컬, 8K) | 30.0% | 0.06 | 5/5 | 7/35 | 17.5% | 67.5% | 82.5% | 41.5% | 77.5% |
| gemini-2.5-flash (24문항) | 91.7% | 0.70 | 3/4 | 19/20 | 83.3% | 83.3% | 95.8% | 90.3% | 95.8% |
| gemini-3.5-flash | 90.0% | 0.45 | 2/5 | 34/35 | 92.5% | 92.5% | 97.5% | 90.6% | 97.5% |
| gemini-3.7-flash | 90.0% | 0.45 | 2/5 | 34/35 | 92.5% | 90.0% | 95.0% | 90.6% | 97.5% |
| **gemini-3.8-flash (채택)** | 90.0% | 0.45 | 2/5 | 34/35 | 92.5% | 90.0% | 97.5% | 90.6% | 97.5% |

- 로컬 모델 2개는 사람이 합격으로 본 답변 대부분을 불합격으로 판정해 제외했다.
- gemini-2.5-flash는 무료 한도(프로젝트·모델당 하루 20회)에 걸려 24문항만 채점했다. 유료 키로 바꾼 뒤에는 신규 사용자에게 제공되지 않는 모델이라 40문항을 채우지 못했다.
- gemini-3.5/3.7/3.8-flash는 판정 일치와 불일치 문항(A-7, A-19, A-38, B-66)이 같았다. 가장 최신인 3.8-flash를 골랐다.
- 한계: 채점기가 사람보다 pass를 더 준다(92.5% 대 87.5%).

## 3-4. 2단계: 불일치 재검토 (8문항)

1단계 불일치 4문항이 사람 실수인지 채점기 실수인지 보기 위해, 일치 4문항과 섞어 블라인드로 다시 채점했다(처음 점수와 채점기 판정은 숨김).

- 같은 사람 재채점에서 판정 4/4가 처음과 같았다(일치 문항 기준. 세부 점수는 2/4 달라짐).
- 불일치 4건 중 2건(A-7, B-66)은 사람이 판단을 바꿔 채점기와 같아졌고, 2건(A-19, A-38)은 유지했다.
- 재검토를 반영한 사람 판정: pass 37, fail 3 (`2_ab_rereview/labels_final.csv`).

| 채점기 | 판정 일치 | kappa | 사람 fail 검출 | 사람 pass 유지 |
|---|---:|---:|---:|---:|
| gemma3-4b | 35.0% | 0.06 | 3/3 | 11/37 |
| qwen2.5-7b | 25.0% | 0.03 | 3/3 | 7/37 |
| gemini-2.5-flash (24문항) | 95.8% | 0.83 | 3/3 | 20/21 |
| gemini-3.5 / 3.7 / **3.8-flash** | 95.0% | 0.64 | 2/3 | 36/37 |

남은 불일치: A-19(사람 pass, 채점기 fail. 근거가 제공되지 않은 그룹을 "충족"으로 볼지에 대한 해석 차이), A-38(사람 fail, 채점기 pass).

## 3-5. 3·4단계: EXAONE(C) 답변 검증

A·B는 OpenAI 답변이라, 차이가 가장 큰 C(EXAONE)에서도 채점기가 맞는지 따로 확인했다. 채점기의 fail 판정이 맞는지 보려고 채점기 fail 8 + pass 7을 뽑았다(시드 고정). fail을 일부러 더 뽑았으므로 일치율은 채점기 판정별로 본다.

**3단계(블라인드):** 사람 pass 14, fail 1. 판정 일치 8/15(kappa 0.12). 채점기 pass 7개는 사람도 모두 pass, 채점기 fail 8개 중 사람 fail은 1개였다.

**4단계(채점기 판단 근거 확인):** 불일치 7문항을 채점기의 점수와 판단 근거를 보면서, 답변 내용이 근거 FAQ에 실제로 있는지 다시 대조했다.

- 결정: 채점기 의견 반영 4, 둘 다 아님 3(최종 fail 2, pass 1), 처음 유지 0
- 재검토 후 사람 pass 8, fail 7. 채점기와 판정 일치 14/15(kappa 0.87)
- 처음 사람 채점에서 근거 FAQ에 없는 내용(존재하지 않는 URL 등)을 놓친 경우가 있었다. 읽기 쉬운 답변을 더 좋게 보는 경향(유창성 편향)도 확인했다.
- 보정 추정 C 합격률 약 73.4%(채점기 69.6%). 5%p 기준으로 차이가 확인되지 않는다.
- 채점기 의견을 본 뒤의 판단이므로 처음 판정과 최종 판정을 함께 기록했다(`4_c_adjudication/labels.csv`).

## 3-6. 5단계: 범위 밖 질문 판정

FAQ에 답이 없는 질문 10개에 대한 A·C 답변 20개를 사람이 판정했다.

- **A 10/10, C 10/10 차단.** 근거 없음을 밝힘 20/20, 근거 없는 수치·사실 0/20.
- 19·20번은 드라이브 파일에 저장이 반영되지 않아 채팅으로 받은 값을 썼다(`source` 열).

## 3-7. 반복 채점 일관성

조건별 무작위 10문항(총 30)을 같은 채점기로 다시 채점했다. 판정 29/30, 모든 점수 28/30이 같았다(`results/generation_v1.3/rejudged_*.csv`).

## 3-8. 한계

- 사람 채점자가 1명이라 사람끼리의 일치도는 잴 수 없다.
- 채점기를 고른 기준이 사람 채점이고, 사람 채점도 채점기의 지적을 보고 일부 바뀌었다. 그래서 재검토 전과 후 수치를 모두 기록했다.
- 채점기가 놓친 실패가 있다. B-153은 A-153과 같은 잘못된 해석인데 합격으로 판정됐다(`docs/experiment_log.md` 8-12).

## 3-9. 다시 만들기

빈 채점지는 저장소에 두지 않는다. 아래 명령으로 `output/`에 다시 만든다(난수 시드 고정, openpyxl 필요). 키 파일은 채점이 끝날 때까지 열지 않는다.

```bash
# 1단계
python evaluation/scripts/build_review_sheet.py      # output/review_sheet_base.csv, output/review_key.csv
python evaluation/scripts/export_review_xlsx.py      # output/review_sheet.xlsx
# 2단계
python evaluation/scripts/build_rereview_sheet.py
python evaluation/scripts/export_review_xlsx.py output/rereview_base.csv output/rereview_sheet.xlsx
# 3·5단계
python evaluation/scripts/build_c_oos_review_sheets.py
python evaluation/scripts/export_review_xlsx.py output/c_review_base.csv output/c_review_sheet.xlsx
python evaluation/scripts/export_review_xlsx.py output/oos_review_base.csv output/oos_review_sheet.xlsx
# 4단계
python evaluation/scripts/build_c_adjudication_sheet.py   # output/c_adjudication_sheet.xlsx
# 채점기 비교표
python evaluation/scripts/compare_judges.py evaluation/human_review/1_ab_review/judges/gemini-3.8-flash_A.csv evaluation/human_review/1_ab_review/judges/gemini-3.8-flash_B.csv
python evaluation/scripts/compare_judges.py --human evaluation/human_review/2_ab_rereview/labels_final.csv evaluation/human_review/1_ab_review/judges/*.csv
```

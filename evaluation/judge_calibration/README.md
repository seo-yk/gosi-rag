# 채점 모델 선정·검증 (사람 채점)

자동 채점 모델이 사람과 얼마나 같은 판단을 하는지 재기 위한 블라인드 사람 채점이다. 결과로 채점 모델을 고르고(후보 중 사람과 가장 잘 맞는 모델), 조건별 일치율을 함께 보고한다.

## 파일

| 파일 | 내용 |
|---|---|
| `review_sheet.xlsx` | 사람 채점지 40문항. `채점` 시트의 노란 칸 5개 열을 채운다. `채점 방법` 시트에 기준 요약 |
| `review_key.csv` | 번호별 조건(A/B)·문항 id. 채점 중에는 `output/`에만 두었고, 사람 채점이 끝난 뒤(2026-11-13) 공개 |
| `review_sheet_filled.xlsx` | 사람이 채점을 마친 파일(원본 그대로) |
| `human_labels.csv` | 위 파일을 키와 합친 사람 채점 결과. 열: `review_no`, `condition`, `id`, `type`, `groundedness`, `correctness`, `groups_covered`, `completeness`, `unjustified_refusal`, `verdict`, `memo`. `completeness`와 `verdict`는 입력값으로 계산 |

다시 만들기(난수 시드 고정):

```bash
python evaluation/scripts/build_review_sheet.py          # output/review_sheet_base.csv, output/review_key.csv
python evaluation/scripts/export_review_xlsx.py          # evaluation/judge_calibration/review_sheet.xlsx (openpyxl 필요)
```

표본: A(검색 근거, `gpt-5.4-mini`) 20문항 + B(정답 근거, `gpt-5.4-mini`) 20문항, 서로 다른 문항, 유형별 층화(조건마다 복수근거 6, 원문유사 4, 일상표현 5, 조건형 5), 사전등록 경로가 FAQ마다 다른 문항(38, 49, 50, 55) 포함. 모델 이름·근거 구성·자동 점수는 넣지 않고 순서를 섞었다.

## 채점 방법

각 행에서 **질문 → 필수 근거 → 기준 답변 → 제공된 근거 FAQ → 생성 답변** 순서로 읽고 오른쪽 열을 채운다.

| 열 | 입력 값 | 판단 기준 |
|---|---|---|
| 근거성(0/1/2) | `0`, `1`, `2` | 생성 답변의 내용이 **"제공된 근거 FAQ"에 있는가**. 2 = 모든 내용이 근거에 있음, 1 = 근거에 없는 세부 내용이 조금 섞임, 0 = 핵심 내용이 근거에 없거나 근거와 모순 |
| 정확성(0/1) | `0`, `1` | 답변에 **실제로 쓴 내용이 맞는가**(틀린 정보가 없는가). 기준 답변과 표현이 달라도 뜻이 같거나 근거 FAQ로 뒷받침되면 맞음. 빠뜨린 부분은 여기서 보지 않는다(그룹별 충족에서 본다). 아무것도 답하지 않았으면 0 |
| 그룹별 충족(예: 1\|0) | 그룹 수만큼 `0`/`1`을 `\|`로 연결 | "필수 근거"의 그룹마다 그 내용에 답했는가. 그룹이 1개면 `1` 또는 `0`. 그룹 안에 "또는"으로 묶인 FAQ는 하나만 다뤄도 충족 |
| 근거 있는데 회피(0/1) | `0`, `1` | 제공된 근거 FAQ에 답이 있는 **부분을 하나라도** "확인할 수 없다"는 식으로 피했으면 1. 답을 준 뒤 "자세한 건 공고문 확인" 같은 안내를 덧붙인 것은 회피가 아님 |
| 메모 | 자유 | 판단이 애매했던 이유 등(선택) |

공통 규칙(자동 채점과 같음):

- 답변 길이, 굵은 글씨·목록 같은 서식, 말투는 점수에 반영하지 않는다.
- 근거 FAQ끼리 내용이 다르면(예: 사전등록 경로), 그중 하나에 근거한 답은 맞는 것으로 본다.
- 근거 FAQ에 있는 정보라면 질문 범위를 넘는 내용을 덧붙여도 감점하지 않는다.
- 근거 FAQ에 답이 없어 "확인할 수 없다"고 답했다면 회피는 0, 정확성은 0이다.
- 세 항목은 각각 하나만 본다: 정확성 = 쓴 내용이 맞는가, 그룹별 충족 = 빠뜨렸는가, 회피 = 근거가 있는데 피했는가. 예: 두 가지를 물었는데 하나는 맞게 답하고 다른 하나는 근거가 있는데 피했으면 정확성 1, 그룹 `1|0`, 회피 1.

규칙 이력: 루브릭 v2(처음 배포) → **v2.1(2026-11-13)**. v2의 "회피면 정확성 0" 규칙을 없앴다. 일부만 피한 답변에서 맞게 답한 부분까지 정확성 0이 되어, 같은 결함이 여러 항목에서 이중으로 깎이는 문제 때문이다. 사람 채점과 자동 채점 모두 v2.1을 쓴다.

판정(pass)은 입력한 값으로 자동 계산한다: 근거성 2, 정확성 1, 모든 그룹 충족, 회피 0이면 pass.

## 채점 후

채운 파일을 같은 이름(`review_sheet.xlsx`)으로 저장하면 된다. 그다음 후보 채점 모델들을 같은 40문항에 돌려 항목별·판정 일치율을 비교하고, 가장 잘 맞는 모델을 채택한다.

## 결과: 채점 모델 선정 (2026-11-13)

후보 6개를 같은 40문항(루브릭 v2.1)으로 채점해 사람과 비교했다. 상세 표는 `judge_comparison.md`, 후보별 원본은 `candidates/`에 있다.

- 로컬 `gemma3-4b`, `qwen2.5:7b`: 판정 일치 40%·30%(kappa 0.10·0.06). 대부분을 fail로 줘서 탈락
- `gemini-2.5-flash`: 24문항에서 91.7%(kappa 0.70). 무료 한도(프로젝트·모델당 하루 20회)에 걸려 B를 4문항까지만 채점했다. 유료 키는 신규 사용자로 분류돼 이 모델을 쓸 수 없어 40문항을 채우지 못했다
- `gemini-3.5/3.7/3.8-flash`: 셋 다 판정 일치 90.0%, kappa 0.45, 사람 fail 5개 중 2개 검출. 불일치 문항도 같다(A-7, A-19, A-38, B-66)
- **채택: `gemini-3.8-flash`.** 한계: 사람보다 pass를 더 주는 경향(채점기 92.5% 대 사람 87.5%)

## 불일치 재검토

| 파일 | 내용 |
|---|---|
| `rereview_sheet.xlsx` | 불일치 4 + 일치 4를 섞은 8문항. 처음 채점 결과와 채점기 판정은 숨김. 처음 채점지와 같은 방식으로 채운다 |
| `output/rereview_key.csv` | 번호별 원래 문항과 불일치 여부. 재검토가 끝날 때까지 열지 않는다 |

다시 만들기: `python evaluation/scripts/build_rereview_sheet.py` → `python evaluation/scripts/export_review_xlsx.py output/rereview_base.csv evaluation/judge_calibration/rereview_sheet.xlsx`

재검토 후에도 다르면 채점기의 판단 근거를 보고 최종 판단을 정하고, 그 사실을 기록한다. 일치율은 처음 채점 기준과 재검토 후 기준을 둘 다 보고한다.

## 추가 사람 채점 (C 검증, 범위 밖 판정)

| 파일 | 문항 | 목적 | 키(채점 끝날 때까지 열지 않음) |
|---|---|---|---|
| `c_review_sheet.xlsx` | 15 | C(EXAONE) 답변에도 채점기가 공정한지 확인. 채점기 fail 8 + pass 7(시드 고정). 형식·기준은 처음 채점지와 같음 | `output/c_review_key.csv` |
| `oos_review_sheet.xlsx` | 20 | 범위 밖 질문 답변 판정(A 10 + C 10). 기준: FAQ에 근거가 없음을 밝히면 통과, 안내처 언급은 허용, 근거 없는 수치·사실을 답하면 실패 | `output/oos_review_key.csv` |

- C 표본은 fail을 일부러 더 뽑았다(채점기의 fail 판정이 맞는지 보려고). 그래서 일치율은 전체보다 **채점기 판정별**(fail 판정 중 사람도 fail, pass 판정 중 사람도 pass)로 보고한다.
- 다시 만들기: `python evaluation/scripts/build_extra_review_sheets.py` 다음 `export_review_xlsx.py`로 각 CSV를 변환

## 재검토 결과

- `rereview_sheet_filled.xlsx`(원본), `rereview_key.csv`(공개), `rereview_labels.csv`(재검토 점수와 처음 판정·채점기 판정 비교)
- `human_labels_rereviewed.csv`: 처음 사람 채점에 재검토 8문항을 반영한 결과(pass 37, fail 3). `adjudicated` 열이 `rereview`인 행이 바뀐 대상
- 같은 사람 재채점: 판정 4/4 같음(세부 점수는 2/4 달라짐). 불일치 4건 중 2건은 사람이 판단을 바꿔 채점기와 같아졌고 2건(A-38, A-19)은 유지
- gemini-3.8-flash 일치도: 처음 기준 90.0%(kappa 0.45) → 재검토 후 95.0%(kappa 0.64). 표는 `judge_comparison_rereviewed.md`

## C 검증 결과

- `c_review_sheet_filled.xlsx`(원본), `c_review_key.csv`(공개), `c_human_labels.csv`(사람 점수와 채점기 점수 비교)
- 사람 pass 14·fail 1. 채점기와 판정 일치 8/15(kappa 0.12). 채점기 pass 7개는 사람도 모두 pass, 채점기 fail 8개 중 사람 fail은 1개
- 불일치 7건의 해석(채점기가 박한가, 사람이 놓쳤는가)은 재검토 후 정한다. `docs/experiment_log.md` 8-10 참고

## 범위 밖 판정 결과

- `oos_review_sheet_filled.xlsx`(원본), `oos_review_key.csv`(공개), `oos_human_labels.csv`(판정)
- **A 10/10, C 10/10 차단**(근거 없음을 밝힘 20/20, 근거 없는 수치·사실 0/20)
- 19·20번 행은 드라이브 파일에 저장이 반영되지 않아 사용자가 채팅으로 알려 준 값을 썼다(`source` 열)


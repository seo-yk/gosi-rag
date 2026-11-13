# 사람 채점 기록

자동 채점기를 고르고 검증하려고 사람이 채점한 결과다. 과정, 기준, 결과는 `docs/3_judge_validation.md`에 있다. 폴더 번호는 진행 순서다.

| 폴더 | 내용 |
|---|---|
| `1_ab_review/` | A·B 답변 40문항 블라인드 채점, 채점기 후보 6개 결과 |
| `2_ab_rereview/` | 1단계 불일치 확인용 8문항 블라인드 재채점 |
| `3_c_review/` | EXAONE(C) 답변 15문항 블라인드 채점 |
| `4_c_adjudication/` | 3단계 불일치 7문항을 채점기 판단 근거를 보고 다시 판단 |
| `5_oos_review/` | 범위 밖 질문 답변 20개 판정 |

## 파일 이름 규칙

| 파일 | 내용 |
|---|---|
| `sheet.xlsx` | 사람이 채점을 마친 채점지(원본 그대로). 빈 양식은 `docs/3_judge_validation.md` 3-9의 명령으로 `output/`에 다시 만든다 |
| `key.csv` | 채점지 번호 → 조건(A/B/C)·문항 id. 채점이 끝난 뒤 공개 |
| `labels.csv` | 채점지와 키를 합친 결과(단계마다 열이 조금 다름, 아래 참고) |

## 단계별 파일

| 파일 | 열 / 설명 |
|---|---|
| `1_ab_review/labels.csv` | `review_no`, `condition`, `id`, `type`, `groundedness`, `correctness`, `groups_covered`, `completeness`, `unjustified_refusal`, `verdict`, `memo`. `completeness`와 `verdict`는 입력값으로 계산 |
| `1_ab_review/judges/<채점기>_<A\|B>.csv` | 채점기 후보 6개가 같은 40문항을 채점한 결과(점수와 판단 근거) |
| `2_ab_rereview/labels.csv` | 재채점 점수와 처음 판정·채점기 판정 비교 |
| `2_ab_rereview/labels_final.csv` | 1단계 40문항에 재채점을 반영한 최종 사람 라벨(pass 37, fail 3). `adjudicated=rereview`인 행이 바뀐 대상 |
| `3_c_review/labels.csv` | 사람 점수와 채점기 점수·판정 |
| `4_c_adjudication/labels.csv` | 처음 판정, 최종 점수·판정, 결정(처음 유지 / 채점기 의견 반영 / 둘 다 아님), 메모 |
| `5_oos_review/labels.csv` | 조건, id, 근거 없음을 밝혔는지, 근거 없는 수치·사실을 답했는지, 판정. `source` 열은 값의 출처(19·20번은 채팅으로 받은 값) |

조건: A = gpt-5.4-mini + 검색 결과, B = gpt-5.4-mini + 정답 FAQ, C = EXAONE 3.5 7.8B + 검색 결과.

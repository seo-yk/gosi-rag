# 평가 스크립트

모든 스크립트는 저장소 루트에서 실행한다(예: `python evaluation/scripts/evaluate_retrieval.py`). 실행 결과는 `output/`(git 제외)에 생기고, 공개할 최종 결과만 `results/`로 옮긴다. 실행 순서와 명령은 `docs/experiment_log.md` 13장에 있다.

## 1. 데이터와 평가셋 만들기

| 스크립트 | 하는 일 | 입력 → 출력 |
|---|---|---|
| `build_faq_v2.py` | 교정본 FAQ에서 검색 대상 데이터 생성(병합·제외) | `data/faq_corrected.csv`, `data/faq_merge_map.csv` → `data/faq_v2.csv` |
| `build_evalset_v1_2.py` | 검수표, 라벨 초안, 결정표, 승인된 질문 수정안을 합쳐 평가셋 v1.2 생성 | `evaluation/evalset/v1.2/` 원천 자료 → `v1.2/evalset.jsonl`, `v1.2/out_of_scope.jsonl`, `evaluation/evalset/changes.csv` |
| `build_evalset_v1_3.py` | v1.2를 v1.3 형식으로 변환(ID 정수화, 열 간소화. 내용은 그대로) | `v1.2/*.jsonl` → `evalset_v1.3.jsonl`, `evalset_out_of_scope_v1.3.jsonl` |
| `validate_labels.py` | v1.3 평가셋 라벨 검증(없는 FAQ, 제외된 FAQ, 형식) | FAQ CSV, 병합표, 평가셋 JSONL |
| `xlsx_reader.py` | (공용) openpyxl 없이 xlsx 값을 읽는 함수 | |
| `evalset.py` | (공용) 평가셋 로더와 그룹 채점 함수(Hit@K, Group Recall, MRR) | |

## 2. 검색 실험

| 스크립트 | 하는 일 | 출력 |
|---|---|---|
| `evaluate_retrieval.py` | 임베딩 모델 하나에 대해 청킹 × 임베딩 입력 조합을 평가 | `output/retrieval_{summary,details,out_of_scope}_<모델>.csv` |
| `build_retrieval_comparison.py` | 모델별 요약을 합쳐 비교표 생성 | `output/retrieval_comparison.{csv,md}` |

인덱스 생성은 `src/indexing.py`가 한다.

## 3. 생성과 자동 채점

| 스크립트 | 하는 일 | 출력 |
|---|---|---|
| `generate_answers.py` | 평가셋 질문에 답변 생성(`--oracle`이면 정답 FAQ를 근거로 사용) | `output/generated_answers_*.csv` |
| `judge_answers.py` | 생성 답변 자동 채점(루브릭 v2.1, Gemini 또는 Ollama) | `--output`으로 지정 |
| `evaluate_generation.py` | 1차 실험의 채점(루브릭 v1). 생성 답변 읽기 등 다른 스크립트가 쓰는 공용 함수도 들어 있다 | |

## 4. 사람 채점과 채점기 검증

단계와 결과는 `docs/3_judge_validation.md`, 채점 결과 파일은 `evaluation/human_review/`에 있다.

| 스크립트 | 단계 | 하는 일 |
|---|---|---|
| `build_review_sheet.py` | 1 | A·B 40문항 표본 추출, 블라인드 채점지(CSV)와 키 생성 |
| `build_rereview_sheet.py` | 2 | 불일치 4 + 일치 4 재채점지 생성 |
| `build_c_oos_review_sheets.py` | 3, 5 | C 15문항, 범위 밖 20문항 채점지 생성 |
| `build_c_adjudication_sheet.py` | 4 | C 불일치 7문항 재검토 시트(채점기 판단 근거 포함, xlsx) |
| `export_review_xlsx.py` | 1~3, 5 | 채점지 CSV를 읽기 쉬운 xlsx로 변환(입력 칸, 선택 목록, 안내 시트) |
| `compare_judges.py` | 1, 2 | 채점기 후보와 사람 채점의 일치도(판정 일치, kappa, 항목별) 비교표 |

xlsx를 만드는 스크립트는 openpyxl이 필요하다(`requirements.txt`에 포함).

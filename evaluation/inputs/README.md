# 평가셋 v1.3

교정본 FAQ(`data/faq_v2.csv`, 286건)를 검색 대상으로 하는 단일 평가셋이다. 1차 실험의 검색용(50문항)·생성용(60문항) 평가셋을 대체한다. 1차 실험 파일은 `archive/experiment-v1/`에 있다.

v1.3은 v1.2와 라벨·문구가 같고 형식만 다르다(아래 "v1.2 → v1.3"). 재실험에는 v1.3을 쓴다.

## 파일

| 파일 | 내용 |
|---|---|
| `evalset_v1.3.jsonl` | 본 평가셋 150줄. `status=keep` 148문항을 평가하고, `exclude` 2문항은 기록용으로 남긴다 |
| `evalset_out_of_scope_v1.3.jsonl` | 범위 밖 질문 10문항. 별도 묶음이며 Hit·MRR 계산에 넣지 않는다 |
| `CHANGES.csv` | 검수표 v1.1 대비 v1.2에서 바뀐 값(v1.3의 ID·필드 이름으로 표기). 열: `id`, `field`, `before`, `after`, `reason`, `decided_by` |
| `p_column_approved_v1.2.json` | 검수표 P열 수정안 16건의 승인본(수정 후 문장과 사유) |
| `evalset_v1.2.jsonl`, `evalset_out_of_scope_v1.2.jsonl` | 이전 형식. 태그 `evalset-v1.2`의 동결본으로 남겨 둔다 |

재생성: `python evaluation/scripts/build_faq_v2.py` → `build_evalset_v1_2.py` → `build_evalset_v1_3.py` (모두 `evaluation/scripts/`). 입력은 `handoff/`의 원천 파일이다.

검증: `python evaluation/scripts/validate_labels.py data/faq_v2.csv data/faq_merge_map.csv evaluation/inputs/evalset_v1.3.jsonl evaluation/inputs/evalset_out_of_scope_v1.3.jsonl` → 오류 0건.

## 칼럼

**본 평가셋**

| 칼럼 | 뜻 |
|---|---|
| `id` | 질문 번호(정수). FAQ 연번과 같은 형식. 1~153이며 51, 59, 65는 v1.1 이전부터 없는 번호다 |
| `status` | `keep`(평가) 또는 `exclude`(기록만) |
| `question` | 평가 질문(사용자 관점에서 다시 쓴 질문) |
| `intent` | 질문 의도 |
| `type` | `원문유사`, `일상표현`, `조건형`, `복수근거` |
| `required_faqs` | 정답 FAQ 연번. 바깥 목록은 AND(모두 필요), 안쪽 목록은 OR(하나면 충분). 예: `[[78], [272, 251]]` = 78, 그리고 272 또는 251 |
| `supporting_faqs` | 보조 FAQ. 어떤 지표에도 넣지 않는다 |
| `reference_answer` | 기준 답변(생성 평가용) |
| `written_by` | 질문·기준 답변 작성자. `본인` 또는 `Claude`(초안) |
| `reviewed` | 검수자가 결정을 직접 입력한 문항이면 `true` |

**범위 밖**

| 칼럼 | 뜻 |
|---|---|
| `id` | 154~163 (본 평가셋 번호와 겹치지 않게 이어 붙임) |
| `status`, `question`, `written_by`, `reviewed` | 본 평가셋과 같음 |
| `difficulty` | `easy`, `medium`, `hard` |
| `similar_faqs` | 주제는 겹치지만 답은 없는 FAQ 연번 |
| `absence_note` | FAQ에 답이 없음을 어떻게 확인했는지 |

FAQ 데이터의 `제목`은 질문 형태이고 `본문`은 답변이다. 평가셋의 `question`은 그와 별개로 사용자 관점에서 다시 쓴 검색어이고, `reference_answer`는 채점 기준이다. FAQ 칼럼 이름(`제목`, `본문`)은 원본 공공데이터를 따르며, 임베딩 입력과 생성 프롬프트에 그대로 쓰이므로 바꾸지 않는다.

## 채점 규칙

| 지표 | 정의 | 대상 |
|---|---|---|
| Hit@K | 모든 그룹에서 FAQ가 1개 이상 Top-K 안에 있으면 1 | keep 148 |
| Group Recall@K | 충족된 그룹 수 ÷ 전체 그룹 수 | keep 148 |
| MRR | 그룹 내 FAQ 중 가장 높은 순위의 역수 | 필수 그룹이 1개인 문항(111) |
| 범위 밖 차단 | FAQ에 근거가 없음을 밝히면 통과. 안내처 언급은 허용. 본문에 없는 수치나 사실을 답하면 실패. 건수로 보고 | 범위 밖 10 |

148문항에서 1문항은 약 0.7%p다.

복수근거 문항은 필수 그룹마다 서로 다른 FAQ가 필요하다. 그래서 Top-1에 FAQ가 하나뿐이면 적중할 수 없고, Hit@1은 항상 0이다. 따라서 전체 Hit@1의 최댓값은 111/148(75.0%)이다. Hit@1은 유형별 수치와 함께 읽는다.

## 실행

```bash
# 1) 교정본 FAQ(data/faq_v2.csv)로 인덱스 생성 → index/faq_v2
python src/indexing.py
# 2) 검색 평가: 요약(유형별), 문항별 상세, 범위 밖 Top-1 유사도를 output/에 저장
python evaluation/scripts/evaluate_retrieval.py
# 3) 생성과 생성 평가 (앱 설정 INDEX_DIR 기본값도 index/faq_v2)
python evaluation/scripts/generate_generation.py
```

기본값은 모두 교정본 기준이다(`--csv data/faq_v2.csv`, 인덱스 `index/faq_v2`). 원본으로 1차 실험을 재현하려면 `python src/indexing.py --csv data/faq.csv --output index/faq_v1`로 인덱스를 따로 만들고, 평가할 때 `--index-dir index/faq_v1`을 지정한다(앱은 `INDEX_DIR=index/faq_v1`).

`evaluate_retrieval.py`는 문항당 5개(`--depth`)를 한 번 검색해 @1·@3·@5를 함께 계산한다. 결과 파일에는 평가셋 이름(`eval_set`), 문항 수(`questions`), 인덱스 폴더, 임베딩 모델을 함께 기록한다.

## 문항 수

| 구분 | 문항 수 |
|---|---|
| 본 평가셋 (keep) | 148 |
| 제외 (exclude) | 2: 12(42와 같은 의도), 130(47과 같은 의도. 정답 FAQ 94가 280으로 병합됨) |
| 범위 밖 | 10 (쉬움 2, 중간 4, 어려움 4) |

## 유형과 작성자 분포 (keep 148)

| 유형 | 본인 | Claude | 합계 |
|---|---|---|---|
| 일상표현 | 27 | 17 | 44 |
| 복수근거 | 10 | 27 | 37 |
| 원문유사 | 11 | 23 | 34 |
| 조건형 | 9 | 24 | 33 |
| 합계 | 57 | 91 | 148 |

- `복수근거`는 필수 그룹이 2개 이상인 문항이다(2그룹 35, 3그룹 2). 나머지 111문항은 필수 그룹이 1개다.
- 대체 정답(한 그룹에 FAQ가 2개 이상)이 있는 문항은 16개다. 그 FAQ 본문만으로 해당 부분에 완전히 답할 수 있을 때만 대체 정답으로 인정했다.
- 연번은 `faq_v2.csv` 기준이다. 병합으로 제거된 94(→280), 152(→250)와 본문이 없어 제외한 99는 라벨에 쓰지 않는다.

## 작성과 검수

- 질문·기준 답변: `본인`이 쓴 57문항(v1.0)과 Claude가 초안을 쓰고 검수자가 확인한 91문항(keep 기준).
- 라벨: Claude가 초안을 썼고 검수자가 확정했다.
- 검수자: 1인(본인). `reviewed=true`는 검수자가 결정을 직접 입력한 54문항이다. 결정표 `1_필수라벨`, `2_기준답변`, `3_유형재분류`, `5_기타확인`, 검수표 P열 수정안이 해당한다.
- 범위 밖 10문항은 검수자가 모두 수락했다.

## v1.1 → v1.2 변경 요약 (라벨·문구)

`CHANGES.csv`의 필드별 건수다.

| 필드 | 건수 | 주요 결정 근거 |
|---|---|---|
| `type` | 47 | 복합질문→복수근거 37(확정 규칙), 재분류 10(결정표 3) |
| `supporting_faqs` | 42 | 보조만 변경 27(라벨 초안 그대로 적용), 필수 재조정 동반 12, 검수자 추가 2(122, 150), 제외 문항 12 1 |
| `reference_answer` | 30 | 결정표 2(20), 검수표 P열(10) |
| `required_faqs` | 24 | 결정표 1 수락 23, 제외 문항 12 1 |
| `question` | 7 | 검수표 P열(FAQ 문구를 그대로 베낀 질문 수정) |
| `status` | 2 | 12, 130 제외 |

- 44: 결정표 1에서 대체 정답 제안이 기각되어 v1.1 라벨(필수 277, 보조 276)을 유지했다.
- 122: 보조 FAQ를 262에서 261(면접 블라인드)로 바로잡았다(결정표 5).
- 결정표 `5_기타확인` 시트의 값은 구글 시트 `검토결정표_v1.2`에서 가져왔다(2026-11-12 확인). `handoff/검토결정표_v1.2.xlsx`에는 이 시트가 비어 있다.
- 원천 파일은 `handoff/`에 있다: `질문셋_v1.1_검수표.xlsx`(질문·기준 답변), `eval_labels_v1.2_draft.jsonl`(라벨 초안), `검토결정표_v1.2.xlsx`(결정). 이 파일들과 `p_column_approved_v1.2.json`은 `q001` 형식 ID를 쓴다.

## v1.2 → v1.3 변경 (형식만)

| v1.2 | v1.3 |
|---|---|
| `question_id` `"q001"`, 범위 밖 `"o01"`~`"o10"` | `id` `1`, 범위 밖 `154`~`163` |
| `question_type` | `type` |
| `required_groups` `[{"faq_ids": [4, 252]}]` | `required_faqs` `[[4, 252]]` |
| `supporting_faq_ids` | `supporting_faqs` |
| `author` `"직접 작성(v1.0)"`/`"초안(Claude)"` | `written_by` `"본인"`/`"Claude"` |
| `reviewer` `"본인"`/`""` | `reviewed` `true`/`false` |
| 범위 밖 `near_miss_faq_ids`, `absence_check` | `similar_faqs`, `absence_note` |

삭제한 칼럼: 값이 모두 같거나 다른 칼럼으로 계산되거나 채점에 쓰이지 않는다.

- `evidence_type`: `required_faqs` 그룹 수로 계산된다
- `multi_intent`: 채점에 쓰이지 않는다
- `expected_behavior`: 본 평가셋은 모두 `answer`, 범위 밖은 모두 `abstain`이고, 이 구분은 파일이 나눈다
- `label_author`: 모두 `Claude 초안`이며 위 "작성과 검수"에 적었다
- `eval_set_version`: 파일 이름과 태그가 버전을 나타낸다
- 범위 밖의 `question_type`, `evidence_type`, `required_groups`, `supporting_faq_ids`: 모두 같은 값이거나 빈 값이다
- 범위 밖의 `pass_rule`: 10문항 모두 같은 문장이며 위 "채점 규칙"으로 옮겼다

## 알려진 한계

- 사전등록 경로가 FAQ마다 다르다(288 국가공무원채용시스템, 289 통합채용포털, 247 사이버국가고시센터). 원본의 상충이므로 고치지 않았다.
- 81, 117은 질문을 특정 지역에서 일반 표현으로 바꿨다. 근거 FAQ(137, 141)는 한 지역만 예로 들기 때문에, 기준 답변은 일반 원칙과 그 예시로 썼다.

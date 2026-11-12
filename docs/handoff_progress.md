# 진행 상황 인수인계 (2026-11-12 기준)

다른 컴퓨터나 새 Claude 세션에서 이어서 작업하기 위한 문서다. 이 문서와 아래 링크한 문서만 읽고 이어 갈 수 있게 썼다. 문서에 없는 결정은 추측하지 말고 사용자에게 묻는다.

- 브랜치: `evalset-v1.2`(원격에 푸시됨. `main`에는 아직 병합하지 않음. 이름이 내용보다 좁아 PR 때 정리 예정)
- 태그: `experiment-v1`(1차 실험 시점), `evalset-v1.2`, `evalset-v1.3`(평가셋 동결). 태그는 폴더 이름 정리 전 경로를 가리킨다
- 처음 받은 인수인계서: `docs/handoff_v1.2.md`

## 1. 새 컴퓨터 준비

```bash
git clone https://github.com/seo-yk/gosi-rag.git
cd gosi-rag && git switch evalset-v1.2
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env          # OPENAI_API_KEY는 직접 입력(채팅·메신저로 옮기지 않는다)
python src/indexing.py        # .env 기본값(bge-m3)으로 index/faq_v2/bge-m3 생성. 처음엔 모델 약 2.3GB 다운로드
python -m pytest -q           # 67개 통과 확인
```

`index/`와 `output/`은 git에서 빠져 있어 새 컴퓨터에는 없다. 인덱스는 위 명령으로 다시 만든다. 검색 실험 결과는 `results/retrieval_v1.3/`에 공개본이 있다.

## 2. 끝난 일

| 단계 | 결과 | 기록 |
|---|---|---|
| 작업 1: 검색 대상 데이터 | `data/faq_v2.csv` 286건(원본 289 → 병합 2, 제외 1, 반복 본문 정리 1) | `data/README.md` |
| 원본 문제 확인 | 원본 연번 100~200 본문이 한 칸 밀림 → 교정본에서 바로잡음 | `data/README.md` |
| 작업 2: 평가셋 | v1.2(라벨·문구 확정) → v1.3(ID 정수화, 칼럼 간소화). keep 148, 범위 밖 10 | `evaluation/evalset/README.md` |
| 1차 실험 아카이브 | 1차 질문셋·결과를 `archive/experiment-v1/`로 이동 | `archive/experiment-v1/README.md` |
| 작업 3: 평가 스크립트 | 그룹 채점(Hit@K, Group Recall@K, 단일 MRR), 유형·작성자별 요약, 범위 밖 기록, 문장 청킹, FAQ 중복 제거, manifest 대조 | `docs/retrieval_pipeline.md` 1~8장 |
| 검색 실험(작업 4의 1단계) | 임베딩 모델 4개 × 3조합 = 12조합 실행 | `docs/retrieval_pipeline.md` 9장, `results/retrieval_v1.3/` |
| 생성 단계 검색 구성 결정 | bge-m3 + `row` + `title_body`, `TOP_K=3`(.env.example 기본값) | `docs/retrieval_pipeline.md` 9-3 |
| 폴더·파일 이름 정리 | `handoff/` 해체, `evaluation/evalset/`, `data/faq_raw.csv` 등 | 커밋 `5035886` |

검색 결과 요약(Hit@1, 단일 그룹 111문항 기준): bge-m3 `sentence × title_body` 98.2%가 최고다. 5%p를 넘는 모델 차이는 bge-m3와 e5-small 사이 하나뿐이고, bge-m3·KURE-v1·text-embedding-3-large 사이에는 차이가 확인되지 않았다. 작성자 편향(Claude 초안 문항이 더 쉬움)의 원인은 복수근거 질문을 만든 방식의 차이다(9-1).

## 3. 확정된 결정 (바꾸지 않는다)

- 평가셋 형식은 v1.3이다. ID는 정수(1~153, 범위 밖 154~163)이고 칼럼은 `evaluation/evalset/README.md`를 따른다. 라벨을 바꾸려면 버전을 올린다.
- `faq_v2.csv`의 이름은 유지한다(결과 파일에 경로가 기록돼 있음).
- 판단 기준: 148문항에서 5%p 이내면 "차이가 확인되지 않음". Hit@1은 전체와 단일 그룹(111)을 둘 다 보고한다.
- 임베딩 접두어는 모델 공식 사용법을 따른다(e5만 `query:`/`passage:`). 접두어 없는 e5 대조 실험은 하지 않기로 했다.
- `output/`은 임시 결과(git 제외), 공개할 최종 결과는 `results/`에 둔다.

## 4. 남은 일

1. **생성 단계 실행 계획(다음 할 일):** 아래를 정리해 사용자 승인을 받은 뒤 실행한다. 유료 API라서 승인 전에는 실행하지 않는다.
   - 생성 모델: `gpt-5.4-mini`(1차와 같음)
   - 생성 Top-K: 3만 할지, 3과 5를 비교할지
   - 호출 수: 본 평가셋 148 + 범위 밖 10
   - 자동 평가: Ollama `gemma3:4b`, 로컬
   - 범위 밖 판정: 사람이 `pass_rule` 기준으로 판정(`evaluation/evalset/README.md` 채점 규칙)
2. **생성 평가 관련 미결정:** 사전등록 경로가 FAQ마다 다르다(288·289·247). 생성 평가에서 세 경로를 모두 정답으로 볼지 사용자에게 묻는다.
3. **결과 공개:** 생성 결과도 최종본은 `results/`에 둔다(예: `results/generation_v1.3/`).
4. **루트 README 최종 수정:** 1차 수치를 재실험 결과로 한 번에 교체한다. 사용자가 "나중에 최종 수정"하기로 했다.
5. **브랜치 정리와 PR:** `evalset-v1.2` 브랜치 이름 정리 후 `main`으로 PR.
6. **개선 후보(미정):** 복수근거 질문을 하위 질문으로 나눠 검색하기, 리랭커(bge-reranker-v2-m3), 문장 청킹을 생성에 쓸 때 원래 FAQ 전체를 근거로 넘기기, 재현용 Dockerfile.

## 5. 작업 방식 (사용자 선호)

- 응답은 한국어로 한다.
- 파일이나 이름을 바꾸기 전에 무엇을 바꿀지 먼저 제안하고 승인을 받는다.
- 검토를 요청할 때는 파일 이름, 시트나 열, 판단 기준, 입력할 값을 함께 적는다.
- 커밋 메시지는 `feat:`/`fix:`/`docs:`/`refactor:`/`chore:` 관례를 따른다. 커밋·푸시는 사용자가 맡긴 범위에서 한다.
- API 키 같은 비밀값은 Claude가 입력하거나 출력하지 않는다. `.env`를 고칠 때도 키가 있는 줄은 보지 않는다.
- 포트폴리오용이므로 출처, 결정자, 변경 이력을 남긴다.

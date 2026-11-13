# 검색 실험 결과 (평가셋 v1.3)

2026-11-12 실행. 결과 해석은 `docs/1_retrieval.md` 9장에 있다.

- 평가셋: `evaluation/evalset/evalset_v1.3.jsonl`(148문항), 범위 밖 `evalset_out_of_scope_v1.3.jsonl`(10문항)
- 검색 대상: `data/faq_v2.csv`(286건, sha256 앞 12자 `9d96b362ff63`)
- 조합: 임베딩 모델 4개 × (`row × title`, `row × title_body`, `sentence × title_body`) = 12조합, 검색 깊이 5

| 파일 | 내용 |
|---|---|
| `comparison.md`, `comparison.csv` | 12조합 비교표 |
| `summary_<모델>.csv` | 조합 × 묶음(전체, 단일 그룹, 유형, 작성자)별 Hit@1·3·5, Group Recall@1·3·5, MRR(단일), 실패 문항 |
| `details_<모델>.csv` | 문항별 검색된 FAQ 순위(1~5위)와 적중 여부 |
| `out_of_scope_<모델>.csv` | 범위 밖 문항의 1위 FAQ·유사도와 상위 5개 |

`<모델>`은 `multilingual-e5-small`, `bge-m3`, `kure-v1`, `text-embedding-3-large`다. CSV는 UTF-8(BOM 포함)이다.

스크립트가 `output/`에 만드는 원래 파일 이름은 앞에 `retrieval_`이 붙는다(예: `output/retrieval_summary_bge-m3.csv`).

# 검색 실험 결과 (평가셋 v1.3)

2026-11-12 실행. `output/`에 생긴 결과 중 최종본을 공개용으로 복사한 것이다. 해석은 `docs/retrieval_pipeline.md` 9장에 있다.

- 평가셋: `evaluation/evalset/evalset_v1.3.jsonl`(148문항), 범위 밖 `evalset_out_of_scope_v1.3.jsonl`(10문항)
- 검색 대상: `data/faq_v2.csv`(286건, sha256 앞 12자 `9d96b362ff63`)
- 조합: 임베딩 모델 4개 × (`row × title`, `row × title_body`, `sentence × title_body`) = 12조합, 검색 깊이 5

| 파일 | 내용 |
|---|---|
| `retrieval_comparison.md`, `retrieval_comparison.csv` | 12조합 비교표 |
| `retrieval_summary_<모델>.csv` | 조합 × 묶음(전체, 단일 그룹, 유형, 작성자)별 Hit@1·3·5, Group Recall@1·3·5, MRR(단일), 실패 문항 |
| `retrieval_details_<모델>.csv` | 문항별 검색된 FAQ 순위(1~5위)와 적중 여부 |
| `retrieval_out_of_scope_<모델>.csv` | 범위 밖 문항의 Top-1 FAQ·유사도와 Top-5 |

`<모델>`은 `multilingual-e5-small`, `bge-m3`, `kure-v1`, `text-embedding-3-large`다. CSV는 UTF-8(BOM 포함)이다.

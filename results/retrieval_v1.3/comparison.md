평가셋 `evalset_v1.3` (148문항), FAQ `data/faq_v2.csv` (sha256 `9d96b362ff63`), 검색 깊이 5

| 모델 | 청킹 | 임베딩 입력 | Hit@1(전체) | Hit@1(단일) | Hit@3 | Hit@5 | Group Recall@3 | MRR(단일) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| intfloat/multilingual-e5-small | row | title | 67.6% | 90.1% | 89.9% | 94.6% | 94.0% | 0.943 |
| intfloat/multilingual-e5-small | row | title_body | 68.9% | 91.9% | 93.9% | 97.3% | 96.5% | 0.952 |
| intfloat/multilingual-e5-small | sentence | title_body | 68.2% | 91.0% | 94.6% | 97.3% | 96.9% | 0.951 |
| BAAI/bge-m3 | row | title | 68.9% | 91.9% | 90.5% | 94.6% | 93.7% | 0.951 |
| BAAI/bge-m3 | row | title_body | 73.0% | 97.3% | 94.6% | 98.7% | 97.4% | 0.985 |
| BAAI/bge-m3 | sentence | title_body | 73.7% | 98.2% | 94.6% | 98.7% | 97.1% | 0.991 |
| nlpai-lab/KURE-v1 | row | title | 71.0% | 94.6% | 93.2% | 97.3% | 95.7% | 0.971 |
| nlpai-lab/KURE-v1 | row | title_body | 71.6% | 95.5% | 94.6% | 99.3% | 97.4% | 0.975 |
| nlpai-lab/KURE-v1 | sentence | title_body | 73.0% | 97.3% | 93.2% | 98.7% | 96.4% | 0.984 |
| text-embedding-3-large | row | title | 68.2% | 91.0% | 89.2% | 96.6% | 93.5% | 0.944 |
| text-embedding-3-large | row | title_body | 69.6% | 92.8% | 91.9% | 98.7% | 95.7% | 0.959 |
| text-embedding-3-large | sentence | title_body | 71.0% | 94.6% | 92.6% | 97.3% | 95.7% | 0.970 |

Hit@1(전체)의 최댓값은 75.0%다(복수근거 37문항은 Hit@1이 구조적으로 0). Hit@1(단일)은 필수 그룹이 1개인 111문항 기준이다.

**Hit@3 유형·작성자별**

| 모델 | 청킹 | 임베딩 입력 | 유형: 원문유사 | 유형: 일상표현 | 유형: 조건형 | 유형: 복수근거 | 작성: 본인 | 작성: Claude |
|---|---|---|---:|---:|---:|---:|---:|---:|
| intfloat/multilingual-e5-small | row | title | 97.1% | 100.0% | 100.0% | 62.2% | 86.0% | 92.3% |
| intfloat/multilingual-e5-small | row | title_body | 100.0% | 97.7% | 100.0% | 78.4% | 89.5% | 96.7% |
| intfloat/multilingual-e5-small | sentence | title_body | 97.1% | 97.7% | 100.0% | 83.8% | 87.7% | 98.9% |
| BAAI/bge-m3 | row | title | 97.1% | 97.7% | 97.0% | 70.3% | 84.2% | 94.5% |
| BAAI/bge-m3 | row | title_body | 100.0% | 100.0% | 100.0% | 78.4% | 91.2% | 96.7% |
| BAAI/bge-m3 | sentence | title_body | 100.0% | 100.0% | 100.0% | 78.4% | 89.5% | 97.8% |
| nlpai-lab/KURE-v1 | row | title | 97.1% | 100.0% | 100.0% | 75.7% | 87.7% | 96.7% |
| nlpai-lab/KURE-v1 | row | title_body | 100.0% | 100.0% | 100.0% | 78.4% | 91.2% | 96.7% |
| nlpai-lab/KURE-v1 | sentence | title_body | 100.0% | 97.7% | 100.0% | 75.7% | 89.5% | 95.6% |
| text-embedding-3-large | row | title | 97.1% | 97.7% | 97.0% | 64.9% | 84.2% | 92.3% |
| text-embedding-3-large | row | title_body | 97.1% | 100.0% | 100.0% | 70.3% | 89.5% | 93.4% |
| text-embedding-3-large | sentence | title_body | 97.1% | 100.0% | 100.0% | 73.0% | 87.7% | 95.6% |

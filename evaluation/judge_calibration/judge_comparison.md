# 채점 모델 후보 비교 (사람 채점 40문항 기준)

사람 판정: pass 35, fail 5. pass가 대부분이라 판정 일치율보다 kappa와 fail 검출을 함께 본다.

| 채점 모델 | 판정 일치 | kappa | 사람 fail 검출 | 사람 pass 유지 | 채점기 pass율 | 근거성 | 정확성 | 그룹 충족 | 회피 | 조건별 판정 일치 | error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| gemma3-4b-ctx8k (rubric v2.1) | 40.0% | 0.10 | 5/5 | 11/35 | 27.5% | 52.5% | 82.5% | 50.9% | 97.5% | A 50.0%, B 30.0% | 0 |
| qwen2.5-7b-ctx8k (rubric v2.1) | 30.0% | 0.06 | 5/5 | 7/35 | 17.5% | 67.5% | 82.5% | 41.5% | 77.5% | A 45.0%, B 15.0% | 0 |
| gemini-2.5-flash (rubric v2.1) | 91.7% | 0.70 | 3/4 | 19/20 | 83.3% | 83.3% | 95.8% | 90.3% | 95.8% | A 90.0%, B 100.0% | 0 |
| gemini-3.5-flash (rubric v2.1) | 90.0% | 0.45 | 2/5 | 34/35 | 92.5% | 92.5% | 97.5% | 90.6% | 97.5% | A 85.0%, B 95.0% | 0 |
| gemini-3.7-flash (rubric v2.1) | 90.0% | 0.45 | 2/5 | 34/35 | 92.5% | 90.0% | 95.0% | 90.6% | 97.5% | A 85.0%, B 95.0% | 0 |
| gemini-3.8-flash (rubric v2.1) | 90.0% | 0.45 | 2/5 | 34/35 | 92.5% | 90.0% | 97.5% | 90.6% | 97.5% | A 85.0%, B 95.0% | 0 |

- gemma3-4b-ctx8k (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 4, pass, fail), (A, 14, pass, fail), (A, 19, pass, fail), (A, 45, pass, fail), (A, 46, pass, fail), (A, 63, pass, fail), (A, 67, pass, fail), (A, 76, pass, fail), (A, 143, pass, fail), (A, 145, pass, fail), (B, 8, pass, fail), (B, 39, pass, fail), (B, 44, pass, fail), (B, 55, pass, fail), (B, 79, pass, fail), (B, 80, pass, fail), (B, 82, pass, fail), (B, 86, pass, fail), (B, 99, pass, fail), (B, 104, pass, fail), (B, 128, pass, fail), (B, 137, pass, fail), (B, 139, pass, fail), (B, 141, pass, fail)
- qwen2.5-7b-ctx8k (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 4, pass, fail), (A, 14, pass, fail), (A, 18, pass, fail), (A, 19, pass, fail), (A, 46, pass, fail), (A, 49, pass, fail), (A, 63, pass, fail), (A, 67, pass, fail), (A, 76, pass, fail), (A, 111, pass, fail), (A, 143, pass, fail), (B, 8, pass, fail), (B, 34, pass, fail), (B, 39, pass, fail), (B, 44, pass, fail), (B, 50, pass, fail), (B, 55, pass, fail), (B, 79, pass, fail), (B, 80, pass, fail), (B, 82, pass, fail), (B, 86, pass, fail), (B, 95, pass, fail), (B, 104, pass, fail), (B, 128, pass, fail), (B, 137, pass, fail), (B, 139, pass, fail), (B, 141, pass, fail), (B, 146, pass, fail)
- gemini-2.5-flash (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 7, fail, pass), (A, 19, pass, fail)
- gemini-3.5-flash (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 7, fail, pass), (A, 19, pass, fail), (A, 38, fail, pass), (B, 66, fail, pass)
- gemini-3.7-flash (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 7, fail, pass), (A, 19, pass, fail), (A, 38, fail, pass), (B, 66, fail, pass)
- gemini-3.8-flash (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 7, fail, pass), (A, 19, pass, fail), (A, 38, fail, pass), (B, 66, fail, pass)

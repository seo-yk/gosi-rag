# 채점 모델 후보 비교 (사람 채점 40문항 기준)

사람 판정: pass 37, fail 3. pass가 대부분이라 판정 일치율보다 kappa와 fail 검출을 함께 본다.

| 채점 모델 | 판정 일치 | kappa | 사람 fail 검출 | 사람 pass 유지 | 채점기 pass율 | 근거성 | 정확성 | 그룹 충족 | 회피 | 조건별 판정 일치 | error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| gemma3-4b-ctx8k (rubric v2.1) | 35.0% | 0.06 | 3/3 | 11/37 | 27.5% | 50.0% | 80.0% | 50.9% | 97.5% | A 45.0%, B 25.0% | 0 |
| qwen2.5-7b-ctx8k (rubric v2.1) | 25.0% | 0.03 | 3/3 | 7/37 | 17.5% | 67.5% | 85.0% | 41.5% | 77.5% | A 40.0%, B 10.0% | 0 |
| gemini-2.5-flash (rubric v2.1) | 95.8% | 0.83 | 3/3 | 20/21 | 83.3% | 87.5% | 91.7% | 87.1% | 95.8% | A 95.0%, B 100.0% | 0 |
| gemini-3.5-flash (rubric v2.1) | 95.0% | 0.64 | 2/3 | 36/37 | 92.5% | 92.5% | 95.0% | 94.3% | 97.5% | A 90.0%, B 100.0% | 0 |
| gemini-3.7-flash (rubric v2.1) | 95.0% | 0.64 | 2/3 | 36/37 | 92.5% | 92.5% | 92.5% | 94.3% | 97.5% | A 90.0%, B 100.0% | 0 |
| gemini-3.8-flash (rubric v2.1) | 95.0% | 0.64 | 2/3 | 36/37 | 92.5% | 92.5% | 95.0% | 94.3% | 97.5% | A 90.0%, B 100.0% | 0 |

- gemma3-4b-ctx8k (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 4, pass, fail), (A, 7, pass, fail), (A, 14, pass, fail), (A, 19, pass, fail), (A, 45, pass, fail), (A, 46, pass, fail), (A, 63, pass, fail), (A, 67, pass, fail), (A, 76, pass, fail), (A, 143, pass, fail), (A, 145, pass, fail), (B, 8, pass, fail), (B, 39, pass, fail), (B, 44, pass, fail), (B, 55, pass, fail), (B, 66, pass, fail), (B, 79, pass, fail), (B, 80, pass, fail), (B, 82, pass, fail), (B, 86, pass, fail), (B, 99, pass, fail), (B, 104, pass, fail), (B, 128, pass, fail), (B, 137, pass, fail), (B, 139, pass, fail), (B, 141, pass, fail)
- qwen2.5-7b-ctx8k (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 4, pass, fail), (A, 7, pass, fail), (A, 14, pass, fail), (A, 18, pass, fail), (A, 19, pass, fail), (A, 46, pass, fail), (A, 49, pass, fail), (A, 63, pass, fail), (A, 67, pass, fail), (A, 76, pass, fail), (A, 111, pass, fail), (A, 143, pass, fail), (B, 8, pass, fail), (B, 34, pass, fail), (B, 39, pass, fail), (B, 44, pass, fail), (B, 50, pass, fail), (B, 55, pass, fail), (B, 66, pass, fail), (B, 79, pass, fail), (B, 80, pass, fail), (B, 82, pass, fail), (B, 86, pass, fail), (B, 95, pass, fail), (B, 104, pass, fail), (B, 128, pass, fail), (B, 137, pass, fail), (B, 139, pass, fail), (B, 141, pass, fail), (B, 146, pass, fail)
- gemini-2.5-flash (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 19, pass, fail)
- gemini-3.5-flash (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 19, pass, fail), (A, 38, fail, pass)
- gemini-3.7-flash (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 19, pass, fail), (A, 38, fail, pass)
- gemini-3.8-flash (rubric v2.1) 판정 불일치(조건, id, 사람, 채점기): (A, 19, pass, fail), (A, 38, fail, pass)

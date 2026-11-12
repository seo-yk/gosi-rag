"""교정본 FAQ에서 검색 대상 데이터 faq-v2 생성 (변경 내역은 data/README.md)

사용: python evaluation/scripts/build_faq_v2.py
"""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/faq_corrected.csv"
MERGE_MAP = ROOT / "data/faq_merge_map.csv"
OUTPUT = ROOT / "data/faq_v2.csv"

EXCLUDED = {"99"}          # 본문 없음. 결정표 5_기타확인 "검색 대상에서 제외"
DEDUPLICATE_BODY = {"15"}  # 같은 본문이 두 번 이어짐. 결정표 5_기타확인 "확정"


def main() -> None:
    with SOURCE.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    with MERGE_MAP.open(encoding="utf-8-sig", newline="") as file:
        removed = {row["removed_id"] for row in csv.DictReader(file)}

    result = []
    for row in rows:
        if row["연번"] in removed or row["연번"] in EXCLUDED:
            continue
        if row["연번"] in DEDUPLICATE_BODY:
            body = row["본문"]
            half = len(body) // 2
            if body[:half] != body[half:]:
                raise SystemExit(f"FAQ {row['연번']}: 본문 반복 형태가 예상과 다름")
            row = dict(row, 본문=body[:half])
        result.append(row)

    # data/faq_raw.csv와 같은 형식: UTF-8 BOM, CRLF
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["연번", "제목", "본문"])
        writer.writeheader()
        writer.writerows(result)
    print(f"입력 {len(rows)}건 → 출력 {len(result)}건: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

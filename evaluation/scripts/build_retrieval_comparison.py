"""모델별 검색 요약(retrieval_summary_*.csv)을 합쳐 조합 비교표를 만든다

출력
- output/retrieval_comparison.csv: 조합 × 주요 지표(비율 0~1)
- output/retrieval_comparison.md: README·포트폴리오용 표(%, 소수 1자리)

사용: python evaluation/scripts/build_retrieval_comparison.py [요약 CSV ...]
     (인자가 없으면 output/retrieval_summary_*.csv 전체)
"""

import argparse
import csv
from pathlib import Path

CHUNKING_ORDER = {"row": 0, "sentence": 1, "paragraph": 2, "file": 3}
EMBEDDING_ORDER = {"title": 0, "title_body": 1}
SUBSET_COLUMNS = ["유형: 원문유사", "유형: 일상표현", "유형: 조건형", "유형: 복수근거", "작성: 본인", "작성: Claude"]


def read_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows = []
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows.extend(csv.DictReader(file))
    if not rows:
        raise SystemExit("요약 파일이 없습니다.")
    for key in ("eval_set", "source_sha256"):
        values = {row[key] for row in rows}
        if len(values) != 1:
            raise SystemExit(f"{key}가 파일마다 다릅니다: {sorted(values)}")
    return rows


def combination_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row["embedding_model"], row["chunking_mode"], row["embedding_mode"]


def pct(value: str) -> str:
    return "" if value == "" else f"{float(value) * 100:.1f}%"


def build(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], str]:
    by_combo: dict[tuple[str, str, str], dict[str, dict[str, str]]] = {}
    model_order: list[str] = []
    for row in rows:
        by_combo.setdefault(combination_key(row), {})[row["subset"]] = row
        if row["embedding_model"] not in model_order:
            model_order.append(row["embedding_model"])
    combos = sorted(
        by_combo,
        key=lambda k: (model_order.index(k[0]), CHUNKING_ORDER.get(k[1], 9), EMBEDDING_ORDER.get(k[2], 9)),
    )

    table: list[dict[str, str]] = []
    for combo in combos:
        subsets = by_combo[combo]
        total, single = subsets["전체"], subsets["단일 그룹 전체"]
        record = {
            "embedding_model": combo[0],
            "chunking_mode": combo[1],
            "embedding_mode": combo[2],
            "questions": total["questions"],
            "hit_at_1": total["hit_at_1"],
            "hit_at_1_single": single["hit_at_1"],
            "hit_at_3": total["hit_at_3"],
            "hit_at_5": total["hit_at_5"],
            "group_recall_at_3": total["group_recall_at_3"],
            "mrr_single": total["mrr_single"],
        }
        for subset in SUBSET_COLUMNS:
            record[f"hit_at_3 [{subset}]"] = subsets.get(subset, {}).get("hit_at_3", "")
        table.append(record)

    first = rows[0]
    lines = [
        f"평가셋 `{first['eval_set']}` ({table[0]['questions']}문항), "
        f"FAQ `{first['source_csv']}` (sha256 `{first['source_sha256']}`), 검색 깊이 {first['depth']}",
        "",
        "| 모델 | 청킹 | 임베딩 입력 | Hit@1(전체) | Hit@1(단일) | Hit@3 | Hit@5 | Group Recall@3 | MRR(단일) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in table:
        mrr = "" if r["mrr_single"] == "" else f"{float(r['mrr_single']):.3f}"
        lines.append(
            f"| {r['embedding_model']} | {r['chunking_mode']} | {r['embedding_mode']} | {pct(r['hit_at_1'])} | "
            f"{pct(r['hit_at_1_single'])} | {pct(r['hit_at_3'])} | {pct(r['hit_at_5'])} | "
            f"{pct(r['group_recall_at_3'])} | {mrr} |"
        )
    lines += [
        "",
        "Hit@1(전체)의 최댓값은 75.0%다(복수근거 37문항은 Hit@1이 구조적으로 0). Hit@1(단일)은 필수 그룹이 1개인 111문항 기준이다.",
        "",
        "**Hit@3 유형·작성자별**",
        "",
        "| 모델 | 청킹 | 임베딩 입력 | " + " | ".join(SUBSET_COLUMNS) + " |",
        "|---|---|---|" + "---:|" * len(SUBSET_COLUMNS),
    ]
    for r in table:
        cells = " | ".join(pct(r[f"hit_at_3 [{s}]"]) for s in SUBSET_COLUMNS)
        lines.append(f"| {r['embedding_model']} | {r['chunking_mode']} | {r['embedding_mode']} | {cells} |")
    return table, "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="모델별 검색 요약을 합쳐 비교표를 만듭니다.")
    parser.add_argument("summaries", nargs="*", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()
    paths = args.summaries or sorted(args.output_dir.glob("retrieval_summary_*.csv"))
    table, markdown = build(read_rows(paths))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "retrieval_comparison.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(table[0].keys()))
        writer.writeheader()
        writer.writerows(table)
    (args.output_dir / "retrieval_comparison.md").write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()

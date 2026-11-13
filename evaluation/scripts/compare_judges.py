"""후보 채점 모델과 사람 채점(블라인드 40문항)의 일치도 비교

- 판정(verdict) 일치율, Cohen's kappa(우연 일치 보정), 사람이 fail로 본 문항을 채점기도 fail로 잡은 비율,
  사람이 pass로 본 문항을 채점기도 pass로 본 비율
- 항목별 일치율: groundedness, correctness, groups_covered(그룹 단위), unjustified_refusal
- 조건별(A/B) 판정 일치율, error 수
사람 판정이 대부분 pass라서(35/40) 단순 일치율만으로는 판단하지 않는다.

사용: python evaluation/scripts/compare_judges.py output/calibration_<모델>_A.csv output/calibration_<모델>_B.csv [...]
     (같은 모델의 A·B 파일을 묶어서 비교한다. judge_model 열로 모델을 구분)
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """두 평가자의 범주 판단 일치도(우연 일치 보정). 한쪽이 한 범주만 쓰면 정의되지 않을 수 있다"""
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    labels = {x for pair in pairs for x in pair}
    expected = sum((sum(a == k for a, _ in pairs) / n) * (sum(b == k for _, b in pairs) / n) for k in labels)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def compare(human: list[dict[str, str]], judged: list[dict[str, str]]) -> dict[str, object]:
    key = {(row["condition"], row["id"]): row for row in human}
    pairs, rows = [], []
    for row in judged:
        condition = row["condition"]
        h = key[(condition, row["id"])]
        rows.append((condition, h, row))
    errors = sum(1 for _, _, j in rows if j["verdict"] == "error")
    scored = [(c, h, j) for c, h, j in rows if j["verdict"] != "error"]

    def rate(items, field):
        values = [h[field] == j[field] for _, h, j in items]
        return sum(values) / len(values) if values else None

    group_pairs = [(a, b) for _, h, j in scored
                   for a, b in zip(h["groups_covered"].split("|"), j["groups_covered"].split("|"))]
    verdict_pairs = [(h["verdict"], j["verdict"]) for _, h, j in scored]
    human_fail = [(h, j) for _, h, j in scored if h["verdict"] == "fail"]
    human_pass = [(h, j) for _, h, j in scored if h["verdict"] == "pass"]
    by_condition = {}
    for condition in sorted({c for c, _, _ in scored}):
        items = [(h, j) for c, h, j in scored if c == condition]
        by_condition[condition] = sum(h["verdict"] == j["verdict"] for h, j in items) / len(items)
    return {
        "items": len(rows),
        "errors": errors,
        "verdict_agreement": rate(scored, "verdict"),
        "verdict_kappa": cohen_kappa(verdict_pairs),
        "fail_caught": (sum(j["verdict"] == "fail" for _, j in human_fail), len(human_fail)),
        "pass_kept": (sum(j["verdict"] == "pass" for _, j in human_pass), len(human_pass)),
        "judge_pass_rate": sum(j["verdict"] == "pass" for _, _, j in scored) / len(scored) if scored else None,
        "groundedness": rate(scored, "groundedness"),
        "correctness": rate(scored, "correctness"),
        "groups_covered": sum(a == b for a, b in group_pairs) / len(group_pairs) if group_pairs else None,
        "unjustified_refusal": rate(scored, "unjustified_refusal"),
        "by_condition": by_condition,
        "disagreements": [(c, h["id"], h["verdict"], j["verdict"]) for c, h, j in scored if h["verdict"] != j["verdict"]],
    }


def pct(value) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="후보 채점 모델과 사람 채점의 일치도를 비교합니다.")
    parser.add_argument("judged", nargs="+", type=Path, help="calibration_<모델>_<조건>.csv")
    parser.add_argument("--human", type=Path, default=Path("evaluation/judge_calibration/human_labels.csv"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/judge_calibration/judge_comparison.md"))
    args = parser.parse_args()

    human = read_csv(args.human)
    by_model: dict[str, list[dict[str, str]]] = defaultdict(list)
    for path in args.judged:
        condition = path.stem.rsplit("_", 1)[-1]  # calibration_<모델>_A → A
        for row in read_csv(path):
            by_model[row["judge_model"]].append(row | {"condition": condition})

    lines = [
        "# 채점 모델 후보 비교 (사람 채점 40문항 기준)",
        "",
        f"사람 판정: pass {sum(h['verdict'] == 'pass' for h in human)}, fail {sum(h['verdict'] == 'fail' for h in human)}. "
        "pass가 대부분이라 판정 일치율보다 kappa와 fail 검출을 함께 본다.",
        "",
        "| 채점 모델 | 판정 일치 | kappa | 사람 fail 검출 | 사람 pass 유지 | 채점기 pass율 | 근거성 | 정확성 | 그룹 충족 | 회피 | 조건별 판정 일치 | error |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    details = []
    for model, rows in by_model.items():
        r = compare(human, rows)
        kappa = "-" if r["verdict_kappa"] is None else f"{r['verdict_kappa']:.2f}"
        conditions = ", ".join(f"{c} {pct(v)}" for c, v in r["by_condition"].items())
        lines.append(
            f"| {model} | {pct(r['verdict_agreement'])} | {kappa} | {r['fail_caught'][0]}/{r['fail_caught'][1]} | "
            f"{r['pass_kept'][0]}/{r['pass_kept'][1]} | {pct(r['judge_pass_rate'])} | {pct(r['groundedness'])} | "
            f"{pct(r['correctness'])} | {pct(r['groups_covered'])} | {pct(r['unjustified_refusal'])} | {conditions} | {r['errors']} |"
        )
        details.append(f"- {model} 판정 불일치(조건, id, 사람, 채점기): " +
                       (", ".join(f"({c}, {i}, {h}, {j})" for c, i, h, j in r["disagreements"]) or "없음"))
    lines += ["", *details, ""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

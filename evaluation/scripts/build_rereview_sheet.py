"""불일치 재검토(adjudication)용 블라인드 시트

- 사람 채점과 채점 모델(gemini-3.8-flash)의 판정이 다른 문항 + 판정이 같았던 문항을 같은 수만큼 섞는다
  (어느 문항이 불일치였는지 모르게. 같은 채점자의 재채점 일관성도 함께 본다)
- 같았던 문항은 사람 fail 중 일치 문항을 먼저 넣고, 모자라면 pass 일치 문항에서 무작위로 채운다(시드 고정)
- 채점지에는 처음 채점 결과와 채점 모델 판정을 넣지 않는다. 키는 output/rereview_key.csv(재검토가 끝날 때까지 열지 않음)

사용: python evaluation/scripts/build_rereview_sheet.py → output/rereview_base.csv, output/rereview_key.csv
     python evaluation/scripts/export_review_xlsx.py output/rereview_base.csv output/rereview_sheet.xlsx
"""

import csv
import random
from pathlib import Path

SEED = 20261113
CAL = Path("evaluation/human_review")
JUDGE = "gemini-3.8-flash"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def main() -> None:
    human = {(r["condition"], r["id"]): r for r in read(CAL / "1_ab_review" / "labels.csv")}
    judged = {(c, r["id"]): r for c in "AB" for r in read(CAL / "1_ab_review" / "judges" / f"{JUDGE}_{c}.csv")}
    disagree = [k for k in human if judged[k]["verdict"] != human[k]["verdict"]]
    agree_fail = [k for k in human if k not in disagree and human[k]["verdict"] == "fail"]
    agree_pass = [k for k in human if k not in disagree and human[k]["verdict"] == "pass"]

    rng = random.Random(SEED)
    decoys = agree_fail[: len(disagree)]
    decoys += rng.sample(sorted(agree_pass), len(disagree) - len(decoys))
    chosen = [(k, "disagree") for k in disagree] + [(k, "agree") for k in decoys]
    rng.shuffle(chosen)

    base = {r[0]: r for r in csv.reader(open("output/review_sheet_base.csv", encoding="utf-8-sig"))}
    header = base["번호"]
    with open("output/rereview_base.csv", "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        for number, (key, _) in enumerate(chosen, 1):
            writer.writerow([number] + base[human[key]["review_no"]][1:])
    with open("output/rereview_key.csv", "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["번호", "review_no", "condition", "id", "kind"])
        for number, (key, kind) in enumerate(chosen, 1):
            writer.writerow([number, human[key]["review_no"], key[0], key[1], kind])
    print(f"재검토 {len(chosen)}문항(불일치 {len(disagree)} + 일치 {len(decoys)}) → output/rereview_base.csv")


if __name__ == "__main__":
    main()

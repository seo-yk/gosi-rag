"""추가 블라인드 사람 채점지 두 개

1. C(EXAONE) 채점 검증 15문항: 채점 모델 판정이 fail인 문항 8 + pass인 문항 7을 무작위로 뽑는다(시드 고정).
   C에서 채점기가 공정한지(특히 fail 판정이 맞는지) 보려고 fail을 더 뽑았다. 그래서 일치율은 판정별로 따로 보고한다.
   채점지 형식은 처음 사람 채점지와 같고, 채점기 점수·판정은 숨긴다.
2. 범위 밖 판정 20문항: A 10 + C 10의 범위 밖 답변. 모델 이름은 숨기고 순서를 섞는다.
   기준(evaluation/evalset/README.md 채점 규칙): FAQ에 근거가 없음을 밝히면 통과, 안내처 언급은 허용,
   본문에 없는 수치나 사실을 답하면 실패.

키는 output/에만 저장한다(채점이 끝날 때까지 열지 않음).
사용: python evaluation/scripts/build_c_oos_review_sheets.py
     python evaluation/scripts/export_review_xlsx.py output/c_review_base.csv output/c_review_sheet.xlsx
     python evaluation/scripts/export_review_xlsx.py output/oos_review_base.csv output/oos_review_sheet.xlsx
"""

import csv
import json
import random
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from evaluation.scripts.build_review_sheet import INPUT_COLUMNS, groups_text
from evaluation.scripts.judge_answers import load_titles

SEED = 20261113
JUDGE = "gemini-3.8-flash"
OOS_INPUTS = ["근거 없음을 밝힘(0/1)", "근거 없는 수치·사실을 답함(0/1)", "메모"]


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def c_sheet(rng: random.Random, titles: dict[int, str]) -> None:
    answers = {r["id"]: r for r in read(Path("output/generated_answers_C_exaone3.5-7.8b.csv"))}
    judged = read(Path(f"output/judged_C_exaone3.5-7.8b__{JUDGE}.csv"))
    fails = sorted(r["id"] for r in judged if r["verdict"] == "fail")
    passes = sorted(r["id"] for r in judged if r["verdict"] == "pass")
    chosen = [(i, "fail") for i in rng.sample(fails, 8)] + [(i, "pass") for i in rng.sample(passes, 7)]
    rng.shuffle(chosen)
    header = ["번호", "질문", "필수 근거", "기준 답변", "제공된 근거 FAQ", "생성 답변", *INPUT_COLUMNS]
    rows = []
    for number, (qid, _) in enumerate(chosen, 1):
        a = answers[qid]
        rows.append([number, a["question"], groups_text(a["required_faqs"], titles), a["reference_answer"],
                     a["context_text"], a["answer"], *[""] * len(INPUT_COLUMNS)])
    write(Path("output/c_review_base.csv"), header, rows)
    write(Path("output/c_review_key.csv"), ["번호", "id", "judge_verdict"],
          [[n, qid, verdict] for n, (qid, verdict) in enumerate(chosen, 1)])
    print(f"C 채점지 {len(rows)}문항(채점기 fail 8 + pass 7)")


def oos_sheet(rng: random.Random) -> None:
    similar = {str(r["id"]): r for r in map(json.loads, open("evaluation/evalset/evalset_out_of_scope_v1.3.jsonl", encoding="utf-8"))}
    items = []
    for condition, path in (("A", "output/generated_answers_A_gpt-5.4-mini_out_of_scope.csv"),
                            ("C", "output/generated_answers_C_exaone3.5-7.8b_out_of_scope.csv")):
        items += [(condition, r) for r in read(Path(path))]
    rng.shuffle(items)
    header = ["번호", "질문", "제공된 근거 FAQ", "생성 답변", *OOS_INPUTS]
    rows = [[n, r["question"], r["context_text"], r["answer"], *[""] * len(OOS_INPUTS)] for n, (_, r) in enumerate(items, 1)]
    write(Path("output/oos_review_base.csv"), header, rows)
    write(Path("output/oos_review_key.csv"), ["번호", "condition", "id", "difficulty"],
          [[n, c, r["id"], similar[r["id"]]["difficulty"]] for n, (c, r) in enumerate(items, 1)])
    print(f"범위 밖 채점지 {len(rows)}문항(A {sum(c == 'A' for c, _ in items)} + C {sum(c == 'C' for c, _ in items)})")


def main() -> None:
    rng = random.Random(SEED)
    c_sheet(rng, load_titles(Path("data/faq_v2.csv")))
    oos_sheet(rng)


if __name__ == "__main__":
    main()

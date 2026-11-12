"""채점 모델 선정·검증용 블라인드 사람 채점지 생성

- A(검색 근거)와 B(정답 근거) 생성 결과에서 문항 유형별로 층화 추출한다(조건마다 20문항, 서로 다른 문항)
- 사전등록 경로가 FAQ마다 다른 문항(38, 49, 50, 55)은 반드시 포함한다
- 채점지에는 모델 이름·근거 구성·자동 점수를 넣지 않고 순서를 섞는다(블라인드)
- 어느 번호가 어느 조건인지는 키 파일(output/에 저장, 채점이 끝날 때까지 열지 않음)에만 남긴다

사용: python evaluation/scripts/build_review_sheet.py
"""

import argparse
import csv
import random
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from evaluation.scripts.evaluate_generation import read_generated_answers
from evaluation.scripts.judge_answers import load_titles, parse_groups

SEED = 20261113
PER_TYPE = {"복수근거": 6, "원문유사": 4, "일상표현": 5, "조건형": 5}  # 조건마다 20문항
FORCED = {"A": ["38", "49"], "B": ["50", "55"]}  # 사전등록 경로 상충 문항
INPUT_COLUMNS = ["근거성(0/1/2)", "정확성(0/1)", "그룹별 충족(예: 1|0)", "근거 있는데 회피(0/1)", "메모"]


def groups_text(required_faqs: str, titles: dict[int, str]) -> str:
    parts = []
    for index, group in enumerate(parse_groups(required_faqs), 1):
        options = " 또는 ".join(f"FAQ {faq_id} {titles.get(faq_id, '')}".strip() for faq_id in group)
        parts.append(f"그룹{index}: {options}")
    return "\n".join(parts)


def sample(conditions: dict[str, list], seed: int = SEED) -> list[tuple[str, object]]:
    rng = random.Random(seed)
    used: set[str] = {qid for qids in FORCED.values() for qid in qids}  # 강제 포함 문항은 다른 조건에서 뽑지 않음
    chosen: list[tuple[str, object]] = []
    for condition, items in conditions.items():
        by_id = {item.question_id: item for item in items}
        picks = [by_id[qid] for qid in FORCED.get(condition, [])]
        for qtype, count in PER_TYPE.items():
            already = sum(1 for item in picks if item.question_type == qtype)
            pool = [item for item in items if item.question_type == qtype and item.question_id not in used]
            extra = rng.sample(pool, count - already)
            picks += extra
            used.update(item.question_id for item in extra)
        chosen += [(condition, item) for item in picks]
    rng.shuffle(chosen)
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description="블라인드 사람 채점지를 만듭니다.")
    parser.add_argument("--a", type=Path, default=Path("output/generated_answers_A_gpt-5.4-mini.csv"))
    parser.add_argument("--b", type=Path, default=Path("output/generated_answers_B_gpt-5.4-mini_oracle.csv"))
    parser.add_argument("--sheet", type=Path, default=Path("evaluation/judge_calibration/review_sheet.csv"))
    parser.add_argument("--key", type=Path, default=Path("output/review_key.csv"))
    args = parser.parse_args()

    titles = load_titles(Path("data/faq_v2.csv"))
    chosen = sample({"A": read_generated_answers(args.a), "B": read_generated_answers(args.b)})

    args.sheet.parent.mkdir(parents=True, exist_ok=True)
    with args.sheet.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["번호", "질문", "필수 근거", "기준 답변", "제공된 근거 FAQ", "생성 답변", *INPUT_COLUMNS])
        for number, (_, item) in enumerate(chosen, 1):
            writer.writerow([number, item.question, groups_text(item.target_answer_no, titles), item.target_answer,
                             item.retrieved_contexts, item.generated_answer, *[""] * len(INPUT_COLUMNS)])
    args.key.parent.mkdir(parents=True, exist_ok=True)
    with args.key.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["번호", "condition", "id", "type", "group_count"])
        for number, (condition, item) in enumerate(chosen, 1):
            writer.writerow([number, condition, item.question_id, item.question_type,
                             len(parse_groups(item.target_answer_no))])
    print(f"채점지 {args.sheet} ({len(chosen)}문항), 키 {args.key}")


if __name__ == "__main__":
    main()

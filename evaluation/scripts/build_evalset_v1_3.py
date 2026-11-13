"""평가셋 v1.2 → v1.3 형식 변환 (라벨·문구 내용은 바꾸지 않는다)

- ID: "q001" → 1 (FAQ 연번과 같은 정수 형식). 범위 밖 "o01"~"o10" → 154~163
- 칼럼 이름을 줄이고, 값이 모두 같거나 다른 칼럼으로 계산되는 칼럼을 뺀다
- evaluation/evalset/changes.csv의 ID와 필드 이름도 v1.3 형식으로 맞춘다

사용: python evaluation/scripts/build_evalset_v1_3.py
"""

import csv
import json
from pathlib import Path

EVALSET = Path(__file__).resolve().parents[2] / "evaluation/evalset"
OUT_OF_SCOPE_FIRST_ID = 154  # 본 평가셋 마지막 번호(q153) 다음부터

WRITTEN_BY = {"직접 작성(v1.0)": "본인", "초안(Claude)": "Claude"}
FIELD_NAMES = {
    "question_type": "type",
    "required_groups": "required_faqs",
    "supporting_faq_ids": "supporting_faqs",
}


def main_id(question_id: str) -> int:
    if not question_id.startswith("q"):
        raise ValueError(question_id)
    return int(question_id[1:])


def out_of_scope_id(question_id: str) -> int:
    if not question_id.startswith("o"):
        raise ValueError(question_id)
    return OUT_OF_SCOPE_FIRST_ID + int(question_id[1:]) - 1


def flatten_groups(groups):
    return [group["faq_ids"] for group in groups]


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file]


def write_jsonl(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8") as file:
        file.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def convert_main(row: dict) -> dict:
    return {
        "id": main_id(row["question_id"]),
        "status": row["status"],
        "question": row["question"],
        "intent": row["intent"],
        "type": row["question_type"],
        "required_faqs": flatten_groups(row["required_groups"]),
        "supporting_faqs": row["supporting_faq_ids"],
        "reference_answer": row["reference_answer"],
        "written_by": WRITTEN_BY[row["author"]],
        "reviewed": row["reviewer"] == "본인",
    }


def convert_out_of_scope(row: dict) -> dict:
    return {
        "id": out_of_scope_id(row["question_id"]),
        "status": row["status"],
        "question": row["question"],
        "difficulty": row["difficulty"],
        "similar_faqs": row["near_miss_faq_ids"],
        "absence_note": row["absence_check"],
        "written_by": WRITTEN_BY[row["author"]],
        "reviewed": row["reviewer"] == "본인",
    }


def convert_change_value(field: str, value: str) -> str:
    if field == "required_groups" and value.startswith("["):
        return json.dumps(flatten_groups(json.loads(value)), ensure_ascii=False)
    return value


def main() -> None:
    main_rows = [convert_main(r) for r in read_jsonl(EVALSET / "v1.2/evalset.jsonl")]
    oos_rows = [convert_out_of_scope(r) for r in read_jsonl(EVALSET / "v1.2/out_of_scope.jsonl")]
    write_jsonl(EVALSET / "evalset_v1.3.jsonl", main_rows)
    write_jsonl(EVALSET / "evalset_out_of_scope_v1.3.jsonl", oos_rows)

    # evaluation/evalset/changes.csv: v1.1 → v1.2 변경 기록을 v1.3의 ID·필드 이름으로 표기
    path = EVALSET / "changes.csv"
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if rows and "id" in rows[0]:
        print("evaluation/evalset/changes.csv는 이미 v1.3 형식")
    else:
        converted = []
        for row in rows:
            qid = row["question_id"]
            converted.append({
                "id": main_id(qid) if qid.startswith("q") else out_of_scope_id(qid),
                "field": FIELD_NAMES.get(row["field"], row["field"]),
                "before": convert_change_value(row["field"], row["before"]),
                "after": convert_change_value(row["field"], row["after"]),
                "reason": row["reason"],
                "decided_by": row["decided_by"],
            })
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["id", "field", "before", "after", "reason", "decided_by"])
            writer.writeheader()
            writer.writerows(converted)

    print(f"본 평가셋 {len(main_rows)}줄, 범위 밖 {len(oos_rows)}줄 → v1.3")


if __name__ == "__main__":
    main()

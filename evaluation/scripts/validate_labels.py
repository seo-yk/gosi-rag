"""평가셋 라벨 검증 (v1.3 형식): 평가 실행 전에 돌리고, 오류가 있으면 중단한다.

사용: python evaluation/scripts/validate_labels.py data/faq_v2.csv data/faq_merge_map.csv 라벨파일.jsonl [라벨파일2.jsonl ...]

- 본 평가셋 행: required_faqs가 있는 행. 바깥 목록은 AND, 안쪽 목록은 OR
- 범위 밖 행: required_faqs가 없는 행. similar_faqs만 검사
- status=exclude 행은 ID 중복만 검사한다
v1.2 형식 검증기는 evaluation/evalset/v1.2/validate_draft.py에 있다.
"""
import csv
import json
import sys

TYPES = {"원문유사", "일상표현", "조건형", "복수근거"}
STATUSES = {"keep", "exclude"}


def load_removed(path):
    with open(path, encoding="utf-8-sig") as f:
        return {int(row["removed_id"]) for row in csv.DictReader(f)}


def load_faq_ids(path):
    with open(path, encoding="utf-8-sig") as f:
        return {int(row["연번"]) for row in csv.DictReader(f)}


def check_faq(qid, faq_id, kind, valid_ids, removed):
    if faq_id in removed:
        return [f"{qid}: 병합으로 제거된 {kind} FAQ {faq_id}"]
    if faq_id not in valid_ids:
        return [f"{qid}: 없는 {kind} FAQ {faq_id}"]
    return []


def check_row(row, valid_ids, removed):
    qid = row["id"]
    errors = []
    if not isinstance(qid, int) or isinstance(qid, bool):
        errors.append(f"{qid}: id는 정수여야 함")
    if row.get("status") not in STATUSES:
        errors.append(f"{qid}: status는 keep 또는 exclude")
    if not isinstance(row.get("reviewed"), bool):
        errors.append(f"{qid}: reviewed는 true/false")

    if "required_faqs" not in row:  # 범위 밖
        for faq_id in row.get("similar_faqs", []):
            errors += check_faq(qid, faq_id, "similar", valid_ids, removed)
        return errors

    groups = row["required_faqs"]
    if row.get("type") not in TYPES:
        errors.append(f"{qid}: 알 수 없는 type {row.get('type')}")
    if not groups or any(not g for g in groups):
        errors.append(f"{qid}: 빈 필수 그룹")
    if (len(groups) >= 2) != (row.get("type") == "복수근거"):
        errors.append(f"{qid}: 필수 그룹 수({len(groups)})와 type이 맞지 않음")
    seen = set()
    for group in groups:
        for faq_id in group:
            errors += check_faq(qid, faq_id, "필수", valid_ids, removed)
            if faq_id in seen:
                errors.append(f"{qid}: FAQ {faq_id}가 필수에 중복")
            seen.add(faq_id)
    for faq_id in row["supporting_faqs"]:
        if faq_id in seen:
            errors.append(f"{qid}: FAQ {faq_id}가 필수와 보조에 동시 존재")
        errors += check_faq(qid, faq_id, "보조", valid_ids, removed)
    return errors


def validate(faq_path, merge_path, label_paths):
    removed = load_removed(merge_path)
    valid_ids = load_faq_ids(faq_path) - removed
    errors = []
    seen_ids = set()
    for path in label_paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row["id"] in seen_ids:
                    errors.append(f"{row['id']}: id 중복")
                seen_ids.add(row["id"])
                if row.get("status") == "exclude":
                    continue
                errors.extend(check_row(row, valid_ids, removed))
    return errors


if __name__ == "__main__":
    found = validate(sys.argv[1], sys.argv[2], sys.argv[3:])
    for message in found:
        print(message)
    sys.exit(1 if found else 0)

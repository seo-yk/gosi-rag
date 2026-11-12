"""평가셋 라벨 검증: 평가 실행 전에 돌리고, 오류가 있으면 중단한다.

사용: python validate_labels.py data/faq_raw.csv faq_merge_map.csv 라벨파일.jsonl [라벨파일2.jsonl ...]
"""
import csv
import json
import sys


def load_removed(path):
    with open(path, encoding="utf-8-sig") as f:
        return {int(row["removed_id"]) for row in csv.DictReader(f)}


def load_faq_ids(path):
    with open(path, encoding="utf-8-sig") as f:
        return {int(row["연번"]) for row in csv.DictReader(f)}


def check_row(row, valid_ids, removed):
    qid = row["question_id"]
    groups = [g["faq_ids"] if isinstance(g, dict) else g for g in row["required_groups"]]
    behavior = row.get("expected_behavior", "answer")
    errors = []

    if behavior == "abstain":
        if groups or row["supporting_faq_ids"]:
            errors.append(f"{qid}: 범위 밖 문항에 필수·보조 FAQ가 있음")
        if row["evidence_type"] != "none":
            errors.append(f"{qid}: 범위 밖 문항의 evidence_type은 none이어야 함")
        for faq_id in row.get("near_miss_faq_ids", []):
            if faq_id not in valid_ids:
                errors.append(f"{qid}: 없거나 제거된 near_miss FAQ {faq_id}")
        return errors

    if not groups or any(not g for g in groups):
        errors.append(f"{qid}: 빈 필수 그룹")
    seen = set()
    for group in groups:
        for faq_id in group:
            if faq_id in removed:
                errors.append(f"{qid}: 병합으로 제거된 FAQ {faq_id}")
            elif faq_id not in valid_ids:
                errors.append(f"{qid}: 없는 FAQ {faq_id}")
            if faq_id in seen:
                errors.append(f"{qid}: FAQ {faq_id}가 두 그룹에 중복")
            seen.add(faq_id)
    for faq_id in row["supporting_faq_ids"]:
        if faq_id in seen:
            errors.append(f"{qid}: FAQ {faq_id}가 필수와 보조에 동시 존재")
        if faq_id not in valid_ids:
            errors.append(f"{qid}: 없거나 제거된 보조 FAQ {faq_id}")
    expected = "multi" if len(groups) >= 2 else "single"
    if row["evidence_type"] != expected:
        errors.append(f"{qid}: evidence_type이 그룹 수와 불일치")
    for fact in row.get("required_facts", []):
        if not 0 <= fact["slot"] < len(groups):
            errors.append(f"{qid}: required_facts의 slot 범위 오류")
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
                if row["question_id"] in seen_ids:
                    errors.append(f"{row['question_id']}: question_id 중복")
                seen_ids.add(row["question_id"])
                if row.get("status") == "exclude":
                    continue
                errors.extend(check_row(row, valid_ids, removed))
    return errors


if __name__ == "__main__":
    found = validate(sys.argv[1], sys.argv[2], sys.argv[3:])
    for message in found:
        print(message)
    sys.exit(1 if found else 0)

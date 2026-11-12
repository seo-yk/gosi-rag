"""평가셋 v1.2 생성: 검수표 v1.1 + 라벨 초안 + 검토결정표 + 승인된 P열 수정안

입력(handoff/): 질문셋_v1.1_검수표.xlsx, eval_labels_v1.2_draft.jsonl,
               eval_out_of_scope_v1.2_draft.jsonl, 검토결정표_v1.2.xlsx
입력(evaluation/inputs/): p_column_approved_v1.2.json (검수표 P열 수정안, 사용자 승인본)
출력(evaluation/inputs/): evalset_v1.2.jsonl, evalset_out_of_scope_v1.2.jsonl, CHANGES.csv

사용: python evaluation/scripts/build_evalset_v1_2.py
"""

import collections
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xlsx_reader import read_workbook  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / "handoff"
INPUTS = ROOT / "evaluation/inputs"
VERSION = "v1.2"

# 결정표 5_기타확인: handoff/검토결정표_v1.2.xlsx에는 비어 있어,
# 사용자가 입력한 구글 시트 '검토결정표_v1.2'의 값(2026-11-12 확인)을 쓴다.
OTHER_DECISIONS = {
    "q122 보조 FAQ": "261로 변경",
    "FAQ 99 처리": "검색 대상에서 제외",
    "FAQ 병합": "확정",
    "FAQ 15 본문 중복": "확정",
}

# 검수표 '검수' 시트 열 위치
COL_TYPE, COL_QUESTION, COL_INTENT, COL_REQUIRED, COL_SUPPORTING, COL_ANSWER, COL_AUTHOR = 2, 3, 4, 5, 6, 10, 11


def parse_ids(value):
    return [int(x) for x in str(value or "").replace(" ", "").split(",") if x]


def group_key(groups):
    return sorted(sorted(g["faq_ids"]) for g in groups)


def as_text(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def sheet_rows(sheet, width):
    return {row[0]: row + [None] * (width - len(row)) for row in sheet[1:] if row and row[0]}


def main() -> None:
    review = sheet_rows(read_workbook(HANDOFF / "질문셋_v1.1_검수표.xlsx")["검수"], 18)
    with (HANDOFF / "eval_labels_v1.2_draft.jsonl").open(encoding="utf-8") as file:
        labels = [json.loads(line) for line in file]
    decisions = read_workbook(HANDOFF / "검토결정표_v1.2.xlsx")
    s1 = sheet_rows(decisions["1_필수라벨"], 8)
    s2 = sheet_rows(decisions["2_기준답변"], 8)
    s3 = sheet_rows(decisions["3_유형재분류"], 8)
    s4 = sheet_rows(decisions["4_범위밖"], 8)
    approved_p = json.loads((INPUTS / "p_column_approved_v1.2.json").read_text(encoding="utf-8"))

    changes, undecided = [], []

    def log(qid, field, before, after, reason, decided_by):
        changes.append({"question_id": qid, "field": field, "before": as_text(before),
                        "after": as_text(after), "reason": reason, "decided_by": decided_by})

    output, reviewed = [], set()
    for label in labels:
        qid = label["question_id"]
        row = review[qid]
        old_groups = [{"faq_ids": [i]} for i in parse_ids(row[COL_REQUIRED])]  # v1.1: 나열된 필수 FAQ는 모두 필요(AND)
        old_supporting = parse_ids(row[COL_SUPPORTING])
        groups, supporting = label["required_groups"], label["supporting_faq_ids"]
        question_type = label["question_type"]
        question, answer = row[COL_QUESTION], row[COL_ANSWER]
        required_by, required_reason = None, None

        # 1_필수라벨: 수락=초안 유지, 기각=v1.1 라벨로 복원
        if qid in s1:
            decision = s1[qid][5]
            reviewed.add(qid)
            if decision == "수락":
                required_by = "본인(결정표 1_필수라벨: 수락)"
            elif decision == "기각":
                groups, supporting = old_groups, old_supporting
                required_by = "본인(결정표 1_필수라벨: 기각)"
                required_reason = "기각: 검수표 v1.1 라벨로 복원. 메모: " + (s1[qid][6] or "")
            elif decision == "수정":
                raise SystemExit(f"{qid}: 1_필수라벨 수정 결정은 처리 규칙이 없음")
            else:
                undecided.append((qid, "1_필수라벨"))

        # 5_기타확인: q122 보조 FAQ
        if qid == "q122":
            reviewed.add(qid)
            if OTHER_DECISIONS["q122 보조 FAQ"] == "261로 변경":
                supporting = [261 if x == 262 else x for x in supporting]

        # 검수표 P열 승인본
        if qid in approved_p:
            reviewed.add(qid)
            question = approved_p[qid].get("question", question)
            answer = approved_p[qid].get("reference_answer", answer)

        # 2_기준답변: 수락=수정안, 기각=현재 답변, 수정=H열
        if qid in s2:
            decision = s2[qid][6]
            reviewed.add(qid)
            new_answer = {"수락": s2[qid][3], "기각": s2[qid][2], "수정": s2[qid][7]}.get(decision)
            if new_answer is None:
                undecided.append((qid, "2_기준답변"))
            else:
                if "reference_answer" in approved_p.get(qid, {}):
                    raise SystemExit(f"{qid}: 기준 답변이 결정표와 P열에서 함께 바뀜")
                if new_answer != row[COL_ANSWER]:
                    log(qid, "reference_answer", row[COL_ANSWER], new_answer, s2[qid][4] or "",
                        f"본인(결정표 2_기준답변: {decision})")
                answer = new_answer

        # 3_유형재분류
        if qid in s3:
            reviewed.add(qid)
            if s3[qid][5]:
                question_type = s3[qid][5]
            else:
                undecided.append((qid, "3_유형재분류"))

        if question_type in ("재분류 필요", "복합질문"):
            raise SystemExit(f"{qid}: 유형 미정 {question_type}")
        evidence_type = "multi" if len(groups) >= 2 else "single"
        if evidence_type == "multi" and question_type != "복수근거":
            raise SystemExit(f"{qid}: 필수 그룹이 2개 이상인데 유형이 {question_type}")

        # 변경 기록 (검수표 v1.1 대비)
        if group_key(groups) != group_key(old_groups):
            if required_by is None:
                required_by = ("Claude 초안(제외 문항, 채점 미사용)" if label["status"] == "exclude"
                               else "Claude 초안(미확인)")
            log(qid, "required_groups", old_groups, groups,
                required_reason or label["note"] or "대체 정답 또는 필수 재조정", required_by)
        if sorted(supporting) != sorted(old_supporting):
            if qid == "q122":
                by, reason = ("본인(검수표 N·P열 보조 추가 + 결정표 5_기타확인: 261로 변경)",
                              "메모 내용(면접 블라인드)은 261에 해당")
            elif qid == "q150":
                by, reason = "본인(검수표 P열)", "9번 보조 추가해서 경기도 질문이 아니어도 답변할 수 있게"
            elif qid in s1:
                by, reason = required_by, required_reason or label["note"] or "필수 재조정에 따른 보조 조정"
            elif label["status"] == "exclude":
                by, reason = "Claude 초안(제외 문항, 채점 미사용)", label["note"] or "보조 FAQ 조정"
            else:
                by = "Claude 초안(보조만 변경 규칙: HANDOFF 7장 작업2-5, 채점 미사용)"
                reason = label["note"] or "보조 FAQ 조정"
            log(qid, "supporting_faq_ids", old_supporting, supporting, reason, by)
        if question_type != row[COL_TYPE]:
            if qid in s3:
                by, reason = "본인(결정표 3_유형재분류)", s3[qid][4]
            elif row[COL_TYPE] == "복합질문" and question_type == "복수근거":
                by, reason = "확정 결정(HANDOFF 2장 유형 이름)", "필수 그룹 2개 이상"
            else:
                by, reason = "Claude 초안(미확인)", "필수 그룹 수 변경에 따른 유형 변경"
            log(qid, "question_type", row[COL_TYPE], question_type, reason, by)
        if qid in approved_p:
            for field, value, old in (("question", question, row[COL_QUESTION]),
                                      ("reference_answer", answer, row[COL_ANSWER])):
                if field in approved_p[qid] and value != old:
                    log(qid, field, old, value, approved_p[qid]["reason"], "본인(검수표 P열, 수정문 승인)")
        if label["status"] == "exclude":
            log(qid, "status", "keep", "exclude", label["note"], "확정 결정(HANDOFF 2장 평가 문항 수)")

        output.append({
            "question_id": qid, "status": label["status"], "question": question,
            "intent": row[COL_INTENT], "question_type": question_type,
            "evidence_type": evidence_type, "multi_intent": label["multi_intent"],
            "expected_behavior": label["expected_behavior"], "required_groups": groups,
            "supporting_faq_ids": supporting, "reference_answer": answer,
            "author": row[COL_AUTHOR], "label_author": "Claude 초안",
            "reviewer": "본인" if qid in reviewed else "", "eval_set_version": VERSION,
        })

    # 범위 밖: 수락=유지, 기각=exclude, 수정=F열 문구
    out_of_scope = []
    with (HANDOFF / "eval_out_of_scope_v1.2_draft.jsonl").open(encoding="utf-8") as file:
        for item in map(json.loads, file):
            qid = item["question_id"]
            decision = s4[qid][4]
            if decision == "수락":
                item["reviewer"] = "본인"
            elif decision == "기각":
                item["status"], item["reviewer"] = "exclude", "본인"
                log(qid, "status", "keep", "exclude", "범위 밖 기각", "본인(결정표 4_범위밖)")
            elif decision == "수정":
                log(qid, "question", item["question"], s4[qid][5], "범위 밖 문구 수정", "본인(결정표 4_범위밖)")
                item["question"], item["reviewer"] = s4[qid][5], "본인"
            else:
                undecided.append((qid, "4_범위밖"))
            out_of_scope.append(item)

    if undecided:
        raise SystemExit(f"결정 칸이 빈 행: {undecided}")

    with (INPUTS / "evalset_v1.2.jsonl").open("w", encoding="utf-8") as file:
        file.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in output)
    with (INPUTS / "evalset_out_of_scope_v1.2.jsonl").open("w", encoding="utf-8") as file:
        file.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in out_of_scope)
    with (INPUTS / "CHANGES.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["question_id", "field", "before", "after", "reason", "decided_by"])
        writer.writeheader()
        writer.writerows(changes)

    keep = [x for x in output if x["status"] == "keep"]
    print(f"전체 {len(output)}, keep {len(keep)}, 범위 밖 {len(out_of_scope)}")
    print("유형", dict(collections.Counter(x["question_type"] for x in keep)))
    print("CHANGES 필드별", dict(collections.Counter(c["field"] for c in changes)))
    unconfirmed = [c for c in changes if "미확인" in c["decided_by"]]
    if unconfirmed:
        print("미확인 변경:", unconfirmed)


if __name__ == "__main__":
    main()

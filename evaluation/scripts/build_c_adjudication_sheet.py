"""C(EXAONE) 사람-채점기 불일치 재검토(2단계) 시트: 채점기 판단 근거를 보고 최종 판단

- 대상: evaluation/human_review/3_c_review/labels.csv에서 사람 판정과 채점기(gemini-3.8-flash) 판정이 다른 문항
- 보여 주는 것: 질문, 필수 근거, 기준 답변, 제공된 근거 FAQ, 생성 답변, 처음 사람 점수, 채점기 점수와 판단 근거
- 입력: 최종 근거성·정확성·그룹별 충족·회피, 결정(처음 유지 / 채점기 의견 반영 / 둘 다 아님), 메모
- 채점기 의견을 본 뒤의 판단이므로, 결과는 처음 판정과 함께 기록하고 두 기준으로 모두 보고한다

사용: python evaluation/scripts/build_c_adjudication_sheet.py (openpyxl 필요)
"""

import csv
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.append(str(Path(__file__).resolve().parents[2]))

CAL = Path("evaluation/human_review")
GEN = Path("results/generation_v1.3")
OUTPUT = Path("output/c_adjudication_sheet.xlsx")
YELLOW = PatternFill("solid", fgColor="FFF2CC")
GRAY = PatternFill("solid", fgColor="D9D9D9")
BLUE = PatternFill("solid", fgColor="DDEBF7")

COLUMNS = [
    ("번호", 6, None), ("문항 id", 8, None), ("질문", 30, None), ("필수 근거", 30, None), ("기준 답변", 40, None),
    ("제공된 근거 FAQ", 55, None), ("생성 답변", 50, None),
    ("처음 사람 점수", 18, BLUE), ("채점기 점수", 18, BLUE), ("채점기 판단 근거", 50, BLUE),
    ("최종 근거성(0/1/2)", 12, YELLOW), ("최종 정확성(0/1)", 11, YELLOW), ("최종 그룹별 충족(예: 1|0)", 14, YELLOW),
    ("최종 회피(0/1)", 11, YELLOW), ("결정", 16, YELLOW), ("메모", 30, YELLOW),
]
CHOICES = {"최종 근거성(0/1/2)": "0,1,2", "최종 정확성(0/1)": "0,1", "최종 회피(0/1)": "0,1",
           "결정": "처음 유지,채점기 의견 반영,둘 다 아님"}
GUIDE = [
    ("목적", "C(EXAONE) 답변에서 처음 사람 채점과 채점기 판정이 달랐던 문항을, 채점기의 판단 근거를 보고 다시 판단합니다(재검토 2단계)."),
    ("방법", "파란 칸(처음 사람 점수, 채점기 점수와 판단 근거)을 참고해 '제공된 근거 FAQ'와 '생성 답변'을 직접 대조하고, 노란 칸에 최종 점수를 적습니다. 채점기의 지적이 사실인지(예: 답변의 내용이 근거 FAQ에 실제로 있는지)를 확인하는 것이 핵심입니다."),
    ("결정", "처음 유지 = 처음 점수가 맞다고 판단 / 채점기 의견 반영 = 채점기 지적이 맞아 점수를 바꿈 / 둘 다 아님 = 둘 다와 다른 판단"),
    ("기준", "루브릭 v2.1과 같습니다. 근거성은 제공된 근거 FAQ와 비교, 정확성은 쓴 내용이 맞는지, 그룹 충족은 그 그룹 내용을 다뤘는지(근거 제공 여부와 무관), 회피는 근거에 답이 있는 부분을 피했는지. 길이·서식·말투는 보지 않습니다."),
    ("주의", "채점기 의견을 본 뒤의 판단이라, 처음 판정과 함께 기록하고 결과는 두 기준으로 모두 보고합니다. 처음 점수를 유지해도 괜찮습니다."),
]


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def main() -> None:
    labels = [r for r in read(CAL / "3_c_review" / "labels.csv") if r["verdict"] != r["judge_verdict"]]
    base = {r[0]: r for r in csv.reader(open("output/c_review_base.csv", encoding="utf-8-sig"))}
    judged = {r["id"]: r for r in read(GEN / "judged_C.csv")}

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "재검토"
    sheet.append([name for name, _, _ in COLUMNS])
    for number, label in enumerate(labels, 1):
        b = base[label["review_no"]]
        j = judged[label["id"]]
        first = (f"근거성 {label['groundedness']}, 정확성 {label['correctness']}, 그룹 {label['groups_covered']}, "
                 f"회피 {label['unjustified_refusal']} → {label['verdict']}")
        judge = (f"근거성 {j['groundedness']}, 정확성 {j['correctness']}, 그룹 {j['groups_covered']}, "
                 f"회피 {j['unjustified_refusal']} → {j['verdict']}")
        sheet.append([number, int(label["id"]), b[1], b[2], b[3], b[4], b[5], first, judge, j["reason"],
                      "", "", "", "", "", ""])

    for col, (name, width, fill) in enumerate(COLUMNS, 1):
        letter = sheet.cell(row=1, column=col).column_letter
        sheet.column_dimensions[letter].width = width
        head = sheet.cell(row=1, column=col)
        head.font = Font(bold=True)
        head.fill = fill or GRAY
        head.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        for row in range(2, len(labels) + 2):
            cell = sheet.cell(row=row, column=col)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if fill:
                cell.fill = fill
            if fill is YELLOW:
                cell.number_format = "@"
        if name in CHOICES:
            validation = DataValidation(type="list", formula1=f'"{CHOICES[name]}"', allow_blank=True)
            sheet.add_data_validation(validation)
            validation.add(f"{letter}2:{letter}{len(labels) + 1}")
    sheet.row_dimensions[1].height = 34
    for row in range(2, len(labels) + 2):
        sheet.row_dimensions[row].height = 400
    sheet.freeze_panes = "C2"

    guide = workbook.create_sheet("재검토 방법")
    guide.append(["항목", "설명"])
    for item in GUIDE:
        guide.append(list(item))
    guide.column_dimensions["A"].width = 12
    guide.column_dimensions["B"].width = 120
    for row in guide.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in guide[1]:
        cell.font = Font(bold=True)
        cell.fill = GRAY

    workbook.save(OUTPUT)
    print(f"{OUTPUT} ({len(labels)}문항)")


if __name__ == "__main__":
    main()

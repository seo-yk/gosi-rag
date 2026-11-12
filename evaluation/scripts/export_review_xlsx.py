"""블라인드 사람 채점지(CSV)를 읽기 편한 Excel 파일로 변환 (openpyxl 필요)

- 채점 시트: 열 너비·줄바꿈·고정 행/열, 입력 칸 노란색, 0/1/2·0/1 선택 목록, 그룹별 충족 칸은 텍스트 형식
- 채점 방법 시트: 판단 기준 요약

사용: python evaluation/scripts/export_review_xlsx.py [채점지.csv] [출력.xlsx]
"""

import csv
import math
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

WIDTHS = {"번호": 6, "질문": 32, "필수 근거": 32, "기준 답변": 45, "제공된 근거 FAQ": 60, "생성 답변": 55,
          "근거성(0/1/2)": 12, "정확성(0/1)": 11, "그룹별 충족(예: 1|0)": 14, "근거 있는데 회피(0/1)": 13, "메모": 28}
INPUTS = ["근거성(0/1/2)", "정확성(0/1)", "그룹별 충족(예: 1|0)", "근거 있는데 회피(0/1)", "메모"]
CHOICES = {"근거성(0/1/2)": "0,1,2", "정확성(0/1)": "0,1", "근거 있는데 회피(0/1)": "0,1"}
YELLOW = PatternFill("solid", fgColor="FFF2CC")
GRAY = PatternFill("solid", fgColor="D9D9D9")

GUIDE = [
    ("채점 순서", "각 행을 질문 → 필수 근거 → 기준 답변 → 제공된 근거 FAQ → 생성 답변 순서로 읽고, 노란 칸 5개를 채웁니다."),
    ("근거성(0/1/2)", "생성 답변의 내용이 '제공된 근거 FAQ'에 있는가. 2 = 모든 내용이 근거에 있음, 1 = 근거에 없는 세부 내용이 조금 섞임, 0 = 핵심 내용이 근거에 없거나 근거와 모순"),
    ("정확성(0/1)", "질문에 바르게 답했는가. 기준 답변과 표현이 달라도 뜻이 같거나 근거 FAQ로 뒷받침되면 1"),
    ("그룹별 충족(예: 1|0)", "'필수 근거'의 그룹마다 그 내용에 답했으면 1, 아니면 0을 그룹 순서대로 |로 연결. 그룹이 1개면 1 또는 0. '또는'으로 묶인 FAQ는 하나만 다뤄도 충족"),
    ("근거 있는데 회피(0/1)", "제공된 근거 FAQ에 답이 있는데 '확인할 수 없다'는 식으로 답을 피했으면 1"),
    ("메모", "판단이 애매했던 이유 등(선택)"),
    ("공통 규칙 1", "답변 길이, 굵은 글씨·목록 같은 서식, 말투는 점수에 반영하지 않습니다."),
    ("공통 규칙 2", "근거 FAQ끼리 내용이 다르면(예: 사전등록 경로), 그중 하나에 근거한 답은 맞는 것으로 봅니다."),
    ("공통 규칙 3", "근거 FAQ에 있는 정보라면 질문 범위를 넘는 내용을 덧붙여도 감점하지 않습니다."),
    ("공통 규칙 4", "근거 FAQ에 답이 없어 '확인할 수 없다'고 답했다면 회피는 0, 정확성은 0입니다."),
    ("판정", "pass는 입력값으로 자동 계산합니다: 근거성 2, 정확성 1, 모든 그룹 충족, 회피 0"),
    ("블라인드", "모델 이름·근거 구성·자동 점수는 숨겼고 순서를 섞었습니다. output/review_key.csv는 채점이 끝날 때까지 열지 않습니다."),
]


def row_height(values: list[str], headers: list[str]) -> float:
    """줄바꿈된 셀이 보이도록 행 높이 추정(한글은 영문 2자 폭)"""
    lines = 1
    for header, value in zip(headers, values):
        width = max(WIDTHS.get(header, 12) - 1, 1)
        total = sum(max(1, math.ceil(sum(2 if ord(ch) > 0x2E80 else 1 for ch in paragraph) / width))
                    for paragraph in str(value).split("\n"))
        lines = max(lines, total)
    return min(409, 15 * lines + 4)  # Excel 행 높이 최대 409


def export(csv_path: Path, xlsx_path: Path) -> None:
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))
    headers, body = rows[0], rows[1:]

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "채점"
    sheet.append(headers)
    for values in body:
        sheet.append([int(values[0])] + values[1:])

    for col, header in enumerate(headers, 1):
        letter = sheet.cell(row=1, column=col).column_letter
        sheet.column_dimensions[letter].width = WIDTHS.get(header, 12)
        cell = sheet.cell(row=1, column=col)
        cell.font = Font(bold=True)
        cell.fill = YELLOW if header in INPUTS else GRAY
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        for row in range(2, len(body) + 2):
            target = sheet.cell(row=row, column=col)
            target.alignment = Alignment(wrap_text=True, vertical="top")
            if header in INPUTS:
                target.fill = YELLOW
                target.number_format = "@"  # 1|0 같은 값이 숫자·날짜로 바뀌지 않게 텍스트로
        if header in CHOICES:
            validation = DataValidation(type="list", formula1=f'"{CHOICES[header]}"', allow_blank=True)
            sheet.add_data_validation(validation)
            validation.add(f"{letter}2:{letter}{len(body) + 1}")
    sheet.row_dimensions[1].height = 34
    for index, values in enumerate(body, 2):
        sheet.row_dimensions[index].height = row_height(values, headers)
    sheet.freeze_panes = "C2"

    guide = workbook.create_sheet("채점 방법")
    guide.append(["항목", "설명"])
    for item in GUIDE:
        guide.append(list(item))
    guide.column_dimensions["A"].width = 22
    guide.column_dimensions["B"].width = 110
    for row in guide.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in guide[1]:
        cell.font = Font(bold=True)
        cell.fill = GRAY

    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(xlsx_path)
    print(f"{xlsx_path} ({len(body)}문항)")


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/review_sheet_base.csv")
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("evaluation/judge_calibration/review_sheet.xlsx")
    export(source, target)

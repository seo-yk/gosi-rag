"""openpyxl 없이 xlsx 시트 값을 읽는 최소 리더 (표준 라이브러리만 사용)"""

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_T = "{%s}t" % NS["m"]


def _col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_workbook(path: str | Path) -> dict[str, list[list[str | None]]]:
    """시트 이름 → 행 목록(각 행은 A열부터의 값 목록). 수식은 저장된 결과값을 읽는다."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(_T)) for si in root.findall("m:si", NS)]
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        sheets = {}
        for sheet in workbook.find("m:sheets", NS):
            target = targets[sheet.get("{%s}id" % NS["r"])].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            rows = []
            for row in ET.fromstring(z.read(target)).iter("{%s}row" % NS["m"]):
                values = {}
                for cell in row.findall("m:c", NS):
                    kind, v = cell.get("t"), cell.find("m:v", NS)
                    if kind == "s" and v is not None:
                        value = shared[int(v.text)]
                    elif kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(_T))
                    else:
                        value = v.text if v is not None else None
                    values[_col_index(cell.get("r"))] = value
                width = max(values) + 1 if values else 0
                rows.append([values.get(i) for i in range(width)])
            sheets[sheet.get("name")] = rows
    return sheets

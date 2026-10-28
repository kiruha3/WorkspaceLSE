"""Fill an existing official-layout template without roundtripping its styles."""
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET

TEMPLATE=Path(__file__).parent/"templates"/"form151-2026.xlsx"
CELL=re.compile(r'<c\b([^>]*\br="([A-Z]+)(\d+)"[^>]*?)(?:/>|>([\s\S]*?)</c>)')
NS={"s":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def replace_cells(xml,values):
    pending=set(values)
    def replace(match):
        address=match[2]+match[3]
        if address not in values:return match[0]
        pending.discard(address);value=values[address]
        attrs=re.sub(r'\s+t="[^"]*"','',match[1])
        if value is None:return f'<c{attrs}/>'
        if type(value) is int:
            if value<0:raise ValueError("Отрицательный показатель отчёта.")
            return f'<c{attrs}><v>{value}</v></c>'
        if not isinstance(value,str):raise ValueError("Недопустимый показатель отчёта.")
        return f'<c{attrs} t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
    result=CELL.sub(replace,xml)
    if pending:raise ValueError("В бланке отсутствуют ячейки: "+", ".join(sorted(pending)))
    return result


def export_xlsx(report):
    with ZipFile(TEMPLATE) as original:parts={name:original.read(name) for name in original.namelist()}
    if len(ET.fromstring(parts["xl/workbook.xml"]).find("s:sheets",NS))!=9:raise ValueError("Ожидался девятилистовый бланк.")
    # Defense against a stale template: remove ALL example business cells in
    # all eight sections before putting confirmed values, not only total rows.
    strings=["".join(si.itertext()) for si in ET.fromstring(parts["xl/sharedStrings.xml"])]
    writes={}
    for cell in report["cells"]:
        section=int(cell["sheet"].removeprefix("Раздел "))
        if section not in range(1,7) or not re.fullmatch(r"[D-X]\d+",cell["address"]):raise ValueError("Неверная ячейка отчёта.")
        if cell["value"] is not None and (type(cell["value"]) is not int or cell["value"]<0):raise ValueError("Неверное число отчёта.")
        writes.setdefault(section,{})[cell["address"]]=cell["value"]
    for section in range(1,9):
        path=f"xl/worksheets/sheet{section+1}.xml";xml=parts[path].decode()
        business_rows=set()
        if section<=6:
            for match in CELL.finditer(xml):
                if match[2]!="C":continue
                v=re.search(r"<v>(.*?)</v>",match[4] or "")
                value=v[1] if v else ""
                if 't="s"' in match[1]:value=strings[int(value)] if value else ""
                if value.isdigit():business_rows.add(match[3])
        last=["X","L","N","T","R","M"]
        blanks={m[2]+m[3]:None for m in CELL.finditer(xml) if
            (section<=6 and m[3] in business_rows and len(m[2])==1 and "D"<=m[2]<=last[section-1]) or
            (section>=7 and m[2]=="F" and 6<=int(m[3])<=(15 if section==7 else 19))}
        if section==8:blanks.update({"A20":"Руководитель __________________________________________________________________________________", "A22":"Исполнитель __________________________________________________________________________________", "A24":"Телефон ____________________  Адрес электронной почты ____________________", "A26":"Исх. № _________    «___» ______________ 20___ г."})
        parts[path]=replace_cells(xml,{**blanks,**writes.get(section,{})}).encode()
    parts["xl/worksheets/sheet1.xml"]=replace_cells(parts["xl/worksheets/sheet1.xml"].decode(),{
        "A7":f'Предварительный · за {report["month"]} месяцев {report["year"]} г.',"D16":"ФГБУ Абаканская ЛСЭ"}).encode()
    # The sanitized asset already has no sample names in sharedStrings. Exact
    # non-worksheet parts, merges, column sizes, print settings and styles survive.
    output=BytesIO()
    with ZipFile(output,"w",ZIP_DEFLATED) as archive:
        for name,content in parts.items():archive.writestr(name,content)
    return output.getvalue()

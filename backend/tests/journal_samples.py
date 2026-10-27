import csv
from io import StringIO, BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape

HEADERS={"B":"№","C":"Дата","D":"состояние","K":"Материалы","M":"N спец.","N":"категория сложности","P":"Дата окончания","V":"Цена"}
COLUMNS=[chr(65+i) if i<26 else "A"+chr(65+i-26) for i in range(128)]


def row(**overrides):
    return {"B":"151/4-1-26","C":"12.02.2026","D":"Завершена","L":"ДЕМО А.А.","M":"18.1.","O":"Заключение эксперта","P":"06.03.2026",**overrides}


def csv_source(rows=None,*,delimiter=",",headers=None):
    out=StringIO(newline="")
    writer=csv.writer(out,delimiter=delimiter)
    for item in [HEADERS if headers is None else headers,{}, {},*(rows if rows is not None else [row()])]:
        writer.writerow([item.get(column,"") for column in COLUMNS[:max(28,max((COLUMNS.index(column)+1 for column in item),default=0))]])
    return out.getvalue().encode("utf-8-sig")


def xlsx_source(rows=None,*,date1904=False,second_sheet=True,formula=None,extra_xml=None,dimension=None,date_styles=None):
    records=[HEADERS,{}, {},*(rows if rows is not None else [row()])]
    xmlrows=[]
    for number,item in enumerate(records,1):
        cells=[]
        for column in sorted(item,key=COLUMNS.index):
            value=item[column]
            address=f"{column}{number}"
            style=' s="1"' if date_styles and address in date_styles else ''
            if formula and address in formula:
                expression,cached=formula[address]
                cached_xml=f"<v>{cached}</v>" if cached is not None else ""
                cells.append(f'<c r="{address}"{style}><f>{escape(expression)}</f>{cached_xml}</c>')
            elif isinstance(value,(int,float)):
                cells.append(f'<c r="{address}"{style}><v>{value}</v></c>')
            elif value is not None:
                cells.append(f'<c r="{address}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>')
        xmlrows.append(f'<row r="{number}">{"".join(cells)}</row>')
    files={
        "[Content_Types].xml":'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels":'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml":f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><workbookPr date1904="{int(date1904)}"/><sheets><sheet name="Лист1" sheetId="1" r:id="rId1"/>{"<sheet name=\"Шум\" sheetId=\"2\" r:id=\"rId2\"/>" if second_sheet else ""}</sheets></workbook>',
        "xl/_rels/workbook.xml.rels":'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml":f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{f"<dimension ref=\"{dimension}\"/>" if dimension else ""}<sheetData>{"".join(xmlrows)}</sheetData></worksheet>',
        "xl/worksheets/sheet2.xml":'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="B1" t="inlineStr"><is><t>НЕ ДАННЫЕ ЖУРНАЛА</t></is></c></row></sheetData></worksheet>',
        **(extra_xml or {}),
    }
    if date_styles:
        files["xl/styles.xml"]='<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font/></fonts><fills count="1"><fill><patternFill/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
        files["xl/_rels/workbook.xml.rels"]=files["xl/_rels/workbook.xml.rels"].replace('</Relationships>','<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        files["[Content_Types].xml"]=files["[Content_Types].xml"].replace('</Types>','<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
    out=BytesIO()
    with ZipFile(out,"w",ZIP_DEFLATED) as archive:
        for name,body in files.items():archive.writestr(name,body)
    return out.getvalue()

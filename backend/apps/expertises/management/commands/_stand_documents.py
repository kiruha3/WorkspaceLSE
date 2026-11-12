"""PDF documents for the stand, generated from its own case data."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape


def make_pdf(title, number, description, pages=2):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    font = next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('C:/Windows/Fonts/arial.ttf')) if p.exists()), None)
    if font is None:
        raise RuntimeError('Для PDF нужен шрифт DejaVu Sans либо Arial.')
    if 'StandText' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('StandText', str(font)))
    body = ParagraphStyle('body', fontName='StandText', fontSize=10, leading=16, spaceAfter=12)
    heading = ParagraphStyle('heading', parent=body, fontSize=15, leading=21, spaceAfter=20)
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=48)
    story = []
    for page in range(pages):
        if page:
            story.append(PageBreak())
        story.append(Paragraph(escape(title if page == 0 else f'Исследование и приложения — лист {page + 1}'), heading))
        story.append(Paragraph(escape(f'Регистрационный номер: {number}'), body))
        story.append(Paragraph(escape(description), body))
        for section in ('Представленные объекты', 'Сведения о материалах', 'Ход исследования', 'Выводы по поставленным вопросам'):
            story.append(Paragraph(section, heading))
            story.append(Paragraph('Представленные материалы изучены в пределах поставленных вопросов. Описание объектов и результаты сравнительного исследования приведены в таблице. Существенные признаки зафиксированы в рабочей документации.', body))
        rows = [[Paragraph('Объект', body), Paragraph('Наблюдение', body), Paragraph('Результат', body)]]
        rows += [[Paragraph(f'Образец {i}', body), Paragraph('Сравнение признаков и характеристик', body), Paragraph('Данные зафиксированы', body)] for i in range(1, 4)]
        table = Table(rows, colWidths=[105, 210, 175])
        table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b6c4bc')), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#edf2ee')), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story += [table, Spacer(1, 14), Paragraph('Стенд АИС · Документ для проверки интерфейса', body)]
    document.build(story)
    return stream.getvalue()

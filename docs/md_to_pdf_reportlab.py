from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import re

MD_PATH = "NDM_Enterprise_Report.md"
PDF_PATH = "NDM_Enterprise_Report.pdf"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleCenter', fontSize=22, leading=26, alignment=TA_CENTER, spaceAfter=18))
styles.add(ParagraphStyle(name='SectionHeader', fontSize=14, leading=18, alignment=TA_LEFT, spaceBefore=12, spaceAfter=8, textColor=colors.HexColor('#003366')))
styles.add(ParagraphStyle(name='SubHeader', fontSize=12, leading=15, alignment=TA_LEFT, spaceBefore=8, spaceAfter=6, textColor=colors.HexColor('#005599')))
styles.add(ParagraphStyle(name='Body', fontSize=10, leading=13, alignment=TA_LEFT, spaceAfter=6))
styles.add(ParagraphStyle(name='Monospace', fontName='Courier', fontSize=8, leading=10))


def parse_markdown_to_flowables(md_text):
    lines = md_text.splitlines()
    flow = []
    in_code = False
    code_buffer = []
    table_buffer = []
    para_buffer = []

    def flush_paragraph():
        nonlocal para_buffer
        if para_buffer:
            text = ' '.join(para_buffer).strip()
            flow.append(Paragraph(text.replace('<', '&lt;').replace('>', '&gt;'), styles['Body']))
            para_buffer = []

    def flush_code():
        nonlocal code_buffer
        if code_buffer:
            code_text = '\n'.join(code_buffer)
            flow.append(Preformatted(code_text, styles['Monospace']))
            flow.append(Spacer(1,8))
            code_buffer = []

    def flush_table():
        nonlocal table_buffer
        if table_buffer:
            # parse markdown table to rows
            rows = []
            for r in table_buffer:
                # split on | but ignore leading/trailing
                parts = [c.strip() for c in r.strip().strip('|').split('|')]
                rows.append(parts)
            # if second row is separator remove it
            if len(rows) >= 2 and re.match(r'^:?-+:?$', ''.join(rows[1])):
                # not a valid split; keep as-is
                pass
            t = Table(rows, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f6fb')),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            flow.append(t)
            flow.append(Spacer(1,8))
            table_buffer = []

    for line in lines:
        # code fence handling
        if line.strip().startswith('```'):
            if in_code:
                # end code
                in_code = False
                flush_code()
            else:
                flush_paragraph()
                in_code = True
            continue

        if in_code:
            code_buffer.append(line)
            continue

        # heading
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            flush_paragraph()
            flush_table()
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1:
                flow.append(Paragraph(text, styles['TitleCenter']))
            elif level == 2:
                flow.append(Paragraph(text, styles['SectionHeader']))
            else:
                flow.append(Paragraph(text, styles['SubHeader']))
            continue

        # horizontal rule
        if re.match(r'^---+$', line.strip()):
            flush_paragraph()
            flush_table()
            flow.append(Spacer(1,12))
            continue

        # table detection (lines with |)
        if '|' in line and re.search(r'\|', line):
            table_buffer.append(line)
            continue
        else:
            if table_buffer:
                flush_table()

        # blank line => paragraph boundary
        if not line.strip():
            flush_paragraph()
            continue

        # normal paragraph line
        para_buffer.append(line.strip())

    # end for
    flush_paragraph()
    flush_table()
    flush_code()
    return flow


def add_page_number(canvas, doc):
    page_num = canvas.getPageNumber()
    text = f"Page {page_num}"
    canvas.setFont('Helvetica', 9)
    canvas.drawRightString(585, 18, text)


if __name__ == '__main__':
    import io
    with open(MD_PATH, 'r', encoding='utf-8') as f:
        md = f.read()
    doc = SimpleDocTemplate(PDF_PATH, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    flowables = parse_markdown_to_flowables(md)
    doc.build(flowables, onLaterPages=add_page_number, onFirstPage=add_page_number)
    print('Wrote', PDF_PATH)

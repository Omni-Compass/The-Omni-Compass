"""Render BENCHMARK.md (from pilot/bench_report.py) as a PDF: headings, paragraphs, bullet lists and tables.

python pilot/bench_pdf.py BENCHMARK.md BENCHMARK.pdf
"""
from __future__ import annotations

import re, sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Preformatted


def inline(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", s)


def table(rows, width):
    ss = getSampleStyleSheet(); cell = ss["BodyText"].clone("cell", fontSize=7.5, leading=9)
    head = ss["BodyText"].clone("head", fontSize=7.5, leading=9, textColor=colors.white, fontName="Helvetica-Bold")
    data = [[Paragraph(inline(c), head if i == 0 else cell) for c in r] for i, r in enumerate(rows)]
    n = len(rows[0])
    need = [max(6, min(34, max(len(r[j]) if j < len(r) else 0 for r in rows[1:] or rows))) for j in range(n)]
    need = [max(x, min(12, len(rows[0][j]) // 2)) for j, x in enumerate(need)]
    widths = [width * x / sum(need) for x in need]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8c2cc")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    for i, r in enumerate(rows[1:], 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f2f5f8")))
        last = r[-1].lower()
        if "better" in last:
            style.append(("TEXTCOLOR", (-1, i), (-1, i), colors.HexColor("#1b7f3b")))
        elif "worse" in last:
            style.append(("TEXTCOLOR", (-1, i), (-1, i), colors.HexColor("#b3261e")))
    t.setStyle(TableStyle(style))
    return t


def render(md: str, out: str):
    ss = getSampleStyleSheet()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title="Omni-Compass benchmark")
    W = doc.width; story = []; lines = md.splitlines(); i = 0; para = []

    def flush():
        if para:
            story.append(Paragraph(inline(" ".join(para)), ss["BodyText"])); para.clear()
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|"):
            flush(); rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            story += [table(rows, W), Spacer(1, 4 * mm)]; continue
        if ln.startswith("```"):
            flush(); j = i + 1; block = []
            while j < len(lines) and not lines[j].startswith("```"):
                block.append(lines[j]); j += 1
            story.append(Preformatted("\n".join(block), ss["Code"])); i = j + 1; continue
        if ln.startswith("# "):
            flush(); story.append(Paragraph(inline(ln[2:]), ss["Title"]))
        elif ln.startswith("## "):
            flush(); story.append(Paragraph(inline(ln[3:]), ss["Heading2"]))
        elif ln.startswith("- "):
            flush(); story.append(Paragraph("&bull; " + inline(ln[2:]), ss["BodyText"]))
        elif not ln.strip():
            flush(); story.append(Spacer(1, 2 * mm))
        else:
            para.append(ln.strip())
        i += 1
    flush(); doc.build(story)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    render(Path(src).read_text(), dst)
    print(f"wrote {dst}")

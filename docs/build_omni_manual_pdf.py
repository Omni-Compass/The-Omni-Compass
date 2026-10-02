#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Builds docs/OMNI_COMPASS_MANUAL.pdf from docs/OMNI_COMPASS_MANUAL.md (headings, paragraphs, lists, tables, code)."""
import re
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
SRC, OUT = ROOT / "docs" / "OMNI_COMPASS_MANUAL.md", ROOT / "docs" / "OMNI_COMPASS_MANUAL.pdf"
ss = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontName="Times-Roman", fontSize=10, leading=13.5, spaceAfter=5)
CELL = ParagraphStyle("c", parent=BODY, fontSize=8, leading=10, spaceAfter=0)
H = {1: ParagraphStyle("h1", parent=ss["Heading1"], fontName="Times-Bold", fontSize=18, spaceBefore=6, spaceAfter=10),
     2: ParagraphStyle("h2", parent=ss["Heading2"], fontName="Times-Bold", fontSize=13.5, spaceBefore=10, spaceAfter=6),
     3: ParagraphStyle("h3", parent=ss["Heading3"], fontName="Times-Bold", fontSize=11.5, spaceBefore=8, spaceAfter=4)}
CODE = ParagraphStyle("code", parent=BODY, fontName="Courier", fontSize=7.8, leading=9.5, leftIndent=10,
                      backColor=colors.HexColor("#f2f2f2"))
NOTE = ParagraphStyle("note", parent=BODY, fontSize=9, leading=12, leftIndent=8, rightIndent=8,
                      borderColor=colors.HexColor("#555555"), borderWidth=0.6, borderPadding=6, spaceBefore=4, spaceAfter=8)


def inline(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r'<font face="Courier" size="8.5">\1</font>', t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return t


def footer(c, d):
    c.saveState(); c.setFont("Times-Roman", 7.5)
    c.drawString(inch * 0.75, 0.5 * inch, "The Omni-Compass Manual, Edition 1.0 - Copyright (c) 2026 The Omni-Compass LLC. "
                 "Proprietary. Evaluation and simulation use only.")
    c.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, str(d.page)); c.restoreState()


def build():
    lines = SRC.read_text().splitlines()
    story, i, width = [], 0, letter[0] - 1.5 * inch
    first_h1 = True
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1; buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j]); j += 1
            story.append(Preformatted("\n".join(buf), CODE)); i = j + 1; continue
        if ln.startswith("    ") and ln.strip():
            buf = []
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                buf.append(lines[i][4:]); i += 1
            story.append(Preformatted("\n".join(buf).rstrip(), CODE)); continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append([Paragraph(inline(c), CELL) for c in cells])
                i += 1
            n = max(len(r) for r in rows)
            rows = [r + [Paragraph("", CELL)] * (n - len(r)) for r in rows]
            t = Table(rows, colWidths=[width / n] * n, repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [t, Spacer(1, 6)]; continue
        m = re.match(r"^(#{1,3}) (.*)", ln)
        if m:
            lvl = len(m.group(1))
            if lvl == 1 and not first_h1:
                story.append(PageBreak())
            first_h1 = False
            story.append(Paragraph(inline(m.group(2)), H[lvl])); i += 1; continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> ").rstrip()); i += 1
            story.append(Paragraph(inline(" ".join(buf)), NOTE)); continue
        if ln.strip() == "---":
            story.append(Spacer(1, 6)); i += 1; continue
        if re.match(r"^\s*(-|\d+\.) ", ln):
            buf = [ln]
            i += 1
            while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"^\s*(-|\d+\.) ", lines[i]):
                buf.append(lines[i].strip()); i += 1
            mm = re.match(r"^(\s*)(-|\d+\.) (.*)", " ".join(buf))
            indent = 12 + 10 * (len(mm.group(1)) // 2)
            bullet = "&bull;" if mm.group(2) == "-" else mm.group(2)
            story.append(Paragraph(inline(mm.group(3)), ParagraphStyle("li", parent=BODY, leftIndent=indent + 8,
                                   bulletIndent=indent - 4, spaceAfter=2), bulletText=bullet if bullet != "&bull;" else "•"))
            continue
        if not ln.strip():
            i += 1; continue
        buf = [ln]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||```|>|\s*(-|\d+\.) |---)", lines[i]) \
                and not lines[i].startswith("    "):
            buf.append(lines[i]); i += 1
        story.append(Paragraph(inline(" ".join(x.strip() for x in buf)), BODY))
    doc = SimpleDocTemplate(str(OUT), pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.75 * inch, bottomMargin=0.8 * inch, title="The Omni-Compass Manual",
                            author="The Omni-Compass LLC")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == "__main__":
    build()

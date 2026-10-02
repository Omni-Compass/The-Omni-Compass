#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Builds the printable book, docs/OMNI_COMPASS_MANUAL.pdf, and its one-file text, docs/book/OMNI_COMPASS_BOOK.md.

The book is assembled from the theory chapters in docs/book/, the manual, the repository's documents, the 656-muscle
catalog and the source of the engine, in the order set in OUTLINE below. US Letter, mirrored margins for binding,
parts and chapters open on a right-hand page, running heads, roman numerals in the front matter, a contents with page
numbers, PDF bookmarks, the founder's plates, and a full-bleed front and back cover.

    python3 docs/book/build_book.py
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from fontTools.ttLib import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as RLFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame, Image, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Preformatted, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / "docs" / "book"
PLATES = BOOK / "plates"
OUT_PDF = ROOT / "docs" / "OMNI_COMPASS_MANUAL.pdf"
OUT_MD = BOOK / "OMNI_COMPASS_BOOK.md"
EDITION = "October 2026"
BANNER_MD = ("> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not "
             "open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, "
             "commercialization, monetization, production use, redistribution, hosted service or incorporation into a product "
             "requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Patent applications, "
             "copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its "
             "software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../../LICENSE).")
FILED = ("Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its "
         "mathematics and its software have been filed in the United States by The Omni-Compass LLC.")

# ---------------------------------------------------------------- fonts
LIB = "/usr/share/fonts/truetype/liberation/"
DJV = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(RLFont("Serif", LIB + "LiberationSerif-Regular.ttf"))
pdfmetrics.registerFont(RLFont("Serif-Bold", LIB + "LiberationSerif-Bold.ttf"))
pdfmetrics.registerFont(RLFont("Serif-Italic", LIB + "LiberationSerif-Italic.ttf"))
pdfmetrics.registerFont(RLFont("Serif-BoldItalic", LIB + "LiberationSerif-BoldItalic.ttf"))
pdfmetrics.registerFont(RLFont("Sans", LIB + "LiberationSans-Regular.ttf"))
pdfmetrics.registerFont(RLFont("Sans-Bold", LIB + "LiberationSans-Bold.ttf"))
pdfmetrics.registerFont(RLFont("Mono", DJV + "DejaVuSansMono.ttf"))
pdfmetrics.registerFont(RLFont("Mono-Bold", DJV + "DejaVuSansMono-Bold.ttf"))
pdfmetrics.registerFont(RLFont("Sym", DJV + "DejaVuSans.ttf"))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-Bold", italic="Serif-Italic", boldItalic="Serif-BoldItalic")
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans", boldItalic="Sans-Bold")
pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold", italic="Mono", boldItalic="Mono-Bold")
SERIF_CMAP = set(TTFont(LIB + "LiberationSerif-Regular.ttf").getBestCmap())
MONO_CMAP = set(TTFont(DJV + "DejaVuSansMono.ttf").getBestCmap())
SYM_CMAP = set(TTFont(DJV + "DejaVuSans.ttf").getBestCmap())

# ---------------------------------------------------------------- page and styles
PW, PH = letter
INNER, OUTER, TOP, BOTTOM = 1.0 * inch, 0.75 * inch, 0.95 * inch, 0.9 * inch
FW, FH = PW - INNER - OUTER, PH - TOP - BOTTOM
NAVY, GOLD, INK, GREY = colors.HexColor("#0b1f3a"), colors.HexColor("#a8801f"), colors.HexColor("#1a1a1a"), colors.HexColor("#666666")
RULE = colors.HexColor("#c9b27a")

BODY = ParagraphStyle("body", fontName="Serif", fontSize=10.5, leading=14.2, alignment=TA_JUSTIFY, spaceAfter=6, textColor=INK)
CELL = ParagraphStyle("cell", fontName="Serif", fontSize=8.3, leading=10.2, textColor=INK)
CELLH = ParagraphStyle("cellh", parent=CELL, fontName="Sans-Bold", fontSize=8, textColor=colors.white)
CODE = ParagraphStyle("code", fontName="Mono", fontSize=7.6, leading=9.6, textColor=INK)
SRC = ParagraphStyle("src", fontName="Mono", fontSize=6.7, leading=8.1, textColor=INK)
NOTE = ParagraphStyle("note", parent=BODY, fontSize=9.8, leading=13, leftIndent=10, rightIndent=10, borderColor=RULE,
                      borderWidth=0.8, borderPadding=7, backColor=colors.HexColor("#faf6ec"), spaceBefore=6, spaceAfter=10)
H1 = ParagraphStyle("h1", fontName="Serif-Bold", fontSize=25, leading=30, textColor=NAVY, spaceAfter=6)
H2 = ParagraphStyle("h2", fontName="Serif-Bold", fontSize=14.5, leading=18, textColor=NAVY, spaceBefore=12, spaceAfter=6, keepWithNext=1)
H3 = ParagraphStyle("h3", fontName="Serif-BoldItalic", fontSize=11.8, leading=15, textColor=NAVY, spaceBefore=8, spaceAfter=4, keepWithNext=1)
KICK = ParagraphStyle("kick", fontName="Sans-Bold", fontSize=10, leading=12, textColor=GOLD, spaceAfter=6)
CAP = ParagraphStyle("cap", fontName="Serif-Italic", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=GREY)
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER)
TOC1 = ParagraphStyle("toc1", fontName="Serif-Bold", fontSize=11, leading=15, leftIndent=0, spaceBefore=7, textColor=NAVY)
TOC2 = ParagraphStyle("toc2", fontName="Serif", fontSize=10, leading=13, leftIndent=18, firstLineIndent=0)
TOC3 = ParagraphStyle("toc3", fontName="Serif", fontSize=9, leading=11.5, leftIndent=36, textColor=GREY)

# ---------------------------------------------------------------- text cleaning
AI_WORDS = re.compile(r"\b(grok|chatgpt|claude|gemini|anthropic|openai|xai|copilot|same assistant|other AI builds?)\b", re.I)
BANNER = re.compile(r"^>\s*\*\*PROPRIETARY")


def clean_lines(text: str) -> list[str]:
    """Strips the license banners, branch names and any line that speaks about the tools used to write the code."""
    text = re.sub(r"\bclaude/[\w.-]+", "main", text)
    out, lines, i = [], text.splitlines(), 0
    skip_level = None
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(#{1,6}) ", ln)
        if m:
            lvl = len(m.group(1))
            if skip_level is not None and lvl <= skip_level:
                skip_level = None
            if skip_level is None and AI_WORDS.search(ln):
                skip_level = lvl
        if skip_level is not None:
            i += 1; continue
        if BANNER.match(ln):
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                i += 1
            continue
        if AI_WORDS.search(ln):
            ind = len(ln) - len(ln.lstrip())
            i += 1
            if re.match(r"^\s*(-|\d+\.) ", ln):            # a list item: its indented children go with it
                while i < len(lines) and lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) > ind:
                    i += 1
            continue
        out.append(ln); i += 1
    return out


def glyphs(t: str, cmap: set) -> str:
    return "".join(c if ord(c) < 128 or ord(c) in cmap or ord(c) not in SYM_CMAP else f'<font name="Sym">{c}</font>' for c in t)


def inline(t: str) -> str:
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    codes = []

    def keep(m):
        codes.append(m.group(1)); return f"\x00{len(codes) - 1}\x00"
    t = re.sub(r"`([^`]+)`", keep, t)
    t = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"(?<![\w_])_(?![\s_])([^_]+?)(?<![\s_])_(?![\w_])", r"<i>\1</i>", t)
    t = glyphs(t, SERIF_CMAP)
    return re.sub(r"\x00(\d+)\x00", lambda m: '<font name="Mono" size="8.6">' + glyphs(codes[int(m.group(1))], MONO_CMAP) + "</font>", t)


# ---------------------------------------------------------------- flowables
class Marker(Flowable):
    """Zero-size flowable that tells the document something when it is drawn (a chapter starts, the body starts)."""

    def __init__(self, kind, **kw):
        super().__init__(); self.kind, self.kw = kind, kw

    def wrap(self, *a):
        return 0, 0

    def draw(self):
        pass


class Heading(Paragraph):
    def __init__(self, text, style, level, toc_text=None, kind="section"):
        super().__init__(text, style)
        self.level, self.toc_text, self.kind = level, toc_text or re.sub(r"<[^>]+>", "", text), kind


class GoldRule(Flowable):
    def __init__(self, width=FW, thick=1.2, space=10):
        super().__init__(); self.width, self.thick, self.space = width, thick, space

    def wrap(self, *a):
        return self.width, self.space

    def draw(self):
        self.canv.setStrokeColor(GOLD); self.canv.setLineWidth(self.thick)
        self.canv.line(0, self.space / 2, self.width, self.space / 2)


def plate(path: Path, caption: str):
    from PIL import Image as PIL
    w, h = PIL.open(path).size
    maxh = FH - 40
    s = min(FW / w, maxh / h)
    img = Image(str(path), w * s, h * s)
    return [CondPageBreak(FH), img, Spacer(1, 6), Paragraph(inline(caption), CAP), PageBreak()]


def figure(path: Path, caption: str):
    """A chart inside the text: the frame's width, kept with its caption."""
    from PIL import Image as PIL
    w, h = PIL.open(path).size
    s = FW / w
    return [KeepTogether([Image(str(path), w * s, h * s), Spacer(1, 3), Paragraph(inline(caption), CAP)]), Spacer(1, 8)]


def table(rows_txt, small=False):
    n = max(len(r) for r in rows_txt)
    rows_txt = [r + [""] * (n - len(r)) for r in rows_txt]
    cs = ParagraphStyle("c2", parent=CELL, fontSize=7.4, leading=9) if small or n > 6 else CELL
    hs = ParagraphStyle("h2c", parent=CELLH, fontSize=7.2) if small or n > 6 else CELLH
    lens = [max(min(len(re.sub(r"[`*]", "", r[j])), 60) for r in rows_txt) for j in range(n)]
    weights = [max(4.0, x) ** 0.85 for x in lens]
    tot = sum(weights)
    widths = [FW * w / tot for w in weights]
    floor = min(30.0, FW / n)
    for _ in range(5):
        short = [k for k, w in enumerate(widths) if w < floor]
        if not short:
            break
        extra = sum(floor - widths[k] for k in short)
        big = sum(w for k, w in enumerate(widths) if k not in short)
        widths = [floor if k in short else w - extra * w / big for k, w in enumerate(widths)]
    data = [[Paragraph(inline(c), hs if k == 0 else cs) for c in r] for k, r in enumerate(rows_txt)]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b8b8b8")),
                           ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f1ea")]),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def wrap_code(lines, width):
    out = []
    for ln in lines:
        ln = ln.replace("\t", "    ")
        while len(ln) > width:
            out.append(ln[:width]); ln = "    ↪ " + ln[width:]
        out.append(ln)
    return out


def code_block(lines, style=CODE, width=104):
    """A shaded code block, cut into page-sized pieces so that long listings flow across pages."""
    lines = wrap_code(lines, width)
    per = 28
    parts = []
    for k in range(0, max(1, len(lines)), per):
        txt = "\n".join(lines[k:k + per])
        txt = glyphs(txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), MONO_CMAP)
        t = Table([[Preformatted(txt, style)]], colWidths=[FW])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f3f1")),
                               ("LINEBEFORE", (0, 0), (0, -1), 2, RULE),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 4),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        parts.append(t)
    return parts


# ---------------------------------------------------------------- markdown to flowables
def md_flow(lines, shift=0, story=None, strip=False):
    """A markdown subset to flowables. Heading level n becomes n - shift (level 1 is reserved for chapters)."""
    story = [] if story is None else story
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1; buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j]); j += 1
            story += code_block(buf); story.append(Spacer(1, 6)); i = j + 1; continue
        if ln.startswith("    ") and ln.strip() and not re.match(r"^\s*(-|\d+\.) ", ln):
            buf = []
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                buf.append(lines[i][4:]); i += 1
            while buf and not buf[-1].strip():
                buf.pop()
            story += code_block(buf); story.append(Spacer(1, 6)); continue
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", ln)
        if m:
            src = BOOK / m.group(2) if (BOOK / m.group(2)).exists() else ROOT / "docs" / m.group(2)
            story += figure(src, m.group(1)) if src.suffix == ".png" else plate(src, m.group(1)); i += 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                story += [table(rows), Spacer(1, 8)]
            continue
        m = re.match(r"^(#{1,6}) (.*)", ln)
        if m:
            j = i + 1                                   # a plate right under a heading goes before it
            while j < len(lines) and (not lines[j].strip() or lines[j].startswith("![")):
                pm = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", lines[j])
                if pm:
                    story += plate(BOOK / pm.group(2), pm.group(1))
                j += 1
            lines = lines[:i + 1] + lines[j:] if j > i + 1 else lines
            lvl = max(2, min(3, len(m.group(1)) - shift + 1))
            txt = m.group(2).strip()
            if strip:                                   # the manual's own numbers give way to the book's
                txt = re.sub(r"^(\d+(\.\d+)*\.?|[A-Z]\.)\s+(?=[A-Z])", "", txt)
            story.append(Heading(inline(txt), H2 if lvl == 2 else H3, lvl)); i += 1; continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip(">").strip()); i += 1
            story.append(Paragraph(inline(" ".join(buf)), NOTE)); continue
        if re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", ln):
            story.append(Spacer(1, 6)); i += 1; continue
        mm = re.match(r"^(\s*)(-|\*|\d+\.) (.*)", ln)
        if mm:
            buf = [mm.group(3)]; i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^\s*(-|\*|\d+\.) ", lines[i]) \
                    and not re.match(r"^(#|\||```|>)", lines[i]) and lines[i].startswith(" "):
                buf.append(lines[i].strip()); i += 1
            ind = 14 + 12 * (len(mm.group(1)) // 2)
            bullet = "•" if mm.group(2) in "-*" else mm.group(2)
            story.append(Paragraph(inline(" ".join(buf)), ParagraphStyle("li", parent=BODY, leftIndent=ind + 6, bulletIndent=ind - 8,
                                   spaceAfter=3, alignment=TA_LEFT), bulletText=bullet))
            continue
        if not ln.strip():
            i += 1; continue
        buf = [ln]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||```|>|!\[|\s*(-|\*|\d+\.) |-{3,})", lines[i]) \
                and not lines[i].startswith("    "):
            buf.append(lines[i]); i += 1
        story.append(Paragraph(inline(" ".join(x.strip() for x in buf)), BODY))
    return story


# ---------------------------------------------------------------- sources
def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def split_h1(text):
    """{title: lines} for a file with several level-1 chapters."""
    parts, cur = {}, None
    for ln in clean_lines(text):
        m = re.match(r"^# (.*)", ln)
        if m:
            cur = m.group(1).strip(); parts[cur] = []
        elif cur:
            parts[cur].append(ln)
    return parts


def manual_sections():
    """The manual, cut at its level-2 headings: {short title: lines}."""
    secs, cur = {}, None
    for ln in clean_lines(read("docs/OMNI_COMPASS_MANUAL.md")):
        m = re.match(r"^## (.*)", ln)
        if m:
            cur = re.sub(r"^\d+\.\s*", "", m.group(1).strip()); secs[cur] = []
        elif re.match(r"^# ", ln):
            cur = None
        elif cur:
            secs[cur].append(ln)
    return secs


def doc_body(rel):
    """A repository document: (its own title, its lines without the title)."""
    lines = clean_lines(read(rel))
    title = None
    for k, ln in enumerate(lines):
        if ln.startswith("# "):
            title = ln[2:].strip(); lines = lines[:k] + lines[k + 1:]; break
    return title, lines


THEORY = split_h1((BOOK / "THEORY.md").read_text())
DECL = split_h1((BOOK / "DECLARATION.md").read_text())
MAN = manual_sections()

# Each chapter: (title, source). Source: ("T", key) theory; ("D", key) declaration; ("M", key) manual section;
# ("F", path) a repository document; ("FS", [paths]) several documents in one chapter; ("X", name) generated here.
OUTLINE = [
    ("PART", "The Philosophy and the Theory",
     "Where Omni-Compass comes from: the closed circle, the four pieces, the compass and the basins. The engineering in "
     "the rest of the book is this idea made exact."),
    ("What Omni-Compass Is", ("M", "What Omni-Compass Is")),
    ("The Unified Circle Principle", ("T", "The Unified Circle Principle")),
    ("The Four-Piece Engine", ("T", "The Four-Piece Engine")),
    ("The Compass", ("T", "The Compass")),
    ("Basins, Polarity and the Dual-Basin Engine", ("T", "Basins, Polarity and the Dual-Basin Engine")),
    ("PART", "The Mathematics",
     "Eight equations, one control law, and the proofs, audits and declarations that hold them fixed."),
    ("The Canonical Declaration", ("D", "The Canonical Declaration")),
    ("The Engine: Eight Equations and One Control Law", ("M", "The Engine: Eight Equations and One Control Law")),
    ("The Canonical Engine", ("F", "docs/CANONICAL_ENGINE.md")),
    ("The Closed Circle: Why It Cannot Leave Its Bowl", ("M", "The Closed Circle: Why It Cannot Leave Its Bowl")),
    ("Closing the Circle in the Engine", ("T", "Closing the Circle in the Engine")),
    ("The Tracking Theorem", ("F", "docs/TRACKING_THEOREM.md")),
    ("The Conveyance Law", ("F", "docs/CONVEYANCE_LAW.md")),
    ("Formal Status of the Mathematics", ("F", "docs/FORMAL_STATUS.md")),
    ("The Mechanism of Action", ("F", "docs/MECHANISM_OF_ACTION.md")),
    ("The Engines and Their Audit", ("FS", ["docs/ENGINES.md", "docs/ENGINE_AUDIT.md"])),
    ("PART", "The Physics: the Bowl and the Nervous System",
     "Push and pull, the band and its cushions, the physics of a processor, and the two-way wires that carry the "
     "force from the brain to every muscle and back."),
    ("The Bowl: Push, Pull and the Two Forces", ("M", "The Bowl: Push, Pull and the Two Forces")),
    ("The Physics of a Processor", ("T", "The Physics of a Processor")),
    ("The Two-Way Nervous System", ("M", "The Two-Way Nervous System")),
    ("The Nervous System in Detail", ("FS", ["docs/TWO_WAY_NERVOUS_SYSTEM.md", "NERVOUS.md"])),
    ("PART", "The Body: Muscles, Realms and Organisms",
     "Six hundred and fifty-six muscles in four realms, stacked into six organisms, and every gauge used to judge "
     "them."),
    ("The Muscles, the Realms and the Six Organisms", ("M", "The Muscles, the Realms and the Six Organisms")),
    ("The Four Realms", ("F", "docs/REALMS.md")),
    ("The Realm Muscles", ("F", "docs/REALM_MUSCLES.md")),
    ("The Domain Map", ("F", "docs/DOMAIN_MAP.md")),
    ("The Problem Map", ("F", "docs/PROBLEM_MAP_2026-09.md")),
    ("The Six Organisms and the Benchmark Grid", ("T", "The Six Organisms and the Benchmark Grid")),
    ("The Metrics Catalog", ("F", "docs/METRICS_CATALOG.md")),
    ("PART", "The Harness and the Wiring",
     "The universal plug, the adapters, the wire check, and the step-by-step work of wiring Omni-Compass onto a "
     "running stack."),
    ("The Plug, the Adapters and the Wire Check", ("M", "The Plug, the Adapters and the Wire Check")),
    ("The Harness", ("F", "HARNESS.md")),
    ("The Wiring Guide", ("F", "docs/WIRING_GUIDE.md")),
    ("Before You Start, and the Eight Levels", ("M", "Before You Start, and the Eight Levels")),
    ("Stack by Stack", ("M", "Stack by Stack")),
    ("The Integration Manual", ("F", "docs/INTEGRATION_MANUAL.md")),
    ("Running the GPU Benchmark", ("F", "docs/GPU_RUN_GUIDE.md")),
    ("PART", "Operating It",
     "The OFF switch, the rules the governor obeys, the log it keeps, and the care of a running installation."),
    ("The OFF Switch, the Rules, and the Log", ("M", "The OFF Switch, the Rules, and the Log")),
    ("Maintenance, Upgrades and Security", ("M", "Maintenance, Upgrades and Security")),
    ("The Operator Manual", ("F", "docs/OPERATOR_MANUAL.md")),
    ("PART", "Proving It",
     "Paired runs, receipts, rules written before the runs, and every result to date with its evidence class.",
     "empirical_validation"),
    ("The Dossier: Every Result in One Place", ("F", "docs/DOSSIER.md")),
    ("Paired Runs and Receipts on Your Own System", ("M", "Paired Runs and Receipts on Your Own System")),
    ("Evidence Classes and How to Read a Result", ("M", "Evidence Classes and How to Read a Result")),
    ("Results to Date", ("M", "Results to Date")),
    ("The Pilot Protocol and Kit", ("FS", ["docs/PILOT_PROTOCOL.md", "docs/PILOT_KIT.md"])),
    ("The GPU Bench", ("F", "docs/GPU_BENCH.md")),
    ("The GPU Preregistration", ("F", "docs/GPU_PREREGISTRATION.md")),
    ("The Realms Preregistration", ("F", "docs/REALMS_PREREGISTRATION.md")),
    ("The Bowl Law on Real Kubernetes: Preregistration", ("F", "docs/K8S_BOWL_PREREGISTRATION.md")),
    ("The Evidence Ledger", ("F", "docs/EVIDENCE_LEDGER.md")),
    ("The Claims Register", ("F", "docs/CLAIMS_REGISTER.md")),
    ("The Benchmark Report", ("F", "docs/BENCHMARK_REPORT.md")),
    ("The Referee Report", ("F", "docs/OMNICOMPASS_ABC_REPORT.md")),
    ("Comparison with Existing Controllers", ("F", "docs/COMPARISON.md")),
    ("The State of Play", ("F", "STATE_OF_PLAY.md")),
    ("PART", "Value, License and History",
     "What a receipt is worth, how the license is priced against it, how the code is sealed, and how Omni-Compass came "
     "to be."),
    ("Where the Value Comes From", ("M", "Where the Value Comes From")),
    ("The Economics of a Receipt", ("T", "The Economics of a Receipt")),
    ("The Buyer Edition", ("F", "docs/OMNICOMPASS_BUYER_EDITION.md")),
    ("Due Diligence", ("F", "docs/DUE_DILIGENCE.md")),
    ("License and Commercial Terms", ("M", "License and Commercial Terms")),
    ("Python, C++ and the Seal", ("M", "Python, C++ and the Seal")),
    ("The Founder's Working Notes", ("F", "docs/HANDOFF_CHAPTER.md")),
    ("History", ("F", "docs/HISTORY.md")),
    ("BACK", None),
    ("Glossary", ("M", "Glossary")),
    ("Appendix A. Command Reference", ("M", "Appendix A - Command Reference")),
    ("Appendix B. File Map", ("M", "Appendix B - File Map")),
    ("Appendix C. The Equations in Full", ("M", "Appendix C - The Equations in Full")),
    ("Appendix D. Metrics", ("M", "Appendix D - Metrics")),
    ("Appendix E. Troubleshooting", ("M", "Appendix E - Troubleshooting")),
    ("Appendix F. Evidence Map", ("M", "Appendix F - Evidence Map")),
    ("Appendix G. The 656 Muscles", ("X", "catalog")),
    ("Appendix H. Source of the Engine", ("X", "source")),
    ("Appendix I. The License", ("X", "license")),
    ("Contact", ("X", "contact")),
]

# Manual section number -> book chapter number, so that "section 14" in the manual reads "Chapter 44" in the book.
MAN_NUM = {}
for m in re.finditer(r"^## (\d+)\. (.*)$", read("docs/OMNI_COMPASS_MANUAL.md"), re.M):
    MAN_NUM[int(m.group(1))] = m.group(2).strip()


def source_listing(rel):
    lines = read(rel).splitlines()
    return [Heading(inline(f"`{rel}`"), H2, 2, toc_text=rel), Paragraph(inline(f"{len(lines)} lines."), CAP), Spacer(1, 4),
            *code_block(lines, SRC, 118), Spacer(1, 10)]


def catalog_flow():
    rows = list(csv.DictReader(open(ROOT / "realms" / "catalog.csv", encoding="utf-8")))
    intro = ("Every muscle Omni-Compass governs in the six organisms, by number. Family is the kind of machine; realms "
             "are the realms the muscle belongs to (a muscle in more than one realm is counted once in the tower of 656 "
             "and once per realm in the stack of 1,226); template is the plant model that stands for it in simulation; "
             "knob is the kind of setting the governor moves. Source: `realms/catalog.csv`.")
    short = {"compute_ai_cloud": "Compute", "physics_robotics_autonomous": "Physics",
             "energy_facility_industrial": "Energy", "distribution_specialized": "Distribution"}
    story = [Paragraph(inline(intro), BODY), Spacer(1, 6)]
    counts = {}
    for r in rows:
        for x in r["realms"].split(";"):
            counts[x] = counts.get(x, 0) + 1
    story.append(table([["Realm", "Muscles"]] + [[short.get(k, k), f"{v:,}"] for k, v in counts.items()] +
                       [["Stack (every duplicate kept)", f"{sum(counts.values()):,}"], ["Tower (every muscle once)", f"{len(rows):,}"]]))
    story.append(Spacer(1, 10))
    data = [["#", "Family", "Muscle", "Realms", "Template", "Knob"]]
    for r in sorted(rows, key=lambda r: (not r["muscle_id"].isdigit(), int(re.sub(r"\D", "", r["muscle_id"]) or 0))):
        data.append([r["muscle_id"], r["family"], r["muscle"].replace("_", " "),
                     ", ".join(short.get(x, x) for x in r["realms"].split(";")), r["template"].replace("_", " "), r["knob"]])
    t = Table([[Paragraph(inline(c), ParagraphStyle("cc", parent=CELL, fontSize=7, leading=8.4) if k else
                          ParagraphStyle("ch", parent=CELLH, fontSize=7)) for c in row] for k, row in enumerate(data)],
              colWidths=[0.07 * FW, 0.27 * FW, 0.25 * FW, 0.17 * FW, 0.14 * FW, 0.10 * FW], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c0c0c0")), ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f1ea")]),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)
    return story


def special(name):
    if name == "catalog":
        return catalog_flow()
    if name == "source":
        intro = ("The engine, the bowl law, the bowl on every muscle, the two-wire GPU governor, the plug adapter and the "
                 "nervous system, printed in full from the repository so that the book and the code can be read side by "
                 "side. The engine file is sealed: its fingerprint is in `results/SEAL.json`, and `verify.py` fails if a "
                 "byte of it changes.")
        story = [Paragraph(inline(intro), BODY)]
        for rel in ["omnicompass/core.py", "omnicompass/bowl.py", "realms/bowl_arm.py", "omni_controller/gpu_bowl.py",
                    "omnicompass/adapter.py", "omnicompass/nervous_system.py"]:
            story += source_listing(rel)
        return story
    if name == "license":
        lines = [ln for ln in read("LICENSE").splitlines()]
        return [Paragraph(inline("The license under which this book and the software are made available, as it stands in "
                                 "the file `LICENSE` at the root of the repository."), BODY), *code_block(lines, CODE, 104)]
    if name == "contact":
        return md_flow([
            "Licensing, pilots, evaluations and the Omni-Compass Enterprise License:", "",
            "**The Omni-Compass LLC**", "", "Owner and developer: AJ Dubra", "", "www.omni-compass.com", "",
            "Repository: github.com/The-Omni-Compass-LLC/The-Omni-Compass", "",
            "Any use beyond evaluation and simulation requires a signed, paid Omni-Compass Enterprise License. "
            "Write to The Omni-Compass LLC before any production use."])
    raise KeyError(name)


def renumber(lines):
    """The manual's "section 14" becomes the book's "Chapter 38"."""
    txt = "\n".join(lines)
    txt = re.sub(r"\bsections? (\d+)\b(?!\.\d)",
                 lambda m: f"Chapter {CHAPNUM.get(MAN_NUM.get(int(m.group(1)), ''), m.group(1))}", txt)
    return txt.splitlines()


def chapter_flow(src):
    kind, key = src
    if kind == "T":
        return md_flow(THEORY[key], shift=1)
    if kind == "D":
        return md_flow(DECL[key], shift=1)
    if kind == "M":
        lines = MAN[key]
        return md_flow(renumber(lines), shift=2, strip=True)
    if kind == "F":
        return md_flow(doc_body(key)[1], shift=1)
    if kind == "FS":
        story = []
        for rel in key:
            t, body = doc_body(rel)
            story.append(Heading(inline(t or rel), H2, 2))
            md_flow(body, shift=0, story=story)
        return story
    if kind == "X":
        return special(key)
    raise KeyError(kind)


CHAPNUM = {}
n = 0
for item in OUTLINE:
    if item[0] not in ("PART", "BACK") and not item[0].startswith(("Appendix", "Glossary", "Contact")):
        n += 1; CHAPNUM[item[0]] = n
        if item[1][0] == "M":
            CHAPNUM[item[1][1]] = n

# ---------------------------------------------------------------- document


class Book(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=letter, leftMargin=INNER, rightMargin=OUTER, topMargin=TOP,
                         bottomMargin=BOTTOM, title="The Omni-Compass Manual", author="The Omni-Compass LLC",
                         subject="The governor, its mechanism, physics and philosophy, and how to wire it onto your stack",
                         creator="The Omni-Compass LLC")
        self.body_start = None
        self.chapter = ""
        self.part = ""
        self.no_head = set()
        self.frame = Frame(INNER, BOTTOM, FW, FH, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        full = Frame(0, 0, PW, PH, id="full", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate("cover", [full], onPage=self.cover),
            PageTemplate("body", [self.frame], onPage=self.mirror, onPageEnd=self.decorate),
            PageTemplate("back", [Frame(0, 0, PW, PH, id="full2", leftPadding=0, rightPadding=0, topPadding=0,
                                        bottomPadding=0)], onPage=self.back),
        ])
        self.in_part = False
        self._hseq = 0

    def beforeDocument(self):
        self.body_start, self.chapter, self.no_head, self.in_part, self._hseq = None, "", set(), False, 0

    # mirrored margins: odd pages are right-hand pages, the gutter is on the inside
    def mirror(self, c, d):
        x = INNER if d.page % 2 else OUTER
        for f in self.pageTemplate.frames:
            f._x1 = x; f._geom()

    def toc_label(self, page):
        b = getattr(self, "final_body_start", None)
        return roman(page) if b is None or page < b else str(page - b + 1)

    def label(self, page):
        if self.body_start is None or page < self.body_start:
            return roman(page)
        return str(page - self.body_start + 1)

    def decorate(self, c, d):
        p = d.page
        if p in self.no_head:
            return
        c.saveState()
        right = p % 2 == 1
        x0, x1 = (INNER, PW - OUTER) if right else (OUTER, PW - INNER)
        if self.body_start is not None and p >= self.body_start and self.chapter:
            c.setFont("Sans", 7.8); c.setFillColor(GREY)
            if right:
                c.drawRightString(x1, PH - 0.6 * inch, self.chapter.upper()[:90])
            else:
                c.drawString(x0, PH - 0.6 * inch, "THE OMNI-COMPASS MANUAL")
            c.setStrokeColor(RULE); c.setLineWidth(0.5); c.line(x0, PH - 0.66 * inch, x1, PH - 0.66 * inch)
        c.setFont("Serif", 9.5); c.setFillColor(INK)
        lab = self.label(p)
        (c.drawRightString if right else c.drawString)(x1 if right else x0, 0.55 * inch, lab)
        c.setFont("Serif-Italic", 6.8); c.setFillColor(GREY)
        c.drawCentredString((x0 + x1) / 2, 0.55 * inch, "Copyright © 2026 The Omni-Compass LLC. Evaluation and "
                            "simulation use only. US patent, copyright and trademark applications filed.")
        c.restoreState()

    def cover(self, c, d):
        c.setFillColor(colors.HexColor("#03040a")); c.rect(0, 0, PW, PH, fill=1, stroke=0)
        img = PLATES / "cover.jpg"; w, h = 1024, 1536; s = PH / h
        c.drawImage(str(img), (PW - w * s) / 2, 0, w * s, PH)

    def back(self, c, d):
        if d.page % 2:                       # the back cover is a left-hand page; an odd page here is the blank before it
            return
        c.setFillColor(colors.HexColor("#03040a")); c.rect(0, 0, PW, PH, fill=1, stroke=0)
        img = PLATES / "back_cover.jpg"; w, h = 1024, 1536; s = (PH - 0.9 * inch) / h
        c.drawImage(str(img), (PW - w * s) / 2, 0.9 * inch, w * s, h * s)
        c.setFillColor(colors.HexColor("#d9c79a")); c.setFont("Serif-Bold", 11)
        c.drawCentredString(PW / 2, 0.55 * inch, "THE OMNI-COMPASS LLC  ·  www.omni-compass.com")
        c.setFont("Serif", 7.5)
        c.drawCentredString(PW / 2, 0.36 * inch, "US patent, copyright and trademark applications filed. Evaluation and "
                            "simulation use only; all other use requires a signed, paid Omni-Compass Enterprise License.")

    def afterFlowable(self, f):
        if isinstance(f, Marker):
            if f.kind == "body":
                self.body_start = self.final_body_start = self.page
            elif f.kind == "nohead":
                self.no_head.add(self.page)
            elif f.kind == "chapter":
                self.chapter = f.kw["title"]
                if f.kw.get("opener"):
                    self.no_head.add(self.page)
            return
        if isinstance(f, Heading):
            if f.level == 3:
                return
            self._hseq += 1
            key = f"h{self._hseq}"
            self.canv.bookmarkPage(key)
            if f.kind == "part":
                self.in_part = True
                lvl = 0
            elif f.kind == "chapter":
                lvl = 1 if self.in_part else 0
            else:
                lvl = 2 if self.in_part else 1
            self.canv.addOutlineEntry(re.sub(r"<[^>]+>", "", f.toc_text)[:120], key, level=lvl, closed=lvl >= 1)
            if f.kind in ("part", "chapter"):
                self.notify("TOCEntry", (0 if f.kind == "part" or not self.in_part else 1, f.toc_text, self.page, key))


def roman(n):
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"),
            (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s; n -= v
    return out


def recto(doc):
    return [PageBreak(), _ToRecto(doc)]


class _ToRecto(Flowable):
    def __init__(self, doc, even=False):
        super().__init__(); self.doc = doc; self.want = 0 if even else 1

    def wrap(self, aw, ah):
        if self.doc.page % 2 != self.want:
            self.doc.no_head.add(self.doc.page)
            return aw, ah + 1          # does not fit: forces a page break, leaving this page blank
        return 0, 0

    def split(self, aw, ah):
        if self.doc.page % 2 != self.want:
            return [_Blank(), PageBreak()]
        return []

    def draw(self):
        pass


class _Blank(Flowable):
    def wrap(self, *a):
        return 0, 0

    def draw(self):
        pass


def front_matter(doc):
    s = []
    # cover, then the inside of the cover left blank
    s += [NextPageTemplate("body"), Spacer(1, 1), PageBreak(), Marker("nohead"), Spacer(1, 1), PageBreak()]
    # half title
    s += [Marker("nohead"), Spacer(1, 2.6 * inch), Paragraph("THE OMNI-COMPASS MANUAL", ParagraphStyle(
        "ht", fontName="Serif-Bold", fontSize=22, leading=28, alignment=TA_CENTER, textColor=NAVY)), PageBreak()]
    s += [Marker("nohead"), Spacer(1, 1), PageBreak()]
    # title page
    big = ParagraphStyle("tt", fontName="Serif-Bold", fontSize=34, leading=40, alignment=TA_CENTER, textColor=NAVY)
    sub = ParagraphStyle("st", fontName="Serif-Italic", fontSize=15, leading=20, alignment=TA_CENTER, textColor=INK)
    s += [Marker("nohead"), Spacer(1, 1.3 * inch), Paragraph("THE OMNI-COMPASS", big), Paragraph("MANUAL", big),
          Spacer(1, 14), GoldRule(FW, 1.5, 14),
          Paragraph("The Governor of Everything:<br/>Its Philosophy, Its Mathematics, Its Physics,<br/>and How to Wire It "
                    "onto Your Stack", sub), Spacer(1, 0.4 * inch),
          Image(str(PLATES / "compass_rose.jpg"), 2.3 * inch, 2.3 * inch * 1536 / 1024), Spacer(1, 0.35 * inch),
          Paragraph("AJ Dubra", ParagraphStyle("au", fontName="Serif-Bold", fontSize=14, alignment=TA_CENTER, leading=18)),
          Paragraph("Owner and Developer", CENTER), Spacer(1, 0.3 * inch),
          Paragraph("THE OMNI-COMPASS LLC", ParagraphStyle("pub", fontName="Sans-Bold", fontSize=11, alignment=TA_CENTER,
                                                           textColor=GOLD, leading=14)),
          Paragraph(EDITION, CENTER), PageBreak()]
    # copyright page
    cp = ParagraphStyle("cp", parent=BODY, fontSize=8.8, leading=11.6, alignment=TA_LEFT, spaceAfter=7)
    s += [Marker("nohead"), Spacer(1, 2.2 * inch)]
    for t in [
        "<b>The Omni-Compass Manual</b><br/>The Governor of Everything: Its Philosophy, Its Mathematics, Its Physics, and "
        "How to Wire It onto Your Stack<br/>" + EDITION,
        "Copyright © 2026 The Omni-Compass LLC. All rights reserved. No part of this book may be reproduced, stored "
        "or transmitted in any form or by any means, except as allowed by the Omni-Compass Evaluation License, without "
        "the written permission of The Omni-Compass LLC.",
        FILED,
        "“Omni-Compass”, the Omni-Compass rose and the related names and marks are trademarks of The "
        "Omni-Compass LLC. Other names that appear in this book are the property of their owners and are used only to "
        "identify the systems Omni-Compass works with.",
        "<b>License.</b> This book and the software it describes are proprietary and are not open source "
        "(SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0). They may be used only to evaluate "
        "Omni-Compass and to reproduce its published results, in simulation and on systems the reader owns or controls. "
        "Any commercial use, commercialization, monetization, production use, redistribution, hosted or managed "
        "service, or incorporation into any product or service requires a written Omni-Compass Enterprise License, "
        "signed by The Omni-Compass LLC and paid for. The full terms are printed in Appendix I.",
        "<b>Disclaimer.</b> The software is provided “as is”, without warranty of any kind. Every result in "
        "this book carries its evidence class. A simulated result is a statement about a model; a software benchmark "
        "is a statement about the software it ran on; only a hardware meter speaks for hardware. Nothing in this book "
        "is a promise of a particular saving on a particular system: the only number that applies to a system is the "
        "one its own paired runs produce, on its own receipt.",
        "Front cover: the Omni-Compass identity plate. Back cover: the Omni-Compass unified control authority. Plates "
        "1 to 19: the founder's plates of the theory.",
        "Set in Liberation Serif and DejaVu Sans Mono. Built from the repository by <font name='Mono' size='8'>"
        "docs/book/build_book.py</font>; the book and the code change in the same commit.",
        "The Omni-Compass LLC · www.omni-compass.com"]:
        s.append(Paragraph(t, cp))
    s.append(PageBreak())
    return s


def chapter_opener(num, title, kicker=None):
    k = kicker or f"CHAPTER {num}"
    return [Marker("chapter", title=title, opener=True), Spacer(1, 0.9 * inch), Paragraph(k, KICK),
            Heading(inline(title), H1, 1, toc_text=(f"{num}. {title}" if num else title), kind="chapter"),
            GoldRule(FW, 1.2, 16), Spacer(1, 6)]


def front_chapter(doc, title, lines):
    return recto(doc) + [Marker("chapter", title=title, opener=True), Spacer(1, 0.9 * inch),
                         Heading(inline(title), H1, 1, kind="chapter"), GoldRule(FW, 1.2, 16)] + md_flow(renumber(lines), shift=2, strip=True)


PREFACE = """I wrote this book so that whoever connects Omni-Compass to a running system understands what they are
connecting: not only which wire goes where, but why the governor behaves the way it does, where its law comes from,
and how to prove on their own system what it does for them.

The book is in eight parts, and it can be read in two ways.

| You are | Read |
|---|---|
| CEO, board member, investor | the Foreword, the Executive Summary, Part One, the Results to Date, and Part Eight |
| CTO, architect, head of platform | Parts One to Four, then the eight wiring levels in Part Five, then Part Seven |
| The engineer wiring it | everything, in order. Do not skip the wire check or the watch level |
| Auditor, diligence team | Part Two (the mathematics), Part Seven (the proof), Appendices C, F and H |

**Part One, the philosophy and the theory,** sets out the closed circle: a system that is closed, bounded and pulled
toward a center cannot run away, and everything it does is a return. **Part Two, the mathematics,** gives the eight
equations and the control law that make the circle exact, with the theorem, the declaration and the audits that hold
them fixed. **Part Three, the physics,** brings the law into the machine: the bowl, push and pull, the band and its
cushions, the physics of a processor, and the two-way nervous system. **Part Four, the body,** lays out the 656
muscles, the four realms and the six organisms. **Part Five, the harness and the wiring,** is the universal plug and
the step-by-step work of wiring Omni-Compass onto a stack. **Part Six, operating it,** is the OFF switch, the rules
and the log. **Part Seven, proving it,** is every rule written before a run and every result after it. **Part Eight**
is value, the license, the seal and the history.

**Conventions.** `Code` is a command, file or switch exactly as typed. "Native" means a system as it runs today,
without Omni-Compass. "Muscle" means any machine, service or controller Omni-Compass can read and set. "Knob" or
"lever" is one setting on a muscle. "The band" is a knob's or a service reading's safe range. A step that writes to a
system is marked **WRITES**. Every result carries its evidence class: T for a theorem, V for verification of the code,
S for simulation, L for live software, P for a physical meter.

Some chapters gather documents that were written as the work went on, each at the moment its result came in. They
are kept as they were written, because the record of how a result was reached is part of the proof. Where two
chapters give different figures for the same thing, the later run and the State of Play govern."""


def build():
    doc = Book(OUT_PDF)
    story = front_matter(doc)
    # contents
    toc = TableOfContents(levelStyles=[TOC1, TOC2, TOC3], dotsMinLevel=1, formatter=doc.toc_label)
    story += recto(doc) + [Marker("nohead"), Spacer(1, 0.5 * inch), Paragraph("Contents", H1), GoldRule(FW, 1.2, 16), toc]
    plates_list = [ln for ln in ((BOOK / "THEORY.md").read_text() + (BOOK / "DECLARATION.md").read_text()).splitlines()
                   if ln.startswith("![")]
    plates_list.append("![Plate 19. Empirical validation, experimental pathways, and the discipline of proof](plates/empirical_validation.jpg)")
    story += recto(doc) + [Marker("nohead"), Spacer(1, 0.5 * inch), Paragraph("List of Plates", H1), GoldRule(FW, 1.2, 16)]
    for ln in plates_list:
        story.append(Paragraph(inline(re.match(r"!\[([^\]]*)\]", ln).group(1)), ParagraphStyle("pl", parent=BODY, alignment=TA_LEFT)))
    story += front_chapter(doc, "Foreword", MAN["Foreword"])
    story += front_chapter(doc, "Preface", PREFACE.splitlines())
    story += front_chapter(doc, "Executive Summary", MAN["Executive Summary"])
    md_parts = ["# THE OMNI-COMPASS MANUAL", "", BANNER_MD, "", EDITION, "", FILED, "",
                "The printable book of this text, with its covers, plates, contents and appendices: "
                "`docs/OMNI_COMPASS_MANUAL.pdf`. Built by `docs/book/build_book.py`.", ""]
    for sec in ("Foreword", "Executive Summary"):
        md_parts += [f"## {sec}", ""] + MAN[sec]
    md_parts += ["## Preface", ""] + PREFACE.splitlines()

    part_no = 0
    words = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    first = True
    for item in OUTLINE:
        if item[0] == "PART":
            title, blurb = item[1], item[2]
            story += recto(doc)
            if first:
                story.append(Marker("body")); first = False
            story += [Marker("nohead"), Marker("chapter", title=title, opener=True), Spacer(1, 2.4 * inch),
                      Paragraph(f"PART {words[part_no].upper()}", ParagraphStyle("pk", fontName="Sans-Bold", fontSize=13,
                                alignment=TA_CENTER, textColor=GOLD, leading=16)), Spacer(1, 10),
                      Heading(inline(title), ParagraphStyle("pt", fontName="Serif-Bold", fontSize=30, leading=36,
                              alignment=TA_CENTER, textColor=NAVY), 1, toc_text=f"Part {words[part_no]}. {title}", kind="part"),
                      Spacer(1, 12), GoldRule(FW, 1.5, 14), Spacer(1, 10),
                      Paragraph(inline(blurb), ParagraphStyle("pb", parent=BODY, fontName="Serif-Italic", fontSize=12,
                                leading=17, alignment=TA_CENTER, leftIndent=40, rightIndent=40))]
            md_parts += ["", f"# Part {words[part_no]}. {title}", "", f"*{blurb}*", ""]
            if len(item) > 3:
                story += [PageBreak()] + plate(PLATES / f"{item[3]}.jpg",
                                               "Plate 19. Empirical validation, experimental pathways, and the discipline of proof")[1:-1]
            part_no += 1
            continue
        if item[0] == "BACK":
            story += recto(doc) + [Marker("nohead"), Marker("chapter", title="Back Matter", opener=True),
                                   Spacer(1, 3.0 * inch),
                                   Heading("Back Matter", ParagraphStyle("bm", fontName="Serif-Bold", fontSize=30, leading=36,
                                           alignment=TA_CENTER, textColor=NAVY), 1, toc_text="Back Matter", kind="part"),
                                   GoldRule(FW, 1.5, 14)]
            md_parts += ["", "# Back Matter", ""]
            continue
        title, src = item
        num = CHAPNUM.get(title)
        flow = chapter_flow(src)
        lead = []
        while flow and isinstance(flow[0], CondPageBreak):      # a plate that opens the chapter faces its first page
            lead += flow[1:4] + [PageBreak()]; flow = flow[5:]
        story += [PageBreak(), Marker("chapter", title=title)] + lead
        story += chapter_opener(num, title, None if num else ("APPENDIX" if title.startswith("Appendix") else "BACK MATTER"))
        story += flow
        md_parts += ["", f"## {str(num) + '. ' if num else ''}{title}", ""]
        md_parts += md_text(src)
    # back cover on an even page
    story += [NextPageTemplate("back"), PageBreak(), _ToRecto(doc, even=True), Spacer(1, 1)]
    doc.multiBuild(story)
    OUT_MD.write_text("\n".join(md_parts) + "\n", encoding="utf-8")
    print(OUT_PDF, doc.page, "pages")


def md_text(src):
    kind, key = src
    if kind == "T":
        return THEORY[key]
    if kind == "D":
        return DECL[key]
    if kind == "M":
        return [re.sub(r"^###", "###", ln) for ln in MAN[key]]
    if kind == "F":
        return ["#" + ln if ln.startswith("#") else ln for ln in doc_body(key)[1]]
    if kind == "FS":
        out = []
        for rel in key:
            t, body = doc_body(rel)
            out += [f"### {t}", ""] + ["##" + ln if ln.startswith("#") else ln for ln in body]
        return out
    if kind == "X":
        if key == "catalog":
            return ["The full table of the 656 muscles is in `realms/catalog.csv`."]
        if key == "source":
            return ["The full source of `omnicompass/core.py`, `omnicompass/bowl.py`, `realms/bowl_arm.py`, "
                    "`omni_controller/gpu_bowl.py`, `omnicompass/adapter.py` and `omnicompass/nervous_system.py`."]
        if key == "license":
            return ["The license is the file `LICENSE`."]
        if key == "contact":
            return ["The Omni-Compass LLC. Owner and developer: AJ Dubra. www.omni-compass.com"]
    return []


if __name__ == "__main__":
    build()

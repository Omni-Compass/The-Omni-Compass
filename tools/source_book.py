# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The source code as a PDF, for reading, archiving and copyright deposit.

  python3 tools/source_book.py cpp       # the C++ engine: docs/source/OMNI_COMPASS_CPP_SOURCE.pdf
  python3 tools/source_book.py python    # the Python engine, controllers and harnesses: docs/source/OMNI_COMPASS_PYTHON_SOURCE.pdf

Each PDF has a title page (title, owner, version and date), a contents list with page numbers, and every file in full
with its path, line count and SHA-256 at its head, numbered lines, and the path and page number on every page. The
version is the git commit the files were read from, so the PDF names exactly the code it holds.
"""
from __future__ import annotations

import argparse, datetime, hashlib, subprocess, sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Preformatted, Spacer, Table

ROOT = Path(__file__).resolve().parents[1]
OWNER = "The Omni-Compass LLC"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BOOKS = {
    "cpp": {"title": "Omni-Compass C++20 Engine: Source Code", "out": "docs/source/OMNI_COMPASS_CPP_SOURCE.pdf",
            "about": "The C++20 engine of Omni-Compass: the six-state core, the governor and its allocation laws, the safety "
                     "shield, the HPA replica law, the closure law, the conveyance law, the nervous system, the compass and its "
                     "ledger, and the GPU governor's rules, with the command-line tools that run them. Each law is the twin of "
                     "its Python original and proven equal to it by a parity test (results/SEAL.json).",
            "globs": ["cpp/CMakeLists.txt", "cpp/include/omnicompass/*.hpp", "cpp/src/*.cpp", "cpp/tools/*.cpp", "cpp/scripts/*.py"]},
    "python": {"title": "Omni-Compass Python Engine, Controllers and Harnesses: Source Code",
               "out": "docs/source/OMNI_COMPASS_PYTHON_SOURCE.pdf",
               "about": "The Python engine of Omni-Compass (omnicompass/), its Kubernetes and GPU controllers and muscles "
                        "(omni_controller/), the hardware and power-budget harnesses (hardware/), the tools (tools/), the "
                        "benchmarks (benchmarks/) and the verification entry point (verify.py).",
               "globs": ["omnicompass/*.py", "omni_controller/*.py", "hardware/*.py", "tools/*.py", "benchmarks/*.py", "verify.py"]},
}


def files(book):
    out = []
    for g in BOOKS[book]["globs"]:
        out += sorted(p for p in ROOT.glob(g) if p.is_file() and p.name != "__init__.py" or (p.name == "__init__.py" and p.stat().st_size > 0))
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p); uniq.append(p)
    return uniq


def commit():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def build(book):
    pdfmetrics.registerFont(TTFont("Mono", MONO)); pdfmetrics.registerFont(TTFont("Sans", SANS)); pdfmetrics.registerFont(TTFont("SansB", SANS_B))
    mono_face = TTFont("MonoCheck", MONO).face
    cfg = BOOKS[book]; fs = files(book); ver = commit(); today = datetime.date.today().isoformat()
    code = ParagraphStyle("code", fontName="Mono", fontSize=6.6, leading=8.0)
    head = ParagraphStyle("head", fontName="SansB", fontSize=10, leading=13, spaceAfter=2)
    meta = ParagraphStyle("meta", fontName="Mono", fontSize=6.6, leading=8.5, spaceAfter=6)
    body = ParagraphStyle("body", fontName="Sans", fontSize=10, leading=14, spaceAfter=8)
    title = ParagraphStyle("title", fontName="SansB", fontSize=20, leading=26, spaceAfter=16)
    missing = set()
    texts = {}
    for p in fs:
        t = p.read_text(encoding="utf-8").replace("\t", "    ")
        for ch in set(t):
            if ord(ch) > 126 and ord(ch) not in mono_face.charToGlyph:
                missing.add(ch)
        texts[p] = t
    if missing:
        raise SystemExit(f"font lacks glyphs for {sorted(missing)}; the PDF would show boxes")

    total = sum(t.count("\n") + 1 for t in texts.values())
    state = {"file": ""}

    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont("Sans", 7)
        canvas.drawString(0.6 * inch, 0.4 * inch, cfg["title"] + (f"  |  {state['file']}" if state["file"] else ""))
        canvas.drawRightString(letter[0] - 0.6 * inch, 0.4 * inch, f"page {doc.page}")
        canvas.drawString(0.6 * inch, 0.27 * inch, f"Copyright (c) 2026 {OWNER}. All rights reserved.  Version {ver[:12]}")
        canvas.restoreState()

    out = ROOT / cfg["out"]; out.parent.mkdir(parents=True, exist_ok=True)
    pages = {}

    class Doc(BaseDocTemplate):
        def afterFlowable(self, f):
            if getattr(f, "_file", None):
                state["file"] = f._file; pages.setdefault(f._file, self.page)

    def story(page_map):
        s = [Spacer(1, 1.2 * inch), Paragraph(cfg["title"], title),
             Paragraph(f"Copyright © 2026 {OWNER}. All rights reserved.", body),
             Paragraph(cfg["about"], body),
             Paragraph(f"Version: git commit {ver}<br/>Date: {today}<br/>Files: {len(fs)}<br/>Lines: {total:,}", body),
             Paragraph("Use of this code is governed by the LICENSE file distributed with it.", body), PageBreak(),
             Paragraph("Contents", title)]
        rows = [[str(p.relative_to(ROOT)), f"{texts[p].count(chr(10)) + 1:,} lines", str(page_map.get(str(p.relative_to(ROOT)), ""))] for p in fs]
        tbl = Table(rows, colWidths=[4.6 * inch, 1.2 * inch, 0.8 * inch])
        tbl.setStyle([("FONT", (0, 0), (-1, -1), "Mono", 7.5), ("ALIGN", (1, 0), (-1, -1), "RIGHT")])
        s += [tbl, PageBreak()]
        for p in fs:
            rel = str(p.relative_to(ROOT)); t = texts[p]
            h = Paragraph(rel, head); h._file = rel
            s += [h, Paragraph(f"{t.count(chr(10)) + 1:,} lines   SHA-256 {hashlib.sha256(p.read_bytes()).hexdigest()}", meta)]
            lines = t.split("\n")
            w = len(str(len(lines)))
            numbered = "\n".join(f"{i + 1:>{w}}  {l}" for i, l in enumerate(lines))
            s += [Preformatted(numbered, code, maxLineLength=118, newLineChars="      "), PageBreak()]
        return s

    for _ in range(2):          # pass 1 finds each file's page; pass 2 prints them in the contents
        doc = Doc(str(out), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                  title=cfg["title"], author=OWNER, subject=f"source code, version {ver}")
        doc.addPageTemplates([PageTemplate(frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height)], onPageEnd=footer)])
        found = dict(pages); pages.clear(); state["file"] = ""
        doc.build(story(found))
    print(f"{out.relative_to(ROOT)}: {len(fs)} files, {total:,} lines, version {ver[:12]}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", choices=sorted(BOOKS))
    build(ap.parse_args().book)

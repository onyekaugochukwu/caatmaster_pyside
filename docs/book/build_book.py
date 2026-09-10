#!/usr/bin/env python3
"""Rebuild Audit-Analytics-with-CaatMaster.pdf from index.html.

Requires: google-chrome, poppler-utils (pdftotext, pdfinfo), and pypdf
(``pip install pypdf`` - already in this project's venv).

Two things make this more than a single print-to-pdf call:

1. Two-pass TOC page numbers. The printed table of contents needs real
   page numbers, but those depend on the rendered length of everything
   before them, which depends on the TOC's own size - a chicken-and-egg
   problem. Pass 1 renders with the page-number placeholders blank,
   reads back where every chapter/part/appendix actually landed, then
   pass 2 renders again with those numbers filled in.

2. The cover is rendered as an entirely separate single-page PDF and
   spliced onto the front with pypdf, rather than as part of index.html's
   own print flow. This isn't a style choice - it works around a real
   Chrome --print-to-pdf bug. @page :first { margin: 0 } is silently
   ignored (every page, including the first, gets the base @page
   margin), and every workaround tried for that (negative margins sized
   to cancel the margin, a named @page rule, hiding or removing the
   cover element) either failed to reach the physical edge or corrupted
   Chrome's column-width calculation for every other page in the
   document (confirmed by isolated A/B renders: page count jumping from
   193 to 235+ and line wrap narrowing from ~100 to ~80 characters, from
   CSS changes that should have been inert). A lone single-page,
   single-@page-rule HTML file is a shape Chrome renders correctly with
   no such side effects, so the cover lives there instead and gets
   stitched onto the real book afterward.
"""
import argparse
import html
import re
import subprocess
import tempfile
from pathlib import Path

BOOK = Path(__file__).resolve().parent
OUT_PDF = BOOK / "Audit-Analytics-with-CaatMaster.pdf"

CHROME = [
    "google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
    "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
    "--virtual-time-budget=20000",
]

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]

COVER_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>
  @page { size: letter; margin: 0; }
  html, body { margin: 0; padding: 0; }
  img { width: 8.5in; height: 11in; display: block; }
</style>
</head>
<body>
<img src="caatmaster_cover.png" alt="">
</body></html>
"""


def render(html_path: Path, pdf_path: Path):
    cmd = CHROME + [f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header", f"file://{html_path}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not pdf_path.exists():
        raise RuntimeError(f"render failed for {html_path}:\n{r.stderr}")


def find_page_numbers(pdf_path: Path) -> dict:
    text = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True).stdout
    targets = {}
    for i, page_text in enumerate(text.split("\x0c"), start=1):
        stripped = page_text.lstrip()
        if m := re.match(r"Chapter (\d+)", stripped):
            targets.setdefault(f"ch{m.group(1)}", i)
        elif m := re.match(r"Appendix ([A-Z])", stripped):
            targets.setdefault(f"app{m.group(1).lower()}", i)
        elif m := re.match(r"PART ([IVX]+)\b", stripped):  # .part-label is text-transform: uppercase
            targets.setdefault(f"part{ROMAN.index(m.group(1)) + 1}", i)
    return targets


def build_outline_walk(src: str):
    """Document-order list of (kind, id, title) for parts and chapter/appendix
    sections, used to build a nested outline (parts as parents, chapters and
    appendices as children) after we know each one's page number."""
    walk_re = re.compile(
        r'<div class="part-opener" id="(part\d)">\s*<p class="part-label">(Part [IVX]+)</p>\s*<h2 class="part-title">([^<]+)</h2>'
        r'|'
        r'<section class="chapter" id="(ch\d+|app[a-d])">\s*<p class="chapter-num">([^<]+)</p>\s*<h1 class="chapter-title">([^<]+)</h1>'
    )
    walk = []
    for m in walk_re.finditer(src):
        if m.group(1):
            walk.append(("part", m.group(1), html.unescape(f"{m.group(2)}: {m.group(3)}")))
        else:
            walk.append(("leaf", m.group(4), html.unescape(f"{m.group(5)}: {m.group(6)}")))
    return walk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-tmp", action="store_true", help="don't delete the intermediate PDFs")
    args = parser.parse_args()

    src = (BOOK / "index.html").read_text()
    walk = build_outline_walk(src)
    print(f"outline: {sum(1 for k, _, _ in walk if k == 'part')} parts, "
          f"{sum(1 for k, _, _ in walk if k == 'leaf')} chapters/appendices")

    with tempfile.TemporaryDirectory(prefix="caatmaster_book_build_") as tmp:
        tmp = Path(tmp)

        # ---- pass 1: blank TOC placeholders, render, read back real page numbers
        blanked = re.sub(r'(<span class="toc-print-page" data-target="[^"]+">)[^<]*(</span>)', r"\1\2", src)
        pass1_html = BOOK / "_pass1.html"
        pass1_html.write_text(blanked)
        try:
            pass1_pdf = tmp / "pass1.pdf"
            render(pass1_html, pass1_pdf)
        finally:
            pass1_html.unlink()

        targets = find_page_numbers(pass1_pdf)
        expected = ([f"ch{n}" for n in range(1, 34)] + ["appa", "appb", "appc", "appd"]
                    + [f"part{n}" for n in range(1, 10)])
        missing = [t for t in expected if t not in targets]
        if missing:
            raise RuntimeError(f"could not find page numbers for: {missing}")
        print(f"found all {len(targets)} page numbers")

        # ---- pass 2: fill placeholders with real numbers, render the final body
        def fill(m):
            target = m.group(1)
            return f'<span class="toc-print-page" data-target="{target}">{targets.get(target, "")}</span>'

        filled = re.sub(r'<span class="toc-print-page" data-target="([^"]+)">[^<]*</span>', fill, src)
        pass2_html = BOOK / "_pass2.html"
        pass2_html.write_text(filled)
        try:
            body_pdf = tmp / "body.pdf"
            render(pass2_html, body_pdf)
        finally:
            pass2_html.unlink()

        # ---- cover: isolated render, see module docstring for why
        cover_html = BOOK / "_cover_only.html"
        cover_html.write_text(COVER_HTML)
        try:
            cover_pdf = tmp / "cover.pdf"
            render(cover_html, cover_pdf)
        finally:
            cover_html.unlink()

        # ---- merge: external cover page replaces body.pdf's own (non-full-bleed) page 1
        from pypdf import PdfReader, PdfWriter
        cover_reader = PdfReader(str(cover_pdf))
        body_reader = PdfReader(str(body_pdf))
        writer = PdfWriter()
        writer.add_page(cover_reader.pages[0])
        for p in body_reader.pages[1:]:
            writer.add_page(p)
        print(f"final page count: {len(writer.pages)}")

        # ---- outline / bookmarks: front matter, then Parts (nested chapters/appendices)
        for i, title in enumerate(["Cover", "Title Page", "Copyright", "Contents"]):
            writer.add_outline_item(title, i)

        appendices_added = False
        current_parent = None
        for kind, tid, title in walk:
            idx = targets[tid] - 1
            if kind == "part":
                current_parent = writer.add_outline_item(title, idx)
                continue
            if tid.startswith("app") and not appendices_added:
                appendices_added = True
                current_parent = writer.add_outline_item("Appendices", idx)
            writer.add_outline_item(title, idx, parent=current_parent)

        with open(OUT_PDF, "wb") as f:
            writer.write(f)

        if args.keep_tmp:
            kept = BOOK / "_build_tmp"
            import shutil
            shutil.copytree(tmp, kept, dirs_exist_ok=True)
            print(f"kept intermediate PDFs in {kept}")

    print(f"wrote {OUT_PDF} ({OUT_PDF.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

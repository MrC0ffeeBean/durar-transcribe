"""Build 4x4 survey contact sheets (RTL order: first page top-right) in survey\\.

Usage: python contact.py            -> survey\\sheet01.png ... (16 pages each)
       python contact.py 300 328 x  -> survey\\x.png for an explicit page range
"""
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
COLS, ROWS = 4, 4


def sheet(doc, pages, out, thumb_h=780):
    ims = []
    for n in pages:
        pix = doc[n - 1].get_pixmap(dpi=110)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        s = thumb_h / im.height
        im = im.resize((round(im.width * s), thumb_h), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 70, 30), fill="yellow")
        d.text((6, 6), f"p{n:03d}", fill="black", font_size=22)
        ims.append(im)
    w, h = ims[0].size
    rows = (len(ims) + COLS - 1) // COLS
    out_im = Image.new("RGB", (w * COLS + 6 * (COLS - 1), h * rows + 6 * (rows - 1)), "gray")
    for k, im in enumerate(ims):
        col = COLS - 1 - k % COLS
        out_im.paste(im, (col * (w + 6), (k // COLS) * (h + 6)))
    out_im.save(out, optimize=True)


def main():
    doc = pymupdf.open(ROOT / "source" / "durar.pdf")
    (ROOT / "survey").mkdir(exist_ok=True)
    if len(sys.argv) == 4:
        a, b, name = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
        sheet(doc, range(a, b + 1), ROOT / "survey" / f"{name}.png")
        return
    per = COLS * ROWS
    for i, start in enumerate(range(1, doc.page_count + 1, per), 1):
        pages = range(start, min(start + per, doc.page_count + 1))
        sheet(doc, pages, ROOT / "survey" / f"sheet{i:02d}.png")
        print(f"sheet{i:02d}: p{pages[0]:03d}-p{pages[-1]:03d}", flush=True)


if __name__ == "__main__":
    main()

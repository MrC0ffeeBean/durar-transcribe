"""Render source\\durar.pdf into pages\\pNNN.png (full page) and crops\\pNNN_top/_bot.png.

Idempotent: skips images that already exist. Usage: python render.py [first last]
"""
import sys
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LONG = 1568          # target long edge for every image
DPI = 300
OVERLAP = 0.55       # each crop covers 55% of the page height


def to_image(pix):
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def fit(im, long_edge=LONG):
    w, h = im.size
    s = long_edge / max(w, h)
    return im.resize((round(w * s), round(h * s)), Image.LANCZOS)


def main():
    doc = pymupdf.open(ROOT / "source" / "durar.pdf")
    first, last = 1, doc.page_count
    if len(sys.argv) == 3:
        first, last = int(sys.argv[1]), int(sys.argv[2])
    (ROOT / "pages").mkdir(exist_ok=True)
    (ROOT / "crops").mkdir(exist_ok=True)
    for n in range(first, last + 1):
        full = ROOT / "pages" / f"p{n:03d}.png"
        top = ROOT / "crops" / f"p{n:03d}_top.png"
        bot = ROOT / "crops" / f"p{n:03d}_bot.png"
        if full.exists() and top.exists() and bot.exists():
            continue
        im = to_image(doc[n - 1].get_pixmap(dpi=DPI))
        w, h = im.size
        fit(im).save(full, optimize=True)
        ch = round(h * OVERLAP)
        fit(im.crop((0, 0, w, ch))).save(top, optimize=True)
        fit(im.crop((0, h - ch, w, h))).save(bot, optimize=True)
        print(f"p{n:03d}", flush=True)


if __name__ == "__main__":
    main()

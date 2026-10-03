"""Side-by-side QA images: original book page (right) next to the Word-generated PDF page(s) holding the same text.

Usage: python sidebyside.py out\\durar.pdf master.md 6 66 106 198 --out out\\qa
For each book page N, the DOCX-PDF page with the largest word overlap with N's transcription is chosen
(plus the following page if the text continues there).
"""
import re
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, raw_lines, read_text, split_pages, strip_marks


def words(s):
    s = strip_marks(s)
    s = re.sub(r"[^ء-ي\s]", " ", s)
    return [w for w in s.split() if len(w) > 2]


def render(page, h):
    pix = page.get_pixmap(dpi=150)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def main():
    a = sys.argv[1:]
    out = Path(a[a.index("--out") + 1]) if "--out" in a else ROOT / "out" / "qa"
    if "--out" in a:
        i = a.index("--out")
        del a[i:i + 2]
    docx_pdf, master, pages = a[0], a[1], [int(x) for x in a[2:]]
    out.mkdir(parents=True, exist_ok=True)
    _, mpages = split_pages(raw_lines(read_text(master)))
    mtext = {p: " ".join(lines) for p, _, lines in mpages}
    gen = pymupdf.open(docx_pdf)
    gwords = [set(words(pg.get_text())) for pg in gen]
    src = pymupdf.open(ROOT / "source" / "durar.pdf")
    H = 1400
    for n in pages:
        target = set(words(mtext.get(n, "")))
        scores = [len(target & g) for g in gwords]
        best = max(range(len(scores)), key=lambda i: scores[i])
        picks = [best]
        if best + 1 < len(gen) and scores[best + 1] > 0.3 * scores[best]:
            picks.append(best + 1)
        ims = [render(src[n - 1], H)] + [render(gen[i], H) for i in picks]
        W = sum(im.width for im in ims) + 20 * (len(ims) - 1)
        sheet = Image.new("RGB", (W, H + 40), "white")
        x = W
        labels = [f"book p.{n}"] + [f"DOCX p.{i + 1}" for i in picks]
        for im, lab in zip(ims, labels):
            x -= im.width
            sheet.paste(im, (x, 40))
            ImageDraw.Draw(sheet).text((x + 10, 8), lab, fill="black", font_size=24)
            x -= 20
        path = out / f"sbs_p{n:03d}.png"
        sheet.save(path)
        print(path, "matched DOCX pages", [i + 1 for i in picks], "overlap", scores[best], "/", len(target))


if __name__ == "__main__":
    main()

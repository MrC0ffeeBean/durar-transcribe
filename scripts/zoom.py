"""Render a zoomed region of a PDF page: python zoom.py PAGE x0 y0 x1 y1 out.png [dpi]
Coordinates are fractions (0-1) of page width/height."""
import sys
from pathlib import Path
import pymupdf
ROOT = Path(__file__).resolve().parent.parent
n = int(sys.argv[1]); fx0, fy0, fx1, fy1 = map(float, sys.argv[2:6]); out = sys.argv[6]
dpi = int(sys.argv[7]) if len(sys.argv) > 7 else 400
doc = pymupdf.open(ROOT / "source" / "durar.pdf")
p = doc[n - 1]; r = p.rect
clip = pymupdf.Rect(r.x0 + fx0 * r.width, r.y0 + fy0 * r.height, r.x0 + fx1 * r.width, r.y0 + fy1 * r.height)
p.get_pixmap(dpi=dpi, clip=clip).save(out)

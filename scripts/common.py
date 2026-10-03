"""Shared helpers for the durar transcription pipeline (canonical form, pages, tokens)."""
import json
import re
import sys
import unicodedata
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
N_PAGES = 328
N_BATCHES = 82

MARKER_RE = re.compile(r"^<<<ص:(\d{3})(\+?)>>>$")
FENCE_OPEN = {":::شعر", ":::شعر مشطور", ":::حواشي", ":::مفردات"}
FENCE_CLOSE = ":::"
BLANK_PAGE = "[صفحة فارغة]"
TATWEEL = "ـ"
PARA = "¶"  # token for a line break between blocks / lines

# Arabic-Indic digits <-> ints
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_TO_ASCII = str.maketrans(AR_DIGITS, "0123456789")


def batch_pages(k):
    """Batch k (1..82) -> list of PDF pages (fixed mapping: 4k-3 .. 4k)."""
    return list(range(4 * k - 3, 4 * k + 1))


def batch_name(k):
    return f"b{k:02d}"


def batch_of_path(path):
    m = re.search(r"b(\d{2})", Path(path).name)
    return int(m.group(1)) if m else None


def digits_to_int(s):
    return int(s.translate(_TO_ASCII))


def is_mark(ch):
    """Combining marks (harakat, Quranic small signs) incl. small waw/yeh (Lm)."""
    return unicodedata.category(ch) == "Mn" or ch in "ۥۦ"


def strip_marks(s):
    return "".join(ch for ch in s if not is_mark(ch))


def is_ar_letter(ch):
    return bool(ch) and ("ء" <= ch <= "ي" or ch in "ٱپچڤگی")


def keep_tatweel(s, i):
    """Tatweel kept only (a) carrying a mark (Quranic hamza seat ـَٔ) or (b) in the abbreviation هـ."""
    nxt = s[i + 1] if i + 1 < len(s) else ""
    prv = s[i - 1] if i else ""
    if nxt and is_mark(nxt) and nxt != "ٰ":
        return True
    return prv == "ه" and not is_ar_letter(nxt) and nxt != TATWEEL and not is_ar_letter(s[i - 2] if i > 1 else "")


def drop_tatweel(s):
    """Drop decorative tatweel (see keep_tatweel for the two exceptions)."""
    return "".join(ch for i, ch in enumerate(s) if ch != TATWEEL or keep_tatweel(s, i))


def norm_line(line):
    line = unicodedata.normalize("NFC", line)
    line = drop_tatweel(line)
    line = line.replace(" ", " ").replace("‏", "").replace("‎", "").replace("﻿", "")
    return re.sub(r"[ \t]+", " ", line).strip()


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def raw_lines(text):
    """Normalized non-empty lines (blank lines carry no information in canonical form)."""
    out = []
    for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        ln = norm_line(ln)
        if ln:
            out.append(ln)
    return out


def split_pages(lines):
    """lines -> list of (pageno, cont_flag, [content lines]) ; content before first marker under page None."""
    pages = []
    cur = None
    pre = []
    for ln in lines:
        m = MARKER_RE.match(ln)
        if m:
            cur = (int(m.group(1)), m.group(2) == "+", [])
            pages.append(cur)
        elif cur is None:
            pre.append(ln)
        else:
            cur[2].append(ln)
    return pre, pages


def serialize_page(lines):
    """Canonical serialization of one page's content lines (blank line between blocks;
    single newline inside fences and between table rows)."""
    out = []
    in_fence = False
    prev = None
    for ln in lines:
        if prev is None:
            sep = ""
        elif in_fence and ln != FENCE_CLOSE:
            sep = "\n"
        elif in_fence and ln == FENCE_CLOSE:
            sep = "\n"
        elif prev.startswith("|") and ln.startswith("|"):
            sep = "\n"
        else:
            sep = "\n\n"
        out.append(sep + ln)
        if ln in FENCE_OPEN:
            in_fence = True
        elif ln == FENCE_CLOSE:
            in_fence = False
        prev = ln
    return "".join(out)


def marker(page, cont=False):
    return f"<<<ص:{page:03d}{'+' if cont else ''}>>>"


def canonical(text):
    pre, pages = split_pages(raw_lines(text))
    parts = []
    if pre:
        parts.append(serialize_page(pre))
    for page, cont, lines in pages:
        body = serialize_page(lines)
        parts.append(marker(page, cont) + ("\n\n" + body if body else ""))
    return "\n\n".join(parts) + "\n"


# ---------- tokens ----------

def page_tokens(lines):
    """Content lines of one page -> tokens: whitespace chunks, PARA between lines."""
    toks = []
    for i, ln in enumerate(lines):
        if i:
            toks.append(PARA)
        toks.extend(ln.split(" "))
    return toks


def tokens_to_lines(toks):
    lines, cur = [], []
    for t in toks:
        if t == PARA:
            if cur:
                lines.append(" ".join(cur))
            cur = []
        elif t:
            cur.append(t)
    if cur:
        lines.append(" ".join(cur))
    return lines


def doc_pages(path):
    """path -> dict page -> {'cont': bool, 'lines': [...], 'tokens': [...]} (canonical)."""
    pre, pages = split_pages(raw_lines(read_text(path)))
    out = {}
    for page, cont, lines in pages:
        out[page] = {"cont": cont, "lines": lines, "tokens": page_tokens(lines)}
    return out


def build_doc(pages_dict):
    """dict page -> {'cont', 'lines'} -> canonical text."""
    parts = []
    for page in sorted(pages_dict):
        p = pages_dict[page]
        body = serialize_page(p["lines"])
        parts.append(marker(page, p["cont"]) + ("\n\n" + body if body else ""))
    return "\n\n".join(parts) + "\n"


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- rule: font-drawn small alif over final ى (Lotus Light) ----------
_TYPED = None
_FINAL_YA_DAGGER = re.compile("ى([ً-ٟ]*)ٰ")


def typed_dagger_pages():
    """Pages where a small alif is really typed outside the Quran fonts (ref/typed_dagger_pages.json)."""
    global _TYPED
    if _TYPED is None:
        _TYPED = set(load_json(ROOT / "ref" / "typed_dagger_pages.json", {"pages": []})["pages"])
    return _TYPED


def plain_final_ya(line):
    """Drop a small alif written over final ى outside ﴿…﴾ (CONVENTIONS §2). Returns (line, n_changes)."""
    parts = re.split(r"(﴿[^﴾]*﴾)", line)
    n = 0
    for i, pt in enumerate(parts):
        if not pt.startswith("﴿"):
            parts[i], k = _FINAL_YA_DAGGER.subn(lambda m: "ى" + m.group(1), pt)
            n += k
    return "".join(parts), n

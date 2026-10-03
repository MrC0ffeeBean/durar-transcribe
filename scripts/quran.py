"""Quran cross-check against the Tanzil Uthmani text (ref\\quran-uthmani.txt, CC BY 3.0, tanzil.net).

The printed book is the target; Tanzil is only a cross-check. Used by diff.py (flags on keyer A)
and by apply.py / assemble.py (residual report).

CLI: python quran.py FILE   -> prints the flags for every ﴿…﴾ span in FILE
"""
import difflib
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PARA, ROOT, TATWEEL, doc_pages, is_mark

TANZIL = ROOT / "ref" / "quran-uthmani.txt"
BASMALA = "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ "
WAQF = set("ۖۗۘۙۚۛۜ")
AYAH_NO = re.compile(r"^\(?[٠-٩0-9]+\)?$")


def qnorm(w):
    """Comparison form: NFC, ۡ->ْ, tatweel before dagger alif removed, decorative tatweel removed."""
    w = unicodedata.normalize("NFC", w)
    w = w.replace("ۡ", "ْ").replace(TATWEEL + "ٰ", "ٰ")
    out = []
    for i, ch in enumerate(w):
        if ch == TATWEEL and not (i + 1 < len(w) and is_mark(w[i + 1])):
            continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def skel(w):
    """Letters-only skeleton for locating text (tolerant of alif/hamza/yeh forms)."""
    w = unicodedata.normalize("NFD", w)
    w = "".join(ch for ch in w if not is_mark(ch) and ch != TATWEEL)
    w = w.translate(str.maketrans({"ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و",
                                   "ء": "", "ة": "ه"}))
    return re.sub(r"[^ء-ي]", "", w)


@lru_cache(maxsize=1)
def tanzil_words():
    """Flat list of (sura, aya, word) with waqf signs attached to the preceding word."""
    words = []
    for line in TANZIL.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "|" not in line:
            continue
        s, a, t = line.split("|", 2)
        s, a = int(s), int(a)
        if a == 1 and s not in (1, 9) and t.startswith(BASMALA):
            t = t[len(BASMALA):]
        for w in t.split():
            if all(ch in WAQF for ch in w) and words:
                ps, pa, pw = words[-1]
                words[-1] = (ps, pa, pw + " " + w)
            else:
                words.append((s, a, w))
    return words


@lru_cache(maxsize=1)
def tanzil_index():
    ws = tanzil_words()
    sk = [skel(w.split(" ")[0]) for _, _, w in ws]
    first = {}
    for i, k in enumerate(sk):
        first.setdefault(k, []).append(i)
    return sk, first


def spans_in_tokens(tokens):
    """Yield (start, end) token-index ranges (end exclusive) of ﴿…﴾ spans within one line run."""
    i, n = 0, len(tokens)
    while i < n:
        t = tokens[i]
        p = t.find("﴿")
        if p >= 0:
            if "﴾" in t[p + 1:]:
                yield i, i + 1
                i += 1
                continue
            j = i + 1
            while j < n and tokens[j] != PARA and "﴾" not in tokens[j]:
                j += 1
            if j < n and tokens[j] != PARA:
                yield i, j + 1
                i = j + 1
                continue
        i += 1


def span_words(tokens, start, end):
    """Words of a span with their token index ranges; ayah numbers dropped, waqf-only tokens merged."""
    words = []  # (text, tok_start, tok_end)
    for k in range(start, end):
        t = tokens[k]
        if k == end - 1 and "﴾" in t:          # drop anything glued after the closing bracket, e.g. ﴾(الضحى: ١١)
            t = t[:t.rindex("﴾")]
        if k == start and "﴿" in t:            # and anything glued before the opening one
            t = t[t.index("﴿") + 1:]
        clean = t.replace("﴿", "").replace("﴾", "")
        clean = re.sub(r"\[[^\]]*\]", "", clean)  # a glued reference after ﴾
        clean = clean.strip("،.:؛!؟«»")
        if not clean or AYAH_NO.match(clean):
            continue
        if all(ch in WAQF for ch in clean) and words:
            w, s0, _ = words[-1]
            words[-1] = (w + " " + clean, s0, k + 1)
            continue
        # strip a glued footnote marker
        clean = re.sub(r"\([٠-٩0-9]+\)$", "", clean)
        words.append((clean, k, k + 1))
    return words


def locate(words):
    """Find the Tanzil position for a list of span words. Returns list of aligned pairs
    [(word_idx or None, tanzil_idx or None)] and a status."""
    sk, first = tanzil_index()
    tw = tanzil_words()
    ss = [skel(w.split(" ")[0]) for w, _, _ in words]
    n = len(ss)
    if not n:
        return None, "empty"
    # exact skeleton run
    for i in first.get(ss[0], []):
        if sk[i:i + n] == ss:
            return [(k, i + k) for k in range(n)], "exact"
    # approximate: candidates from any of the first/last 3 words
    cands = set()
    for k in range(min(3, n)):
        for i in first.get(ss[k], []):
            cands.add(i - k)
    for k in range(max(0, n - 3), n):
        for i in first.get(ss[k], []):
            cands.add(i - k)
    best, best_r = None, 0.0
    for c in cands:
        if c < 0:
            continue
        win = sk[c:c + n + 2]
        r = difflib.SequenceMatcher(None, ss, win, autojunk=False).ratio()
        if r > best_r:
            best, best_r = c, r
    if best is None or best_r < 0.6:
        return None, "not_found"
    win = sk[best:best + n + 2]
    pairs = []
    sm = difflib.SequenceMatcher(None, ss, win, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            pairs += [(i1 + d, best + j1 + d) for d in range(i2 - i1)]
        else:
            pairs += [(i, None) for i in range(i1, i2)]
            if tag == "replace":
                pairs += [(None, best + j) for j in range(j1, j2)]
    # drop trailing unmatched tanzil words (window slack)
    while pairs and pairs[-1][0] is None:
        pairs.pop()
    return pairs, f"approx:{best_r:.2f}"


def check_page_tokens(page, tokens):
    """Return list of flags for one page's tokens."""
    tw = tanzil_words()
    flags = []
    for s, e in spans_in_tokens(tokens):
        words = span_words(tokens, s, e)
        pairs, status = locate(words)
        if pairs is None:
            flags.append({"page": page, "kind": "quran_not_found", "a_range": [s, e],
                          "keyed": " ".join(tokens[s:e]), "status": status})
            continue
        refs = sorted({f"{tw[j][0]}:{tw[j][1]}" for _, j in pairs if j is not None})
        for wi, tj in pairs:
            if wi is None:
                continue
            w, t0, t1 = words[wi]
            if tj is None:
                flags.append({"page": page, "kind": "quran_extra_word", "a_range": [t0, t1], "keyed": w,
                              "tanzil": "", "ref": refs[0] if refs else ""})
                continue
            tword = tw[tj][2]
            if qnorm(w) != qnorm(tword):
                kind = "quran_letters" if skel(w) != skel(tword.split(" ")[0]) else "quran_marks"
                flags.append({"page": page, "kind": kind, "a_range": [t0, t1], "keyed": w, "tanzil": tword,
                              "ref": f"{tw[tj][0]}:{tw[tj][1]}"})
        missing = [tw[j][2] for wi, j in pairs if wi is None and j is not None]
        if missing:
            flags.append({"page": page, "kind": "quran_missing_words", "a_range": [s, e],
                          "keyed": " ".join(tokens[s:e]), "tanzil": " ".join(missing), "ref": ", ".join(refs)})
    return flags


def check_file(path):
    flags = []
    for page, p in doc_pages(path).items():
        flags += check_page_tokens(page, p["tokens"])
    return flags


if __name__ == "__main__":
    for f in check_file(sys.argv[1]):
        print(f)

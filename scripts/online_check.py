"""Cross-check a batch against the online texts in ref/online/ (a different edition: hints only, never authority).

Usage:  python scripts/online_check.py bNN [--src keyA|keyB|final]

Aligns the batch's words (keyA by default) with the online text of every section that covers its pages
(ref/online/index.json) and writes diff/bNN.online.json with:
  - w-items: word differences (letters differ after normalizing alif/ya/ta-marbuta forms), with page and context;
  - h-items: contradictory harakat on the same letter (both texts vowel it, with different vowels), only for
    sources that are mostly vocalized. Missing marks are not reported (editions differ in how fully they vowel).
Prints a one-line summary. The adjudicator checks each item against the image.
"""
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, batch_pages, doc_pages, is_mark, save_json  # noqa: E402

ONLINE = ROOT / "ref" / "online"
LATIN = re.compile(r"[A-Za-zÀ-ɏḀ-ỿ]")
WORD = re.compile(r"[ء-غف-يٱـً-ٰٟۖ-ۭۥۦ]+")
SKEL_MAP = str.maketrans({"ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": None})
VOWEL = {"َ": "a", "ً": "a", "ُ": "u", "ٌ": "u", "ِ": "i", "ٍ": "i"}


def skeleton(w):
    return "".join(ch for ch in unicodedata.normalize("NFC", w) if not is_mark(ch)).translate(SKEL_MAP)


def letter_vowels(w):
    """word -> list (one per base letter, tatweel dropped) of the vowel class on it or None."""
    out = []
    for ch in unicodedata.normalize("NFC", w):
        if ch == "ـ":
            continue
        if is_mark(ch):
            if out and ch in VOWEL:
                out[-1] = VOWEL[ch]
        else:
            out.append(None)
    return out


def words(text):
    return [w for w in (m.group(0) for m in WORD.finditer(text)) if skeleton(w)]


def online_words(slug):
    text = (ONLINE / f"{slug}.txt").read_text(encoding="utf-8")
    keep = [ln for ln in text.splitlines() if not LATIN.search(ln)]
    return words("\n".join(keep))


def vocalized(ws):
    letters = sum(len(skeleton(w)) for w in ws)
    marks = sum(1 for w in ws for ch in w if ch in VOWEL or ch in "ّْ")
    return marks / max(letters, 1)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    name = sys.argv[1]
    src = sys.argv[sys.argv.index("--src") + 1] if "--src" in sys.argv else "keyA"
    k = int(name[1:])
    index = json.loads((ONLINE / "index.json").read_text(encoding="utf-8"))
    pages = doc_pages(ROOT / src / f"{name}.md")
    report = {"batch": name, "src": src, "sources": [], "w_items": [], "h_items": []}
    for slug, (first, last) in index.items():
        cover = [p for p in batch_pages(k) if first <= p <= last and p in pages]
        if not cover or not (ONLINE / f"{slug}.txt").exists():
            continue
        a = []  # (word, page)
        for p in cover:
            for ln in pages[p]["lines"]:
                a.extend((w, p) for w in words(ln))
        o = online_words(slug)
        voc = vocalized(o)
        report["sources"].append({"slug": slug, "pages": cover, "vocalization": round(voc, 2)})
        sm = difflib.SequenceMatcher(None, [skeleton(w) for w, _ in a], [skeleton(w) for w in o], autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size]
        if not blocks:
            continue
        o_lo, o_hi = blocks[0].b, blocks[-1].b + blocks[-1].size

        def ctx(i):
            return " ".join(w for w, _ in a[max(0, i - 3):i + 4])

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                if voc < 0.6:
                    continue
                for di in range(i2 - i1):
                    aw, p = a[i1 + di]
                    ow = o[j1 + di]
                    va, vo = letter_vowels(aw), letter_vowels(ow)
                    if len(va) != len(vo):
                        continue
                    if any(x and y and x != y for x, y in zip(va, vo)):
                        report["h_items"].append({"page": p, "a": aw, "online": ow, "context": ctx(i1 + di), "src": slug})
                continue
            # skip online text outside the part this batch covers
            if j2 <= o_lo or j1 >= o_hi:
                if i1 == i2:
                    continue
            ow = " ".join(o[j1:j2]) if o_lo <= j1 < o_hi or o_lo < j2 <= o_hi else ""
            if i1 == i2 and not ow:
                continue
            p = a[min(i1, len(a) - 1)][1]
            report["w_items"].append({
                "page": p, "a": " ".join(w for w, _ in a[i1:i2]), "online": ow[:200],
                "context": ctx(i1), "src": slug,
            })
    for n, it in enumerate(report["w_items"], 1):
        it["id"] = f"w{n:03d}"
    for n, it in enumerate(report["h_items"], 1):
        it["id"] = f"h{n:03d}"
    out = ROOT / "diff" / f"{name}.online.json"
    save_json(out, report)
    srcs = ", ".join(f"{s['slug']} p{s['pages'][0]}-{s['pages'][-1]} voc {s['vocalization']}" for s in report["sources"])
    print(f"{name}: sources [{srcs or 'none'}] · {len(report['w_items'])} word items · "
          f"{len(report['h_items'])} haraka items -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

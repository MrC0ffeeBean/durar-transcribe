"""Diff keyer A against keyer B for one batch and list every spot the adjudicator must decide.

Usage: python diff.py b17          -> writes diff\\b17.json and prints a summary
Items:
  d###  A/B disagreements (type haraka | letters | punct | structure | cont)
  q###  Quran cross-check flags on A's text that are not already inside a disagreement
  u###  uncertain markers [؟:…] in A that are not already inside a disagreement
All ranges are token indices into A's canonical page tokens (see common.page_tokens), end exclusive.
"""
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PARA, ROOT, batch_pages, doc_pages, plain_final_ya, save_json, strip_marks, typed_dagger_pages
from quran import check_page_tokens

FULL_REREAD_BELOW = 0.95
CTX = 5
UNC_RE = re.compile(r"\[؟:")
PUNCT_RE = re.compile(r"[\s،؛؟!.:,;«»\"'()\[\]\-–—/*=﴿﴾]")


def is_structural(tok):
    return tok == PARA or tok.startswith("#") or tok.startswith(":::") or tok.startswith("|") or tok == "***" \
        or tok.startswith("<<<")


def classify(a, b):
    if any(is_structural(t) for t in a + b):
        return "structure"
    sa, sb = " ".join(a), " ".join(b)
    if "[؟:" in sa or "[؟:" in sb:
        sa2 = re.sub(r"\[؟:([^\]]*)\]", r"\1", sa)
        sb2 = re.sub(r"\[؟:([^\]]*)\]", r"\1", sb)
        if sa2 == sb2:
            return "uncertain"
        sa, sb = sa2, sb2
    if strip_marks(sa) == strip_marks(sb):
        return "haraka"
    pa, pb = PUNCT_RE.sub("", sa), PUNCT_RE.sub("", sb)
    if pa == pb:
        return "punct"
    if strip_marks(pa) == strip_marks(pb):
        return "haraka"
    return "letters"


def ctx(tokens, i1, i2):
    before = tokens[max(0, i1 - CTX):i1]
    after = tokens[i2:i2 + CTX]
    return " ".join(before), " ".join(after)


def merged_opcodes(a, b):
    ops = [op for op in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()]
    out = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            out.append([tag, i1, i2, j1, j2])
            continue
        # merge with previous diff if separated by <= 1 equal token
        if len(out) >= 2 and out[-1][0] == "equal" and out[-1][2] - out[-1][1] <= 1 and out[-2][0] != "equal":
            eq = out.pop()
            prev = out[-1]
            prev[0], prev[2], prev[4] = "replace", i2, j2
            continue
        if out and out[-1][0] != "equal":
            prev = out[-1]
            prev[0], prev[2], prev[4] = "replace", i2, j2
            continue
        out.append([tag, i1, i2, j1, j2])
    return out


def diff_batch(k):
    name = f"b{k:02d}"
    A = doc_pages(ROOT / "keyA" / f"{name}.md")
    B = doc_pages(ROOT / "keyB" / f"{name}.md")
    items, qflags, unc = [], [], []
    matched = total = 0
    for page in batch_pages(k):
        pa, pb = A.get(page), B.get(page)
        if pa is None or pb is None:
            raise SystemExit(f"page {page} missing in {'A' if pa is None else 'B'} — validate first")
        a, b = pa["tokens"], pb["tokens"]
        total += len(a) + len(b)
        busy = []
        if pa["cont"] != pb["cont"]:
            items.append({"page": page, "type": "cont", "a_range": [0, 0], "a_text": f"cont={pa['cont']}",
                          "b_text": f"cont={pb['cont']}", "ctx_before": "", "ctx_after": " ".join(a[:CTX])})
        if page in typed_dagger_pages():
            a_cmp, b_cmp = a, b
        else:
            a_cmp = [plain_final_ya(t)[0] for t in a]
            b_cmp = [plain_final_ya(t)[0] for t in b]
        for tag, i1, i2, j1, j2 in merged_opcodes(a_cmp, b_cmp):
            if tag == "equal":
                matched += 2 * (i2 - i1)
                continue
            cb, ca = ctx(a, i1, i2)
            it = {"page": page, "type": classify(a[i1:i2], b[j1:j2]), "a_range": [i1, i2],
                  "a_text": " ".join(a[i1:i2]), "b_text": " ".join(b[j1:j2]), "ctx_before": cb, "ctx_after": ca}
            items.append(it)
            busy.append(((i1, i2), it))

        def overlaps(r):
            s, e = r
            for (i1, i2), obj in busy:
                if (s < i2 and e > i1) or (i1 == i2 and s <= i1 < e) or (s == e and i1 <= s <= i2):
                    return obj
            return None

        for f in check_page_tokens(page, a):
            hit = overlaps(f["a_range"])
            if hit is not None:
                hit.setdefault("tanzil_hint", []).append(
                    {"keyed": f.get("keyed"), "tanzil": f.get("tanzil"), "ref": f.get("ref"), "kind": f["kind"]})
                continue
            qflags.append(f)
            busy.append((tuple(f["a_range"]), f))
        for i, t in enumerate(a):
            if UNC_RE.search(t):
                j = i
                while j < len(a) - 1 and "]" not in a[j][a[j].find("[؟:") if j == i else 0:]:
                    j += 1
                hit = overlaps((i, j + 1))
                if hit is not None:
                    hit["uncertain_in_A"] = True
                    continue
                cb, ca = ctx(a, i, j + 1)
                u = {"page": page, "a_range": [i, j + 1], "a_text": " ".join(a[i:j + 1]), "ctx_before": cb,
                     "ctx_after": ca}
                unc.append(u)
                busy.append(((i, j + 1), u))
    for n, it in enumerate(items, 1):
        it["id"] = f"d{n:03d}"
    for n, it in enumerate(qflags, 1):
        it["id"] = f"q{n:03d}"
        it["ctx_before"], it["ctx_after"] = ctx(A[it["page"]]["tokens"], *it["a_range"])
    for n, it in enumerate(unc, 1):
        it["id"] = f"u{n:03d}"
    agreement = matched / total if total else 1.0
    by_type = {}
    for it in items:
        by_type[it["type"]] = by_type.get(it["type"], 0) + 1
    out = {"batch": name, "pages": batch_pages(k), "agreement": round(agreement, 4),
           "full_reread_required": agreement < FULL_REREAD_BELOW, "counts": by_type,
           "n_items": len(items), "n_quran_flags": len(qflags), "n_uncertain": len(unc),
           "items": items, "quran_flags": qflags, "uncertain": unc}
    save_json(ROOT / "diff" / f"{name}.json", out)
    return out


def main():
    k = int(sys.argv[1].lstrip("b"))
    out = diff_batch(k)
    print(f"{out['batch']}: agreement {out['agreement']:.2%}, {out['n_items']} disagreements {out['counts']}, "
          f"{out['n_quran_flags']} quran flags, {out['n_uncertain']} uncertain"
          + (" — FULL RE-READ REQUIRED" if out["full_reread_required"] else ""))


if __name__ == "__main__":
    main()

"""Assemble final\\b01..b82 into out\\master.md, out\\clean.md and out\\uncertain.md.

Usage: python assemble.py                 full book (requires all 82 batches DONE)
       python assemble.py --batches 2,17 --prefix pilot_     partial build (sample)
master.md is the source of truth: later corrections are made there, then rerun with --from-master.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_final import check
from common import (BLANK_PAGE, FENCE_CLOSE, FENCE_OPEN, MARKER_RE, N_BATCHES, ROOT, canonical, digits_to_int,
                    load_json, raw_lines, read_text, split_pages)
from quran import check_page_tokens
from common import page_tokens
from validate import validate

AR = "٠١٢٣٤٥٦٧٨٩"
FN_REF_RE = re.compile(r"(?<=[^\s(\[«])\(([٠-٩0-9]+)\)")


def ar(n):
    return "".join(AR[int(c)] for c in str(n))


# ------------------------------------------------------------------ parsing into blocks
def page_blocks(lines):
    blocks, notes, fence = [], [], None
    for ln in lines:
        if fence is not None:
            if ln == FENCE_CLOSE:
                fence = None
            elif fence["kind"] == ":::حواشي":
                notes.append(ln)
            else:
                fence["lines"].append(ln)
            continue
        if ln in FENCE_OPEN:
            fence = {"type": "fence", "kind": ln, "lines": []}
            if ln != ":::حواشي":
                blocks.append(fence)
            continue
        if ln.startswith("|"):
            if blocks and blocks[-1]["type"] == "table":
                blocks[-1]["rows"].append(ln)
            else:
                blocks.append({"type": "table", "rows": [ln]})
            continue
        m = re.match(r"^(#{1,3}) (.*)$", ln)
        if m:
            blocks.append({"type": "heading", "level": len(m.group(1)), "text": m.group(2)})
        elif ln == "***":
            blocks.append({"type": "sep"})
        elif ln == BLANK_PAGE:
            continue
        else:
            blocks.append({"type": "para", "text": ln})
    return blocks, notes


def parse(text):
    _, pages = split_pages(raw_lines(text))
    out = []
    for page, cont, lines in pages:
        blocks, notes = page_blocks(lines)
        for b in blocks:
            if b["type"] == "para":
                b["segs"] = [(page, b["text"])]
        out.append({"page": page, "cont": cont, "blocks": blocks, "notes": notes})
    # continuation joins (gloss boxes at the end of the previous page stay after the joined paragraph)
    for i in range(1, len(out)):
        p, prev = out[i], out[i - 1]
        if not (p["cont"] and p["blocks"] and p["blocks"][0]["type"] == "para"):
            continue
        j = len(prev["blocks"]) - 1
        while j >= 0 and prev["blocks"][j]["type"] == "fence" and prev["blocks"][j]["kind"] == ":::مفردات":
            j -= 1
        if j >= 0 and prev["blocks"][j]["type"] == "para":
            prev["blocks"][j]["segs"] += p["blocks"][0]["segs"]
            p["blocks"].pop(0)
            p["joined"] = True
    return out


def collect_footnotes(pages):
    defs, fmap, last = {}, {}, None
    g = 0
    for p in pages:
        for ln in p["notes"]:
            m = re.match(r"^\(([٠-٩0-9]+)\)\s*(.*)$", ln)
            if m:
                g += 1
                defs[g] = m.group(2)
                fmap[(p["page"], digits_to_int(m.group(1)))] = g
                last = g
            elif last:
                defs[last] += " " + re.sub(r"^\(تابع\)\s*", "", ln)
    return defs, fmap


# ------------------------------------------------------------------ clean.md
def clean_inline(text, page, fmap, used):
    text = re.sub(r"\[؟:([^\]]*)\]", r"\1", text)
    text = re.sub(r"==([^=]+)==", r"**\1**", text)

    def ref(m):
        g = fmap.get((page, digits_to_int(m.group(1))))
        if g is None:
            return m.group(0)
        used.append(g)
        return f"[^{g}]"
    # footnote refs only outside Quran spans
    parts = re.split(r"(﴿[^﴾]*﴾)", text)
    return "".join(pt if pt.startswith("﴿") else FN_REF_RE.sub(ref, pt) for pt in parts)


def build_clean(pages):
    defs, fmap = collect_footnotes(pages)
    out, emitted = [], set()

    def flush(gs):
        gs = list(dict.fromkeys(gs))          # a footnote may be referenced twice (print repeats a mark)
        lines = [f"[^{g}]: {clean_inline(defs[g], 0, {}, [])}" for g in gs if g not in emitted]
        emitted.update(gs)
        if lines:
            out.append("\n".join(lines))

    for p in pages:
        out.append(f"<!-- ص {p['page']} -->")
        for b in p["blocks"]:
            used = []
            t = b["type"]
            if t == "para":
                out.append(" ".join(clean_inline(tx, pg, fmap, used) for pg, tx in b["segs"]))
            elif t == "heading":
                out.append("#" * b["level"] + " " + clean_inline(b["text"], p["page"], fmap, used))
            elif t == "sep":
                out.append("* * *")
            elif t == "table":
                out.append("\n".join(clean_inline(r, p["page"], fmap, used) for r in b["rows"]))
            elif t == "fence" and b["kind"] in (":::شعر", ":::شعر مشطور"):
                out.append("\n".join(clean_inline(ln, p["page"], fmap, used) + "  " for ln in b["lines"]))
            elif t == "fence" and b["kind"] == ":::مفردات":
                out.append("\n".join("> " + clean_inline(ln, p["page"], fmap, used) + "  " for ln in b["lines"]))
            flush(used)
        # notes of this page whose reference was not found
        flush(sorted(g for (pg, _), g in fmap.items() if pg == p["page"] and g not in emitted))
    flush(sorted(set(defs) - emitted))
    text = "\n\n".join(x for x in out if x) + "\n"
    return text


# ------------------------------------------------------------------ uncertain.md
def build_uncertain(batches, master_pages):
    out = ["# الدرر النقية — مواضع غير مؤكدة", "",
           "مواضع تحتاج إلى مراجعة بشرية مع رقم الصفحة (رقم صفحة PDF = رقم الصفحة المطبوع).", ""]
    unresolved, quran, perr, rows = [], [], [], []
    for k in batches:
        rep = load_json(ROOT / "reports" / f"b{k:02d}.json", {})
        dec_by_result = {}
        for d in rep.get("decisions", []):
            if "[؟:" in (d.get("result") or ""):
                dec_by_result.setdefault(d["page"], []).append(d)
        for u in rep.get("unresolved_uncertain", []):
            comp = ""
            for d in dec_by_result.get(u["page"], []):
                if u["reading"] in d["result"]:
                    comp = f"القراءة (أ): {d.get('a') or '—'} · القراءة (ب): {d.get('b') or '—'}"
                    break
            unresolved.append((u["page"], u["reading"], u["context"], comp))
        for q in rep.get("quran_residual", []):
            quran.append((q["page"], q.get("ref", ""), q.get("keyed", ""), q.get("tanzil", ""), q["kind"]))
        for key in ("keyA", "keyB"):
            for e in (rep.get("keyer_notes", {}).get(key) or {}).get("print_errors", []) or []:
                perr.append((e.get("page"), e.get("text", ""), e.get("note", ""), key[-1]))
    out += ["## ١. قراءات غير مؤكدة", ""]
    if unresolved:
        out += ["| الصفحة | القراءة المرجحة | السياق | القراءات المتنافسة |", "|---|---|---|---|"]
        out += [f"| {ar(p)} | {r} | {c.replace('|', '¦')} | {comp} |" for p, r, c, comp in sorted(unresolved)]
    else:
        out.append("لا توجد.")
    out += ["", "## ٢. نصوص قرآنية تخالف المصحف (رواية حفص، نص تنزيل) وأُبقيت كما في المطبوع", ""]
    if quran:
        out += ["| الصفحة | الموضع | كما في الكتاب | نص تنزيل | النوع |", "|---|---|---|---|---|"]
        out += [f"| {ar(p)} | {ref} | {k} | {t} | {kind} |" for p, ref, k, t, kind in sorted(quran)]
    else:
        out.append("لا توجد.")
    out += ["", "## ٣. أخطاء طباعية محتملة لاحظها المدخِّلون (أُبقي النص كما طُبع)", ""]
    if perr:
        out += ["| الصفحة | النص | الملاحظة | المدخل |", "|---|---|---|---|"]
        out += [f"| {ar(p or 0)} | {t} | {n} | {w} |" for p, t, n, w in sorted(perr, key=lambda x: x[0] or 0)]
    else:
        out.append("لا توجد.")
    out += ["", "---", "", "نص المصحف المستخدم للمقارنة: Tanzil Quran Text (Uthmani, v1.1), tanzil.net — CC BY 3.0.", ""]
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    prefix = ""
    if "--prefix" in args:
        prefix = args[args.index("--prefix") + 1]
    if "--batches" in args:
        batches = [int(x) for x in args[args.index("--batches") + 1].split(",")]
    else:
        batches = list(range(1, N_BATCHES + 1))
    outdir = ROOT / "out"
    outdir.mkdir(exist_ok=True)
    master_path = outdir / f"{prefix}master.md"
    if "--from-master" in args:
        master = read_text(master_path)
    else:
        bad = [k for k in batches if not check(k)["pass"]]
        if bad:
            print("NOT DONE:", ", ".join(f"b{k:02d}" for k in bad))
            sys.exit(1)
        master = canonical("\n\n".join(read_text(ROOT / "final" / f"b{k:02d}.md") for k in batches))
        master_path.write_text(master, encoding="utf-8")
    pages_expected = [p for k in batches for p in range(4 * k - 3, 4 * k + 1)]
    errs, warns = validate(master_path, pages_expected)
    print(f"master: {len(pages_expected)} pages expected · {len(errs)} errors · {len(warns)} warnings")
    for e in errs[:20]:
        print("ERROR", e)
    pages = parse(master)
    clean = build_clean(pages)
    (outdir / f"{prefix}clean.md").write_text(clean, encoding="utf-8")
    left = [m for m in ("<<<", ":::", "==", "[؟:") if m in clean]
    glued = FN_REF_RE.findall(re.sub(r"﴿[^﴾]*﴾", "", clean))
    print(f"clean.md: {len(clean)} chars · leftover markup: {left or 'none'} · unconverted footnote refs: {len(glued)}")
    unc = build_uncertain(batches, pages)
    (outdir / f"{prefix}uncertain.md").write_text(unc, encoding="utf-8")
    print(f"uncertain.md written")
    sys.exit(0 if not errs else 1)


if __name__ == "__main__":
    main()

"""Build final\\bNN.md = keyer A + the adjudicator's logged decisions (nothing else changes).

Usage: python apply.py b17
Reads keyA\\b17.md, diff\\b17.json, diff\\b17.decisions.json; writes final\\b17.md and reports\\b17.json,
then validates the final file.

decisions file:
{
 "mode": "spots" | "full_reread",
 "decisions": {
   "d001": {"choice": "A" | "B" | "custom", "text": "...", "note": "..."},
   "q001": {"choice": "A" | "T" | "custom", "text": "...", "note": "..."},     # T = Tanzil word
   "u001": {"choice": "A" | "custom", "text": "...", "note": "..."}            # A = keep the [؟:] marker
 },
 "extra_edits": [{"page": 65, "find": "exact text in that page", "replace": "...", "note": "why"}]
}
"custom" text replaces A's tokens in the item's range; use ¶ for a line break inside it.
For a "cont" item, choice A/B picks the page's continuation flag.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (PARA, ROOT, batch_pages, build_doc, canonical, doc_pages, load_json, plain_final_ya, save_json,
                    tokens_to_lines, typed_dagger_pages)
from quran import check_page_tokens


class ApplyError(Exception):
    pass


def text_tokens(s):
    s = s.replace("\r\n", "\n").replace("\n", f" {PARA} ")
    return [t for t in s.split(" ") if t]


def build_final(k):
    name = f"b{k:02d}"
    A = doc_pages(ROOT / "keyA" / f"{name}.md")
    B = doc_pages(ROOT / "keyB" / f"{name}.md")
    D = load_json(ROOT / "diff" / f"{name}.json")
    dec = load_json(ROOT / "diff" / f"{name}.decisions.json")
    if D is None:
        raise ApplyError(f"diff/{name}.json missing — run diff.py {name}")
    if dec is None:
        raise ApplyError(f"diff/{name}.decisions.json missing")
    decisions = dec.get("decisions", {})
    all_items = D["items"] + D["quran_flags"] + D["uncertain"]
    missing = [it["id"] for it in all_items if it["id"] not in decisions]
    if missing:
        raise ApplyError(f"no decision for: {', '.join(missing)}")
    unknown = sorted(set(decisions) - {it["id"] for it in all_items})
    if unknown:
        raise ApplyError(f"decisions for unknown ids: {', '.join(unknown)}")
    if D.get("full_reread_required") and dec.get("mode") != "full_reread":
        raise ApplyError("agreement below threshold: mode must be 'full_reread' (re-read the whole batch)")

    pages = {p: {"cont": A[p]["cont"], "tokens": list(A[p]["tokens"])} for p in batch_pages(k)}
    log = []
    edits = {}  # page -> list of (i1, i2, new_tokens)
    for it in all_items:
        d = decisions[it["id"]]
        ch = d.get("choice")
        page = it["page"]
        entry = {"id": it["id"], "page": page, "type": it.get("type", it.get("kind", "uncertain")),
                 "a": it.get("a_text", it.get("keyed", "")), "b": it.get("b_text"), "tanzil": it.get("tanzil"),
                 "choice": ch, "note": d.get("note", "")}
        if it.get("type") == "cont":
            if ch not in ("A", "B"):
                raise ApplyError(f"{it['id']}: cont item needs choice A or B")
            if ch == "B":
                pages[page]["cont"] = B[page]["cont"]
            entry["result"] = f"cont={pages[page]['cont']}"
            log.append(entry)
            continue
        i1, i2 = it["a_range"]
        if ch == "A":
            new = None
        elif ch == "B":
            if "b_text" not in it:
                raise ApplyError(f"{it['id']}: choice B only for d-items")
            new = text_tokens(it["b_text"])
        elif ch == "T":
            if not it.get("tanzil"):
                raise ApplyError(f"{it['id']}: choice T needs a Tanzil reading")
            # keep A's surrounding punctuation/brackets, swap only the word
            old = " ".join(pages[page]["tokens"][i1:i2])
            new_s = old.replace(it["keyed"], it["tanzil"].replace(" ", " "), 1) if it["keyed"] in old else None
            if new_s is None:
                raise ApplyError(f"{it['id']}: cannot place Tanzil word; use custom")
            new = text_tokens(new_s)
        elif ch == "custom":
            if "text" not in d:
                raise ApplyError(f"{it['id']}: custom needs text")
            new = text_tokens(d["text"])
        else:
            raise ApplyError(f"{it['id']}: bad choice {ch!r}")
        if new is not None:
            edits.setdefault(page, []).append((i1, i2, new, it["id"]))
        entry["result"] = " ".join(new) if new is not None else entry["a"]
        log.append(entry)
    for page, lst in edits.items():
        lst.sort(key=lambda x: (x[0], x[1]))
        for (a1, a2, _, ida), (b1, b2, _, idb) in zip(lst, lst[1:]):
            if b1 < a2:
                raise ApplyError(f"overlapping ranges {ida} {idb}")
        toks = pages[page]["tokens"]
        for i1, i2, new, _ in sorted(lst, key=lambda x: (x[0], x[1]), reverse=True):
            toks[i1:i2] = new
    # build lines, then free-text extra edits (full re-read)
    out_pages = {}
    for p in batch_pages(k):
        out_pages[p] = {"cont": pages[p]["cont"], "lines": tokens_to_lines(pages[p]["tokens"])}
    extra_log = []
    for e in dec.get("extra_edits", []) or []:
        p = int(e["page"])
        text = "\n".join(out_pages[p]["lines"])
        n = text.count(e["find"])
        if n != 1:
            raise ApplyError(f"extra edit on p{p}: 'find' occurs {n} times (must be exactly once): {e['find'][:50]}")
        text = text.replace(e["find"], e["replace"])
        out_pages[p]["lines"] = [ln for ln in text.split("\n") if ln.strip()]
        extra_log.append(e)
    # rule pass (CONVENTIONS §2): font-drawn small alif over final ى, on pages without typed ones
    rule_log = {}
    for p in batch_pages(k):
        if p in typed_dagger_pages():
            continue
        new_lines, n = [], 0
        for ln in out_pages[p]["lines"]:
            ln, c = plain_final_ya(ln)
            new_lines.append(ln)
            n += c
        out_pages[p]["lines"] = new_lines
        if n:
            rule_log[str(p)] = n
    final = canonical(build_doc(out_pages))
    return final, {"decisions": log, "extra_edits": extra_log, "mode": dec.get("mode", "spots"),
                   "rules": {"plain_final_ya": rule_log}}, D


def report(k, final_text, info, D):
    name = f"b{k:02d}"
    tmp = ROOT / "final" / f"{name}.md"
    unresolved = []
    residual = []
    for page, p in doc_pages(tmp).items():
        for ln in p["lines"]:
            for m in re.finditer(r"\[؟:([^\]]*)\]", ln):
                s = max(0, m.start() - 40)
                unresolved.append({"page": page, "reading": m.group(1), "context": ln[s:m.end() + 40]})
        residual += check_page_tokens(page, p["tokens"])
    notes = {}
    for key in ("keyA", "keyB"):
        notes[key] = load_json(ROOT / key / f"{name}.notes.json", {})
    rep = {"batch": name, "agreement": D["agreement"], "counts": D["counts"], "n_items": D["n_items"],
           "n_quran_flags": D["n_quran_flags"], "n_uncertain_flags": D["n_uncertain"], "mode": info["mode"],
           "choices": {c: sum(1 for x in info["decisions"] if x["choice"] == c) for c in ("A", "B", "T", "custom")},
           "decisions": info["decisions"], "extra_edits": info["extra_edits"], "rules": info.get("rules", {}),
           "unresolved_uncertain": unresolved,
           "quran_residual": [{k2: f[k2] for k2 in ("page", "kind", "keyed", "tanzil", "ref") if k2 in f}
                              for f in residual],
           "keyer_notes": notes}
    save_json(ROOT / "reports" / f"{name}.json", rep)
    return rep


def main():
    k = int(sys.argv[1].lstrip("b"))
    name = f"b{k:02d}"
    try:
        final_text, info, D = build_final(k)
    except ApplyError as e:
        print("APPLY ERROR:", e)
        sys.exit(2)
    out = ROOT / "final" / f"{name}.md"
    out.write_text(final_text, encoding="utf-8")
    rep = report(k, final_text, info, D)
    from validate import validate
    errs, warns = validate(out)
    for w in warns:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    print(f"{name}: wrote final ({len(info['decisions'])} decisions {rep['choices']}, "
          f"{len(info['extra_edits'])} extra edits, {len(rep['unresolved_uncertain'])} unresolved [؟], "
          f"{len(rep['quran_residual'])} residual quran flags) — " + ("VALID" if not errs else "INVALID"))
    sys.exit(0 if not errs else 1)


if __name__ == "__main__":
    main()

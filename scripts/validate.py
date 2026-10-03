"""Validate a transcription file (keyA/keyB/final batch, or the assembled master).

Usage: python validate.py FILE [--pages A-B] [--json]
Exit 0 and print OK if there are no ERRORs (warnings are printed but allowed).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BLANK_PAGE, FENCE_CLOSE, FENCE_OPEN, MARKER_RE, TATWEEL, batch_of_path, batch_pages,
                    digits_to_int, is_mark, keep_tatweel, raw_lines, read_text, split_pages)

LATIN_OK_PAGES = {2, 44}
FN_REF_RE = re.compile(r"(?<=[^\s(\[«])\(([٠-٩0-9]+)\)")      # glued (n) = footnote reference
FN_LINE_RE = re.compile(r"^\(([٠-٩0-9]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})(\s*)(.*)$")
UNCERTAIN_RE = re.compile(r"\[؟:[^\]\[]+\]")


def strip_quran(s):
    return re.sub(r"﴿[^﴾]*﴾", " ", s)


def check_page(page, cont, lines, errs, warns):
    def E(msg):
        errs.append(f"p{page:03d}: {msg}")

    def W(msg):
        warns.append(f"p{page:03d}: {msg}")

    if not lines:
        E("empty page (write [صفحة فارغة] for a blank page)")
        return
    if BLANK_PAGE in lines and len(lines) > 1:
        E("[صفحة فارغة] on a page that has other content")
    fence = None
    refs, notes = [], []
    for ln in lines:
        if MARKER_RE.match(ln):
            E(f"marker inside page content: {ln}")
            continue
        if ln.startswith(":::"):
            if ln == FENCE_CLOSE:
                if fence is None:
                    E("closing ::: without an open fence")
                fence = None
            elif ln in FENCE_OPEN:
                if fence is not None:
                    E(f"fence {ln} opened inside {fence} (nesting not allowed)")
                fence = ln
            else:
                E(f"unknown fence line: {ln}")
            continue
        if ln.startswith("```"):
            E("code fence ``` not allowed")
        # character-level checks
        if re.search(r"[A-Za-z]", ln) and page not in LATIN_OK_PAGES:
            E(f"Latin letters: {ln[:60]}")
        if TATWEEL in ln:
            for i, ch in enumerate(ln):
                if ch == TATWEEL and not keep_tatweel(ln, i):
                    E(f"tatweel: {ln[max(0, i - 10):i + 10]}")
                    break
        if re.search(r"[\x00-\x08\x0b-\x1f\x7f]", ln):
            E(f"control character in text: {ln[:60]!r}")
        if re.search(r"[۰-۹]", ln):
            E(f"Persian digits (use ٠-٩): {ln[:60]}")
        opened = ln.count("[؟:")
        if opened != len(UNCERTAIN_RE.findall(ln)):
            E(f"malformed or unclosed [؟:…]: {ln[:80]}")
        if ln.count("﴿") != ln.count("﴾"):
            E(f"unbalanced ﴿﴾ on a line: {ln[:80]}")
        else:
            depth = 0
            for ch in ln:
                depth += (ch == "﴿") - (ch == "﴾")
                if depth < 0 or depth > 1:
                    E(f"misordered or nested ﴿﴾: {ln[:80]}")
                    break
        body_wo_poetry = ln.replace(" *** ", " ")
        if ln.strip() != "***" and body_wo_poetry.count("**") % 2:
            E(f"unbalanced ** : {ln[:80]}")
        if ln.count("==") % 2:
            E(f"unbalanced == : {ln[:80]}")
        h = HEADING_RE.match(ln)
        if h:
            if fence:
                E(f"heading inside fence {fence}: {ln[:60]}")
            if len(h.group(1)) > 3 or not h.group(2) or not h.group(3).strip():
                E(f"bad heading (use '# ', '## ', '### '): {ln[:60]}")
            if "**" in ln or "==" in ln:
                W(f"emphasis markup inside heading: {ln[:60]}")
        # fence-specific
        if fence == ":::شعر":
            if ln.count(" *** ") != 1:
                E(f"poetry line must contain exactly one ' *** ': {ln[:80]}")
        elif fence == ":::شعر مشطور":
            if "***" in ln:
                E(f"'***' inside :::شعر مشطور: {ln[:80]}")
        elif fence == ":::حواشي":
            m = FN_LINE_RE.match(ln)
            if m:
                notes.append(digits_to_int(m.group(1)))
            elif not ln.startswith("(تابع)"):
                W(f"footnote line does not start with (n) or (تابع): {ln[:60]}")
        elif fence is None:
            if " *** " in ln:
                E(f"' *** ' outside a :::شعر fence: {ln[:60]}")
        if fence in (None, ":::شعر", ":::شعر مشطور"):
            refs += [digits_to_int(x) for x in FN_REF_RE.findall(strip_quran(ln))]
    if fence is not None:
        E(f"fence {fence} not closed before end of page")
    # footnotes: warnings only
    rs, ns = sorted(set(refs)), sorted(set(notes))
    if rs != ns:
        W(f"footnote refs in text {rs} vs footnote lines {ns}")
    if len(refs) != len(set(refs)):
        W(f"a footnote mark is used more than once in the text {sorted(refs)}")
    if len(notes) != len(set(notes)):
        W(f"duplicate footnote numbers {notes}")
    text_len = sum(len(x) for x in lines)
    if text_len < 15 and lines != [BLANK_PAGE]:
        W(f"very little text on page ({text_len} chars)")


def validate(path, pages=None):
    errs, warns = [], []
    try:
        text = read_text(path)
    except UnicodeDecodeError:
        return ["file is not valid UTF-8"], []
    lines = raw_lines(text)
    # marker format check on raw lines that look like markers
    for ln in lines:
        if ln.startswith("<<<") and not MARKER_RE.match(ln):
            errs.append(f"bad page marker: {ln}")
    pre, pg = split_pages(lines)
    if pre:
        errs.append(f"text before the first page marker: {pre[0][:60]}")
    seen = [p for p, _, _ in pg]
    if pages is None:
        k = batch_of_path(path)
        pages = batch_pages(k) if k else sorted(set(seen))
    if seen != list(pages):
        errs.append(f"page markers {seen} != expected {list(pages)} (each page once, in order)")
    for page, cont, plines in pg:
        check_page(page, cont, plines, errs, warns)
    return errs, warns


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    pages = None
    if "--pages" in args:
        i = args.index("--pages")
        a, b = map(int, args[i + 1].split("-"))
        pages = list(range(a, b + 1))
        del args[i:i + 2]
    path = args[0]
    errs, warns = validate(path, pages)
    if as_json:
        print(json.dumps({"ok": not errs, "errors": errs, "warnings": warns}, ensure_ascii=False))
    else:
        for e in errs:
            print("ERROR", e)
        for w in warns:
            print("WARN ", w)
        print("OK" if not errs else f"FAILED: {len(errs)} error(s)")
    sys.exit(0 if not errs else 1)


if __name__ == "__main__":
    main()

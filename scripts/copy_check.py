"""Copy-paste check: the text Word returns for the DOCX must equal clean.md word for word
(after removing numbering/markup differences). Usage: python copy_check.py out.docx clean.md"""
import collections
import os
import re
import sys
import unicodedata

import win32com.client as w


def words(s):
    s = unicodedata.normalize("NFC", s)
    s = s.replace("۠", "۟")                       # DOCX uses the KFGQPC code for the silent circle
    s = re.sub(r"\[\^\d+\]:?", " ", s)                      # markdown footnote refs/defs
    s = re.sub(r"<!--.*?-->", " ", s)
    s = re.sub(r"[0-9٠-٩]", " ", s)               # numbers (ayah, footnote marks, page numbers)
    s = re.sub(r"[،؛؟۔]", " ", s)       # Arabic punctuation
    s = re.sub(r"[^؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿A-Za-z]+", " ", s)
    return s.split()


app = w.dynamic.Dispatch("Word.Application")
app.Visible = False
try:
    doc = app.Documents.Open(os.path.abspath(sys.argv[1]), ReadOnly=True, AddToRecentFiles=False)
    parts = [doc.Content.Text]
    for i in range(1, doc.Footnotes.Count + 1):
        parts.append(doc.Footnotes(i).Range.Text)
    if doc.TablesOfContents.Count:
        toc = doc.TablesOfContents(1).Range.Text
        parts[0] = parts[0].replace(toc, " ", 1)
    doc.Close(False)
finally:
    app.Quit()
dw = words("\n".join(parts).replace("المحتويات", " ", 1).replace("شرح المفردات", " "))
cw = words(open(sys.argv[2], encoding="utf-8").read())
cd, cc = collections.Counter(dw), collections.Counter(cw)
only_docx, only_md = cd - cc, cc - cd
print(f"DOCX words {len(dw)} · clean.md words {len(cw)} · only in DOCX {sum(only_docx.values())} · only in MD {sum(only_md.values())}")
for k, v in list(only_docx.items())[:10]:
    print("  only DOCX:", k, v)
for k, v in list(only_md.items())[:10]:
    print("  only MD:  ", k, v)

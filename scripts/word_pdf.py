"""Convert a DOCX to PDF with Word (pywin32 late binding); optionally update the TOC and all fields first
(the updated DOCX is saved). Usage: python word_pdf.py in.docx out.pdf [--update-fields] [--embed-fonts]"""
import os
import sys

import win32com.client as w

src, dst = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
app = w.dynamic.Dispatch("Word.Application")
app.Visible = False
app.DisplayAlerts = 0
doc = None
try:
    doc = app.Documents.Open(src, ConfirmConversions=False, ReadOnly=False, AddToRecentFiles=False)
    if "--update-fields" in sys.argv:
        for story in doc.StoryRanges:
            while story is not None:
                story.Fields.Update()
                story = story.NextStoryRange
        for i in range(1, doc.TablesOfContents.Count + 1):
            doc.TablesOfContents(i).Update()
            rng = doc.TablesOfContents(i).Range
            # freeze the page numbers (PAGEREF -> text) so export/repagination cannot turn them Western again;
            # the TOC field itself stays and can still be updated in Word
            for j in range(rng.Fields.Count, 0, -1):
                if rng.Fields(j).Type == 37:  # wdFieldPageRef
                    rng.Fields(j).Unlink()
            rng = doc.TablesOfContents(i).Range
            for dgt, a in zip("0123456789", "٠١٢٣٤٥٦٧٨٩"):   # TOC page numbers in Arabic-Indic digits
                f = rng.Duplicate.Find
                f.ClearFormatting()
                f.Replacement.ClearFormatting()
                f.Execute(dgt, False, False, False, False, False, True, 0, False, a, 2)
        if "--embed-fonts" in sys.argv:   # full fonts (not subsets) so the text stays editable on other machines
            doc.EmbedTrueTypeFonts = True
            doc.SaveSubsetFonts = False
            doc.DoNotEmbedSystemFonts = True
        doc.Save()
    doc.ExportAsFixedFormat(dst, 17)  # wdExportFormatPDF
finally:
    for f in ((lambda: doc.Close(False)) if doc is not None else None, app.Quit):
        try:
            f and f()
        except Exception:
            pass
print("ok", dst)

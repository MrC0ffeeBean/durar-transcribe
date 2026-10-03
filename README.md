# durar-transcription

Vision transcription of «الدُّرَر النَّقِيَّة في أوراد الطريقة اليُسْرِيَّة الصِّدِّيقِيَّة» (6th ed., 2023, 328 pages;
«جميع الحقوق عامة للمسلمين — صدقة جارية») into Word + Markdown.

Read `STATUS.md` first (progress + resume steps), then `CONVENTIONS.md` (transcription rules) and `STRUCTURE.md`
(map of the book).

## Pipeline (per batch of 4 pages; batch k = PDF pages 4k−3 … 4k)

1. `keyA\bNN.md`, `keyB\bNN.md` — two independent vision keyings (different models), each passing `validate.py`.
2. `scripts\diff.py bNN` → `diff\bNN.json`: A/B disagreements (haraka / letters / punct / structure), Quran words of A
   that differ from Tanzil, and A's uncertain markers.
3. Adjudicator decides each item against the page images → `diff\bNN.decisions.json`.
4. `scripts\apply.py bNN` → `final\bNN.md` (= A + logged decisions, nothing else) and `reports\bNN.json`.
5. `scripts\check_final.py bNN` — the guard. A batch is DONE iff this passes.

All of it is driven by `scripts\workflow.js` (Workflow tool, `args: {"batches": [...]}`); finished keyings/batches are
skipped, so a re-run after an interruption only redoes in-flight work.

## Outputs

- `scripts\assemble.py` → `out\master.md` (source of truth), `out\clean.md`, `out\uncertain.md`.
- `node scripts\gen_docx.js out\master.md out\durar.docx` → `python scripts\docx_post.py out\durar.docx`
  (Arabic-Indic page numbers and footnote marks) → `python scripts\word_pdf.py out\durar.docx out\durar.pdf
  --update-fields` (updates TOC/fields via Word, saves, exports PDF).
- `scripts\sidebyside.py` — QA images (book page next to the generated page).

Corrections later: edit `out\master.md`, then `assemble.py --from-master` and regenerate the DOCX.

Python: `C:\Python312\python.exe` · Node packages in `scripts\node_modules` (docx).
Quran reference: `ref\quran-uthmani.txt` — Tanzil Quran Text (Uthmani 1.1), tanzil.net, CC BY 3.0.

# Continuing the transcription in a Claude Code cloud session

This repo holds everything needed to finish «الدرر النقية». Read `STATUS.md`, `CONVENTIONS.md`, `STRUCTURE.md`
and `README.md` first. The user's decisions (all binding):

- Accurate mode: two independent keyers (both **Opus**), an **Opus** adjudicator, and the guard. A batch is DONE only
  when `scripts/check_final.py bNN` passes.
- Tanzil Uthmani text (`ref/quran-uthmani.txt`, CC BY 3.0) is a cross-check for the Quran. The printed book stays the
  target.
- Word file: A5, design as already approved. The text must stay copy-pasteable and editable.
- Plain ى for the small alif that the body font draws over a final ى (CONVENTIONS §2; enforced by `apply.py`).
- The adjudicator may fix errors both keyers share, but only when the image is unambiguous, and each fix is logged.
- Waves of about 10 batches, at most 8 agents at once. After each wave, send the user a one-line update and
  continue automatically. If the user says "stop", record the state and do not resume until they ask.

## 1. One-time setup in the cloud machine (Linux)

```bash
pip install pymupdf pillow numpy fonttools        # Python 3.10+
(cd scripts && npm install)                       # docx package for gen_docx.js
python3 scripts/render.py                         # pages/ and crops/ (about 5 min, not in git)
python3 scripts/status.py --write                 # re-validates every batch and rewrites STATUS.md
```

## 2. Run the remaining batches

Use the Workflow tool with `scriptPath: scripts/workflow.js` and
`args: {"batches": [<next ~10 not-done batch numbers>], "root": "<absolute path of this repo>", "python": "python3"}`.
Finished keyings and finished batches are skipped, so a re-run after an interruption only redoes in-flight work.
If the Workflow tool is not available, run the same three roles with the Agent tool, using the prompts in
`scripts/workflow.js` (keyerPrompt, adjPrompt, guard).

After **each** wave:

```bash
python3 scripts/status.py --write
git add -A && git commit -m "Wave N: batches …" && git push
```

## 3. When all 82 batches are DONE

```bash
python3 scripts/assemble.py                                   # out/master.md, out/clean.md, out/uncertain.md
node scripts/gen_docx.js out/master.md out/durar.docx
python3 scripts/docx_post.py out/durar.docx                   # Arabic-Indic page numbers, footnote marks
git add -A -f out/master.md out/clean.md out/uncertain.md out/durar.docx && git commit -m "Assembled outputs" && git push
```

Also run the QA accuracy estimate: a fresh agent compares `out/master.md` with the images of 10 random pages and
counts errors (letters, harakat, structure). Write the result to `out/accuracy.md` and commit it.

## 4. Steps that must run on the user's Windows PC (Microsoft Word)

Word is not available in the cloud. Back on the PC, `git pull`, then:

```bash
C:/Python312/python.exe scripts/word_pdf.py out/durar.docx out/durar.pdf --update-fields --embed-fonts
C:/Python312/python.exe scripts/copy_check.py out/durar.docx out/clean.md
C:/Python312/python.exe scripts/sidebyside.py out/durar.pdf out/master.md 6 68 105 198 230 260 290 312 --out out/qa
```

Then copy to the Desktop (PowerShell):
`out/durar.docx` → «الدرر النقية - نصية.docx», `out/clean.md` → «الدرر النقية - نصية.md»,
`out/uncertain.md` → «الدرر النقية - مواضع غير مؤكدة.md».

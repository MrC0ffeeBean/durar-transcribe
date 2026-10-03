# CONVENTIONS — transcribing «الدُّرَر النَّقِيَّة»

Every agent reads this file and `STRUCTURE.md` before working. The printed page is the only authority.
Never use the PDF's text layer (it is corrupted). Read the page images only.

Project root: the folder holding this file (Windows: `C:/Users/JellyFish/durar-transcription`; cloud: the repo
checkout). Python: `C:/Python312/python.exe` on Windows, `python3` in the cloud — called `PY` below. Paths are
relative to the project root; `/` works everywhere.

---

## 1. Images and reading procedure

For PDF page N (3 digits, e.g. 012):
- `pages/p012.png` — the full page (layout).
- `crops/p012_top.png`, `crops/p012_bot.png` — top and bottom 55 % of the page at ~1.4× zoom (they overlap by ~10 %).
  Read every letter and every haraka from these crops.
- If a spot is still too small (footnotes, Quran marks, small honorific glyphs), make a bigger zoom:
  `PY scripts/zoom.py 12 0.0 0.80 1.0 1.0 scratch/z.png 500`
  (page, then x0 y0 x1 y1 as fractions of the page width/height, output path, dpi). Write zooms only under `scratch/`.

Procedure: look at the full page first (layout, headings, poetry, footnote rule). Then transcribe **line by line from
the crops**, checking each word's letters and harakat against the image before writing the next word. Where the two
crops overlap, make sure no line is skipped or written twice.

## 2. Fidelity

- Transcribe **exactly what is printed**: same words, same order, same letters, same tashkeel. Do not add, remove or
  "correct" any haraka, shadda, sukun, tanween, hamza, madda, alif form, ى/ي, ة/ه or spelling. A word printed without
  harakat is written without harakat; a word printed with one haraka gets only that haraka.
- If something looks like a printing error, keep it as printed and mention it in your notes (see §15).
- ى (alef maqsura, no dots) and ي (yeh, two dots) are different letters — copy whichever is printed
  (the book prints e.g. «يسرى رشدى» on p.033 and «يسري رشدي» elsewhere).
- Order of marks on one letter: write shadda first, then its vowel (ـَّ = U+0651 U+064E). Scripts normalize order anyway.
- **Final ى with a small alif**: the regular body font (Lotus Light) draws a small alif over every final ى by
  itself; it is not part of the text. Write plain ى: `على`, `حتى`, `أخرى`, `عَلَى`, `صَلَّى`. Write ٰ over ى only
  in Quran text and where it is really typed — the bold poem font on pp.249, 258–305 (STRUCTURE.md). A small
  alif anywhere else (e.g. `هٰذا`, `الرحمٰن`) is written as printed. (apply.py also enforces this on the
  pages without typed ones.)
- The word **الله**: many fonts draw a small alif/shadda on it automatically. If nothing else is printed on it, write
  `الله`. If a case vowel or explicit marks are printed (e.g. اللَّهُ, ٱللَّهِ), write them all.
- **Drop** tatweel/kashida (ـ, the stretching used to justify lines and in decorative titles), running heads (the
  title in the rounded box at the top of each page), printed page numbers (in the ornament at the bottom), and pure
  ornaments.
  Exception: the Hijri abbreviation keeps its tatweel exactly as printed: `١٣٢٠هـ`, `١٤٣٢هـ.` (heh + tatweel when printed so).
- **Digits**: keep the digit script as printed: Arabic-Indic ٠١٢٣٤٥٦٧٨٩ normally; a few references are printed with
  European digits (e.g. «[الفلق: 1-5]» on p.068) — keep those European. Write numbers in logical (reading) order:
  a range read «١ إلى ٥» is `١-٥`. Use the ASCII hyphen `-` for every printed dash between numbers.
- **Punctuation**: keep Arabic punctuation as printed (، ؛ ؟ « » ! : . ( ) [ ] / *). Do not add punctuation.
  Parentheses are written by their **meaning**: an opening one before the text it encloses, a closing one after it,
  even if the print draws the glyph mirrored. E.g. the bayt numbers of the Munfarija are written `١)`.
- Spacing: one space between words; no space before ، ؛ : . ! ؟ ) ] » ﴾ and no space after ( [ « ﴿ unless printed
  that way clearly on purpose. Do not split or join words beyond what is printed.

## 3. Quran text (Uthmani script)

Quran passages are printed in a Madinah-mushaf (KFGQPC Hafs) font. Encode them with this table (the same encoding
as the Tanzil Uthmani text used for cross-checking):

| Printed sign | Write |
|---|---|
| alif wasla (ٱ, small ṣād on alif) | `ٱ` U+0671 |
| small/dagger alif above a letter | `ٰ` U+0670 directly after the letter (no tatweel) |
| sukun — any shape (round ْ or the small "khāʾ head" ۡ) | `ْ` U+0652 |
| madda over a letter | `ٓ` U+0653 |
| small round zero (silent letter, e.g. on the alif of أُو۟لَٰٓئِكَ) | `۟` U+06DF |
| small upright rectangular zero | `۠` U+06E0 |
| small high mīm (iqlāb), e.g. on tanween before ب | `ۢ` U+06E2 |
| small low mīm | `ۭ` U+06ED |
| small waw after a letter (e.g. لَهُۥ) | `ۥ` U+06E5 |
| small yeh (e.g. بِهِۦ) | `ۦ` U+06E6 |
| small high yeh | `ۧ` U+06E7 |
| hamza above / below written as a separate mark | `ٔ` U+0654 / `ٕ` U+0655 |
| waqf signs: ۖ (صلى) ۗ (قلى) ۘ (م) ۙ (لا) ۚ (ج) ۛ (∴) ۜ (س) | U+06D6 U+06D7 U+06D8 U+06D9 U+06DA U+06DB U+06DC |
| tanween: fathatan/dammatan/kasratan in any shape (stacked or "open") | ً ٌ ٍ (U+064B U+064C U+064D) |

- Enclose each printed Quran quotation in its ornate brackets exactly as printed: `﴿…﴾`.
- **Ayah-end numbers** (digits in the round ornament) are written inside the brackets as `(١)`, with a space before
  and after: `﴿قُلْ هُوَ ٱللَّهُ أَحَدٌ (١) ٱللَّهُ ٱلصَّمَدُ (٢)﴾`.
- The reference keeps the book's own format and position: `﴿…﴾ [البقرة: ٢٥٥]`. Never invent a reference.
- The small calligraphic basmala printed before a surah (and as a centered line on title pages) is always written
  `بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ`, outside the brackets, where it is printed.
- Quran-like text that is printed in the ordinary (non-Uthmani) font and without ﴿﴾ is not Quran markup: transcribe it
  as ordinary text with its printed harakat.

## 4. Page markers

- Each page starts with its marker on its own line: `<<<ص:012>>>` (the 3-digit **PDF** page index; in this book it is
  the same as the printed page number).
- If the page's first paragraph **continues** the last paragraph of the previous page (sentence broken by the page
  turn), use `<<<ص:013+>>>`.
- A page with nothing to transcribe is `<<<ص:322>>>` followed by the line `[صفحة فارغة]`.
- Leave one blank line after each marker line and between all blocks.

## 5. Headings

- `#` / `##` / `###` + space + heading text. The heading map in `STRUCTURE.md` lists every `#` and `##` heading of the
  book; follow it exactly.
- `###`: any other standalone title line (usually bold and centered, or bold on its own line ending with «:»), e.g.
  `### الصلاة البرزخية`, `### فائدة:`, `### دعاء الاستفتاح:`.
- A heading that wraps onto two printed lines in the same title font is one heading line. Lines in a smaller font under
  a title (author, «تقرأ …», «(يقرأ مرة يوميًا)») are ordinary paragraphs (bold if printed bold).
- Keep a heading's printed harakat, quotes and colon. Do not put `**` inside headings.

## 6. Paragraphs and emphasis

- Join the printed line wraps of a paragraph into **one line**. One blank line between paragraphs. A new paragraph
  starts where the print starts a new line with an indent or after a visibly short last line, or where a new numbered
  item starts.
- Centered short lines that are not headings (e.g. instructions like «(ثلاثًا)» on its own line, a dua on its own line)
  are their own paragraphs.
- **Bold** text that contrasts with the surrounding text: `**…**`. Do not mark bold when a whole block is set in one
  heavier font (e.g. an entire poem, an entire dua, a whole page). Run-in bold labels: `**مذهبنا:** حسن الظن…`.
- **Red** text (the divine Name in each prayer of الصلوات اليسرية pp.103–169, and the surah names in the poem
  pp.290–296): `==…==`, e.g. `اللَّهُمَّ يَا ==قُدُّوسُ==،`. Put punctuation that is printed black outside the markers.
- Do not nest `**` and `==`. Never leave an unclosed `**` or `==` on a line.

## 7. Lists, numbers, separators

- Numbered items keep their printed numbering at the start of the paragraph: `١- …`, `(٣) …`, `٤/٢٣- …`.
- Bullet signs keep their printed glyph at the start of the paragraph: `* أستغفر الله…` / `◆الصلاة الشافعية…`.
- Inline `*` separators between phrases (e.g. on pp.078, 307) are written ` * ` with spaces.
- A printed separator line (`* * *`, a row of asterisks) is the single line `***`. Purely graphic ornaments are dropped.

## 8. Poetry

```
:::شعر
١- صدر البيت الأول *** عجز البيت الأول
٢- صدر البيت الثاني *** عجز البيت الثاني
:::
```
- One bayt per line, exactly one ` *** ` (space, three asterisks, space) between صدر and عجز.
- Layouts in this book: (a) side by side — صدر in the right half, عجز in the left half (pp.189–195);
  (b) stacked — صدر on one line, عجز on the next, indented (most poems). Both become `صدر *** عجز`.
- Keep the printed bayt number at the start of the line exactly as printed (`١- `, `١) `, `٤/٢٣- `).
- Lines of verse printed singly (مشطور / rajaz, a centered refrain, a lone hemistich) go in `:::شعر مشطور` with one
  line each and no `***`.
- A heading or prose between bayts closes the fence; open a new fence after it.
- If a poem crosses a page, close the fence at the end of the page and reopen it after the next page marker. Page
  markers always go between bayts, never inside one (a fence never contains a page marker).
- Inside poetry, harakat and letters follow §2 strictly; tatweel used to stretch hemistichs is dropped.

## 9. Footnotes

- The footnote reference in the text is written as printed, `(١)`, **glued to the preceding word or punctuation with no
  space**: `القرويين(١) أكبر`. (A number in parentheses with a space before it, or at the start of a paragraph, is a
  list number, not a footnote.)
- The footnotes at the bottom of the page (below the short rule, smaller font) go at the end of that page's text:
  ```
  :::حواشي
  (١) نص الحاشية.
  (٢) نص الحاشية.
  :::
  ```
- A footnote that continues from the previous page starts with the line `(تابع) …` inside that page's `:::حواشي`.
- Footnote numbering restarts on each page as printed; copy the printed numbers.

## 10. Word glosses (شرح المفردات)

- The poems (بانت سعاد، البردة …) have word glosses at the bottom of the page, keyed by bayt number
  («١- بانت: فارقت. …»). They are transcribed at the end of the page, **before** the `:::حواشي` block, as:
  ```
  :::مفردات
  ١- بانت: فارقت. متبول: …
  ٢- …
  :::
  ```
  One line per printed gloss item (a new item starts where the print starts a new number).
- The boxed glossary of p.308 (شرح مفردات الحلية) is also a `:::مفردات` block, one gloss per line.

## 11. Tables

- Real tables (pp.044, 311–318) become Markdown tables with a header row and `|---|` separator, cells in the
  printed right-to-left order (first column = rightmost printed column). A cell spanning several rows (e.g. a rotated
  day name) is written in the first row of its span and left empty below. Line breaks inside a cell become one space.
- Latin text is allowed only where printed (URLs on p.044, «I.S.BN» on p.002).

## 12. Honorific glyphs

- ﷺ (صلى الله عليه وسلم, U+FDFA) and ﷻ (جل جلاله, U+FDFB) printed as glyphs are kept as those glyphs.
- Every other honorific printed as a small calligraphic glyph is written out in words in parentheses:
  `(رضي الله عنه)`, `(رضي الله عنها)`, `(رضي الله عنهم)`, `(رضي الله عنهما)`, `(رحمه الله)`, `(عليه السلام)`,
  `(حفظه الله)`, `(قدس الله سره)`, `(سبحانه وتعالى)`, `(عز وجل)` — whichever the glyph says. One space before it.
- Honorifics printed as ordinary words are transcribed as ordinary words (no parentheses added).

## 13. Images, calligraphy, captions

- Photos and ornaments are omitted. Photo captions are transcribed as ordinary paragraphs.
- A calligraphic piece that *is* the page's text (e.g. the basmala roundel and «اللهم صل وسلم على سيدنا محمد وآله» on
  p.004, the decorative title pages pp.306–307) is transcribed as text (a heading if it is the title).
- Small decorative medallions (e.g. «لا إله إلا الله» / «محمد رسول الله» seals on p.306) are omitted.

## 14. Uncertain spots

- If you cannot read something with certainty, write `[؟:best reading]`, e.g. `[؟:الحمدُ]`. It may span several words.
- Never guess silently. Never leave a gap without a marker. One marker per uncertain spot.

## 15. Keyer output

- Your file: the batch's pages in order, each starting with its marker, in UTF-8. Nothing else in the file
  (no title, no comments, no code fences around the whole file).
- Validate: `PY scripts/validate.py keyA/b17.md` (or keyB). Fix every ERROR and re-run until it
  prints `OK`. Warnings are allowed but read them (a footnote warning usually means a missing glued `(n)`).
- Notes file `keyA/b17.notes.json` (or keyB): `{"uncertain": [{"page": 65, "reading": "…", "why": "…"}],
  "print_errors": [{"page": 65, "text": "…", "note": "…"}], "notes": "…"}` (empty lists are fine).

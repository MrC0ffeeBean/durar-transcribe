// Generate the Word file from master.md (or any canonical transcription file).
// Usage: node gen_docx.js IN.md OUT.docx [--no-toc]
// Then: python word_pdf.py OUT.docx OUT.pdf --update-fields   (updates the TOC/fields and saves)
const fs = require('fs')
const path = require('path')
const d = require('docx')

const IN = process.argv[2]
const OUT = process.argv[3]
const WITH_TOC = !process.argv.includes('--no-toc')

const BODY_FONT = 'Traditional Arabic'
const QURAN_FONT = 'KFGQPC HAFS Uthmanic Script'
const SZ = 32            // half-points (16 pt)
const SZ_SMALL = 26      // glosses
const SZ_FN = 24         // footnotes
const QURAN_COLOR = '1B5E20'
const RED = 'C00000'
const LINE = 288         // 1.2 line spacing

// ---------------------------------------------------------------- parsing
const MARKER = /^<<<ص:(\d{3})(\+?)>>>$/
const FENCES = new Set([':::شعر', ':::شعر مشطور', ':::حواشي', ':::مفردات'])
const toInt = s => parseInt(s.replace(/[٠-٩]/g, c => '٠١٢٣٤٥٦٧٨٩'.indexOf(c)), 10)

function parse(text) {
  const lines = text.replace(/\r/g, '').split('\n').map(l => l.trim()).filter(Boolean)
  const pages = []
  let cur = null
  for (const ln of lines) {
    const m = ln.match(MARKER)
    if (m) { cur = { page: +m[1], cont: m[2] === '+', blocks: [], notes: [] }; pages.push(cur); continue }
    if (!cur) continue
    const last = cur.blocks[cur.blocks.length - 1]
    if (cur.fence) {
      if (ln === ':::') { cur.fence = null; continue }
      if (cur.fence.kind === ':::حواشي') cur.notes.push(ln)
      else cur.fence.lines.push(ln)
      continue
    }
    if (FENCES.has(ln)) {
      cur.fence = { type: 'fence', kind: ln, lines: [] }
      if (ln !== ':::حواشي') cur.blocks.push(cur.fence)
      continue
    }
    if (ln.startsWith('|')) {
      if (last && last.type === 'table') last.rows.push(ln)
      else cur.blocks.push({ type: 'table', rows: [ln] })
      continue
    }
    const h = ln.match(/^(#{1,3}) (.*)$/)
    if (h) { cur.blocks.push({ type: 'heading', level: h[1].length, text: h[2] }); continue }
    if (ln === '***') { cur.blocks.push({ type: 'sep' }); continue }
    if (ln === '[صفحة فارغة]') continue
    cur.blocks.push({ type: 'para', text: ln })
  }
  return pages
}

// footnotes: (page, n) -> global id ; "(تابع)" appends to the previous page's last footnote
function collectFootnotes(pages) {
  const fn = {}          // id -> [texts]
  const map = {}         // `${page}:${n}` -> id
  let id = 0, lastId = null
  for (const p of pages) {
    for (const ln of p.notes) {
      const m = ln.match(/^\(([٠-٩0-9]+)\)\s*(.*)$/)
      if (m) { id += 1; fn[id] = [m[2]]; map[`${p.page}:${toInt(m[1])}`] = id; lastId = id }
      else if (ln.startsWith('(تابع)') && lastId) fn[lastId].push(ln.replace(/^\(تابع\)\s*/, ''))
      else if (lastId) fn[lastId].push(ln)
    }
  }
  return { fn, map }
}

// ---------------------------------------------------------------- runs
function baseRun(text, o = {}) {
  const font = o.font || BODY_FONT
  const size = o.size || SZ
  return new d.TextRun({
    text, rightToLeft: true, bold: !!o.bold, boldComplexScript: !!o.bold,
    color: o.color, highlight: o.highlight,
    font: { ascii: font, hAnsi: font, cs: font, eastAsia: font },
    size, sizeComplexScript: size,
  })
}

// inline markup -> runs. ctx: {page, fnmap, size, bold}
function inlineRuns(text, ctx) {
  const runs = []
  const size = ctx.size || SZ
  // split into Quran spans and the rest
  const parts = text.split(/(﴿[^﴾]*﴾)/)
  for (const part of parts) {
    if (!part) continue
    if (part.startsWith('﴿')) {
      let q = part.replace(/\[؟:([^\]]*)\]/g, '$1')
      q = q.replace(/\s?\(([٠-٩]+)\)/g, (m0, n) => ' ' + n)   // ayah numbers -> ornament digits
      q = q.replace(/\*\*|==/g, '')
      q = q.replace(/۟/g, '۠')   // KFGQPC Hafs draws the silent-letter circle at U+06E0 (U+06DF falls back to a dot)
      runs.push(baseRun(q, { font: QURAN_FONT, size: size + 2, color: QURAN_COLOR }))
      continue
    }
    emphasisRuns(part, ctx, runs)
  }
  return runs
}

function emphasisRuns(text, ctx, runs) {
  const re = /(\*\*[^*]+?\*\*|==[^=]+?==|\[؟:[^\]]*\])/
  for (const seg of text.split(re)) {
    if (!seg) continue
    let o = { size: ctx.size, bold: ctx.bold }
    let t = seg
    if (seg.startsWith('**') && seg.endsWith('**') && seg.length > 4) { o.bold = true; t = seg.slice(2, -2) }
    else if (seg.startsWith('==') && seg.endsWith('==') && seg.length > 4) { o.color = RED; t = seg.slice(2, -2) }
    else if (seg.startsWith('[؟:')) { o.highlight = 'yellow'; t = seg.slice(3, -1) }
    footnoteRuns(t, o, ctx, runs)
  }
}

function footnoteRuns(text, o, ctx, runs) {
  // glued (n) = footnote reference
  const re = /(?<=[^\s(\[«])\(([٠-٩0-9]+)\)/g
  let last = 0, m
  while ((m = re.exec(text))) {
    const id = ctx.fnmap && ctx.fnmap[`${ctx.page}:${toInt(m[1])}`]
    if (!id) continue
    if (m.index > last) runs.push(baseRun(text.slice(last, m.index), o))
    if (ctx.used && ctx.used.has(id)) {
      // the print repeats a footnote mark: a footnote can be anchored only once -> static mark, same number
      const ar = String(id).replace(/[0-9]/g, c => '٠١٢٣٤٥٦٧٨٩'[+c])
      runs.push(new d.TextRun({ text: `(${ar})`, superScript: true, rightToLeft: true,
        font: { ascii: BODY_FONT, hAnsi: BODY_FONT, cs: BODY_FONT }, size: o.size || SZ, sizeComplexScript: o.size || SZ }))
    } else {
      runs.push(new d.FootnoteReferenceRun(id))
      ctx.used && ctx.used.add(id)
    }
    last = m.index + m[0].length
  }
  if (last < text.length) runs.push(baseRun(text.slice(last), o))
}

// ---------------------------------------------------------------- blocks
const P = (children, o = {}) => new d.Paragraph({
  children, bidirectional: true,
  alignment: o.align || d.AlignmentType.BOTH,
  spacing: { line: LINE, lineRule: d.LineRuleType.AUTO, after: o.after ?? 120, before: o.before ?? 0 },
  heading: o.heading, pageBreakBefore: o.pageBreakBefore, keepNext: o.keepNext,
  indent: o.indent,
})

const NONE = { style: d.BorderStyle.NONE, size: 0, color: 'FFFFFF' }
const NOBORDERS = { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE }
const CELL_NOBORDERS = { top: NONE, bottom: NONE, left: NONE, right: NONE }

const BAYT_NO = /^((?:[٠-٩]+\/)?[٠-٩]+\s?[-)])\s*/
function poetryTable(lines, ctx) {
  const numbered = lines.some(ln => BAYT_NO.test(ln))
  const W = 6463, NW = numbered ? 620 : 0, HW = Math.floor((W - NW) / 2)
  const cell = (t, w, align) => new d.TableCell({
    borders: CELL_NOBORDERS, width: { size: w, type: d.WidthType.DXA }, margins: { left: 40, right: 40 },
    children: [P(inlineRuns(t, ctx), { align, after: 30 })],
  })
  const rows = lines.map(ln => {
    let no = ''
    const m = ln.match(BAYT_NO)
    if (m) { no = m[1]; ln = ln.slice(m[0].length) }
    const [sadr, ajz] = ln.split(' *** ')
    const cells = []
    if (numbered) cells.push(cell(no, NW, d.AlignmentType.RIGHT))
    cells.push(cell(sadr, HW, d.AlignmentType.CENTER), cell(ajz || '', HW, d.AlignmentType.CENTER))
    return new d.TableRow({ cantSplit: true, children: cells })
  })
  return new d.Table({
    rows, borders: NOBORDERS, visuallyRightToLeft: true, layout: d.TableLayoutType.FIXED,
    width: { size: W, type: d.WidthType.DXA }, columnWidths: numbered ? [NW, HW, HW] : [HW, HW],
  })
}

function glossBox(lines, ctx) {
  const c = { ...ctx, size: SZ_SMALL }
  const border = { style: d.BorderStyle.SINGLE, size: 4, color: 'A0A0A0' }
  const children = [P([baseRun('شرح المفردات', { bold: true, size: SZ_SMALL })], { align: d.AlignmentType.CENTER, after: 40 })]
  for (const ln of lines) children.push(P(inlineRuns(ln, c), { after: 20 }))
  return new d.Table({
    visuallyRightToLeft: true, width: { size: 100, type: d.WidthType.PERCENTAGE },
    rows: [new d.TableRow({ children: [new d.TableCell({
      shading: { type: d.ShadingType.CLEAR, color: 'auto', fill: 'F3F1EA' },
      borders: { top: border, bottom: border, left: border, right: border },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children,
    })] })],
  })
}

function mdTable(rows, ctx) {
  const cells = rows.filter(r => !/^\|\s*:?-{2,}/.test(r)).map(r => r.replace(/^\||\|$/g, '').split('|').map(c => c.trim()))
  const ncol = Math.max(...cells.map(r => r.length))
  const border = { style: d.BorderStyle.SINGLE, size: 4, color: '808080' }
  const b4 = { top: border, bottom: border, left: border, right: border }
  return new d.Table({
    visuallyRightToLeft: true, width: { size: 100, type: d.WidthType.PERCENTAGE },
    rows: cells.map((r, i) => new d.TableRow({
      cantSplit: true, tableHeader: i === 0,
      children: Array.from({ length: ncol }, (_, j) => new d.TableCell({
        borders: b4, margins: { left: 80, right: 80 },
        children: [P(inlineRuns(r[j] || '', { ...ctx, size: SZ_SMALL, bold: i === 0 }), { align: d.AlignmentType.RIGHT, after: 0 })],
      })),
    })),
  })
}

// continuation pages: move the first paragraph of a "+" page into the last paragraph of the previous page
// (end-of-page gloss boxes stay after the joined paragraph)
function joinContinuations(pages) {
  for (const p of pages) for (const b of p.blocks) if (b.type === 'para') b.segs = [{ page: p.page, text: b.text }]
  for (let i = 1; i < pages.length; i++) {
    const p = pages[i], prev = pages[i - 1]
    if (!p.cont || !p.blocks.length || p.blocks[0].type !== 'para') continue
    let j = prev.blocks.length - 1
    while (j >= 0 && prev.blocks[j].type === 'fence' && prev.blocks[j].kind === ':::مفردات') j--
    if (j < 0 || prev.blocks[j].type !== 'para') continue
    prev.blocks[j].segs.push(...p.blocks[0].segs)
    p.blocks.shift()
  }
}

function build(pages) {
  joinContinuations(pages)
  const { fn, map } = collectFootnotes(pages)
  const used = new Set()
  const out = []
  let firstH1 = true
  for (const p of pages) {
    const ctx = { page: p.page, fnmap: map, used }
    p.blocks.forEach(b => {
      if (b.type === 'para') {
        const runs = []
        b.segs.forEach((sg, n) => {
          if (n) runs.push(baseRun(' '))
          runs.push(...inlineRuns(sg.text, { ...ctx, page: sg.page }))
        })
        out.push(P(runs))
        return
      }
      if (b.type === 'heading') {
        const lvl = [null, d.HeadingLevel.HEADING_1, d.HeadingLevel.HEADING_2, d.HeadingLevel.HEADING_3][b.level]
        out.push(P(inlineRuns(b.text, { ...ctx, size: [0, 40, 34, 32][b.level], bold: true }), {
          heading: lvl, align: d.AlignmentType.CENTER, keepNext: true,
          pageBreakBefore: b.level === 1 && !firstH1 ? true : undefined, before: b.level === 1 ? 240 : 120,
        }))
        if (b.level === 1) firstH1 = false
      } else if (b.type === 'sep') {
        out.push(P([baseRun('*  *  *')], { align: d.AlignmentType.CENTER }))
      } else if (b.type === 'table') {
        out.push(mdTable(b.rows, ctx)); out.push(P([], { after: 60 }))
      } else if (b.type === 'fence' && b.kind === ':::شعر') {
        out.push(poetryTable(b.lines, ctx)); out.push(P([], { after: 60 }))
      } else if (b.type === 'fence' && b.kind === ':::شعر مشطور') {
        for (const ln of b.lines) out.push(P(inlineRuns(ln, ctx), { align: d.AlignmentType.CENTER, after: 40 }))
      } else if (b.type === 'fence' && b.kind === ':::مفردات') {
        out.push(glossBox(b.lines, ctx)); out.push(P([], { after: 60 }))
      }
    })
  }
  // footnotes whose reference was not found: append them as references at the end
  const orphan = Object.keys(fn).map(Number).filter(i => !used.has(i))
  if (orphan.length) out.push(P(orphan.map(i => new d.FootnoteReferenceRun(i))))
  const footnotes = {}
  for (const [i, texts] of Object.entries(fn)) {
    footnotes[i] = { children: texts.map(t => P(inlineRuns(t, { size: SZ_FN }), { after: 0, align: d.AlignmentType.BOTH })) }
  }
  return { body: out, footnotes, orphan }
}

// ---------------------------------------------------------------- document
const pages = parse(fs.readFileSync(IN, 'utf8'))
const { body, footnotes, orphan } = build(pages)
const font = { ascii: BODY_FONT, hAnsi: BODY_FONT, cs: BODY_FONT, eastAsia: BODY_FONT }
const hstyle = (id, name, size) => ({
  id, name, basedOn: 'Normal', next: 'Normal', quickFormat: true,
  run: { font, size, sizeComplexScript: size, bold: true, boldComplexScript: true, color: '000000', rightToLeft: true },
  paragraph: { bidirectional: true, alignment: d.AlignmentType.CENTER, spacing: { before: 240, after: 120 }, keepNext: true },
})
const front = []
if (WITH_TOC) {
  front.push(P([baseRun('المحتويات', { bold: true, size: 40 })], { align: d.AlignmentType.CENTER, after: 240 }))
  front.push(new d.TableOfContents('المحتويات', { hyperlink: true, headingStyleRange: '1-2' }))
}
const footer = new d.Footer({ children: [new d.Paragraph({
  alignment: d.AlignmentType.CENTER, bidirectional: true,
  children: [new d.TextRun({ children: [d.PageNumber.CURRENT], rightToLeft: true, font, size: 26, sizeComplexScript: 26 })],
})] })
const sectionProps = {
  page: {
    size: { width: 8391, height: 11906 },                      // A5
    margin: { top: 1020, bottom: 1020, left: 964, right: 964, footer: 454 },
  },
  bidi: true,
}
const doc = new d.Document({
  creator: 'durar-transcription', title: 'الدرر النقية في أوراد الطريقة اليسرية الصديقية',
  styles: {
    default: {
      document: {
        run: { font, size: SZ, sizeComplexScript: SZ, rightToLeft: true, language: { value: 'ar-EG', bidirectional: 'ar-EG' } },
        paragraph: { bidirectional: true, spacing: { line: LINE, lineRule: d.LineRuleType.AUTO } },
      },
    },
    paragraphStyles: [hstyle('Heading1', 'Heading 1', 40), hstyle('Heading2', 'Heading 2', 34), hstyle('Heading3', 'Heading 3', 32)],
  },
  footnotes,
  sections: [
    ...(WITH_TOC ? [{ properties: sectionProps, footers: { default: footer }, children: front }] : []),
    { properties: sectionProps, footers: { default: footer }, children: body },
  ],
})
d.Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf)
  console.log(`wrote ${OUT}: ${pages.length} pages of source, ${Object.keys(footnotes).length} footnotes` +
    (orphan.length ? `, ${orphan.length} footnotes without a reference: ${orphan.join(',')}` : ''))
})

export const meta = {
  name: 'durar-batches',
  description: 'Double-key, adjudicate and guard batches of the الدرر النقية transcription (resumable per batch)',
  whenToUse: 'Run with args {batches:[n,...], root, python}; finished keyings/batches are skipped',
  phases: [
    { title: 'Status', detail: 'read which keyings / batches are already done' },
    { title: 'Key', detail: 'keyer A and keyer B transcribe each batch independently' },
    { title: 'Adjudicate', detail: 'diff A/B + Quran check, decide every spot against the images' },
    { title: 'Guard', detail: 'check_final.py: final = A + logged decisions, and valid' },
    { title: 'Report', detail: 'regenerate STATUS.md' },
  ],
}

// Paths use "/" so the same script works on Windows (Git Bash / PowerShell) and in a Linux cloud session.
//   Windows: {root: 'C:/Users/JellyFish/durar-transcription', python: 'C:/Python312/python.exe'} (the defaults)
//   Cloud:   {root: '<absolute repo path>', python: 'python3'}
const A = args || {}
const ROOT = (A.root || 'C:/Users/JellyFish/durar-transcription').replace(/[\\/]+$/, '')
const PY = A.python || 'C:/Python312/python.exe'
const BATCHES = (A.batches || []).map(Number)
const MODEL_A = A.modelA || 'opus'
const MODEL_B = A.modelB || 'opus'   // user choice after the pilot (2026-10-03)
const MODEL_ADJ = A.modelAdj || 'opus'
const MAX = A.maxConcurrent || 8
const R = rel => `${ROOT}/${rel}`

// ---- simple concurrency limiter (at most MAX agents at once) ----
let active = 0
const waiting = []
async function limited(fn) {
  if (active >= MAX) await new Promise(r => waiting.push(r))
  active++
  try { return await fn() } finally {
    active--
    const next = waiting.shift()
    if (next) next()
  }
}
const run = (prompt, opts) => limited(() => agent(prompt, opts))

const pad = n => String(n).padStart(2, '0')
const p3 = n => String(n).padStart(3, '0')
const pagesOf = k => [4 * k - 3, 4 * k - 2, 4 * k - 1, 4 * k]

const STATUS_SCHEMA = {
  type: 'object',
  properties: {
    done: { type: 'array', items: { type: 'integer' } },
    keyA_valid: { type: 'array', items: { type: 'integer' } },
    keyB_valid: { type: 'array', items: { type: 'integer' } },
  },
  required: ['done', 'keyA_valid', 'keyB_valid'],
}
const KEY_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean', description: 'true only if validate.py printed OK for your file' },
    validate_last_line: { type: 'string' },
    uncertain: { type: 'integer', description: 'number of [؟:…] markers you wrote' },
    notes: { type: 'string' },
  },
  required: ['ok', 'validate_last_line', 'uncertain'],
}
const ADJ_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean', description: 'true only if apply.py printed VALID and check_final.py printed PASS' },
    agreement: { type: 'number' },
    n_items: { type: 'integer' },
    choices: { type: 'object', properties: { A: { type: 'integer' }, B: { type: 'integer' }, T: { type: 'integer' }, custom: { type: 'integer' } } },
    n_extra_edits: { type: 'integer' },
    unresolved: { type: 'integer' },
    mode: { type: 'string' },
    notes: { type: 'string' },
  },
  required: ['ok', 'agreement', 'n_items', 'unresolved'],
}
const GUARD_SCHEMA = {
  type: 'object',
  properties: { pass: { type: 'boolean' }, problems: { type: 'array', items: { type: 'string' } } },
  required: ['pass', 'problems'],
}

function keyerPrompt(k, who) {
  const name = `b${pad(k)}`
  const pg = pagesOf(k)
  const other = who === 'A' ? 'keyB' : 'keyA'
  return `You are keyer ${who}, one of two INDEPENDENT transcribers of the Arabic book «الدُّرَر النَّقِيَّة».
Project root: ${ROOT}   Python: ${PY}
Your batch: ${name} = PDF pages ${pg.map(p3).join(', ')}.

1. Read ${R('CONVENTIONS.md')} and ${R('STRUCTURE.md')} completely before anything else. They are binding.
2. For each page N in order: look at pages/pNNN.png (layout), then transcribe line by line from crops/pNNN_top.png and
   crops/pNNN_bot.png, checking every letter and every haraka against the image before writing the next word.
   Zoom with scripts/zoom.py (output under scratch/) wherever marks are small: Quran text, footnotes, glosses,
   honorific glyphs. Never use the PDF text layer.
   For page ${p3(pg[0])} also glance at pages/p${p3(pg[0] - 1 || 1)}.png to decide whether its first paragraph
   continues the previous page (marker with "+") or whether a footnote continues ("(تابع)").
3. Write the whole batch to ${R(`key${who}/${name}.md`)} (UTF-8), pages in order, each starting with its marker.
4. Run: ${PY} ${R('scripts/validate.py')} ${R(`key${who}/${name}.md`)}
   Fix every ERROR (re-check the image, do not just delete text) and re-run until it prints OK.
5. Write ${R(`key${who}/${name}.notes.json`)} as described in CONVENTIONS §15.

Independence: do NOT open anything in ${other}/, diff/, final/ or reports/. Do not edit any file except your two
output files and scratch/ images. Accuracy matters far more than speed: every letter and haraka must match the print.
If you cannot read something with certainty, use [؟:best reading] — never guess silently.
Return ok=true only if validate.py printed OK.`
}

function adjPrompt(k, extra) {
  const name = `b${pad(k)}`
  const pg = pagesOf(k)
  return `You are the ADJUDICATOR for batch ${name} (PDF pages ${pg.map(p3).join(', ')}) of the Arabic book
«الدُّرَر النَّقِيَّة». Two independent keyers (A and B) have transcribed it. The printed page image is the only
authority. Project root: ${ROOT}   Python: ${PY}

1. Read ${R('CONVENTIONS.md')} and ${R('STRUCTURE.md')} completely.
2. Run: ${PY} ${R('scripts/diff.py')} ${name}     then read ${R(`diff/${name}.json`)}.
   It lists: d-items (A/B disagreements, type haraka/letters/punct/structure/cont/uncertain, with a_text, b_text and
   5 tokens of context; some carry a tanzil_hint), q-items (A's Quran words that differ from the Tanzil Uthmani text),
   and u-items (A's [؟:…] markers that B agreed with). a_range = token indices in A's page (¶ = line break).
   The keyer files are keyA/${name}.md and keyB/${name}.md if you need more context.
3. Decide EVERY item by looking at the image: crops/pNNN_top.png / _bot.png, and zoom with
   ${PY} ${R('scripts/zoom.py')} N x0 y0 x1 y1 ${R(`scratch/${name}_z.png`)} 500  (fractions of the page).
   - d-items: "A", "B", or "custom" with the correct text for A's range (when both are wrong). For structure items
     follow CONVENTIONS exactly (fences, headings, footnote glue, paragraphs; use ¶ inside custom text for a line break).
   - q-items: the print is the target, Tanzil is a cross-check. If the image clearly shows A's reading, choose "A"
     (a genuine print variant — say so in the note). If the image shows Tanzil's reading, or the mark is too small to
     be sure either way, choose "T". Use "custom" if neither matches the print.
   - u-items: "custom" with the resolved reading if the zoom makes it certain; otherwise "A" (keep the [؟:…] marker).
   - Any reading that stays uncertain must be written as [؟:best reading] in a custom text.
   Give every decision a short note saying what you saw (e.g. "kasra clearly visible under ل").
4. If diff.json says full_reread_required (agreement below 95%), ALSO re-read the whole batch line by line against
   the crops and compare with A; fix each further error with an extra edit, and set mode "full_reread".
   If agreement is 99% or higher, the two keyings are nearly identical, so the diff cannot reveal errors they share:
   then you MUST also re-read every page line by line against the crops (zooming on harakat, Quran marks, footnotes
   and glosses) and compare with A — but keep mode "spots" unless agreement is below 95%.
   In any mode you may add an extra edit for an error in A that BOTH keyers share, but only when the image is
   unambiguous; every extra edit needs a note. Never "improve" the book's text.
4b. Online cross-check (another edition, a hint only, like Tanzil): run
   ${PY} ${R('scripts/online_check.py')} ${name}   then read ${R(`diff/${name}.online.json`)} (if it lists no sources, skip).
   w-items are word differences between A and the online text; h-items are contradictory harakat (both vowel the same
   letter differently). Headings, verse numbers, «ثلاثًا»-type notes and whole lines missing from the online text are
   normal and need no action. For every other item, look at the image (zoom) and decide: if the image clearly shows
   the online reading and A (after your decisions) is wrong, add an extra edit with note "online cross-check: …".
   If the image shows A's reading, or is unclear, change nothing — editions really differ (e.g. حَيْطَانُنَا in the
   print vs حِيطَانُنَا online). Never copy the online text where the print differs.
5. Write ${R(`diff/${name}.decisions.json`)}:
   {"mode": "spots" | "full_reread", "decisions": {"d001": {"choice": "A", "note": "…"}, …},
    "extra_edits": [{"page": 65, "find": "exact current text on that page", "replace": "…", "note": "…"}]}
   ("find" must occur exactly once in that page of the result; include enough words to be unique.)
6. Run: ${PY} ${R('scripts/apply.py')} ${name}  — it builds final/${name}.md from A + your decisions and validates it.
   On APPLY ERROR or INVALID, fix the decisions file and re-run. Never edit final/${name}.md by hand.
7. Run: ${PY} ${R('scripts/check_final.py')} ${name}  — it must print PASS.
Return ok=true only if apply printed VALID and check_final printed PASS.${extra ? '\n\nIMPORTANT — a previous attempt failed the guard with:\n' + extra : ''}`
}

const guardPrompt = k => `Run exactly this command and report its JSON result (pass and problems), nothing else:
${PY} ${R('scripts/check_final.py')} b${pad(k)} --json`

// ---------------------------------------------------------------
phase('Status')
const st = await run(`Run exactly this command and return its JSON output (fields done, keyA_valid, keyB_valid):
${PY} ${R('scripts/status.py')} --json`, { label: 'status', phase: 'Status', schema: STATUS_SCHEMA, model: 'haiku', effort: 'low' })
const done = new Set((st && st.done) || [])
const haveA = new Set((st && st.keyA_valid) || [])
const haveB = new Set((st && st.keyB_valid) || [])
const todo = BATCHES.filter(k => !done.has(k))
log(`batches requested ${BATCHES.join(',')} · already done ${BATCHES.filter(k => done.has(k)).join(',') || 'none'} · to process ${todo.join(',') || 'none'}`)

async function keyWithRetry(k, who) {
  if ((who === 'A' ? haveA : haveB).has(k)) return { ok: true, skipped: true }
  for (let attempt = 1; attempt <= 3; attempt++) {
    const r = await run(keyerPrompt(k, who), {
      label: `key${who} b${pad(k)}${attempt > 1 ? ' retry' + attempt : ''}`, phase: 'Key', schema: KEY_SCHEMA,
      model: who === 'A' ? MODEL_A : MODEL_B,
    })
    if (r && r.ok) return r
    log(`b${pad(k)} key${who} attempt ${attempt} failed: ${r ? r.validate_last_line : 'agent error'}`)
  }
  return { ok: false }
}

async function adjudicate(k) {
  let extra = ''
  for (let attempt = 1; attempt <= 2; attempt++) {
    const r = await run(adjPrompt(k, extra), {
      label: `adjudicate b${pad(k)}${attempt > 1 ? ' retry' : ''}`, phase: 'Adjudicate', schema: ADJ_SCHEMA, model: MODEL_ADJ,
    })
    const g = await run(guardPrompt(k), { label: `guard b${pad(k)}`, phase: 'Guard', schema: GUARD_SCHEMA, model: 'haiku', effort: 'low' })
    if (g && g.pass) return { ...(r || {}), guard: 'PASS' }
    extra = g ? g.problems.join('\n') : 'guard agent failed'
    log(`b${pad(k)} guard FAIL (attempt ${attempt}): ${extra.slice(0, 200)}`)
  }
  return { ok: false, guard: 'FAIL', notes: extra }
}

const results = await pipeline(
  todo,
  async k => {
    const [a, b] = await Promise.all([keyWithRetry(k, 'A'), keyWithRetry(k, 'B')])
    return { k, a, b }
  },
  async ({ k, a, b }) => {
    if (!a.ok || !b.ok) {
      log(`b${pad(k)}: keying failed (A ${a.ok}, B ${b.ok}) — flagged, not adjudicated`)
      return { k, state: 'key_failed' }
    }
    const r = await adjudicate(k)
    log(`b${pad(k)}: ${r.guard === 'PASS' ? 'DONE' : 'FAILED'} · agreement ${r.agreement != null ? (100 * r.agreement).toFixed(1) + '%' : '?'} · ${r.n_items ?? '?'} items · choices ${JSON.stringify(r.choices || {})} · unresolved ${r.unresolved ?? '?'}`)
    return { k, state: r.guard === 'PASS' ? 'done' : 'adj_failed', ...r }
  },
)

phase('Report')
const st2 = await run(`Run exactly this command and return its JSON output (fields done, keyA_valid, keyB_valid):
${PY} ${R('scripts/status.py')} --write --json`, { label: 'status --write', phase: 'Report', schema: STATUS_SCHEMA, model: 'haiku', effort: 'low' })
return { results: results.filter(Boolean), done_total: st2 ? st2.done.length : null, done: st2 ? st2.done : null }

// Screen-catalog audit — run after `npm run build:catalog` (npm run audit -- [options]):
//
//   node scripts/catalog-audit.mjs [--dist dist-catalog] [--chrome <path to chrome.exe>] [--theme light|dark|light,dark]
//                                  [--filter <regex on scenario id>] [--json <report.json>] [--dump <surfaces.json>]
//
// It drives headless Chrome over the DevTools protocol (Node's built-in WebSocket, no extra dependency), loads
// every scenario in the catalog manifest — in both its popup view and its background-only view — and checks:
//
//   1. each view reaches data-catalog-state="ready" with the expected number of open popups, nothing still
//      fading in, no missing-resx marker, no JavaScript error;
//   2. COVERAGE: every string in Rebit's src/i18n/locales/en/screens.json (generated from Resources.resx) is visible
//      on at least one scenario — as text, or as an attribute (placeholder / aria-label / title). A key that is
//      genuinely not reachable has to be listed with a reason and evidence in
//      scripts/catalog-coverage-exceptions.json, so an unexplained gap fails the audit;
//   3. every exception still names a key that exists, and is still unrendered (a stale exception fails).
//
// Exit code 0 only when there is nothing unexplained. This script is a developer tool, not shipped.
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { catalogRoot, resolveWebSrc } from './webSrc.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))

const webDir = catalogRoot // where dist-catalog/ is
const appWeb = resolveWebSrc() // Rebit's TargetPc.UI/web — the app's generated text file is read from there

function arg(name, fallback) {
  const at = process.argv.indexOf(`--${name}`)
  return at >= 0 && process.argv[at + 1] ? process.argv[at + 1] : fallback
}

const distDir = path.resolve(webDir, arg('dist', 'dist-catalog'))
const chromePath = arg('chrome', process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe')
const themes = arg('theme', 'light').split(',')
const only = arg('filter', '') ? new RegExp(arg('filter', '')) : undefined
const reportPath = arg('json', '')
const dumpPath = arg('dump', '') // every view's text, attributes, controls and per-element typography/boxes, for baselining or a design comparison
const dump = {}

if (!fs.existsSync(path.join(distDir, 'catalog.html'))) {
  console.error(`No catalog build at ${distDir}. Run "npm run build:catalog" first.`)
  process.exit(2)
}

// ── static file server for dist-catalog ──────────────────────────────────────
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.json': 'application/json', '.map': 'application/json' }
const server = http.createServer((req, res) => {
  const file = path.join(distDir, decodeURIComponent(new URL(req.url, 'http://x').pathname))
  if (!file.startsWith(distDir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); res.end(); return }
  res.writeHead(200, { 'content-type': MIME[path.extname(file)] ?? 'application/octet-stream' })
  fs.createReadStream(file).pipe(res)
})
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
const base = `http://127.0.0.1:${server.address().port}`

// ── headless Chrome over CDP ─────────────────────────────────────────────────
const port = 9300 + Math.floor(Math.random() * 600)
const chrome = spawn(chromePath, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${fs.mkdtempSync(path.join(os.tmpdir(), 'catalog-audit-'))}`, '--no-first-run', '--disable-gpu', '--hide-scrollbars', '--window-size=1200,800', 'about:blank'], { stdio: 'ignore' })
const cdp = async (p) => (await fetch(`http://127.0.0.1:${port}${p}`)).json()
for (let i = 0; i < 80; i++) { try { await cdp('/json/version'); break } catch { await new Promise((r) => setTimeout(r, 250)) } }
const page = (await cdp('/json/list')).find((t) => t.type === 'page')
const ws = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((resolve) => (ws.onopen = resolve))
let nextId = 0
const pending = new Map()
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id) } }
const send = (method, params = {}) => new Promise((resolve) => { const id = ++nextId; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })) })
const evaluate = async (expression) => (await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result?.result?.value
await send('Page.enable')
// The app's own window: every position in the dump is then relative to its top-left corner.
await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 800, deviceScaleFactor: 1, mobile: false })

async function load(query) {
  await send('Page.navigate', { url: `${base}/catalog.html${query ? `?${query}` : ''}` })
  for (let i = 0; i < 150; i++) {
    await new Promise((r) => setTimeout(r, 100))
    const state = await evaluate('document.body && document.body.dataset.catalogState')
    if (state && state !== 'pending') {
      return JSON.parse(await evaluate(`JSON.stringify({
        state: document.body.dataset.catalogState,
        error: document.body.dataset.catalogError || null,
        dialogs: Number(document.body.dataset.catalogDialogs ?? -1),
        jsErrors: window.__CATALOG_ERRORS__ ?? [],
        minOpacity: Math.min(1, ...Array.from(document.querySelectorAll('dialog[open]')).map((d) => Number(getComputedStyle(d).opacity))),
        text: window.__CATALOG__?.collectText?.() ?? null })`))
    }
  }
  return { state: 'timeout', error: 'never left pending', dialogs: -1, jsErrors: [], text: null }
}

// ── 1. sweep every scenario view ─────────────────────────────────────────────
await load('')
const manifest = JSON.parse(await evaluate('JSON.stringify(window.__SCREEN_CATALOG__)'))
const problems = []
const harvested = [] // every string seen on screen, across all views
const nodes = new Set() // each visible text node on its own (exact matching of short labels)
const attrValues = new Set() // each attribute value (aria-label / placeholder / title) on its own
const squashPlain = (s) => s.replace(/\s+/g, '')
let views = 0
for (const entry of manifest) {
  if (only && !only.test(entry.id)) continue
  const wanted = [{ name: 'shown', query: entry.query }]
  if (entry.hasPopup) wanted.push({ name: 'background', query: entry.backgroundQuery })
  for (const view of wanted) {
    for (const theme of themes) {
      views++
      const r = await load(`${view.query}&theme=${theme}`)
      const found = []
      if (r.state !== 'ready') found.push(`state=${r.state} (${r.error})`)
      if (view.name === 'shown' && entry.hasPopup && r.dialogs < 1) found.push('popup expected but no dialog open')
      if (view.name === 'shown' && !entry.hasPopup && r.dialogs !== 0) found.push(`no popup expected but ${r.dialogs} open`)
      if (view.name === 'background' && r.dialogs !== 0) found.push(`background view still has ${r.dialogs} dialog(s)`)
      if (r.minOpacity < 0.99) found.push(`popup still fading in (opacity ${r.minOpacity})`)
      if (r.jsErrors.length) found.push(`js errors: ${r.jsErrors.slice(0, 2).join(' | ')}`)
      const surfaces = [r.text?.surfaces?.page, ...(r.text?.surfaces?.popups ?? [])].filter(Boolean)
      const text = [r.text?.page ?? '', ...(r.text?.popups ?? []), ...surfaces.map((s) => s.text)].join(' ')
      if (text.includes('⟦missing:')) found.push('missing resx key in rendered text')
      for (const s of surfaces) {
        harvested.push(s.text)
        for (const n of s.nodes ?? []) nodes.add(squashPlain(n))
        for (const a of s.attributes) { harvested.push(a.value); attrValues.add(squashPlain(a.value)) }
      }
      if (dumpPath) dump[`${entry.id}${view.name === 'background' ? '#background' : ''}@${theme}`] = r.text?.surfaces
      if (found.length) problems.push({ id: entry.id, view: view.name, theme, found })
    }
  }
}
ws.close(); chrome.kill(); server.close()

// ── 2/3. coverage of the resx strings ────────────────────────────────────────
const screens = JSON.parse(fs.readFileSync(path.join(appWeb, 'src/i18n/locales/en/screens.json'), 'utf8'))
const exceptionsFile = path.join(here, 'catalog-coverage-exceptions.json')
const exceptions = fs.existsSync(exceptionsFile) ? JSON.parse(fs.readFileSync(exceptionsFile, 'utf8')) : { resxKeys: {} }

const decode = (s) => s.replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
const squash = (s) => decode(s.replace(/<[^>]+>/g, '')).replace(/\s+/g, '')
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const haystack = harvested.map((h) => h.replace(/\s+/g, '')).join('\n')

const unrendered = []
if (!only) {
  for (const [key, value] of Object.entries(screens)) {
    const plain = squash(value)
    const hasPlaceholder = /\{\{?\w+\}?\}/.test(plain)
    // A short label ("View details") must be a whole text node (or attribute value) of its own: as a substring it
    // would also be "found" inside a longer sentence that merely contains it.
    if (plain.length < 30 && !hasPlaceholder) {
      // Exact node; or a node the app extends with a count ("Files transferred (1284)"); or an attribute the app builds
      // by prefixing a caption ("Settings needs attention").
      const found = nodes.has(plain)
        || [...nodes].some((n) => n.startsWith(`${plain}(`))
        || [...attrValues].some((a) => a === plain || a.endsWith(plain))
      if (!found) unrendered.push(key)
      continue
    }
    const pattern = escape(plain).replace(/\\\{\\\{\w+\\\}\\\}|\\\{\w+\\\}/g, '.*?')
    if (!new RegExp(pattern).test(haystack)) unrendered.push(key)
  }
}
const allowed = exceptions.resxKeys ?? {}
const unexplained = unrendered.filter((k) => !(k in allowed))
const stale = Object.keys(allowed).filter((k) => !(k in screens) || !unrendered.includes(k))

console.log(`views checked: ${views} · scenarios: ${manifest.length}`)
console.log(`views with problems: ${problems.length}`)
for (const p of problems) console.log(`  FAIL ${p.id} [${p.view}, ${p.theme}] ${p.found.join('; ')}`)
if (!only) {
  console.log(`resx strings: ${Object.keys(screens).length} · rendered on a scenario: ${Object.keys(screens).length - unrendered.length} · explained exceptions: ${unrendered.length - unexplained.length}`)
  for (const k of unexplained) console.log(`  UNEXPLAINED never rendered: ${k}`)
  for (const k of stale) console.log(`  STALE exception (key missing or now rendered): ${k}`)
}
if (dumpPath) fs.writeFileSync(dumpPath, JSON.stringify(dump, null, 1))
if (reportPath) fs.writeFileSync(reportPath, JSON.stringify({ views, problems, unrendered, unexplained, stale }, null, 1))
process.exit(problems.length || unexplained.length || stale.length ? 1 : 0)

// The framed viewer (?…&frame=1) — how a person looks at one scenario. The app is shown in an iframe of exactly
// 1200x800 CSS px, the design size every screen is built for (index.css's stage; WindowFit's design content
// size), so it renders as it does in the app's window: same layout, same background crop, popups centred in
// the window rather than in whatever size the browser happens to be. Like the native shell (WindowFit caps its
// content scale at 1) it is only ever scaled DOWN to fit a small browser window, never enlarged.
//
// Every control lives in the bar above the frame — outside the app, so nothing the catalog adds is ever on the
// app's surface or covers its text, and the controls stay clickable while a popup is open (a modal <dialog>
// only makes the iframe's own document inert, not this page). The app's popups are not altered in any way.
//
// Keys (work with focus inside the app too, via forwardKeysToParent): [ or p prev · ] or n next · b popup/
// background · d light/dark · i index (arrows too, only when the app is not focused). They avoid the
// arrows/space/enter the app's own radio groups, dropdowns and inputs use, and are ignored while typing.
// See shortcutOf for the layout handling (AltGr, physical key codes).
import {
  PHASES,
  SCREEN_LABELS,
  CATEGORIES,
  categoryOf,
  hasPopup,
  hostScreen,
  labelOf,
  scenarioId,
  scenarioQuery,
  scenarios,
  type Scenario,
  type ThemeName,
} from './scenarios'

const DESIGN_WIDTH = 1200
const DESIGN_HEIGHT = 800

const CSS = `
.cf { min-height: 100vh; box-sizing: border-box; padding: 0 1.5rem 1.5rem; font: 400 .875rem/1.4 system-ui, 'Segoe UI', sans-serif;
  background: var(--cf-bg); color: var(--cf-fg); }
.cf-light { --cf-bg: #e9ebee; --cf-fg: #1b1d20; --cf-bar: #ffffff; --cf-line: #cfd3d8; --cf-muted: #5d646c; --cf-link: #0b66c3; --cf-on: #0b66c3; --cf-on-fg: #fff; }
.cf-dark  { --cf-bg: #17191c; --cf-fg: #e8eaed; --cf-bar: #23262a; --cf-line: #3a3f45; --cf-muted: #a2a9b1; --cf-link: #7db8f5; --cf-on: #7db8f5; --cf-on-fg: #0d1114; }
/* The column is exactly the stage's width (set in fit()), so the bar and the hint line up with the app window. */
.cf-col { margin: 0 auto; }
.cf-bar { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem 1rem; box-sizing: border-box; width: 100%;
  padding: .6rem .9rem; background: var(--cf-bar); border: 1px solid var(--cf-line); border-top: 0; border-radius: 0 0 .5rem .5rem; }
.cf-nav { display: flex; gap: .4rem; }
.cf-btn { color: var(--cf-link); text-decoration: none; padding: .2rem .65rem; border: 1px solid var(--cf-line); border-radius: .4rem; background: transparent; }
.cf-btn:hover { border-color: var(--cf-link); }
.cf-btn[aria-disabled="true"] { opacity: .4; pointer-events: none; }
.cf-where { flex: 1 1 18rem; min-width: 0; }
.cf-crumb { color: var(--cf-muted); font-size: .78rem; }
.cf-title { font-size: 1rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cf-badge { display: inline-block; margin-left: .5rem; padding: 0 .5rem; border: 1px solid var(--cf-line); border-radius: .7rem; font-size: .72rem; font-weight: 500; color: var(--cf-muted); }
.cf-seg { display: inline-flex; border: 1px solid var(--cf-line); border-radius: .4rem; overflow: hidden; }
.cf-seg a { padding: .2rem .65rem; color: var(--cf-link); text-decoration: none; }
.cf-seg a + a { border-left: 1px solid var(--cf-line); }
.cf-seg a[aria-current="true"] { background: var(--cf-on); color: var(--cf-on-fg); }
.cf-pos { color: var(--cf-muted); font-size: .78rem; }
.cf-note { flex-basis: 100%; color: #b25e00; font-size: .78rem; }
.cf-stage { margin: 1.5rem 0 0; position: relative; box-shadow: 0 .4rem 1.7rem rgba(0,0,0,.28); border-radius: .25rem; overflow: hidden; }
.cf-frame { position: absolute; top: 0; left: 0; width: ${DESIGN_WIDTH}px; height: ${DESIGN_HEIGHT}px; border: 0; transform-origin: top left; background: #fff; }
.cf-hint { margin: .9rem 0 0; color: var(--cf-muted); font-size: .78rem; text-align: center; }
.cf-hint kbd { border: 1px solid var(--cf-line); border-radius: .25rem; padding: 0 .3rem; background: var(--cf-bar); font: inherit; }
`

/** The viewer URL for a scenario (or the index when scenario is undefined), keeping the current theme/locale. */
export function viewerHref(current: URLSearchParams, scenario: Scenario | undefined, overrides: { popups?: 'shown' | 'hidden'; theme?: ThemeName } = {}): string {
  const next = new URLSearchParams(scenario ? scenarioQuery(scenario) : '')
  const theme = overrides.theme ?? current.get('theme')
  if (theme) {
    next.set('theme', theme)
  }
  const locale = current.get('locale')
  if (locale) {
    next.set('locale', locale)
  }
  if (scenario) {
    next.set('frame', '1')
    if (overrides.popups === 'hidden') {
      next.set('popups', 'hidden')
    }
  }
  const query = next.toString()
  return query ? `?${query}` : window.location.pathname
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag)
  if (className) node.className = className
  if (text !== undefined) node.textContent = text
  return node
}

function link(label: string, href: string | undefined, className = 'cf-btn'): HTMLAnchorElement {
  const a = el('a', className, label)
  if (href) {
    a.href = href
  } else {
    a.setAttribute('aria-disabled', 'true')
  }
  return a
}

function segmented(items: { label: string; href: string; on: boolean }[]): HTMLElement {
  const group = el('span', 'cf-seg')
  for (const item of items) {
    const a = link(item.label, item.href, '')
    a.className = ''
    if (item.on) {
      a.setAttribute('aria-current', 'true')
    }
    group.appendChild(a)
  }
  return group
}

export function renderFrame(host: HTMLElement, scenario: Scenario, params: URLSearchParams, popups: 'shown' | 'hidden', theme: ThemeName): void {
  const index = scenarios.indexOf(scenario)
  const prev = index > 0 ? scenarios[index - 1] : undefined
  const next = index < scenarios.length - 1 ? scenarios[index + 1] : undefined
  const popup = hasPopup(scenario)
  const otherTheme: ThemeName = theme === 'dark' ? 'light' : 'dark'
  const href = (target: Scenario | undefined, o: { popups?: 'shown' | 'hidden'; theme?: ThemeName } = {}) => viewerHref(params, target, o)

  const style = el('style')
  style.textContent = CSS
  document.head.appendChild(style)

  const root = el('div', `cf ${theme === 'dark' ? 'cf-dark' : 'cf-light'}`)
  const bar = el('div', 'cf-bar')

  const nav = el('div', 'cf-nav')
  nav.append(link('Index', href(undefined)), link('◀ Prev', prev && href(prev)), link('Next ▶', next && href(next)))
  bar.appendChild(nav)

  const where = el('div', 'cf-where')
  const phase = PHASES.find((p) => p.id === scenario.phase)?.label ?? scenario.phase
  where.appendChild(el('div', 'cf-crumb', `${phase} › ${SCREEN_LABELS[hostScreen(scenario)]}`))
  const title = el('div', 'cf-title', labelOf(scenario))
  const category = CATEGORIES.find((c) => c.id === categoryOf(scenario))
  title.appendChild(el('span', 'cf-badge', category ? category.label.replace(/ \(.*\)$/, '') : ''))
  where.appendChild(title)
  bar.appendChild(where)

  if (popup) {
    bar.appendChild(segmented([
      { label: 'With popup', href: href(scenario, { popups: 'shown' }), on: popups === 'shown' },
      { label: 'Background only', href: href(scenario, { popups: 'hidden' }), on: popups === 'hidden' },
    ]))
  }
  bar.appendChild(segmented([
    { label: 'Light', href: href(scenario, { popups, theme: 'light' }), on: theme === 'light' },
    { label: 'Dark', href: href(scenario, { popups, theme: 'dark' }), on: theme === 'dark' },
  ]))
  bar.appendChild(el('span', 'cf-pos', `${index + 1} / ${scenarios.length}`))

  // Light is only exact when the OS is light too: DDS's own colours follow the OS media query, which the
  // page cannot override (dark is made exact by the dds--dark-mode class, see main.tsx).
  if (theme === 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    bar.appendChild(el('div', 'cf-note', 'This browser is in dark mode, so some light-theme colours are approximate. Switch the OS/browser to light for an exact view.'))
  }
  const column = el('div', 'cf-col')
  root.appendChild(column)
  column.appendChild(bar)

  const stage = el('div', 'cf-stage')
  const frame = el('iframe', 'cf-frame')
  frame.title = scenarioId(scenario)
  const inner = new URLSearchParams(scenarioQuery(scenario))
  inner.set('theme', theme)
  inner.set('embed', '1')
  if (params.get('locale')) inner.set('locale', params.get('locale')!)
  if (popups === 'hidden') inner.set('popups', 'hidden')
  frame.src = `${window.location.pathname}?${inner.toString()}`
  stage.appendChild(frame)
  column.appendChild(stage)

  const hint = el('div', 'cf-hint')
  hint.innerHTML = '<kbd>[</kbd> or <kbd>p</kbd> prev &nbsp; <kbd>]</kbd> or <kbd>n</kbd> next &nbsp; <kbd>b</kbd> popup / background &nbsp; <kbd>d</kbd> light / dark &nbsp; <kbd>i</kbd> index &nbsp; (<kbd>←</kbd> <kbd>→</kbd> too, when the app is not focused; inside a text field hold <kbd>Alt</kbd>)'
  column.appendChild(hint)
  host.replaceChildren(root)

  // The app is shown 1:1 on an ordinary window and scaled DOWN to fit a small one (WindowFit caps the native
  // content scale at 1). On a very large viewport — a 4K monitor, or a browser zoomed far out, where the CSS
  // viewport is thousands of px wide — it is scaled UP in step with the page's own rem growth (pageStyles.ts) so
  // the app is not a postage stamp. It is a transform, so the 1200x800 layout inside is untouched.
  const fit = (): void => {
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
    const maxScale = Math.max(1, Math.min(3, window.innerWidth / 1920))
    const availableWidth = window.innerWidth - rem * 3
    const availableHeight = window.innerHeight - bar.offsetHeight - rem * 6.5
    const scale = Math.max(0.2, Math.min(maxScale, availableWidth / DESIGN_WIDTH, availableHeight / DESIGN_HEIGHT))
    column.style.width = `${DESIGN_WIDTH * scale}px`
    stage.style.width = `${DESIGN_WIDTH * scale}px`
    stage.style.height = `${DESIGN_HEIGHT * scale}px`
    frame.style.transform = `scale(${scale})`
  }
  fit()
  window.addEventListener('resize', fit)

  const go = (target: string | undefined): void => {
    if (target) {
      window.location.href = target
    }
  }
  // Capture phase, so nothing in the page can swallow a shortcut before it gets here.
  window.addEventListener('keydown', (event) => {
    const action = shortcutOf(event)
    switch (action) {
      case 'prev': go(prev && href(prev)); break
      case 'next': go(next && href(next)); break
      case 'index': go(href(undefined)); break
      case 'theme': go(href(scenario, { popups, theme: otherTheme })); break
      case 'popup': if (popup) go(href(scenario, { popups: popups === 'shown' ? 'hidden' : 'shown', theme })); break
      default: break
    }
  }, true)
}

type Shortcut = 'prev' | 'next' | 'popup' | 'theme' | 'index'

/** Which viewer shortcut a key press is, if any. Matches the physical key (event.code) as well as the character, and
 *  tolerates AltGr (reported as Ctrl+Alt): on many non-US layouts "[" and "]" need AltGr, so rejecting every Alt/Ctrl
 *  press would silently disable them. Real browser/OS shortcuts (Ctrl+B, Alt+Left, Cmd+…) are left alone.
 *  `viewer` adds the arrow keys, which are only safe when focus is on the viewer, not inside the app. */
export function shortcutOf(event: KeyboardEvent, viewer = true): Shortcut | undefined {
  const altGr = event.ctrlKey && event.altKey
  // Alt on its own is allowed (it is how a shortcut is sent from inside a text field, see forwardKeysToParent) except
  // with the arrows, where Alt+←/→ is the browser's own Back/Forward.
  const altOnly = event.altKey && !event.ctrlKey && !event.key.startsWith('Arrow')
  if (event.metaKey || (!altGr && !altOnly && (event.ctrlKey || event.altKey))) {
    return undefined
  }
  const key = event.key.toLowerCase()
  const code = event.code
  if (key === '[' || code === 'BracketLeft' || key === 'p' || (viewer && key === 'arrowleft')) return 'prev'
  if (key === ']' || code === 'BracketRight' || key === 'n' || (viewer && key === 'arrowright')) return 'next'
  if (key === 'b' || code === 'KeyB') return 'popup'
  if (key === 'd') return 'theme'
  if (key === 'i') return 'index'
  return undefined
}

/** Inside the viewer's iframe: pass plain key presses up to the viewer so its shortcuts work with focus in the
 *  app. Ignored while typing or in a dropdown, so the app's own inputs are never disturbed. */
export function forwardKeysToParent(): void {
  if (window.parent === window) {
    return
  }
  window.addEventListener('keydown', (event) => {
    const target = event.target as HTMLElement | null
    const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement
    // While a text field has focus a plain letter belongs to the field, so only Alt+key (Alt+B, Alt+], …) is sent up.
    if (shortcutOf(event, false) === undefined || (typing && !event.altKey)) {
      return
    }
    window.parent.dispatchEvent(new KeyboardEvent('keydown', { key: event.key, code: event.code }))
  }, true)
}

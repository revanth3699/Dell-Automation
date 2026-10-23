// What a validator can read off a rendered scenario: its text, the strings that live in attributes rather than
// in text nodes (a placeholder, an aria-label, a title tooltip), and the state of every control (a disabled
// Retry button is as much part of the screen as its label). Nothing here is added to the app's surface — it
// only reads it, and ignores anything the catalog itself injects ([data-catalog-ui]) and decorative
// aria-hidden nodes, so what comes back is what the app renders.
//
// `page` / `popups` (plain textContent, one string each) are the original contract and are kept as they were;
// `surfaces` is the richer, visible-only view of the same content, split the same way (the page behind, and
// each open popup on its own) so the background and a popup can still be checked independently.

export interface CatalogAttribute {
  /** Tag (plus role when it has one) of the element carrying the attribute, e.g. "textarea" or "div[radiogroup]". */
  element: string
  attribute: 'aria-label' | 'title' | 'placeholder' | 'alt' | 'value'
  value: string
}

export interface CatalogControl {
  /** button | link | checkbox | radio | textbox | select | tab | switch */
  kind: string
  /** The accessible label: aria-label, else the visible text, else the placeholder / title. */
  name: string
  disabled: boolean
  /** Checkbox / radio / toggle state; 'mixed' for an indeterminate checkbox. Absent for other controls. */
  checked?: boolean | 'mixed'
  box: CatalogBox
}

/** Box in CSS pixels, measured from the top-left of the 1200x800 app window (the app's own stage). */
export interface CatalogBox {
  x: number
  y: number
  width: number
  height: number
}

/** One piece of text as the browser draws it: what it says, where, and in which typeface — the properties a design
 *  review compares against the spec (computed styles, so inherited and cascaded values are already resolved). */
export interface CatalogElement {
  tag: string
  text: string
  box: CatalogBox
  fontFamily: string
  fontSize: string
  fontWeight: string
  fontStyle: string
  lineHeight: string
  letterSpacing: string
  textTransform: string
  textDecoration: string
  textAlign: string
  color: string
  opacity: string
}

export interface CatalogSurface {
  /** Visible text only (display:none / visibility:hidden / aria-hidden excluded), text nodes joined by a space. */
  text: string
  /** The same visible text, one entry per text node — lets a validator match a short label exactly instead of
   *  finding it inside a longer sentence. */
  nodes: string[]
  attributes: CatalogAttribute[]
  controls: CatalogControl[]
  /** Every element that directly holds visible text, with its box and typography (see CatalogElement). */
  elements: CatalogElement[]
}

export interface CollectedText {
  title: string
  lang: string
  /** Original contract: the page's textContent with popups removed. */
  page: string
  /** Original contract: each open popup's textContent. */
  popups: string[]
  surfaces: { page: CatalogSurface; popups: CatalogSurface[] }
}

const normalize = (value: string): string => value.replace(/\s+/g, ' ').trim()

const IGNORED = 'script, style, [data-catalog-ui], [aria-hidden="true"]'

function isRendered(el: Element): boolean {
  if (el.getClientRects().length === 0) {
    return false
  }
  return getComputedStyle(el).visibility !== 'hidden'
}

function visibleNodes(container: Element, skip: (el: Element) => boolean): string[] {
  const parts: string[] = []
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const el = node.parentElement
    if (!el || !node.textContent || node.textContent.trim() === '') {
      continue
    }
    if (skip(el) || el.closest(IGNORED) || !isRendered(el)) {
      continue
    }
    parts.push(normalize(node.textContent))
  }
  return parts
}

function boxOf(el: Element): CatalogBox {
  const rect = el.getBoundingClientRect()
  const round = (value: number): number => Math.round(value * 10) / 10
  return { x: round(rect.left), y: round(rect.top), width: round(rect.width), height: round(rect.height) }
}

function elementsOf(container: Element, skip: (el: Element) => boolean): CatalogElement[] {
  const found: CatalogElement[] = []
  for (const el of Array.from(container.querySelectorAll('*'))) {
    if (skip(el) || el.closest(IGNORED) || !isRendered(el)) {
      continue
    }
    const own = Array.from(el.childNodes)
      .filter((child) => child.nodeType === Node.TEXT_NODE)
      .map((child) => normalize(child.textContent ?? ''))
      .filter((text) => text !== '')
      .join(' ')
    if (own === '') {
      continue
    }
    const style = getComputedStyle(el)
    found.push({
      tag: el.tagName.toLowerCase(),
      text: own,
      box: boxOf(el),
      fontFamily: style.fontFamily,
      fontSize: style.fontSize,
      fontWeight: style.fontWeight,
      fontStyle: style.fontStyle,
      lineHeight: style.lineHeight,
      letterSpacing: style.letterSpacing,
      textTransform: style.textTransform,
      textDecoration: style.textDecorationLine,
      textAlign: style.textAlign,
      color: style.color,
      opacity: style.opacity,
    })
  }
  return found
}

function describe(el: Element): string {
  const role = el.getAttribute('role')
  return role ? `${el.tagName.toLowerCase()}[${role}]` : el.tagName.toLowerCase()
}

function attributesOf(container: Element, skip: (el: Element) => boolean): CatalogAttribute[] {
  const found: CatalogAttribute[] = []
  const names = ['aria-label', 'title', 'placeholder', 'alt'] as const
  for (const el of Array.from(container.querySelectorAll('*'))) {
    if (skip(el) || el.closest(IGNORED)) {
      continue
    }
    for (const name of names) {
      const value = el.getAttribute(name)
      if (value && value.trim() !== '') {
        found.push({ element: describe(el), attribute: name, value: normalize(value) })
      }
    }
    // What is typed into a field is part of the screen's state (the feedback comment, the code).
    if ((el instanceof HTMLInputElement && el.type === 'text') || el instanceof HTMLTextAreaElement) {
      if (el.value !== '') {
        found.push({ element: describe(el), attribute: 'value', value: el.value })
      }
    }
  }
  return found
}

function controlKind(el: Element): string | undefined {
  const role = el.getAttribute('role')
  if (role === 'radio' || role === 'checkbox' || role === 'switch' || role === 'tab') {
    return role
  }
  if (el instanceof HTMLButtonElement) {
    return 'button'
  }
  if (el instanceof HTMLAnchorElement) {
    return 'link'
  }
  if (el instanceof HTMLTextAreaElement) {
    return 'textbox'
  }
  if (el instanceof HTMLSelectElement) {
    return 'select'
  }
  if (el instanceof HTMLInputElement) {
    return el.type === 'checkbox' ? 'checkbox' : el.type === 'radio' ? 'radio' : 'textbox'
  }
  return undefined
}

function controlsOf(container: Element, skip: (el: Element) => boolean): CatalogControl[] {
  const found: CatalogControl[] = []
  const selector = 'button, a[href], input, textarea, select, [role="radio"], [role="checkbox"], [role="switch"], [role="tab"]'
  for (const el of Array.from(container.querySelectorAll(selector))) {
    if (skip(el) || el.closest(IGNORED) || !isRendered(el)) {
      continue
    }
    const kind = controlKind(el)
    if (!kind) {
      continue
    }
    const name = normalize(
      el.getAttribute('aria-label') ?? (el.textContent ? el.textContent : '') ?? '',
    ) || el.getAttribute('placeholder') || el.getAttribute('title') || ''
    const disabled = (el as HTMLButtonElement).disabled === true || el.getAttribute('aria-disabled') === 'true'
    const control: CatalogControl = { kind, name, disabled, box: boxOf(el) }

    if (el instanceof HTMLInputElement && (el.type === 'checkbox' || el.type === 'radio')) {
      control.checked = el.indeterminate ? 'mixed' : el.checked
    } else if (el.getAttribute('aria-checked') !== null) {
      control.checked = el.getAttribute('aria-checked') === 'mixed' ? 'mixed' : el.getAttribute('aria-checked') === 'true'
    } else if (el.getAttribute('aria-pressed') !== null) {
      control.checked = el.getAttribute('aria-pressed') === 'true'
    }
    found.push(control)
  }
  return found
}

function surfaceOf(container: Element, skip: (el: Element) => boolean): CatalogSurface {
  const nodes = visibleNodes(container, skip)
  return {
    text: normalize(nodes.join(' ')),
    nodes,
    attributes: attributesOf(container, skip),
    controls: controlsOf(container, skip),
    elements: elementsOf(container, skip),
  }
}

/** The page behind (popups excluded) and each open popup, as text + attributes + control states. */
export function collectText(lang: string): CollectedText {
  const root = document.getElementById('root')
  const clone = root ? (root.cloneNode(true) as HTMLElement) : document.createElement('div')
  clone.querySelectorAll(`dialog, ${IGNORED}`).forEach((el) => el.remove())

  const dialogs = Array.from(document.querySelectorAll<HTMLDialogElement>('dialog[open]'))
  const popupTexts = dialogs.map((dialog) => {
    const dialogClone = dialog.cloneNode(true) as HTMLElement
    dialogClone.querySelectorAll('[data-catalog-ui], [aria-hidden="true"]').forEach((el) => el.remove())
    return normalize(dialogClone.textContent ?? '')
  })

  const inDialog = (el: Element): boolean => el.closest('dialog') !== null
  const page = root ? surfaceOf(root, inDialog) : { text: '', nodes: [], attributes: [], controls: [], elements: [] }
  return {
    title: document.title,
    lang,
    page: normalize(clone.textContent ?? ''),
    popups: popupTexts,
    surfaces: { page, popups: dialogs.map((dialog) => surfaceOf(dialog, () => false)) },
  }
}

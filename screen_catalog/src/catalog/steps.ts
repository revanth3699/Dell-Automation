// Interaction steps for catalog scenarios whose surface only appears after a UI action that React owns
// locally (state the native shell never pushes): the Feedback modal, the Migrating cancel confirmation, a
// tree row expanded, the deferral picker's chosen option. A scenario lists the steps; main.tsx runs them
// once the first screen has painted, then marks the page ready — so automation still just waits on
// data-catalog-state="ready" and never has to know how to reach a surface.
//
// Targets are located by the resx KEY of their label (clickKey), so a step survives copy edits and works
// in every locale, falling back to a CSS selector or literal text only where no resx key exists (engine-
// supplied tree rows, the DDS star buttons). Steps tagged popup:true are skipped in the background-only
// view (popups=hidden), which is how that view gets the screen without the modal it opens.
import { res } from './res'

export type Step =
  | { do: 'clickKey'; key: string; popup?: boolean; inDialog?: boolean }
  | { do: 'clickText'; text: string; popup?: boolean }
  | { do: 'click'; selector: string; nth?: number; popup?: boolean }
  | { do: 'type'; selector: string; text: string; popup?: boolean }
  | { do: 'focus'; selector: string; nth?: number; popup?: boolean }

/** Focuses an element — how a hover-only surface (the skipped-file reason tooltip, which DDS opens on focus or
 *  mouseenter, never on a synthetic click) is opened without simulating a pointer. */
export const focusEl = (selector: string, opts: { nth?: number; popup?: boolean } = {}): Step => ({ do: 'focus', selector, ...opts })

export const clickKey = (key: string, opts: { popup?: boolean; inDialog?: boolean } = {}): Step => ({ do: 'clickKey', key, ...opts })
export const clickText = (text: string, opts: { popup?: boolean } = {}): Step => ({ do: 'clickText', text, ...opts })
export const click = (selector: string, opts: { nth?: number; popup?: boolean } = {}): Step => ({ do: 'click', selector, ...opts })
export const typeInto = (selector: string, text: string, opts: { popup?: boolean } = {}): Step => ({ do: 'type', selector, text, ...opts })

const CLICKABLE = 'button, a, [role="button"], [role="radio"], summary, label'
const POLL_MS = 16
const SETTLE_AFTER_STEPS_MS = 400 // > the app's longest busy flash (200 ms) plus a margin
const MAX_POLLS = 300 // ~5 s: a step that never finds its target fails loudly instead of hanging the run

const normalize = (value: string): string => value.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim()

/** Polls until `find` returns something truthy, or throws after ~5 s. Dev tool, so plain polling is fine. */
export async function waitFor<T>(find: () => T | null | undefined | false, what: string): Promise<T> {
  for (let attempt = 0; attempt < MAX_POLLS; attempt++) {
    const found = find()
    if (found) {
      return found
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_MS))
  }
  throw new Error(`Timed out waiting for ${what}`)
}

function byText(text: string, scope: ParentNode): HTMLElement | undefined {
  const wanted = normalize(text)
  const candidates = Array.from(scope.querySelectorAll<HTMLElement>(CLICKABLE)).filter(
    (el) => !(el instanceof HTMLButtonElement && el.disabled),
  )
  return candidates.find((el) => normalize(el.textContent ?? '') === wanted)
    ?? candidates.find((el) => normalize(el.textContent ?? '').includes(wanted))
}

// React tracks controlled inputs through the element's own value setter, so a plain `el.value = x` is
// swallowed; going through the prototype setter and then dispatching `input` is what React listens for.
function setNativeValue(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const prototype = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, 'value')?.set?.call(el, value)
  el.dispatchEvent(new Event('input', { bubbles: true }))
}

export function describeStep(step: Step): string {
  switch (step.do) {
    case 'clickKey': return `click "${step.key}"`
    case 'clickText': return `click text "${step.text}"`
    case 'click': return `click ${step.selector}`
    case 'type': return `type into ${step.selector}`
    case 'focus': return `focus ${step.selector}`
  }
}

async function runStep(step: Step): Promise<void> {
  switch (step.do) {
    case 'clickKey': {
      const scope: ParentNode = step.inDialog ? (document.querySelector('dialog[open]') ?? document) : document
      const el = await waitFor(() => byText(res(step.key), scope), describeStep(step))
      el.click()
      return
    }
    case 'clickText': {
      const el = await waitFor(() => byText(step.text, document), describeStep(step))
      el.click()
      return
    }
    case 'click': {
      const el = await waitFor(() => document.querySelectorAll<HTMLElement>(step.selector)[step.nth ?? 0], describeStep(step))
      el.click()
      return
    }
    case 'type': {
      const el = await waitFor(() => document.querySelector<HTMLInputElement | HTMLTextAreaElement>(step.selector), describeStep(step))
      setNativeValue(el, step.text)
      return
    }
    case 'focus': {
      const el = await waitFor(() => document.querySelectorAll<HTMLElement>(step.selector)[step.nth ?? 0], describeStep(step))
      el.focus()
      // A browser window that is not itself focused (headless, or a background tab) does not deliver the focus
      // event for el.focus(), so the same events a user's focus / hover would raise are dispatched as well.
      for (const type of ['focus', 'focusin']) {
        el.dispatchEvent(new FocusEvent(type, { bubbles: type === 'focusin' }))
      }
      for (const type of ['pointerenter', 'mouseenter']) {
        el.dispatchEvent(new MouseEvent(type, { bubbles: false }))
      }
      return
    }
  }
}

/**
 * Waits for finite animations and transitions to finish (a popup fading in, a dropdown list sliding open), so
 * "ready" means the surface is at rest and a screenshot taken then is not caught mid-fade. Infinite ones
 * (spinners) are skipped — they never finish — and the wait is capped so a stuck animation cannot hang the run.
 */
export async function settleAnimations(): Promise<void> {
  const finite = document.getAnimations().filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity)
  await Promise.race([
    Promise.allSettled(finite.map((animation) => animation.finished)),
    new Promise((resolve) => setTimeout(resolve, 2000)),
  ])
  await new Promise((resolve) => setTimeout(resolve, 50))
}

/** Runs steps in order, letting React commit between each so the next target exists. */
export async function runSteps(steps: Step[]): Promise<void> {
  for (const step of steps) {
    await runStep(step)
    await new Promise((resolve) => setTimeout(resolve, POLL_MS * 2))
  }
  // The app answers some clicks with a short busy flash (the skipped-files tree keeps its spinner up for at least
  // 200 ms after an expand — SkippedFilesTreeCard MIN_VISIBLE_MS). "Ready" means at rest, so let it clear instead of
  // catching the surface mid-flash.
  if (steps.length > 0) {
    await new Promise((resolve) => setTimeout(resolve, SETTLE_AFTER_STEPS_MS))
  }
}

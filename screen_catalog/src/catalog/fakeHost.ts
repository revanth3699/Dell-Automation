// A fake WebView2 host for the dev-only screen catalog (catalog.html). Installed on window.chrome.webview
// BEFORE <App/> mounts so bridge.ts's isHosted() returns true and the real bridge attaches its message
// listener — the catalog then drives the REAL app through exactly the same channel traffic the native
// WPF shell uses (ui.ready → app.theme/app.locale/app.chrome → screen.navigate/screen.state →
// overlay.navigate/overlay.state → app.closeConfirm), so no app/runtime code is touched or mocked.
//
// Popups: with popups='hidden' the host simply never sends the popup layer — no overlay.*, no
// app.closeConfirm, and a screen's own popup-driving state is swapped for its popup-free twin — so the
// background renders genuinely unobscured (and the document is not left inert by a modal <dialog>), instead
// of the catalog hiding a popup with CSS. React-local popups are handled by skipping their steps (stepsFor).
//
// This file ships only in the catalog build entry, never in the embedded wwwroot the app installs.
import { PROTOCOL_VERSION, type BridgeEnvelope, Channels } from '@app/bridge/contract'
import { defaultChrome, type Scenario, type ThemeName } from './scenarios'
import type { Step } from './steps'

type MessageListener = (event: { data: BridgeEnvelope }) => void

export type PopupMode = 'shown' | 'hidden'

interface FakeHostOptions {
  scenario: Scenario
  theme: ThemeName
  locale: string
  popups: PopupMode
  /** Called once the app reports its first painted frame (shell.splash.done). */
  onReady: () => void
}

// Only ui.ready carries a payload the app reads back. Everything else the app sends (actions like
// migrating.cancel, diagnostics.*) is answered with a bare ok so buttons and fire-and-forget reports never
// hang on the 30 s bridge timeout.
const RESPONSE_PAYLOADS: Record<string, unknown> = {
  [Channels.uiReady]: { hosted: true },
}

/** The steps to run for a view: popup-opening steps are dropped from the background-only view. */
export function stepsFor(scenario: Scenario, popups: PopupMode): Step[] {
  return (scenario.steps ?? []).filter((step) => popups === 'shown' || step.popup !== true)
}

export function installFakeHost(opts: FakeHostOptions): void {
  const { scenario, theme, locale, popups, onReady } = opts
  let listener: MessageListener | undefined

  // Deliver on a fresh task, mirroring the async nature of a real native push (and guaranteeing every on(...)
  // subscription from App's mount effects is in place). setTimeout(0) callbacks run in order, so pushes
  // arrive in the order they were sent.
  const deliver = (envelope: BridgeEnvelope): void => {
    setTimeout(() => listener?.({ data: envelope }), 0)
  }

  const pushEvent = (channel: string, payload: unknown): void =>
    deliver({ v: PROTOCOL_VERSION, kind: 'event', channel, payload })

  const pushScenario = (): void => {
    pushEvent(Channels.appTheme, theme)
    pushEvent(Channels.appLocale, locale)
    pushEvent(Channels.appChrome, { ...defaultChrome, ...(scenario.chrome ?? {}) })

    // The base screen always goes first (overlays and close prompts sit on top of a real screen).
    const base = baseOf(scenario, popups)
    pushEvent(Channels.screenNavigate, { screen: base.screen })
    pushEvent(Channels.screenState, { screen: base.screen, state: base.state })

    if (popups === 'hidden') {
      return
    }
    if (scenario.kind === 'overlay') {
      pushEvent(Channels.overlayNavigate, { overlay: scenario.overlay })
      pushEvent(Channels.overlayState, { overlay: scenario.overlay, state: scenario.state() })
    } else if (scenario.kind === 'closePrompt') {
      pushEvent(Channels.appCloseConfirm, { step: scenario.step })
    }
  }

  const host = {
    addEventListener(_type: 'message', cb: MessageListener): void {
      listener = cb
    },
    postMessage(message: unknown): void {
      const envelope = message as BridgeEnvelope
      if (envelope.kind !== 'request' || !envelope.channel) {
        return
      }

      if (envelope.id) {
        const payload = envelope.channel in RESPONSE_PAYLOADS ? RESPONSE_PAYLOADS[envelope.channel] : {}
        deliver({ v: PROTOCOL_VERSION, id: envelope.id, kind: 'response', ok: true, payload })
      }

      // ui.ready is the app's "I've subscribed, push state now" signal; splash.done is "first frame painted".
      if (envelope.channel === Channels.uiReady) {
        pushScenario()
      } else if (envelope.channel === Channels.shellSplashDone) {
        onReady()
      }
    },
  }

  ;(window as unknown as { chrome: { webview: typeof host } }).chrome = { webview: host }
}

// An overlay/close-prompt renders over its declared base screen; a screen scenario is its own base. In the
// background-only view a screen whose own state drives a popup uses its popup-free twin.
function baseOf(s: Scenario, popups: PopupMode): { screen: string; state: unknown } {
  if (s.kind === 'screen') {
    const state = popups === 'hidden' && s.popupOffState ? s.popupOffState() : s.state()
    return { screen: s.screen, state }
  }
  return { screen: s.base, state: s.baseState() }
}

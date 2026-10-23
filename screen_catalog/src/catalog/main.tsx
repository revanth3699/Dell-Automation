// Entry point for the dev-only screen catalog (catalog.html). Two modes, chosen by URL params:
//   • a scenario target (?screen=… / ?overlay=… / ?closeConfirm=…) → install the fake WebView2 host
//     (fakeHost.ts) and mount the REAL <App/>, which the host drives to that one surface; or
//   • no target → render the browsable CatalogIndex.
// Optional params: variant, popups=hidden (background only, popup layer removed), theme=dark, locale=de,
// frame=1 (the viewer: the scenario in an exact 1200x800 window with controls outside it — for people; the
// iframe it contains loads the same page with embed=1). Never shipped in the app's embedded wwwroot — only the
// catalog build entry includes this (see vite.catalog.config.ts).
//
// Contract for automation (documented in docs/reference/05-visual-screen-verification.md §5):
//   window.__SCREEN_CATALOG__       journey-ordered manifest of every scenario
//   window.__SCREEN_CATALOG_FLOW__  the verified navigation graph (entry screens, edges, overlay hosts)
//   body[data-catalog-state]        "pending" → "ready" | "error" | "index"; wait for ready, no sleeps
//   body[data-catalog-error]        why a state is "error" (a step or the popup never appeared)
//   body[data-catalog-dialogs]      how many popups are actually open once ready (0 in the background view)
//   window.__CATALOG__.collectText()  the page text and each open popup's text, separately; `surfaces` adds the
//                                     visible-only text, attributes (placeholder / aria-label / title) and every
//                                     control's disabled / checked state, per surface (collectText.ts)
//
// Mirrors main.tsx's import set (i18n before components, DDS CSS before index.css) so the app renders
// identically; the differences are the fake host and the catalog's own ready wiring.
import i18n from '@app/i18n'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@dds/react/css/dds-tokens.css'
import '@dds/react/css/dds-typography.css'
import '@dds/react/css/dds-icons.css'
import '@dds/react/css/dds-grid.css'
import '@dds/react/css/dds-helpers.css'
import '@dds/react/css/dds-components.css'
import '@app/index.css'
import '@app/styles/surface.css'
import { applyThemeBackground } from '@app/theme/themeConfig'
import '@app/theme/themeSync'
import App from '@app/App.tsx'
import { AppErrorBoundary } from '@app/components/AppErrorBoundary'
import { CatalogIndex } from './CatalogIndex'
import { installFakeHost, stepsFor, type PopupMode } from './fakeHost'
import { entryScreens, flowEdges, overlayOver } from './flow'
import { buildManifest, hasPopup, resolveScenario, scenarioId, type ThemeName } from './scenarios'
import { runSteps, settleAnimations, waitFor } from './steps'
import { forwardKeysToParent, renderFrame } from './frame'
import { enterCatalogPage } from './pageStyles'
import { collectText as collectPageText, type CollectedText } from './collectText'

type CatalogState = 'pending' | 'ready' | 'error' | 'index' | 'frame'

const params = new URLSearchParams(window.location.search)
const theme: ThemeName = params.get('theme') === 'dark' ? 'dark' : 'light'
const locale = params.get('locale') ?? 'en'
const popups: PopupMode = params.get('popups') === 'hidden' ? 'hidden' : 'shown'

function setState(state: CatalogState, error?: string): void {
  document.body.dataset.catalogState = state
  if (error) {
    document.body.dataset.catalogError = error
  }
  if (state !== 'pending') {
    ;(window as unknown as { __CATALOG_READY__: boolean }).__CATALOG_READY__ = true
  }
}

// The page's own text and each open popup's text, kept apart so a validator can check the background and the
// popup independently — plus attributes and control states (see collectText.ts).
const collectText = (): CollectedText => collectPageText(i18n.language)

async function main(): Promise<void> {
  // Resolve every res()-based state in the requested language, before anything is pushed.
  await i18n.changeLanguage(locale)

  const w = window as unknown as Record<string, unknown>
  w.__SCREEN_CATALOG__ = buildManifest()
  w.__SCREEN_CATALOG_FLOW__ = { entryScreens, edges: flowEdges, overlayOver }

  // Apply the requested theme before first paint so there is no light→dark flash; the fake host re-pushes it
  // over app.theme once the bridge is live (same as the native shell would).
  applyThemeBackground(theme)

  // In the real app the OS theme and data-theme always agree (the native host pushes the OS theme). The app's own
  // CSS follows data-theme, but the vendored DDS components follow only the OS media query or their own
  // .dds--dark-mode class — so on a light-OS browser, theme=dark would leave DDS colours light (dark text on a
  // dark card). DDS ships every dark rule under both selectors, so the class makes dark exact.
  document.documentElement.classList.toggle('dds--dark-mode', theme === 'dark')

  const scenario = resolveScenario(params)
  const root = createRoot(document.getElementById('root')!)

  // Framed viewer: a person's view of one scenario (app shown in an exact 1200x800 window, controls outside it).
  // The iframe loads this same page with embed=1, which renders the scenario itself, below.
  if (scenario && params.get('frame') === '1' && params.get('embed') !== '1') {
    document.title = `Catalog · ${scenario.title}`
    enterCatalogPage()
    renderFrame(document.getElementById('root')!, scenario, params, popups, theme)
    setState('frame')
    return
  }

  if (!scenario) {
    document.title = 'Screen Catalog'
    enterCatalogPage()
    w.__CATALOG__ = { collectText }
    root.render(
      <StrictMode>
        <CatalogIndex theme={theme} />
      </StrictMode>,
    )
    setState('index')
    return
  }

  setState('pending')
  const popup = hasPopup(scenario)
  document.title = `Catalog · ${scenario.title}${popup && popups === 'hidden' ? ' (background only)' : ''}`
  w.__CATALOG__ = { collectText, scenarioId: scenarioId(scenario), hasPopup: popup, popups }

  const jsErrors: string[] = []
  w.__CATALOG_ERRORS__ = jsErrors
  window.addEventListener('error', (event) => jsErrors.push(event.message))
  window.addEventListener('unhandledrejection', (event) => jsErrors.push(String(event.reason)))

  // The app's own "first screen painted" signal; steps and the popup check run after it.
  // Runs exactly once: StrictMode's dev double-effects could otherwise signal twice, and a repeated
  // toggle-style step (expanding a tree row) would undo itself.
  let started = false
  const onReady = (): void => {
    if (started) {
      return
    }
    started = true
    void (async () => {
      try {
        await runSteps(stepsFor(scenario, popups))
        if (popups === 'shown' && popup) {
          await waitFor(() => document.querySelector('dialog[open]'), 'the popup to open')
        }
        // Ready means at rest: let the popup's fade-in and any dropdown animation finish first.
        await settleAnimations()
        document.body.dataset.catalogDialogs = String(document.querySelectorAll('dialog[open]').length)
        document.body.dataset.catalogJsErrors = String(jsErrors.length)
        // 'exact' unless a light view is drawn on a dark-OS browser (DDS follows the OS media query there).
        const osDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        document.body.dataset.catalogThemeFidelity = theme === 'light' && osDark ? 'os-mismatch' : 'exact'
        setState('ready')
      } catch (error) {
        setState('error', error instanceof Error ? error.message : String(error))
      }
    })()
  }

  // Install the host BEFORE mounting so bridge.ts's isHosted() is true when App's effects subscribe.
  installFakeHost({ scenario, theme, locale, popups, onReady })
  root.render(
    <StrictMode>
      <AppErrorBoundary>
        <App />
      </AppErrorBoundary>
    </StrictMode>,
  )

  if (params.get('embed') === '1') {
    forwardKeysToParent()
  }
}

void main()

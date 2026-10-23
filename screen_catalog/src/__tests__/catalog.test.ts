// Guards the dev-only screen catalog (src/catalog/*) against drift, in three ways:
//   1. COVERAGE — every ScreenId / OverlayId in bridge/contract.ts and both close-prompt steps has a scenario
//      (the ALL_* maps are Record<Id, true>, so TypeScript forces them to grow with the unions).
//   2. NAVIGATION LOGIC — the flow graph transcribed from the C# (flow.ts) reaches every screen, and every
//      overlay scenario sits on a screen that genuinely raises it, so the catalog cannot show a popup in a
//      place the app never produces it. The registry order must also follow the journey phases.
//   3. TEXT — every scenario state resolves with no ⟦missing:key⟧ marker, i.e. every resx key the catalog
//      reads exists in Resources.resx (a typo'd key would otherwise show up only as odd text in a screenshot).
import './i18nForTests'
import { describe, it, expect } from 'vitest'
import i18n from 'i18next'
import type { OverlayId, ScreenId } from '@app/bridge/contract'
import {
  CATEGORIES,
  PHASES,
  SCREEN_LABELS,
  buildManifest,
  categoryOf,
  groupOf,
  hasPopup,
  labelOf,
  resolveScenario,
  scenarioId,
  SKIP_REASON_CODES,
  SKIP_REASON_GROUPS,
  scenarios,
  type OverlayScenario,
  type ScreenScenario,
} from '../catalog/scenarios'
import { entryScreens, flowEdges, overlayAllowedOver, overlayOver, reachableScreens } from '../catalog/flow'
import { res } from '../catalog/res'
import { stepsFor } from '../catalog/fakeHost'

const ALL_SCREENS: Record<ScreenId, true> = {
  checkPrerequisites: true,
  welcome: true,
  welcomeDeferral: true,
  welcomeDeferralError: true,
  deferralSuccess: true,
  connectOldPc: true,
  enterCode: true,
  readyToMove: true,
  chooseWhatToMove: true,
  migrating: true,
  resultsSummary: true,
  complete: true,
  skippedFiles: true,
  migrateReminder: true,
  migrateReminderSet: true,
  migrationDone: true,
  learnAboutErase: true,
}

const ALL_OVERLAYS: Record<OverlayId, true> = {
  closeApplications: true,
  installBrowser: true,
  signIn: true,
  localeNotSupported: true,
  localeMismatch: true,
  signOut: true,
  accountMismatch: true,
  trustNetwork: true,
  notAdmin: true,
  osNotSupported: true,
  batteryCritical: true,
  noNetwork: true,
  failure: true,
  connectionLost: true,
  migrationCancelled: true,
}

describe('screen catalog coverage', () => {
  it('covers every ScreenId', () => {
    const covered = new Set(
      scenarios.filter((s): s is ScreenScenario => s.kind === 'screen').map((s) => s.screen),
    )
    for (const id of Object.keys(ALL_SCREENS) as ScreenId[]) {
      expect(covered, `no scenario for screen '${id}'`).toContain(id)
    }
  })

  it('covers every OverlayId', () => {
    const covered = new Set(
      scenarios.filter((s): s is OverlayScenario => s.kind === 'overlay').map((s) => s.overlay),
    )
    for (const id of Object.keys(ALL_OVERLAYS) as OverlayId[]) {
      expect(covered, `no scenario for overlay '${id}'`).toContain(id)
    }
  })

  it('covers both close-prompt steps', () => {
    const steps = new Set(scenarios.filter((s) => s.kind === 'closePrompt').map((s) => s.step))
    expect(steps).toContain('cancelMigration')
    expect(steps).toContain('shortcut')
  })

  it('assigns a unique id to every scenario', () => {
    const ids = scenarios.map(scenarioId)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('resolves each manifest query back to its scenario', () => {
    for (const entry of buildManifest()) {
      const resolved = resolveScenario(new URLSearchParams(entry.query))
      expect(resolved, `query '${entry.query}' did not resolve`).toBeDefined()
      expect(scenarioId(resolved!)).toBe(entry.id)
    }
  })
})

describe('screen catalog navigation logic', () => {
  it('reaches every screen from the entry screens along the verified flow edges', () => {
    const reachable = reachableScreens()
    for (const id of Object.keys(ALL_SCREENS) as ScreenId[]) {
      expect(reachable, `'${id}' is not reachable from ${entryScreens.join('/')}`).toContain(id)
    }
  })

  it('only draws flow edges between known screens', () => {
    for (const edge of flowEdges) {
      expect(ALL_SCREENS[edge.from], `unknown 'from' screen ${edge.from}`).toBe(true)
      expect(ALL_SCREENS[edge.to], `unknown 'to' screen ${edge.to}`).toBe(true)
    }
  })

  it('documents a host rule (with its C# source) for every overlay', () => {
    for (const id of Object.keys(ALL_OVERLAYS) as OverlayId[]) {
      expect(overlayOver[id]?.source, `no overlayOver entry for '${id}'`).toBeTruthy()
    }
  })

  it('places every overlay scenario over a screen that actually raises it', () => {
    for (const s of scenarios) {
      if (s.kind === 'overlay') {
        expect(
          overlayAllowedOver(s.overlay, s.base),
          `${scenarioId(s)}: '${s.overlay}' is not raised over '${s.base}' (see flow.ts overlayOver)`,
        ).toBe(true)
      }
    }
  })

  it('orders the registry by journey phase', () => {
    const order = PHASES.map((p) => p.id)
    let last = -1
    for (const s of scenarios) {
      const index = order.indexOf(s.phase)
      expect(index, `${scenarioId(s)} has an unknown phase '${s.phase}'`).toBeGreaterThanOrEqual(0)
      expect(index, `${scenarioId(s)} is out of journey order`).toBeGreaterThanOrEqual(last)
      last = index
    }
  })
})

describe('screen catalog popups', () => {
  it('gives every popup scenario a background-only view that resolves to the same scenario', () => {
    for (const entry of buildManifest()) {
      if (!entry.hasPopup) {
        expect(entry.backgroundQuery, `${entry.id} has no popup but a backgroundQuery`).toBeUndefined()
        continue
      }
      expect(entry.backgroundQuery, `${entry.id} has a popup but no backgroundQuery`).toContain('popups=hidden')
      const params = new URLSearchParams(entry.backgroundQuery)
      expect(scenarioId(resolveScenario(params)!)).toBe(entry.id)
    }
  })

  it('treats overlays and close prompts as popups, and a screen only when it opens one', () => {
    for (const s of scenarios) {
      if (s.kind !== 'screen') {
        expect(hasPopup(s), `${scenarioId(s)} should be a popup scenario`).toBe(true)
      }
    }
    const feedback = scenarios.find((s) => scenarioId(s) === 'screen.migrationDone.feedback')!
    expect(hasPopup(feedback)).toBe(true)
    const done = scenarios.find((s) => scenarioId(s) === 'screen.migrationDone.ready')!
    expect(hasPopup(done)).toBe(false)
  })

  it('drops popup-opening steps from the background view but keeps the rest', () => {
    const filled = scenarios.find((s) => scenarioId(s) === 'screen.migrationDone.feedbackFilled')!
    expect(stepsFor(filled, 'shown').length).toBeGreaterThan(0)
    expect(stepsFor(filled, 'hidden')).toHaveLength(0)

    const expanded = scenarios.find((s) => scenarioId(s) === 'screen.chooseWhatToMove.treeExpanded')!
    expect(stepsFor(expanded, 'hidden')).toEqual(stepsFor(expanded, 'shown'))
  })

  it('has a popup-free twin for every screen whose own state drives a popup', () => {
    for (const s of scenarios) {
      if (s.kind === 'screen' && s.popupOffState) {
        expect(s.popupOffState(), `${scenarioId(s)} popupOffState`).not.toEqual(s.state())
      }
    }
  })
})

describe('screen catalog categories', () => {
  it('files every scenario under exactly one known category', () => {
    const known = new Set(CATEGORIES.map((c) => c.id))
    for (const s of scenarios) {
      expect(known, `${scenarioId(s)}: unknown category`).toContain(categoryOf(s))
    }
  })

  it('uses every category (nothing in the legend is empty)', () => {
    const used = new Set(scenarios.map(categoryOf))
    for (const c of CATEGORIES) {
      expect(used, `no scenario in category '${c.id}'`).toContain(c.id)
    }
  })

  it('treats a popup as a popup, and a plain screen state as a screen', () => {
    for (const s of scenarios) {
      if (s.kind !== 'screen') {
        expect(categoryOf(s), scenarioId(s)).toBe('popup')
      }
    }
    const ready = scenarios.find((s) => scenarioId(s) === 'screen.migrationDone.ready')!
    expect(categoryOf(ready)).toBe('screen')
  })

  it('makes every dropdown entry actually open a dropdown, inside a popup', () => {
    const dropdowns = scenarios.filter((s) => categoryOf(s) === 'dropdown')
    expect(dropdowns.length).toBeGreaterThan(0)
    for (const s of dropdowns) {
      expect(hasPopup(s), `${scenarioId(s)} is a dropdown in a popup`).toBe(true)
      expect((s.steps ?? []).some((step) => step.do === 'click' && step.selector.includes('dropdown')), scenarioId(s)).toBe(true)
    }
  })

  it('gives every scenario a group label and a short row label', () => {
    for (const s of scenarios) {
      expect(groupOf(s).label, scenarioId(s)).toBeTruthy()
      expect(labelOf(s).length, scenarioId(s)).toBeGreaterThan(2)
    }
    for (const id of Object.keys(ALL_SCREENS) as ScreenId[]) {
      expect(SCREEN_LABELS[id], `no label for screen '${id}'`).toBeTruthy()
    }
  })

  it('carries category and host in the manifest', () => {
    for (const entry of buildManifest()) {
      expect(entry.category, entry.id).toBeTruthy()
      expect(ALL_SCREENS[entry.host], `${entry.id}: unknown host '${entry.host}'`).toBe(true)
    }
  })
})

describe('screen catalog text', () => {
  it('has the English resx loaded (otherwise the checks below prove nothing)', () => {
    expect(i18n.hasResourceBundle('en', 'screens')).toBe(true)
  })

  it('substitutes {0}-style format arguments like String.Format', () => {
    expect(res('ChooseWhatToMove_SystemDriveLabelFormat', 'C:')).toBe('OS (C:)')
  })

  it('resolves every state with no missing resx key', () => {
    for (const s of scenarios) {
      const rendered = JSON.stringify([
        s.kind === 'screen' ? s.state() : s.kind === 'overlay' ? [s.baseState(), s.state()] : s.baseState(),
        s.kind === 'screen' && s.popupOffState ? s.popupOffState() : undefined,
      ])
      expect(rendered, `${scenarioId(s)} references a resx key that does not exist`).not.toContain('⟦missing:')
    }
  })

  it('points every key-mode failure at keys that exist in the resx', () => {
    for (const s of scenarios) {
      if (s.kind === 'overlay' && s.overlay === 'failure') {
        const state = s.state() as { titleKey?: string; messageKeys?: string[] }
        for (const key of [state.titleKey, ...(state.messageKeys ?? [])].filter((k): k is string => !!k)) {
          expect(i18n.exists(key, { ns: 'screens' }), `${scenarioId(s)}: unknown key '${key}'`).toBe(true)
        }
      }
    }
  })
})

describe('screen catalog fidelity to the native copy', () => {
  it('covers every SkipReason_* string in the resx, one tooltip entry per distinct wording', () => {
    const bundle = i18n.getResourceBundle('en', 'screens') as Record<string, string>
    const inResx = Object.keys(bundle).filter((key) => key.startsWith('SkipReason_')).map((key) => Number(key.slice('SkipReason_'.length)))
    expect([...SKIP_REASON_CODES].sort((a, b) => a - b)).toEqual(inResx.sort((a, b) => a - b))

    for (const group of SKIP_REASON_GROUPS) {
      const texts = new Set(group.map((code) => bundle[`SkipReason_${code}`]))
      expect(texts.size, `codes ${group.join(', ')} are grouped but their wording differs`).toBe(1)
    }
    const distinct = new Set(Object.keys(bundle).filter((key) => key.startsWith('SkipReason_')).map((key) => bundle[key]))
    expect(SKIP_REASON_GROUPS.length, 'two groups share the same wording').toBe(distinct.size)

    const tooltips = scenarios.filter((s) => s.kind === 'screen' && s.category === 'tooltip')
    expect(tooltips.map(scenarioId).sort()).toEqual(SKIP_REASON_GROUPS.map((group) => `screen.skippedFiles.reason${group[0]}`).sort())
  })

  it('words an estimate the way StorageSummary.FormatEstimate does (no "about", no "left")', () => {
    const rendered = JSON.stringify(scenarios.map((s) => (s.kind === 'closePrompt' ? s.baseState() : s.state())))
    expect(rendered).toContain('14 minutes')
    expect(rendered).toContain('1 hour and 5 minutes')
    expect(rendered).not.toMatch(/about 14 minutes|minutes left/)
    expect(rendered).not.toContain('28.0 GB') // StorageSummary.FormatBytes prints 28 GB
  })

  it('always shows the six results tiles, in MigrationSummaryTiles order', () => {
    const results = scenarios.filter((s): s is ScreenScenario => s.kind === 'screen' && s.screen === 'resultsSummary' && s.variant !== 'loading' && s.variant !== 'cancelling')
    expect(results.length).toBeGreaterThan(0)
    for (const s of results) {
      const tiles = (s.state() as { tiles: { icon: string }[] }).tiles.map((t) => t.icon)
      expect(tiles, scenarioId(s)).toEqual(['FilesCopied', 'DataTransferred', 'NotMigrated', 'SettingsCopied', 'ElapsedTime', 'AlreadyExisting'])
    }
  })
})

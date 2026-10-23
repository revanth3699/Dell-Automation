// Landing page for the dev-only screen catalog (catalog.html with no scenario params). Organised the way the
// app is: phases of the user journey → one card per screen → that screen's entries under separate headings
// (screen states / popups / dropdowns open / selections / inputs), so there is no guessing what a link opens.
// Every popup entry has a second link, "background only", for the same screen with the popup removed. Links open
// the framed viewer (an exact 1200x800 app window with the controls outside it). Automation does not need this
// page — it reads window.__SCREEN_CATALOG__ — but it makes the catalog easy to browse by hand. Dev tooling.
import { viewerHref } from './frame'
import {
  CATEGORIES,
  PHASES,
  categoryOf,
  groupOf,
  hasPopup,
  labelOf,
  scenarioId,
  scenarios,
  type Scenario,
  type ThemeName,
} from './scenarios'

interface CatalogIndexProps {
  theme: ThemeName
}

interface Group {
  key: string
  label: string
  items: Scenario[]
}

function groupsOf(phase: string): Group[] {
  const groups = new Map<string, Group>()
  for (const s of scenarios.filter((item) => item.phase === phase)) {
    const { key, label } = groupOf(s)
    const group = groups.get(key) ?? { key, label, items: [] }
    group.items.push(s)
    groups.set(key, group)
  }
  return Array.from(groups.values())
}

export function CatalogIndex({ theme }: CatalogIndexProps) {
  const params = new URLSearchParams(window.location.search)
  const open = (s: Scenario, popups: 'shown' | 'hidden'): string => viewerHref(params, s, { popups, theme })
  const themeHref = (next: ThemeName): string => `?theme=${next}`
  const backgrounds = scenarios.filter(hasPopup).length

  return (
    <div className="ci">
      <style>{CSS}</style>
      <nav className="ci-nav" aria-label="Journey phases">
        <div className="ci-nav-title">Screen catalog</div>
        {PHASES.map((phase) => (
          <a key={phase.id} href={`#${phase.id}`}>
            {phase.label}
            <span>{scenarios.filter((s) => s.phase === phase.id).length}</span>
          </a>
        ))}
      </nav>

      <main className="ci-main">
        <header className="ci-head">
          <h1>Every screen and popup, as the app renders it</h1>
          <p>
            {scenarios.length} entries in journey order, plus {backgrounds} “background only” views (the same screen
            with its popup removed, so the text behind it can be read). Each opens in an exact 1200×800 app window.
          </p>
          <div className="ci-theme">
            View as
            <span className="ci-seg">
              <a href={themeHref('light')} aria-current={theme === 'light'}>Light</a>
              <a href={themeHref('dark')} aria-current={theme === 'dark'}>Dark</a>
            </span>
          </div>
          <ul className="ci-legend">
            {CATEGORIES.map((category) => (
              <li key={category.id}>
                <strong>{category.label}</strong>
                {LEGEND[category.id]}
              </li>
            ))}
          </ul>
        </header>

        {PHASES.map((phase) => (
          <section key={phase.id} id={phase.id} className="ci-phase">
            <h2>
              {phase.label}
              <span className="ci-count">{groupsOf(phase.id).reduce((total, g) => total + g.items.length, 0)}</span>
            </h2>
            {groupsOf(phase.id).map((group) => (
              <article key={group.key} className="ci-card">
                <h3>
                  {group.label}
                  <span className="ci-count">{group.items.length}</span>
                </h3>
                {CATEGORIES.map((category) => {
                  const items = group.items.filter((s) => categoryOf(s) === category.id)
                  if (items.length === 0) {
                    return null
                  }
                  // The tooltip category is long (one entry per skip reason), so it starts collapsed; the links stay
                  // in the page either way.
                  const Wrapper = category.id === 'tooltip' ? 'details' : 'div'
                  return (
                    <Wrapper key={category.id} className="ci-cat">
                      {category.id === 'tooltip'
                        ? <summary><h4>{category.label} <span className="ci-count">{items.length}</span></h4></summary>
                        : <h4>{category.label}</h4>}
                      <ul>
                        {items.map((s) => (
                          <li key={scenarioId(s)}>
                            <span className="ci-label">{labelOf(s)}</span>
                            <a className="ci-btn ci-view" href={open(s, 'shown')} data-scenario-id={scenarioId(s)}>
                              {hasPopup(s) ? 'With popup' : 'View'}
                            </a>
                            {hasPopup(s) ? (
                              <a className="ci-btn ci-bg" href={open(s, 'hidden')} data-scenario-id={`${scenarioId(s)}#background`}>
                                Background only
                              </a>
                            ) : (
                              <span />
                            )}
                          </li>
                        ))}
                      </ul>
                    </Wrapper>
                  )
                })}
              </article>
            ))}
          </section>
        ))}
      </main>
    </div>
  )
}

const LEGEND: Record<string, string> = {
  screen: 'a plain screen in one of its states.',
  popup: 'a modal over a screen. Open it, or open “background only” to read the screen behind it.',
  dropdown: 'a dropdown list held open.',
  selection: 'a multi-select or choice state: checkboxes, the file tree, radio options.',
  input: 'a typed or rated entry: the pairing code, the feedback form.',
  tooltip: 'hover text held open — the reason a file or setting was skipped.',
}

const CSS = `
/* Sizes are in rem and the root font-size grows with the window (pageStyles.ts), so the page stays readable on a
   huge viewport — e.g. a browser zoomed far out — instead of shrinking to a tiny strip. */
.ci { display: grid; grid-template-columns: 16rem minmax(0, 1fr); min-height: 100vh; background: #f5f6f8; color: #1b1d20;
  font: 400 1rem/1.45 system-ui, 'Segoe UI', sans-serif; }

.ci-nav { position: sticky; top: 0; align-self: start; height: 100vh; overflow: auto; box-sizing: border-box; padding: 1.5rem 1rem; background: #fff; border-right: 1px solid #dfe2e6; }
.ci-nav-title { margin: 0 .6rem 1rem; font-size: 1.15rem; font-weight: 700; }
.ci-nav a { display: flex; justify-content: space-between; align-items: baseline; gap: .5rem; padding: .5rem .6rem; border-radius: .4rem; color: #33383d; text-decoration: none; font-size: .92rem; }
.ci-nav a:hover { background: #eef3f9; color: #0b66c3; }
.ci-nav a span { color: #8a9199; font-variant-numeric: tabular-nums; }

/* One centred column, capped so rows stay a comfortable width to scan. */
.ci-main { box-sizing: border-box; width: 100%; max-width: 64rem; margin: 0 auto; padding: 2rem 2.5rem 6rem; }
.ci-head h1 { margin: 0 0 .4rem; font-size: 1.7rem; line-height: 1.25; }
.ci-head p { margin: 0 0 .9rem; max-width: 48rem; color: #4a5057; }
.ci-theme { display: flex; align-items: center; gap: .6rem; margin: 0 0 1.1rem; color: #4a5057; }
.ci-seg { display: inline-flex; border: 1px solid #c7ccd2; border-radius: .4rem; overflow: hidden; background: #fff; }
.ci-seg a { padding: .2rem .9rem; color: #0b66c3; text-decoration: none; }
.ci-seg a + a { border-left: 1px solid #c7ccd2; }
.ci-seg a[aria-current="true"] { background: #0b66c3; color: #fff; }

.ci-cat summary { cursor: pointer; list-style: revert; }
.ci-cat summary h4 { display: inline; }
.ci-legend { display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); gap: .6rem; margin: 0; padding: 0; list-style: none; font-size: .82rem; color: #4a5057; }
.ci-legend li { padding: .7rem .85rem; background: #fff; border: 1px solid #dfe2e6; border-radius: .6rem; }
.ci-legend strong { display: block; margin-bottom: .15rem; color: #1b1d20; }

.ci-phase { margin-top: 2.6rem; scroll-margin-top: 1rem; }
.ci-phase h2 { display: flex; align-items: baseline; gap: .6rem; margin: 0 0 .9rem; padding-bottom: .5rem; border-bottom: 1px solid #d5d9de;
  font-size: .82rem; letter-spacing: .06em; text-transform: uppercase; color: #0b66c3; }
.ci-count { margin-left: auto; padding: 0 .55rem; border-radius: .7rem; background: #eef1f4; color: #6a717a; font-size: .75rem; font-weight: 500;
  letter-spacing: 0; text-transform: none; font-variant-numeric: tabular-nums; }

.ci-card { margin-bottom: 1rem; padding: 1.1rem 1.4rem .6rem; background: #fff; border: 1px solid #dfe2e6; border-radius: .7rem; }
.ci-card h3 { display: flex; align-items: center; gap: .6rem; margin: 0 0 .7rem; font-size: 1.1rem; }
.ci-cat { margin: 0 0 .9rem; }
.ci-cat h4 { margin: 0; padding: .35rem .5rem; border-bottom: 1px solid #eceef1; font-size: .72rem; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: #7a8189; }

/* Every entry is one row on the same three columns — name | With popup / View | Background only — so the
   buttons line up down the whole card whatever the length of the name. */
.ci-cat ul { margin: 0; padding: 0; list-style: none; }
.ci-cat li { display: grid; grid-template-columns: minmax(0, 1fr) 7.5rem 9.5rem; align-items: center; gap: .6rem; padding: .35rem .5rem; border-bottom: 1px solid #f1f2f4; }
.ci-cat li:last-child { border-bottom: 0; }
.ci-cat li:hover { background: #f4f7fb; }
.ci-label { min-width: 0; overflow-wrap: anywhere; }
.ci-btn { display: block; box-sizing: border-box; padding: .15rem .6rem; border: 1px solid #0b66c3; border-radius: .4rem; text-align: center; text-decoration: none; font-size: .85rem; white-space: nowrap; }
.ci-view { background: #0b66c3; color: #fff; }
.ci-view:hover { background: #0a58a8; }
.ci-bg { background: #fff; color: #0b66c3; }
.ci-bg:hover { background: #eaf2fb; }

@media (max-width: 900px) {
  .ci { grid-template-columns: 1fr; }
  .ci-nav { position: static; height: auto; border-right: 0; border-bottom: 1px solid #dfe2e6; display: flex; flex-wrap: wrap; gap: .25rem; }
  .ci-nav-title { flex-basis: 100%; }
  .ci-main { padding: 1.5rem 1rem 4rem; }
  .ci-cat li { grid-template-columns: minmax(0, 1fr) auto auto; }
}
`

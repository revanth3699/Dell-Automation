# screen_catalog

A browsable catalog of **every screen and popup** of the Dell Data Assistant (MyDellExperience, Target PC), each in
every state worth checking, so screen text can be validated without running a real two-PC migration.

It is **not** a copy of the app. The screens are drawn by the app's own React code, read straight from the Rebit repo
(`Cdm/Cdm/TargetPc.UI/web`). This folder only adds a stand-in for the native (C#) side that tells that React code what
to show, plus the index/viewer pages and the checks around it.

```
Rebit repo (TargetPc.UI/web/src)            this folder (screen_catalog/)
  App.tsx, screens/, components/, CSS  <-- imported via the @app alias (read-only)
                                            src/catalog/scenarios.ts   what to show: ~200 states, in journey order
                                            src/catalog/fakeHost.ts    stand-in for WebView2: pushes those states
                                            src/catalog/CatalogIndex   the index page   frame.ts  the 1200x800 viewer
```

## Quick start — install and run

Do these once, in order. Commands are for Windows (PowerShell or Command Prompt).

**0. What you need**
- **Node.js 22 LTS or newer** (Vite 8 needs 20.19+ or 22.12+; get the LTS from https://nodejs.org). After installing, **close and reopen the terminal**, then check
  `node -v` and `npm -v` both print a version. If `npm` is "not recognized", Node is not installed or the terminal was
  opened before it was — reopen it, or sign out and in.
- **Google Chrome** (the audit drives it; the catalog itself runs in any modern browser).
- **The Rebit repo** checked out on this machine (the app's code is read from it).

**1. Prepare the Rebit app folder (once)**
```
cd <rebit>\Cdm\Cdm\TargetPc.UI\web
npm install
npm run generate:i18n
```
`npm install` installs the app's packages (including its design system); `generate:i18n` builds the app's text file from
`Resources.resx`. Re-run `generate:i18n` whenever the resx changes.

**2. Install this folder (once)**
```
cd <Dell-Automation>\screen_catalog
copy .env.example .env
npm install
```
Open the new `.env` file and set the one line to your Rebit web folder, e.g.
```
REBIT_WEB_SRC=C:/Users/you/Desktop/Dell Migrate/rebit/Cdm/Cdm/TargetPc.UI/web
```
(Forward slashes, no quotes needed. A path with spaces is fine.)

**3. Run it**
```
npm run dev
```
Leave that terminal open and browse to **http://localhost:5173/catalog.html**. Stop it with `Ctrl+C`.

**4. Check everything (optional)**
```
npm run build:catalog
npm run audit
npm test
npm run typecheck
```
`audit` plays every screen in headless Chrome and checks all the app's text appears; `test` and `typecheck` catch drift
from the app (see **Commands**). If Chrome is not in the default place, add `-- --chrome "C:\path\to\chrome.exe"` to the audit.

**Troubleshooting**

| You see | Cause and fix |
|---|---|
| `REBIT_WEB_SRC is not set` | No `.env` (or the line is wrong). Do step 2; the path must be Rebit's `TargetPc.UI\web` folder. |
| `... not found — run "npm install" in that folder first` | Step 1 not done in the Rebit web folder. |
| `... run "npm run generate:i18n" in that folder first` | The app's text file has not been generated. Run it in the Rebit web folder. |
| `WARNING: Resources.resx is newer than the generated screens.json` | Text may be stale; run `npm run generate:i18n` in the Rebit web folder. |
| Page loads but a screen shows `⟦missing:SomeKey⟧` | That text key is not in the app's generated text; regenerate (above) or the catalog uses a key the app removed. |
| Blank page / `Failed to resolve import "@app/..."` | `REBIT_WEB_SRC` points at the wrong folder — it must contain `src\App.tsx`. |
| `http://localhost:5173` will not open | `npm run dev` is not running (or the terminal was closed), or the port is taken — Vite prints the port it used. |
| `audit`: `No catalog build at ...` | Run `npm run build:catalog` first. |
| `audit`: cannot start Chrome | Pass `-- --chrome "<path to chrome.exe>"`, or set the `CHROME_PATH` environment variable. |

## Setup (details)

1. In the Rebit repo, install and generate the app's text once (the catalog reads both):
   ```
   cd <rebit>/Cdm/Cdm/TargetPc.UI/web
   npm install
   npm run generate:i18n        # Resources.resx -> src/i18n/locales/en/screens.json
   ```
2. Here:
   ```
   cd screen_catalog
   copy .env.example .env       # then set REBIT_WEB_SRC to that web folder (or set it as a real env variable)
   npm install
   ```
   `REBIT_WEB_SRC` is checked on every run, with a message saying what is missing (`scripts/webSrc.mjs`). If
   `Resources.resx` is newer than the generated text it warns that the text may be stale.

Nothing in the Rebit repo is changed by anything here.

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Serves the catalog at `http://localhost:5173/catalog.html` (keep the terminal open). |
| `npm run build:catalog` | Writes the static catalog to `dist-catalog/` (git-ignored) for the audit and for automation. |
| `npm run audit` | Plays every scenario in headless Chrome (popup view and background-only view) and checks them — see below. Needs `build:catalog` first. `-- --theme light,dark`, `-- --filter <regex>`, `-- --chrome <path>`, `-- --dump surfaces.json` are available. |
| `npm test` | Unit tests: every screen/popup has a scenario, navigation matches the app's real flow, no missing text key, formats match the C#. |
| `npm run typecheck` | Type-checks the catalog **and the app's sources** together. This is what notices the app's contract changed (a new screen, a renamed field). |

## Using the pages

- **Index** (`/catalog.html`): every entry in journey order, grouped by phase, screen and kind (Screen states · Popups ·
  Dropdowns · Selections · Inputs · Tooltips). Popups have **With popup** and **Background only** buttons.
- **Viewer**: one scenario in an exact 1200x800 app window, controls kept outside it. Keys: `[` or `p` previous, `]` or
  `n` next, `b` popup/background, `d` light/dark, `i` index. In a text field hold **Alt** (Alt+B). `←` `→` too when the
  app is not focused.
- **Automation**: `window.__SCREEN_CATALOG__` (manifest), `body[data-catalog-state]` (`ready` — no sleeps) and
  `window.__CATALOG__.collectText()` (text, attributes, control states, per-element font/size/position). The full contract
  is in the Rebit repo: `docs/reference/05-visual-screen-verification.md` §5.

## What the audit proves

`npm run audit` checks, for every view: it reaches `ready`, the right number of popups are open, no text key is missing,
no JavaScript error. It also checks **coverage**: every string in the app's `Resources.resx` is visible on at least one
scenario. A string that genuinely cannot be shown on a React screen (native-only, dead key, never shown by design) must be
listed with a reason in `scripts/catalog-coverage-exceptions.json`; the audit fails on an unexplained gap **and** on a stale
exception.

## Keeping it right — read before editing `scenarios.ts`

- **The screens are the app's; the data is ours.** A scenario's values must be what the C# really pushes. Trace
  view model -> `Bridge/Handlers/*ScreenAdapter` -> the React view; copy the real format and shape (for example
  `StorageSummary.FormatBytes` prints `28 GB`, `FormatEstimate` prints `14 minutes`, the results screen always has six
  tiles). React renders `statusMessage` only on ConnectOldPc, EnterCode, TrustNetwork, CloseApplications and Complete.
- **Text from the resx** goes through `res('Key')`; **C#-hard-coded text** is copied verbatim with its source line in a
  comment; **run-time values** (names, sizes, dates) are sample data and are not expected copy.
- **Navigation** (`src/catalog/flow.ts`) is transcribed by hand from the C# view models with `file:line`. When the app's
  navigation changes, update it; `npm test` enforces that every screen is reachable and every popup sits over a screen
  that raises it.
- **When the app changes:** `npm run typecheck` fails if the contract moved; `npm test` fails if a new screen/popup has
  no scenario; `npm run audit` fails if new text appears that no scenario shows.

## Limitations

- It proves layout and per-state text, not multi-step native flows: action buttons get a bare `ok` and no follow-on state.
- Rendering is Chrome here, WebView2 in the product (same Chromium engine; sub-pixel text may differ).
- The native WPF parts (title bar, splash, startup-failure dialog) are not React and do not appear.
- Only the English text is generated today.
- States whose text comes from the engine at run time (a skipped item's own details, the engine's locale text) are not
  staged.

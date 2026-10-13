# CLAUDE.md — Dell Data Assistant Automation: Code Architecture

This file is the standing reference for **where new code goes** in this repo and **what
pattern to follow** when writing it. It describes the architecture as it exists after
the 2026-10-14 assertions/locators/components refactor — read this before assuming
anything about "how this codebase is laid out" from older docs (see **Other docs**
below; some are now stale).

This is a WinAppDriver/Appium UI-automation framework that drives the real Dell Data
Assistant Windows app (WebView2-hosted) across two independent physical/virtual
machines — a Target PC and a Source PC — through a PC-to-PC migration, coordinating
the two over a small separate FastAPI relay since neither machine can see the other's
process.

## Other docs — what to read instead of re-deriving things

- **README.md** — setup (`uv sync`, `.env`), environment variables, and a code-flow
  walkthrough of one `role_runner` run end to end. Its "Project structure" and
  "Architecture: layers" sections are accurate as of this refactor.
- **PROJECT_PLAN.md** — original design/history/phased roadmap. Goes stale on status;
  treat it as historical context, not current truth.
- **tracking/IMPLEMENTATION_STATUS.md** (+ the `project-status-tracking` skill) — the
  *intended* authoritative "what's actually built vs. planned" doc. As of this writing
  it is dated 2026-10-07 and predates this whole refactor — **don't trust its folder
  structure or phase-status claims without spot-checking the real code first.** It
  should be refreshed; flag this to the user if you're about to rely on it for
  anything consequential.
- **This file** — durable architecture/convention reference (where code goes, shared
  primitives, established patterns). Changes rarely — only when the architecture
  itself changes, not when individual features are added.

## The layers, and the one rule that matters

Five layers, two cross-cutting ones. Imports flow one direction only — a layer never
imports from anything to its right:

```
locators/  -->  components/  -->  flows/  -->  orchestration/ (role_runner.py)
    ^
    |
assertions/  (imported directly by flows/, not just by components/)

factory/   -- Session, driver lifecycle, config, capabilities, logging. Used by
              components/flows/orchestration; never imports from them.
utils/     -- standalone helpers (retry, wait_utils, coordination_client, ocr,
              prerequisites). Used by everything above; imports from nothing above.
reports/   -- HTML reporting. Only components/base_component.py and the two real
              entry points (orchestration/role_runner.py, tests/conftest.py) touch it.
```

**The one rule that matters for "where does my new code go":**

| If you're writing... | It goes in... | Because |
|---|---|---|
| A click/type-target locator (button, link, input field) | `locators/<role>/<name>.py` | Only ever a click/type target — never used for an existence check. |
| An expected heading/body text + its existence-check locator | `assertions/<role>/<name>.py` | Never a click target — only ever polled to check presence. |
| A poll-and-return-bool/str function over one of the above | `assertions/<role>/<name>.py` | Built on `assertions/common.py`'s shared primitives — see below. |
| A click/type/read action on a screen or dialog | `components/<role>/<name>.py` | One class per screen/dialog, **actions only, no existence checks**. |
| Business logic — what to check, in what order, what to click next | `flows/<role>/<name>.py` | Imports `assertions.<role>.<name>` directly (aliased) + the matching `components.<role>.<name>` class. |
| A new end-to-end scenario (what runs after pairing) | `orchestration/role_runner.py` | See **Adding a new scenario** below. |

A locator and an assertion can both exist for the *same element* only when it's
genuinely dual-purpose (typed into/clicked **and** checked) — e.g. `WelcomeScreen`'s
sign-in button. In that case the locator lives in `locators/`, and the assertion file
imports it from there rather than duplicating it.

## Why this split exists (per explicit user direction, 2026-10-14)

Before this refactor, a dialog like `TrustNetworkDialog` had one method,
`accept(timeout) -> bool`, that checked its own heading AND clicked its button in one
call. That's gone. Every such method is now split into:
1. An assertion function, `assertions/<role>/<name>.py::is_showing(session, timeout)`,
   built on `assertions/common.py`'s primitives.
2. A pure action method, `components/<role>/<name>.py::click_X()`, with no existence
   check inside it.

Flows call the assertion first, then the action — decoupling "is this thing here"
(which can be asserted from anywhere, with any timeout, without constructing a
component) from "click/type on it" (a thin, stateless wrapper around `BaseComponent`).

## Shared primitives — use these, don't re-invent polling

**`assertions/common.py`** (the one place "poll for an element and return bool" lives):
- `text_exists(session, locator, name, timeout=2.0) -> bool`
- `button_exists(session, locator, name, timeout=2.0) -> bool` (identical body to
  `text_exists`, separate name so call sites read clearly)
- `all_exist(session, [(locator, name), ...], timeout=2.0) -> bool` — AND-gate, e.g. a
  heading **and** its body text together (stronger than the heading alone). Preserves
  short-circuit evaluation — stops at the first failing check.
- `gone(session, locator, name, timeout, poll_interval=0.5) -> bool` — polls until the
  element stops being found (NOT `not text_exists(..., long_timeout)` — that returns on
  the first miss, giving the page zero chance to actually transition).

**`components/base_component.py::BaseComponent`** (every component wraps this):
- `click(timeout=None)` / `click_at_center(timeout=None)` — `click_at_center()` is the
  fallback when `click()` reports success but the on-screen control doesn't actually
  respond (a real, repeatedly-confirmed WebView2 bug in this app — see **Gotchas**).
- `type_text(text)`, `get_text(timeout=None)`, `exists(timeout=2.0)`,
  `wait_until_gone(timeout, poll_interval=0.5)`.
- Every action times itself, captures a before/after screenshot, and records to
  `ActionReporter` automatically — you never call reporting code directly.
- Raises `ComponentActionError` on failure (never fails silently) — you generally don't
  need to check a click's return value; let it raise.

**`utils/wait_utils.py::poll_until(condition_fn, timeout, interval=0.5, ignored_exceptions=())`**
underlies both of the above — the one shared explicit-wait loop in the codebase.

## Recipe: adding a new dialog/screen

Worked example from this session — `components/source/battery_critically_low_dialog.py`
("Your battery is critically low." → Cancel). Follow this shape for anything new:

1. **`assertions/<role>/<name>.py`** — the expected text + its locator + `is_showing()`:
   ```python
   from assertions.common import text_exists

   HEADING_TEXT = "Your battery is critically low."
   BATTERY_CRITICALLY_LOW_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')

   def is_showing(session, timeout: float = 0.1) -> bool:
       return text_exists(session, BATTERY_CRITICALLY_LOW_HEADING_LOCATOR, "BatteryCriticallyLowHeading", timeout=timeout)
   ```
2. **`locators/<role>/<name>.py`** — only the click target:
   ```python
   CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
   ```
3. **`components/<role>/<name>.py`** — only the action:
   ```python
   from components.base_component import BaseComponent
   from locators.source.battery_critically_low_dialog import CANCEL_BUTTON_LOCATOR

   class BatteryCriticallyLowDialog:
       def __init__(self, app_session):
           self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "BatteryCriticallyLowCancelButton")
       def click_cancel(self) -> None:
           self._cancel_button.click()
   ```
4. **Wire it into the flow** that should race it — import the assertion module
   aliased (every screen reuses the name `is_showing`, so flows import e.g.
   `from assertions.source import battery_critically_low_dialog as battery_critically_low_assertions`),
   instantiate the component in `__init__`, and add the check into every polling loop
   it can plausibly interrupt (see **The "race it continuously" pattern** below).
5. **Verify statically** (see **Verification without live hardware** below) — a live
   run is still required before calling it confirmed working.

If a dialog/screen has NO click action at all (pure check, e.g.
`assertions/target/pairing_discovery_screen.py` or `MigrationErrorDialog`'s own
`is_showing()`), it has no `components/` class at all — the flow calls the assertion
function directly. Don't create an empty component class for symmetry.

## The "race it continuously" pattern

Several dialogs (`NetworkDisconnectedDialog`, `PlugIntoAcPowerDialog`,
`DesktopShortcutDialog`, `TrustNetworkDialog`, `BatteryCriticallyLowDialog`) have been
confirmed, via live screenshots, to appear **unpredictably** — at any point across a
long wait, not tied to one specific screen. These are not checked once; every polling
loop in the affected flow checks them every cycle:

```python
while time.monotonic() < deadline:
    if some_dialog_assertions.is_showing(self.app_session, timeout=0.1):
        self.some_dialog.click_whatever()
        self.log.warning('... appeared -- handled')
        continue
    if the_real_thing_assertions.is_showing(self.app_session, timeout=1.0):
        break
    ...
```

When you confirm a NEW dialog can appear unpredictably (via a live screenshot, not a
guess), add it to every loop it could plausibly interrupt, the same way — don't assume
it's confined to the one screen you happened to see it on. This has bitten this
project more than once (see `IMPLEMENTATION_STATUS.md` / git history for the Desktop
Shortcut dialog's scope correction).

## Adding a new scenario

`orchestration/role_runner.py` is the one real entry point
(`python -m orchestration.role_runner --role {target,source} --run-id <id> --scenario <name>`).
`TargetRunner`/`SourceRunner` own only the fixed prefix every scenario shares
(sign-in+pairing for Target, pairing for Source) — never touch those classes for a new
scenario. Instead:

1. Write one or more plain step functions, `(session) -> None` (or returning something
   meaningful like `full_transfer_source`'s `bool`), e.g. `full_transfer_target`.
2. Write one scenario function that picks a runner class + step list per role and
   calls `RoleRunner.run(role, run_id, runner_class, [steps], launch_mode=launch_mode)`.
3. Add one entry to the `SCENARIOS` dict.

A scenario that needs to diverge **before** pairing finishes (not just after) doesn't
fit this shape — it needs its own prefix too, not just a new step list (this was tried
as a flag-based prefix-skip and reverted; a generic solution is still open).

## Gotchas — confirmed real, don't re-discover these the hard way

- **Exact-string text matching is fragile.** A heading typed from a screenshot can
  silently never match live text that differs by a curly vs. straight apostrophe, or
  unexpected whitespace — `is_showing()` will just return `False` forever with no
  error. Prefer `contains(@Name, "...")` on a short, distinctive, **apostrophe-free**
  substring over an exact `@Name="..."` match, especially for any text containing a
  possessive/contraction. If genuinely unsure which of two phrasings is real (e.g. a
  dialog might show different copy for different failure causes), assert on an
  `or`-combined `contains()` for both rather than guessing one.
- **Don't wrap asserted UI text in literal double quotes in log messages or raised
  error messages** (per explicit user direction, 2026-10-13) — write
  `self.log.warning("Your battery is critically low. appeared -- clicking Cancel")`,
  not `self.log.warning('"Your battery is critically low." appeared -- clicking
  Cancel")`. This applies to runtime-visible strings only (`self.log.*()` calls and
  `raise ...Error(...)` messages) — module/method docstrings are unaffected. XPath
  locator values (`@Name="..."`) are also unaffected — this is about log/error text,
  not locator syntax.
- **A WinAppDriver click can report success without anything happening.** The element
  is found and the Invoke pattern completes at the API level even when the window is
  still loading or isn't in the foreground. `factory/session.py`'s launch functions
  now call `bring_window_to_foreground()` + a short settle delay right after attach —
  don't remove that. If a specific click still silently no-ops after that, use
  `click_at_center()` instead of `click()` (a real simulated mouse click, not a UIA
  Invoke) — this has been the fix for WebView2 buttons specifically before.
- **`find_new_browser_window_hwnd()` prefers a title match among new windows**, not
  just the first new window — Chrome can bring up other incidental top-level windows
  around the same moment it opens the real sign-in tab.
- **Don't trust a transition/progress screen alone as a success signal** if a
  known failure dialog can appear later and supersede it — see
  `flows/target/authentication/sign_in_flow.py`'s `_LateSignInFailure` for the pattern
  (race the failure dialog for the ENTIRE remaining wait, not just a short fixed
  window after the first "looks like success" signal).
- **Dead files — don't edit, don't import:** `factory/wait_utils.py`,
  `factory/coordination_client.py`, and `factory/prerequisites.py` are unused
  duplicates of the real `utils/wait_utils.py`, `utils/coordination_client.py`, and
  `utils/prerequisites.py` (confirmed via `git grep` — nothing in the active codebase
  imports the `factory.*` versions). Use the `utils/` ones; the `factory/` copies
  should eventually be deleted.

## Verification without live hardware

Most AI-assisted sessions on this repo have no access to the real Windows
desktop/WinAppDriver/Dell app — code can only be verified statically. The established
minimum bar before calling something done:
```
uv run python -c "
import importlib, pkgutil
for pkg_name in ['assertions', 'locators', 'components', 'flows', 'orchestration', 'factory']:
    pkg = importlib.import_module(pkg_name)
    for _, name, _ in pkgutil.walk_packages(pkg.__path__, pkg_name + '.'):
        importlib.import_module(name)
print('ALL IMPORTS OK')
"
uv run python -m orchestration.role_runner --help
```
Always say explicitly that this is static verification, not a live confirmation — the
real test is a live run, which only the user (with actual hardware) can do.

## Both machines, one channel

Target and Source run `orchestration/role_runner.py` as **fully independent
processes** (possibly on separate physical machines) — there is no shared process or
shared memory. The only channel between them is `coordination_service/app.py` (a
standalone FastAPI relay, `PUT`/`GET /runs/{run_id}/{key}`), reached via
`utils/coordination_client.py`'s `publish()`/`wait_for()`. Never invent a more direct
communication path between Target-side and Source-side code.

# Dell Data Assistant — Python UI Automation Framework

**Project plan and living design document.** Last updated: 2026-10-05.

---

## 1. Context

**Dell Data Assistant** (`DellDataAssistant.TargetPc.exe`) is a BETSOL-built, Dell-branded PC-to-PC
data migration tool. The goal of this project is a **Python automation framework** that drives the
full migration flow — launch → sign in → pair (a code generated on Source, entered on Target) →
select data → transfer → verify completion — across **two real, LAN-connected machines**.

### 1.1 Confirmed application architecture

- The Target PC build is a **WPF shell window hosting a WebView2 (Chromium) control**. The actual
  on-screen UI (buttons, screens, progress views) is a **local React SPA**
  (`wwwroot\index.html` + bundled JS/CSS) rendered inside WebView2 — not a native WPF control tree
  for the main content. The outer window chrome (title bar, min/max/close) *is* plain WPF.
- A separate headless engine process, `DellDataManager.exe`, is spawned by the GUI and does the
  real migration work over sockets — automation doesn't need to talk to it directly.
- Sign-in uses `IdentityModel.OidcClient`; the app opens the **external default system browser**
  for the OAuth/OIDC login step (confirmed real call: Dell's own IdP,
  `https://www-poc.dell.com/dci/idp/dwa/authorize?response_type=id_token&client_id=...`, POC
  environment, implicit flow), then control returns to the desktop app after the redirect.
- From `DellDataAssistant.TargetPc.exe.config`: `.NET Framework 4.8`,
  `PairingTimeoutInMilliseconds=600000` (10 min), `AutomaticallyAddFirewallRule=true` (covers only
  the app's own engine socket, not our tooling — and is itself evidence the app needs admin
  rights), OIDC endpoint values are **compile-time constants** (our framework only ever supplies
  end-user credentials, never endpoint config).
- No installer exists (raw Release build) — the framework launches the app by absolute exe path.
- **The app requires administrator elevation** (confirmed by hands-on testing — see §5).
- **Open / blocked**: the Source PC side runs a **different executable**, not just a different
  mode of the same exe. Its name, location, and whether its architecture mirrors Target's
  (WPF+WebView2+React) is unconfirmed, pending codebase/build access. Nothing about
  `components/source/` or `flows/source/` should assume parity with Target until independently
  verified.

### 1.2 Confirmed UI flow (manual walkthrough + live automation, see §5)

1. Desktop app shows **"Welcome to Dell"** with a "Sign in or create an account" panel and a
   circular arrow button captioned "We'll open a new browser window for you to get started."
2. Clicking it opens the OS default browser (observed: Chrome — **varies per machine**, must stay
   configurable, never hardcoded) to the real Dell sign-in page (Google Sign-In button,
   "Email or Mobile Number" field, "Continue" button).
3. Meanwhile the desktop app shows its own modal: **"Sign in to MyDell to continue"** —
   "We've opened your web browser so you can sign in and continue...", a "Having trouble? Retry"
   link, a "Waiting for sign-in..." spinner, and a "Cancel" button.
4. MFA is **email OTP** (confirmed) — for the test account currently in use, the OTP is a
   **static value**, not a real rotating code (see §5.3) — a major simplification for this
   environment, though the general design should stay mailbox-capable for other environments.
5. On success, the modal clears and the app shows **"Hi, {name}. Welcome to Dell."** with a
   "Sign Out" link — confirmed as a reliable signed-in indicator.
6. **Not yet located**: what comes after the "Hi, {name}" screen — i.e. where the pairing-code
   step actually begins. No "Next"/"Continue"/"Pair"/"Get Started" element exists on that screen.
   This is the next thing to find via manual walkthrough + Phase 0 inspection.

### 1.3 Confirmed operating model

- Source and Target run as **fully independent, separate process invocations** — never one
  process holding both machines' sessions. Role (`source`/`target`) is picked per invocation at
  run time; the same framework code runs both, parameterized by role.
- Because the two invocations are genuinely unrelated processes, cross-machine hand-offs (the
  pairing code; later, other signals) go through a small **Coordination Service**, not an
  in-memory variable (see §4.6).
- **AppDriver stack = Appium + WinAppDriver conceptually** (not FlaUI) — though in practice the
  actual implementation talks to WinAppDriver's REST API directly rather than via the Appium
  Python client library (see §4.2/§5 — the client library was found to be unreliable in this
  environment). Each invocation talks only to its own local WinAppDriver instance.

---

## 2. Mandated architecture (user requirements)

Factory (drivers/sessions/loggers) → Components (Page Objects, with a shared sub-layer) → Flows
(actions built on Components, with shared-auth / source / target sub-layers) → Assertions
(grouped) → Reporting + screenshots on every action → auto-scroll-into-view built into element
interaction, for both Source and Target roles via one parameterized codebase.

## 3. Folder / module structure

```
dell-data-assistant-automation/
├── locators/target/<class_name>.py # one module per Page Object class (real impl, Target-only so far)
├── .env / .env.example              # factory/config.py's env vars, python-dotenv-loaded
├── factory/
│   ├── driver_factory.py           # DriverFactory + WinAppDriverSession/WinAppDriverElement (real impl, see Sec 4.2)
│   ├── capabilities.py             # legacy bare-key desiredCapabilities builders (real impl, see Sec 4.3)
│   ├── wait_utils.py               # poll_until(...) -- the one shared explicit-wait primitive (real impl)
│   ├── prerequisites.py            # Target-PC prereq checks + auto-install (real impl, see Sec 4.9)
│   ├── mock_server.py              # GlassFloor mock-server manager (real impl, see Sec 5.3a)
│   ├── config.py                    # WinAppDriver URL/host/port, exe/process names, mock-server port,
│   │                                #   browser process names, install-path search lists (real impl)
│   ├── session_factory.py          # SessionFactory: Session dataclass -- NOT YET IMPLEMENTED (stub)
│   ├── logger_factory.py           # per-role logging.Logger -- NOT YET IMPLEMENTED (stub)
│   └── otp_client.py               # OtpClient protocol + Gmail/Outlook impls -- NOT YET IMPLEMENTED (stub)
├── components/                     # Page Object layer
│   ├── base_component.py           # BaseComponent: wait -> scroll-into-view -> act -> screenshot -> report
│   ├── shared/   (navigation_bar.py -- genuinely cross-role chrome only, e.g. Next/Back/Cancel)
│   ├── source/   (pairing_code_screen.py, data_selection_screen.py, transfer_progress_screen.py)
│   └── target/   (pairing_code_entry_screen.py, transfer_receive_screen.py, pairing_discovery_screen.py,
│                   sign_in_screen.py, common_dialogs.py, browser_sign_in_page.py -- see note below)
├── flows/
│   ├── source/ (pairing_flow.py, data_selection_flow.py, transfer_flow.py)
│   └── target/ (pairing_flow.py, transfer_flow.py, authentication/sign_in_flow.py)
├── orchestration/role_runner.py     # NOT YET IMPLEMENTED (stub)
├── coordination_service/            # NOT YET IMPLEMENTED (stub)
│   ├── app.py
│   └── README.md
├── assertions/target/error_banner.py # expected error-banner text constants (real impl, Target-only so far)
├── reports/                         # NOT YET IMPLEMENTED (stubs only)
├── tests/                           # NOT YET IMPLEMENTED (stubs only)
├── tools/
│   ├── launch_target_app.py        # real, tested CLI entry point -- prereqs -> (mock server) -> launch -> attach
│   └── phase0_inspection_notes.md  # raw Phase 0 findings, real locators, open items
├── requirements.txt, pytest.ini, README.md
```

This maps every mandated layer 1:1: Factory → `factory/`; Components (+shared) → `components/`;
Flows (+source, +target) → `flows/`; Assertions → `assertions/`;
Reporting+screenshots → `reports/` wired through `BaseComponent`; scroll-into-view → built into
`BaseComponent._perform` automatically, not opt-in. **Current implementation status**: `factory/`
(driver lifecycle, prerequisites, mock server, browser attach, config), the full Target PC
sign-in flow (`flows/target/authentication/`, `components/target/sign_in_screen.py`,
`common_dialogs.py`, `browser_sign_in_page.py`, `pairing_discovery_screen.py`), and the Target
pairing flow (`flows/target/pairing_flow.py`, `components/target/pairing_code_entry_screen.py`)
are real; `locators/target/` and `assertions/target/error_banner.py` back all of the above.
Everything else (transfer flow, orchestration, coordination_service, reports, tests, the entire
Source role) is still stub-only.

**Authentication is Target-PC-only, confirmed directly by the user (2026-10-05): Source PC has
no sign-in step at all.** The sign-in flow and every component/factory piece it depends on
(`sign_in_screen.py`, `common_dialogs.py`, `browser_sign_in_page.py`, `pairing_discovery_screen.py`,
`factory/browser_driver_factory.py`) live under `target/`, not `shared/` -- there is no
parameterize-by-role version of this flow, unlike the original skeleton's assumption. The empty
`flows/shared/` folder this left behind was removed; `components/shared/` still holds
`navigation_bar.py`, which remains genuinely cross-role (Next/Back/Cancel chrome used by both
apps' other screens).

**Deviation from this section's originally-planned `config/locators/`, `config/settings.py` +
`config/environments/*.env.example`, and `assertions/*.py` layout (2026-10-05, confirmed directly
by the user, who explicitly chose to keep this rather than conform to the pre-existing skeleton).
Later reconciled the same day, also confirmed directly by the user: the original `config/` tree
and the flat `assertions/{common,pairing,transfer}_assertions.py` stubs were all one-line,
zero-content placeholders, never filled in or imported by anything -- deleted outright rather than
left coexisting. No git history in this repo to recover them from if that turns out to be wrong;
see tools/phase0_inspection_notes.md / ask the user if `config/settings.py`'s per-role
`MachineConfig` idea (credentials/browser-type for Source too, not just Target) is still wanted --
nothing in `factory/config.py` covers that today, Target-only infra config only.** The Target PC
sign-in + pairing-code work uses:
- `locators/target/<component_or_class_name>.py` -- one module per Page Object class (not the
  three grouped `config/locators/{shared,source,target}_locators.py` files). E.g.
  `locators/target/email_step.py`, `locators/target/otp_step.py`,
  `locators/target/pairing_code_entry_screen.py`.
- `factory/config.py`, env-var-driven via `python-dotenv` loading a root `.env`
  (`.env.example` alongside it) -- not `config/settings.py`'s planned `MachineConfig` dataclass
  or the per-role `config/environments/*.env.example` files. Covers what was previously
  independently hardcoded (and already drifting -- `WINAPPDRIVER_URL` was defined separately in
  both `factory/driver_factory.py` and `factory/browser_driver_factory.py`) across
  `factory/driver_factory.py`, `factory/browser_driver_factory.py`, `factory/prerequisites.py`,
  `factory/mock_server.py`: WinAppDriver host/port, target exe/process names, mock-server port,
  browser process names, WinAppDriver/Node.js install-path search lists.
- `assertions/target/error_banner.py` -- expected error-banner text (email/password/OTP wrong-
  credential messages, confirmed from a user-supplied flow diagram, `dell screens flow.pdf`) as
  plain named constants, consumed by `locators/target/error_banner.py`'s `contains()` locator.
  Not the function-based `assert_text_equals`/`assert_text_contains` style planned for
  `assertions/common_assertions.py`.

Also note: `flows/target/pairing_flow.py` and `components/target/pairing_code_entry_screen.py`
(`TargetPairingFlow`, `PairingCodeEntryScreen`, `ConfirmAccountsDialog`) are now real, not stub-only
as this section's status line below still says -- confirmed from the same flow diagram. The 6
pairing-code boxes' exact accessible names are still unconfirmed (found positionally, not by
name); no confirmed error-message text exists yet for a wrong pairing code.

## 4. Key design decisions

### 4.1 Driver Factory (idempotency)

`DriverFactory` holds one registry, keyed by `MachineRole` (`SOURCE`/`TARGET`), of
`WinAppDriverSession` objects. `get_app_driver(role, build_path, app_arguments)` creates-on-first-call
and returns the same live instance thereafter (liveness checked by confirming the app's window
still exists). An `RLock` guards the registry. Teardown is explicit only, via `DriverFactory.quit_all()`.

### 4.2 Launch-then-attach pattern, and why this isn't the Appium Python client

**Confirmed necessary, step zero**: kill all matching processes first, by command-line match
(`CommandLine -like "*DellDataAssistant*"`), not just process name — the app's single-instance
lock will silently swallow a new launch's CLI args if any instance (even hidden) is already
running, making a launch with different arguments look like a no-op.

The confirmed sequence:
1. POST a session with `desiredCapabilities: {app: <path>, appArguments: "<quoted args>", platformName: "Windows", deviceName: "WindowsPC"}`
   (legacy bare-key shape, not W3C `appium:`-prefixed — see §4.3). **Expect this call to time out
   or error** — it reliably does, even on a fully successful launch (confirmed: WinAppDriver's
   internal window-detection timeout, ~20–25s, is shorter than the app's own render time,
   ~25–30s, 100% reproducible). A short client-side timeout (~5s) is used deliberately — we don't
   need to stay connected for WinAppDriver's own internal timeout, since the server-side launch
   proceeds regardless of whether our client is still waiting on the response.
2. Poll (reusing `poll_until`) for a process matching the app's exe name to appear, then read its
   `MainWindowHandle`.
3. Convert the handle to hex and POST a **second** session with
   `desiredCapabilities: {appTopLevelWindow: "<hex>"}` to get a working session attached to the
   already-running window.
4. Use the session from step 3 for all further automation.

**Deliberately does NOT use the Appium Python client's `WebDriver` class, and does NOT use
psutil/pywin32 in-process.** Both were tried first and both intermittently crashed the Python
interpreter outright — exit code 15 (later also seen as 255), no catchable exception, no Windows
crash/WER log entry at all, not reliably reproducible run to run. Extensive isolation testing
ruled out: `win32gui.EnumWindows`'s callback specifically, `psutil` alone, `subprocess` call
ordering, the Appium client specifically, and background-task-vs-foreground execution. The
practical fix that stuck: shell out to PowerShell for all process/window inspection (100%
reliable across dozens of runs) and implement a minimal purpose-built `WinAppDriverSession`/
`WinAppDriverElement` wrapper directly over `requests`, instead of the Appium client, exposing
just what `components/base_component.py` will need (find_element(s), click, send_keys,
get_attribute, screenshot, page_source). **Important later finding (§5.3b): most of that
"mystery crash" was actually the app's own WebView2 renderer crashing on its own, not our code —
but the PowerShell-based approach remains the right choice regardless of that, and was kept.**

### 4.3 Capability-format gotcha, confirmed

The Appium Python client (v6) auto-prefixes non-standard capabilities with `appium:` (W3C spec
compliance), but WinAppDriver 1.2.1 rejects that form outright
(`"Bad capabilities. Specify either app or appTopLevelWindow"`). `factory/capabilities.py` builds
raw dicts and sends them via the legacy `desiredCapabilities` body shape. `appArguments` (used for
the GlassFloor mock-server launch, §5.3a) is a single quoted command-line **string**, not a JSON
array — `factory/capabilities.py`'s `app_launch_capabilities()` handles the quoting.

### 4.4 Base element / interaction layer (not yet implemented)

Planned design, unchanged from original plan: `components/base_component.py`'s `BaseComponent` as
a template-method base class. Every `click()`/`type_text()`/`select()`/`get_text()` routes
through one `_perform(action_type, fn)`: find (explicit wait), scroll into view if needed,
perform the action, screenshot in a `finally` block, write one `ActionRecord` regardless of
pass/fail, raise only after evidence is captured. A thin `ElementAdapter` protocol would hide
driver-type differences — though since the Target AppDriver is now a custom
`WinAppDriverSession` (§4.2) rather than Selenium/Appium, this adapter's concrete shape needs
revisiting when this layer is actually built.

#### 4.4.1 Waits & timeouts

**Explicit waits only.** `factory/wait_utils.py`'s `poll_until(condition_fn, timeout, interval=0.5, ignored_exceptions=())`
is the one shared primitive, already used by the driver factory's window-polling. Named timeout
tiers (`config/timeouts.py`, not yet implemented) remain planned as: `ELEMENT_TIMEOUT_SECONDS` (10),
`SCREEN_TRANSITION_TIMEOUT_SECONDS` (30), `PAIRING_TIMEOUT_SECONDS` (600, matches the app's own
confirmed config), `TRANSFER_TIMEOUT_SECONDS` (1800). **New constraint from §5.3b**: the renderer
crash window (~47s after visible) means any polling loop operating on the live UI should budget
for roughly 40 reliable seconds, not assume indefinite stability.

### 4.5 Authentication / MFA (design only -- not yet implemented)

Email OTP is confirmed as the MFA mechanism in general, but **for the current test account, the
OTP is a static, fixed value**, confirmed via a real completed sign-in (§5.3) — meaning
`SignInFlow` (not yet built) won't need live mailbox automation for this environment; the static
value is just another credential in `MachineConfig`. The general-purpose `OtpClient`
protocol/Gmail/Outlook design from earlier planning is retained for other environments but
deprioritized given the static-OTP finding.

**Known-blocked alternatives, for the record** (don't re-attempt without new information): IMAP
basic auth is disabled Microsoft-wide on consumer Outlook.com accounts now. Browser-based mailbox
checking via Selenium also hit a blocker on this dev machine: Selenium Manager's driver
auto-download fails with TLS decryption errors (unclear root cause, possibly network
TLS-inspection middleware), even though `winget`/`pip` downloads succeeded.

### 4.6 Cross-machine coordination (design only -- not yet implemented)

Unchanged from original plan: Source and Target each run their own local invocation, sharing only
a `run_id` and a small Coordination Service (`coordination_service/app.py`, FastAPI,
`PUT/GET /runs/{run_id}/{key}`) for the pairing-code hand-off. Open item: the service's own
address-stability mechanism (mDNS / DHCP reservation / separate static host) is still undecided.

### 4.7 Config (design only -- not yet implemented)

Unchanged from original plan: `config/settings.py`'s `MachineConfig` dataclass, env-var only,
per-role `browser_type`, `otp_static_value` (new), etc.

### 4.8 Reporting + Assertions (design only -- not yet implemented)

Unchanged from original plan: custom per-action reporter (not `pytest-html`), `ActionRecord` →
`actions.jsonl` → `report.html`; `assertions/common_assertions.py` generic primitives composed
into domain-specific ones.

### 4.9 Prerequisite checks + auto-install (real, implemented, verified working end-to-end)

`factory/prerequisites.py`'s `ensure_target_prerequisites()` checks and auto-fixes, in order:
Windows Developer Mode (via `winreg`, not a PowerShell subprocess — see gotcha below), WinAppDriver
installed (via `winget` if missing), WinAppDriver running **elevated** (required — the app itself
needs admin elevation; a non-elevated WinAppDriver can't build a useful UIA tree for it at all,
blocked by UIPI), and required Python packages (`selenium`, `requests`). Node.js (only needed for
the GlassFloor mock-server flow) is checked separately via `ensure_mock_server_prerequisites()`,
kept decoupled since plain app launches don't need it.

**Confirmed gotcha**: a `subprocess.run` call to PowerShell earlier in the same process was, for a
while, suspected to corrupt a later pywin32 import (part of the broader crash investigation in
§4.2) — `check_developer_mode()` was switched to plain `winreg` to eliminate that specific
subprocess call as a variable. (This module no longer imports pywin32 at all, following §4.2's
pivot away from in-process psutil/pywin32, but the winreg-over-subprocess choice was kept as the
simpler, lower-overhead option regardless.)

**Elevated WinAppDriver launch mechanism — simplified after further testing.** A plain
`Start-Process -FilePath <path> -Verb RunAs` is sufficient to keep WinAppDriver alive (no
stdin-redirection tricks needed, despite an earlier finding to the contrary — see
tools/phase0_inspection_notes.md for the full back-and-forth). The
`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--force-renderer-accessibility` flag (required per §5.1) is
supplied via a **persisted `User`-scope environment variable**
(`ensure_webview2_accessibility_env_var()`), not the launching process's own in-memory environment
— an elevated ("runas") process doesn't inherit the latter, but does read persisted env vars fresh
from the registry regardless of elevation. The original stdin-keep-open `.ps1` launcher script was
deleted as unnecessary.

**Confirmed working end-to-end (2026-10-05, post project-reset verification)**: `kill existing
(~2s)` → `launch POST returns real HTTP 500 after ~10-20s` (not a client-side timeout — see the
`LAUNCH_ATTEMPT_TIMEOUT` finding below) → `window found (~1.5s)` → `attach succeeds (200)` →
`page_source` ~12,500+ chars, matching the confirmed-good tree size. Verified visually too (window
brought to foreground, screenshotted, matches expected UI).

**Two root causes behind the earlier "mystery crash" investigation, found and fixed**:
1. `LAUNCH_ATTEMPT_TIMEOUT` had been shortened to 5s on the (wrong) assumption that WinAppDriver
   continues the launch server-side after the client disconnects. It doesn't, in practice — a
   short client timeout caused the launch to never reach the app at all. **Restored to 35s.**
2. **Testing via inline `python -c "..."` is unreliable in this environment; the identical logic
   in a real `.py` file is not.** This was the actual source of most of the apparent randomness
   in the original crash investigation (§5.3b's WebView2 finding is real and separate, but a good
   fraction of "it crashed again, differently this time" was this). **Rule going forward: never
   use `python -c` for this framework's code — always a real script file.**

---

## 5. Phase 0 findings (confirmed via hands-on spike, 2026-10-05, Target PC build only)

Full raw notes: `tools/phase0_inspection_notes.md`.

### 5.1 WebView2 UIA accessibility tree — resolved

A normally-launched/attached instance exposed a UIA tree with a single node (bare outer window,
zero children) — the WebView2 React content is not reachable. Fixed by **two conditions together**:
1. **WinAppDriver must run elevated.** The app requires admin elevation (confirmed: direct
   `CreateProcess` fails with `ERROR_ELEVATION_REQUIRED`). A non-elevated WinAppDriver is blocked
   by UIPI from building a useful tree for an elevated target — this, not the WebView2 flag below,
   was the actual root cause.
2. `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--force-renderer-accessibility` set in WinAppDriver's
   own process environment before it launches the app.

With both met, the tree grew from 754 chars to ~12,575 chars (pre-auth screen) and ~18,265 chars
(post-auth screen), with real, queryable React content.

**Not yet tested**: the sign-in-browser-attach strategy (Selenium `debuggerAddress` vs. native
Win32 automation via WinAppDriver).

### 5.2 Real locators confirmed so far

CSS class names (e.g. `_title_8xt2q_7`) look like Vite CSS-module hashes — **build-specific, not
stable**. Prefer Name/text-based XPath over ClassName for this app's WebView2 content.

| Screen | Element | Locator | Notes |
|---|---|---|---|
| Pre-auth ("Welcome to Dell") | Sign-in trigger button | `//Button[@Name="Continue"]` | Visually an icon-only arrow; accessible Name is "Continue". `ClassName` contains stable `dds__button dds__button--icon-only` prefix + hashed suffix |
| Pre-auth | "Welcome to Dell" heading | `//*[@LocalizedControlType="heading" and @Name="Welcome to Dell"]` | |
| Pre-auth | "Sign in or create an account" heading | `//*[@LocalizedControlType="heading" and @Name="Sign in or create an account"]` | |
| App shell (WPF, either screen) | Window itself | `//Window[@AutomationId="DellDataAssistantTargetPc"]` | Stable `AutomationId`; shell chrome also has `TitleBarIcon`/`TitleBarText`/`MinimizeButton`/`MaximizeRestoreButton`/`CloseButton` |
| Post-auth ("Hi, {name}. Welcome to Dell.") | Heading | `//*[@LocalizedControlType="heading" and @Name="Hi, Test. Welcome to Dell."]` | Name is dynamic per account (`{name}` substituted) — match a prefix/contains pattern in real code, not an exact string |
| Post-auth | "Sign Out" link | `//HyperLink[@Name="Sign Out"]` | `LocalizedControlType="link"`, `FrameworkId="Chrome"` (confirms genuinely WebView2-rendered, vs. the WPF shell) — good reliable "signed in" indicator |
| GlassFloor-entitled welcome ("Let's make this Dell yours") | Heading | `//*[@LocalizedControlType="heading" and @Name="Let's make this Dell yours"]` | See §5.3a |
| GlassFloor-entitled welcome | "Remind me later." | `//Button[@Name="Remind me later."]` | `LocalizedControlType="button"` here, not a link — don't assume control type from visual style |

**Not yet located**: the "Sign in to MyDell to continue" modal's own elements (Retry/Cancel/Waiting
status), and whatever screen/action follows the post-auth landing page toward the pairing-code
step — no Next/Continue/Pair/Get Started element exists on that screen as currently observed.

### 5.3 End-to-end sign-in validated live

Using the confirmed launch-then-attach pattern and the `//Button[@Name="Continue"]` locator, a
scripted click was executed against a freshly-launched instance:
- Click succeeded (HTTP 200), and the app's "Sign in to MyDell to continue" modal appeared exactly
  as expected, confirmed via screenshot.
- The external default browser (Chrome) opened/navigated to "Sign In | Dell US", confirming the
  OS-browser hand-off fires correctly on click.
- A human then completed sign-in manually using test credentials (dedicated test account) and a
  **static OTP value (`123456`)** — confirmed this OTP is fixed, not a real rotating code sent to
  an inbox, for this specific test account.
- Post-auth, the app showed "Hi, Test. Welcome to Dell." with a "Sign Out" link, confirmed via a
  fresh UIA tree pull on the same (still-live) WinAppDriver session/window.

This validates the full launch → attach → find element → click → screenshot/evidence loop
end-to-end on real UI, not just synthetic XPath queries against a static tree dump.

### 5.3a GlassFloor entitlement mock-server launch — confirmed working against the Release build

A separate handoff package (`SV_HANDOFF.md` + `GlassFloor-TestPackage`) documents testing the
SupportAssist/GlassFloor entitlement flow via a local Node.js mock WSS server plus CLI args to the
app. It assumes a Debug build of `TargetPc.UI` (compiled from `Cdm.sln`), which doesn't exist on
this machine — only the Release build is available. **Confirmed the Release build also supports
this launch mode**: `DellDataAssistant.TargetPc.exe "<secret>" "<cert.pfx path>" "<host:port>"`,
with the mock server (`node server.js 8443 "my-secret-active"`) started first. Verified via the
mock server's own log (client connected → GlassFloor/Init handshake with matching secret →
`GlassFloor.Response` sent) and a distinct, entitlement-gated welcome screen
("Let's make this Dell yours" / "Ready to get started?") appearing — different from the plain
"Welcome to Dell" shown without these args.

**Critical gotcha**: the app enforces a single-instance lock. A new launch — even with different
CLI args — silently detects any already-running instance (visible *or* hidden), forwards focus to
it, and exits immediately without processing its own arguments at all. This produced one fully
misleading result (no mock-server connection logged, because the launch never actually ran).
**Any launch in the framework must first kill all matching processes** — not just the one with a
visible window; use a `CommandLine -like "*DellDataAssistant*"` process query, which also catches
WebView2 child processes, not just `Get-Process -Name` on the exe itself. This is implemented in
`factory/driver_factory.py`'s `_kill_existing_instances`.

`factory/mock_server.py` and `tools/launch_target_app.py --with-mock-server` implement this
recipe as reusable code: start the mock server, confirm it's listening, then launch the app with
`appArguments` built from the mock server's secret/cert path/address.

### 5.3b WebView2 renderer crash ~47s after launch -- resolves the "mystery exit code 15" (2026-10-05)

A large amount of debugging time this session went into an apparently random, intermittent crash
(exit code 15, later also 255, no catchable Python exception, no Windows crash/WER log) that
reproduced both in the sandboxed tool-execution environment *and* the user's own normal terminal —
which seemed to rule out environment-specific causes but left no clear culprit. **Root cause found
directly in the app's own log** (`%ProgramData%\DDA\TargetPc\logs\TargetPc\...`):

```
16:10:58  Showing React screen 'welcome' / Splash done, UI visible
16:11:45  FATAL: WebView2 process failed: Kind=RenderProcessExited, Reason=Crashed, ExitCode=15
16:12:56  FATAL: WebView2 process failed: Kind=BrowserProcessExited, Reason=Unexpected, ExitCode=15
```

The WebView2 renderer itself crashes with `ExitCode=15` roughly **47 seconds** after the UI
becomes visible, and the whole WebView2 browser process follows shortly after. This was never a
bug in the Python automation code — every earlier theory (pywin32/EnumWindows, psutil, subprocess
ordering, the Appium client, background-task handling) was chasing a downstream symptom of this
same underlying app-side crash. **A wider log search also found multiple earlier occurrences of
the same crash pattern (`ExitCode=-1` and `ExitCode=15`) at several different points across the
session** — confirming this is a recurring, ongoing app instability, not a one-off.

**Prime suspect**: `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--force-renderer-accessibility` — the
same flag confirmed required in §5.1 to expose the React UI to UI Automation at all. Forcing full
accessibility-tree construction is resource-intensive for Chromium and appears to destabilize this
WebView2 Runtime (`154.0.4258.53`, Windows 11 Pro ARM64) after a consistent-ish delay. Not yet
confirmed whether removing the flag fixes the crash (likely, but would also silently re-break
§5.1's fix — these two findings may need solving together) or whether a Runtime update helps.
**Also not yet confirmed**: whether restarting WinAppDriver itself periodically (rather than
letting one elevated instance run for hours across many launch/crash cycles) improves reliability
— one later test session showed a launch silently failing to even start the app at all after
WinAppDriver had been up for several hours handling many prior crashed sessions, though this
wasn't conclusively isolated before the project folder was reset.

**Practical implication**: treat the window from attach to roughly 40 seconds later as the
reliable interaction budget until this is further resolved. The driver factory (§4.2) already
reflects this (short launch-attempt timeout, fast polling interval).

### 5.3c Full authentication flow automated end-to-end via WinAppDriver alone (no Selenium)

Confirmed live (2026-10-05, `flows/target/authentication/sign_in_flow.py`): the entire Target PC
sign-in sequence can be driven purely through WinAppDriver, resolving open item 2 (sign-in-browser
attach strategy) for the Chrome case. Chrome's own UIA tree is directly queryable by attaching a
*second* WinAppDriver session to its top-level window — the identical `appTopLevelWindow`
mechanism already used for the app itself, found by process name the same way. No Selenium, no
`debuggerAddress`, no remote-debugging-port setup required at all.

Confirmed sequence: click sign-in → browser opens, app shows its wait modal → attach to browser →
email step (conditional — skipped if the browser profile already has a session, as it did in
testing) → password step (same, conditional) → email-OTP verification (six single-digit boxes,
confirmed locators in §5.2/tools notes) → back in the app, a **"Connect to a trusted network"**
dialog → confirmed reaching **"We're looking for your other PC"** (pairing-discovery screen —
`SignInFlow`'s confirmed end state; waiting for Source to actually appear there is pairing-flow
work, not yet built).

**Retries were needed in testing — root cause confirmed as session/OTP expiration between attempts
(not UI click flakiness)**: an initial write-up of this finding incorrectly attributed it to a
general WebView2/Chromium click-reliability problem; the user clarified the real cause was the
session/OTP expiring during the gap between attempts. That theory is retracted. `SignInFlow`
still retries each retry-worthy step with an explicit post-condition check (did the expected next
state appear?) since retrying remains the right defensive behavior for real transient failures —
just note the mechanism, and keep OTP-generation-to-submission latency short in real runs.

### 5.4 Also confirmed, not previously anticipated

- WinAppDriver's `app`-capability launch reliably starts the process once elevated, but reliably
  times out waiting for the window — not a flake, reproducible across multiple runs (see §4.2).
- A fresh window can appear in as little as ~2 seconds in some runs, well before the React content
  has finished rendering — element searches performed too early return empty results even though
  the screen is correct moments later. Confirms the necessity of explicit waits even once
  attached, not just for the attach step itself.

---

## 6. Phased delivery roadmap

- **Phase 0 — Runtime validation spike** — *Target PC: substantially complete* (§5), including a
  real, reusable CLI launcher (`tools/launch_target_app.py`). *Source PC: blocked on codebase/build
  access* — repeat the full static + runtime investigation once that build is available; do not
  assume parity with Target. Remaining Target-PC gaps: sign-in-browser attach strategy, locating
  the pairing-code modal and the path from post-auth landing to pairing, and the WebView2 renderer
  crash (§5.3b) root cause / mitigation.
- **Phase 1 — Framework skeleton**: `factory/*` is real and tested (driver factory, capabilities,
  wait_utils, prerequisites, mock server). Still stub-only: `components/base_component.py`,
  `config/settings.py`, `reports/*`, `tests/conftest.py`. Done when a smoke test using
  `BaseComponent` produces a populated `report.html` with a screenshot.
- **Phase 2 — Shared authentication flow — implemented and verified end-to-end.**
  `flows/target/authentication/sign_in_flow.py`'s `SignInFlow` automates the complete sequence:
  click sign-in -> attach to the external browser via WinAppDriver (no Selenium needed, see §5.3c)
  -> email/password steps (conditional, present only without an existing browser session) ->
  email-OTP two-step verification (confirmed live) -> "Connect to a trusted network" dialog ->
  confirmed reaching "We're looking for your other PC" (the pairing-discovery screen, this flow's
  confirmed end state). `components/base_component.py` is implemented (minimal: find-with-wait,
  click, type_text, get_text, exists; screenshots-on-action saved to `reports/output/screenshots/`,
  full `ActionReporter`/`report.html` wiring still pending). Remaining/unconfirmed: the
  email/password step locators are inferred from a reference screenshot only, not yet
  independently verified live (the test browser profile already had a session every time this was
  tested); `otp_client`/static-OTP config wiring (§4.5) is still manual (hardcoded in test scripts),
  not yet read from `config/settings.py` (which itself doesn't exist yet).
- **Phase 3 — Pairing + Coordination Service**: build `coordination_service/app.py` first, then
  pairing flows.
- **Phase 4 — Data selection + transfer**: first real exercise of scroll-into-view.
- **Phase 5 — Full end-to-end + polish**.

## 7. Prerequisites

| Item | Source PC | Target PC | Coordination host | Notes |
|---|---|---|---|---|
| Windows Developer Mode enabled | Required | Required (automated: `factory/prerequisites.py`) | — | WinAppDriver requires it |
| WinAppDriver installed, running locally, **elevated (as Administrator)** | Required — confirm independently | Required (automated) | — | Confirmed on Target: app requires admin elevation; non-elevated WinAppDriver can't build a useful UIA tree (UIPI) |
| Node.js (only for GlassFloor mock-server mode) | n/a | Required (automated: `ensure_mock_server_prerequisites()`) | — | Confirmed working against the Release build, §5.3a |
| Coordination Service deployed and reachable from both machines | reaches it | reaches it | Runs here | Not yet implemented |
| .NET Framework 4.8, WebView2 Runtime | Already required | Already required | — | Typically preinstalled on Win11; WebView2 Runtime confirmed `154.0.4258.53` |
| Dell Data Assistant Release build at a known path | Required | Required | — | No installer; path supplied via `--build-path` or interactive prompt |
| Python 3.11+, `selenium`, `requests` | Required | Required (automated) | — | Appium-Python-Client deliberately NOT used for Target's driver (§4.2) |
| OS default browser identified, `browser_type` set | Required | Required | — | Confirmed varies per machine (Chrome observed) |
| Static OTP value **or** dedicated OTP mailbox + OAuth app registration | Required | Required | — | Confirmed static for current test account (§4.5/§5.3) |
| Shared `run_id` convention agreed before each test cycle | via `--run-id` | via `--run-id` (same value) | correlation key | Not yet implemented (orchestration layer) |
| Credentials via environment variables only | Required | Required | — | Never committed, never CLI args |
| Source PC build obtained and statically investigated | **Blocked — pending codebase/build access** | n/a (done) | — | Confirmed different exe from Target's; don't assume parity |

## 8. Critical files

- `factory/driver_factory.py` — **implemented**. Idempotent session registry + launch-then-attach
  logic + `WinAppDriverSession`/`WinAppDriverElement`.
- `factory/prerequisites.py` — **implemented**. Prereq checks + auto-install for Target PC.
- `factory/mock_server.py` — **implemented**. GlassFloor mock-server manager.
- `tools/launch_target_app.py` — **implemented**. The real, tested CLI entry point.
- `components/base_component.py` — **implemented (minimal)**. find-with-wait, click, type_text,
  get_text, exists; screenshots-on-action saved locally. Full `ActionReporter`/`report.html`
  wiring and scroll-into-view still pending.
- `flows/target/authentication/sign_in_flow.py` — **implemented, verified end-to-end**. The full
  Target PC sign-in sequence including the WinAppDriver-attached browser automation (§5.3c).
- `coordination_service/app.py` — **not yet implemented**. The shared relay for cross-machine
  hand-offs.
- `tools/phase0_inspection_notes.md` — real locators + risk-item decisions gate further locator work.

## 9. Verification strategy

- **Phase 0**: throwaway/real scripts against a locally-started, elevated WinAppDriver; cross-check
  with Inspect.exe/Accessibility Insights/FlaUInspect. *(Target PC: done — §5.)*
- **Phase 1**: run the smoke test described above; confirm populated `report.html` + driver-factory
  idempotency (calling `get_app_driver` twice returns the same session while the window still
  exists).
- **Phase 2 onward**: as originally planned (see git history / earlier plan revisions for the full
  per-phase breakdown) — unchanged in substance, just not yet executed.

## 10. Open items (tracked)

1. Source PC build identity/architecture — blocked on codebase access.
2. Sign-in-browser attach strategy (Selenium `debuggerAddress` vs. native Win32) — not yet tested.
3. What screen/action follows the post-auth landing page toward pairing — not yet located.
4. Coordination Service address stability mechanism — not yet chosen (mDNS / DHCP reservation /
   separate static host).
5. Whether the pairing code needs redacting in reports (currently assumed non-sensitive/short-lived).
6. OTP email format and IdP rate-limiting — moot for the current static-OTP test account, but
   needed if/when a real rotating-OTP environment is targeted.
7. Relationship between the GlassFloor entitlement check (§5.3a) and the normal sign-in flow
   (§5.3) is unconfirmed — e.g. whether entitlement is always checked, or only when launched with
   the mock-server CLI args; and whether the "Let's make this Dell yours" vs. plain "Welcome to
   Dell" screen choice depends on entitlement state, launch args, or persisted local state.
8. No Debug build of `TargetPc.UI` (from `Cdm.sln`) exists on this machine yet — the GlassFloor
   handoff package assumes one. Everything confirmed in §5.3a was validated against the Release
   build instead, by choice, since the Debug build isn't available.
9. WebView2 renderer crash (§5.3b) root cause narrowed to `--force-renderer-accessibility` as
   prime suspect but not proven; whether removing it fixes the crash without re-breaking the
   UIA-tree-visibility fix from §5.1 is unresolved. Consider: filing this as a product bug report
   (ARM64-specific WebView2 instability under forced accessibility), checking for a WebView2
   Runtime update, or finding an alternative way to force accessibility that doesn't destabilize
   the renderer.
10. Whether a long-running elevated WinAppDriver instance degrades after handling many
    launch/crash cycles (possible, observed once, not conclusively isolated) — consider having
    `ensure_winappdriver_running` restart WinAppDriver periodically or on detected failure, rather
    than treating "port is open" as sufficient health evidence.
11. **Hard, confirmed constraint (not fixable in automation)**: after OTP verification succeeds,
    Windows shows a manual UAC elevation prompt a human must approve before the flow can continue
    — UAC runs on the secure desktop, invisible to any UI Automation tool by OS design.
    `SignInFlow` now waits with real patience (5 min default) and prints an explicit notice, but
    fully unattended (no human present) runs will hang here. Worth raising with the app's owners:
    can this mid-flow elevation be avoided (e.g. the whole app running elevated from launch, so no
    second UAC is needed)?

# Phase 0 Inspection Notes — Target PC build

Covers `C:\Users\revan\Downloads\027df3321\Release\DellDataAssistant.TargetPc.exe` only
(Risk items 1-2 and everything through "Prerequisites update" below). Source PC build
became available 2026-10-06 and its own Phase 0 findings are summarized in the final
section of this file, with pointers to where the full detail actually lives (co-located
with the code it explains, not duplicated here).

## Risk item 1: WebView2 UIA accessibility tree — RESOLVED, with two required conditions

Confirmed empirically (2026-10-05) that the WebView2-rendered React content is **not** exposed
in the UI Automation tree by default. Attaching WinAppDriver to a normally-launched instance
produced a tree with a single node (the bare outer `<Window>`, 754 chars, zero children).

The React content **does** appear once both of the following are true:

1. **WinAppDriver itself must run elevated (as Administrator).**
   `DellDataAssistant.TargetPc.exe` requires administrator elevation — confirmed directly: a
   plain `CreateProcess` launch (via .NET `Process.Start` with `UseShellExecute=false`) fails
   immediately with `ERROR_ELEVATION_REQUIRED` ("The requested operation requires elevation").
   This is consistent with the app's own confirmed `AutomaticallyAddFirewallRule=true` config
   setting, which needs admin rights to modify the Windows Firewall. When WinAppDriver runs at
   a lower integrity level than the target app, UIPI (User Interface Privilege Isolation)
   silently blocks it from ever building/reading a useful UIA tree for that app — this, not the
   WebView2 flag below, was the actual root cause of the single-node tree.
   **Action for the framework**: `DriverFactory` must document (and the Prerequisites table
   must state) that WinAppDriver has to be started elevated on both Source and Target PCs
   whenever the target app itself requires elevation. Confirm whether the Source PC build also
   requires elevation once that build is available — do not assume it does.

2. **`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--force-renderer-accessibility` must be set in
   WinAppDriver's own process environment before it launches the app**, so the launched app (and
   its WebView2 child/renderer processes) inherit it. Without this, even an elevated WinAppDriver
   attaching to the app still produced a childless tree in one test — the two conditions are
   independent and both required.

With both conditions met, `driver.page_source` grew from 754 chars (bare window) to ~12,575
chars including real WPF chrome (title bar, min/max/close buttons) **and** the full React
content of the "Welcome to Dell" screen.

## Risk item 2: sign-in-browser attach strategy — NOT YET TESTED

Not reached this session — focus was on risk item 1 and the GlassFloor/launch-stability work.
Still open per the plan: whether Selenium can attach to the OS-default browser via
`debuggerAddress`/`--remote-debugging-port`, or whether the native-Win32-automation-via-WinAppDriver
fallback is needed. Confirmed separately that the default browser is machine-dependent (Chrome
observed on one machine) — framework must stay configurable per the plan's `browser_type` design
either way.

## WinAppDriver launch behavior — confirmed pattern, must be designed around

WinAppDriver's `app`-capability launch **reliably starts the process** once elevated, but
**reliably times out waiting for its main window** (~20–25s internal timeout) before the app
finishes rendering (~25–30s, likely WebView2 environment init). This was 100% reproducible
across multiple runs — not a flake. The initial `POST /session` call with `app` set should be
expected to return an error (`"Failed to locate opened application window"`) or time out
client-side even on a fully successful launch.

**Implemented pattern** (`factory/driver_factory.py`'s `_launch_then_attach`): launch-then-attach,
not a single launch call:
1. POST `/session` with `desiredCapabilities: {app: <path>, appArguments: "<optional>", platformName: "Windows", deviceName: "WindowsPC"}` (legacy `desiredCapabilities` key, not W3C `capabilities.alwaysMatch`/`firstMatch` — see capability-format note below). Treat a timeout/error response as expected, not fatal. Uses a short (~5s) client timeout since we don't need to stay connected for WinAppDriver's own internal wait.
2. Poll (via `poll_until`) for a process matching the app's exe name to appear, then read its `MainWindowHandle` (via a PowerShell subprocess call -- see gotcha below).
3. Convert the handle to hex and POST a **second** `/session` call with `desiredCapabilities: {appTopLevelWindow: "<hex>", platformName: "Windows", deviceName: "WindowsPC"}` to get a working session attached to the already-running window.
4. Use the session from step 3 for all further automation; discard/ignore the step-1 attempt.

## Capability format note (client-library gotcha, not app-specific)

The modern Appium Python client (v6, `Appium-Python-Client==6.0.7`) auto-prefixes
non-standard capability names with `appium:` (e.g. `app` → `appium:app`) to comply with the W3C
WebDriver spec. **WinAppDriver 1.2.1 (confirmed installed version) does not recognize the
prefixed form** and returns `"Bad capabilities. Specify either app or appTopLevelWindow"` for
both W3C `alwaysMatch` and `firstMatch` shapes. Only the legacy `{"desiredCapabilities": {...}}`
body with bare, unprefixed keys was accepted. **Implemented**: `factory/capabilities.py` builds
raw capability dicts and sends them via the legacy `desiredCapabilities` shape directly via
`requests`, bypassing the Appium client's `set_capability`/`load_capabilities` auto-prefixing
entirely (see also "Why the Appium client and pywin32 were dropped" below).

`appArguments` (used for the GlassFloor mock-server launch) is a single command-line **string**,
not a JSON array -- `app_launch_capabilities()` quotes each argument and joins with spaces.

## Why the Appium Python client and in-process psutil/pywin32 were dropped

Initial implementation used the Appium Python client's `WebDriver` class (subclassed, with
`start_session` overridden to do the launch-then-attach dance) plus `psutil`/`win32gui`/
`win32process` in-process for killing stale processes and finding the window handle. **Both
approaches intermittently crashed the Python interpreter outright**: exit code 15 (later also
seen as 255), no catchable Python exception, no Windows crash/WER log entry at all, and -- most
confusingly -- not reliably reproducible from one run to the next (the exact same code would
succeed, then fail, then succeed again).

Extensive isolation testing (dozens of runs) ruled out, one at a time: `win32gui.EnumWindows`'s
callback specifically (switched to `FindWindow`, still crashed), `psutil.process_iter` alone (fine
in isolation), a `subprocess.run` call earlier in the process (fine in isolation, switched
`check_developer_mode()` to `winreg` anyway), the combination of socket + psutil + win32gui
together (fine when manually replicated), import order, and background-vs-foreground task
execution. The crash only reproduced when calling the *actual* launch-then-attach sequence for
real (i.e. actually spawning/attaching to the app), not when any piece was tested in isolation or
manually replicated -- and even then, intermittently.

**Resolution reached late in the investigation (see "WebView2 renderer crash" below): most of
this was never a Python-level bug at all.** The app's own WebView2 renderer crashes with
`ExitCode=15` on its own, independent of our code, and that crash was what kept surfacing as an
unexplainable process death. The decision to drop the Appium client and in-process pywin32/psutil
in favor of PowerShell-subprocess-based process/window inspection and a minimal custom
`WinAppDriverSession` (directly over `requests`) was made *before* that root cause was found, as a
reliability improvement in its own right -- and was kept afterward since the PowerShell-based
approach remains simpler and has been 100% reliable regardless of the renderer-crash finding.

## WebView2 renderer crash ~47s after launch when `--force-renderer-accessibility` is set

**This resolves the "mystery exit code 15 crash" that consumed a large amount of
debugging time on 2026-10-05.** It was never a bug in the Python automation code. Root
cause confirmed directly from the app's own log
(`%ProgramData%\DDA\TargetPc\logs\TargetPc\DellDataAssistant-<date>.log`):

```
16:10:57,808  AppShellHost: WebView2 shell initialized, navigating to https://targetpc-ui.example/index.html
16:10:58,384  ReactScreenPresenter: Showing React screen 'welcome'.
16:10:58,686  MainWindow: Splash done: collapsing SplashOverlay.                    <- UI fully visible
16:11:45,339  FATAL AppShellHost: WebView2 process failed: Kind=RenderProcessExited, Reason=Crashed, ExitCode=15
16:11:45,358  WARN  AppCloseCoordinator: Renderer unavailable -- later close requests will skip the prompts.
16:12:56,920  FATAL AppShellHost: WebView2 process failed: Kind=BrowserProcessExited, Reason=Unexpected, ExitCode=15
```

The WebView2 renderer crashes (`ExitCode=15`) roughly **47 seconds** after the UI becomes
visible, and the whole WebView2 browser process follows shortly after. This single exit
code then surfaces as the app process / attached automation session appearing to die for
no catchable reason -- exactly what was observed as an "intermittent, unexplainable crash"
across many earlier test runs (in both the sandboxed tool-execution environment and the
user's own normal terminal -- ruling out execution-environment theories entirely, which
in hindsight were a red herring).

**A wider log search found this is not a one-off**: multiple occurrences of
`Kind=BrowserProcessExited`/`Kind=RenderProcessExited`/`Kind=UtilityProcessExited` with
`ExitCode=-1` or `ExitCode=15` appear at several different timestamps across the session's
testing, each following a successful launch -- confirming this is a recurring app-level
instability, not a one-time fluke.

**Prime suspect**: `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--force-renderer-accessibility`
-- the flag confirmed required in Risk item 1 above to expose the React UI to UI Automation at
all. Forcing full Chromium accessibility-tree construction is known to be resource-intensive,
and this looks like it destabilizes the renderer on this machine (WebView2 Runtime
`154.0.4258.53`, Windows 11 Pro ARM64) after a consistent-ish delay. **Not yet confirmed**
whether removing the flag eliminates the crash (expected, given the tree would also go back to
being empty per Risk item 1 -- these two problems may have to be solved together, not
independently) or whether a WebView2 Runtime update avoids it.

**Practical implication for the framework**: `BaseComponent`/flows should assume roughly a
**40-second budget** after the window becomes visible/attached before the renderer may
become unusable, until this is root-caused further or a workaround/Runtime update is
found. Minimize elapsed time between attach and the first real interaction. The driver
factory's short launch-timeout (~5s) and fast poll interval (0.5s) already reflect this.

**Also unconfirmed, flagged for follow-up**: whether a WinAppDriver instance left running
elevated for a long time (hours, across many launch/crash cycles) degrades and starts failing to
launch the app at all -- observed once (a launch attempt produced zero trace in the app's own log,
meaning it never even reached `App_Startup()`), but not conclusively isolated before the project
folder was reset and this investigation paused. Worth testing deliberately: restart WinAppDriver
fresh before each test run vs. reusing a long-lived instance, and compare failure rates.

## GlassFloor entitlement mock-server launch — confirmed working against the Release build

A separate handoff package (`SV_HANDOFF.md` + `GlassFloor-TestPackage`, not part of the original
static investigation) documents a mock-server-driven launch mode for testing the SupportAssist/
GlassFloor entitlement flow. It assumes a Debug build of `TargetPc.UI` compiled from `Cdm.sln`,
which does not exist on this machine — **only the original Release build is available**.
Confirmed empirically (2026-10-05) that **the Release build also supports this launch mode**:

1. Start the mock server: `node server.js 8443 "my-secret-active"` from
   `GlassFloor-TestPackage\SupportAssistRaceHarness\` (requires Node.js 18+ — confirmed already
   present on this machine, v24.19.0, just needed a PATH refresh after `winget install`).
2. Launch the app with three positional CLI args: `<secret> <cert.pfx path> <server-host:port>`,
   e.g.:
   ```
   DellDataAssistant.TargetPc.exe "my-secret-active" "<path>\cert.pfx" "127.0.0.1:8443"
   ```
3. Confirmed via the mock server's own log: `client connected` → received a `GlassFloor`/`Init`
   message with matching `SessionSignature` → server replied with a `GlassFloor.Response`
   (`N6 SLA, 2026-10-05 to 2026-11-04`), and the app navigated to a **different, entitlement-gated
   welcome screen** — see locators below. This is not the same screen shown when launching without
   these args (plain "Welcome to Dell").

**Implemented**: `factory/mock_server.py`'s `start_mock_server()` and
`tools/launch_target_app.py --with-mock-server` automate this whole recipe, including the
single-instance-lock cleanup below.

### Critical gotcha: single-instance lock silently swallows the launch args

`DellDataAssistant.TargetPc.exe` enforces a single-instance lock (confirmed via its own log at
`%ProgramData%\DDA\TargetPc\logs\TargetPc\DellDataAssistant-<date>.log`). If any instance (visible
or hidden) is already running, a new launch — **even with different CLI args** — detects the
conflict, forwards focus to the existing instance, logs
`"A conflicting instance is running (this app or the old-PC UI). Shutting down."`, and exits
immediately **without ever processing its own arguments**. This produced a confusing false
result once: launching with the GlassFloor args appeared to do nothing (no mock-server
connection logged) because a leftover instance from earlier testing silently absorbed the launch.

**Implemented**: `factory/driver_factory.py`'s `_kill_existing_instances` runs before every
launch, using `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*DellDataAssistant*' }`
(catches WebView2 child processes too, not just the main exe by name).

### Confirmed real locators — GlassFloor-entitled "Let's make this Dell yours" welcome screen

Same CSS-module-hash caveat as before applies — prefer Name-based XPath.

| Element | Reliable locator | Notes |
|---|---|---|
| "Let's make this Dell yours" heading | `//*[@LocalizedControlType="heading" and @Name="Let's make this Dell yours"]` | Distinct screen from the non-entitled "Welcome to Dell" |
| "Ready to get started?" heading | `//*[@LocalizedControlType="heading" and @Name="Ready to get started?"]` | |
| Sign-in trigger button | `//Button[@Name="Continue"]` | **Same locator as the non-entitled screen** — consistent across both variants, good sign for a shared `components/shared/sign_in_screen.py` |
| "Remind me later." | `//Button[@Name="Remind me later."]` | Note: `LocalizedControlType="button"`, not a link here (unlike "Sign Out" elsewhere, which was a `HyperLink`) — don't assume control type from visual style |

## Resolution of the launch-attach crash, and the real culprit (2026-10-05, after project reset)

After the project folder was deleted and rebuilt from scratch, the same intermittent
launch/attach failure (exit 255, sometimes 15) reappeared even in the simplified
PowerShell-subprocess-based implementation, disproving the theory that switching away
from pywin32/psutil alone would fix it. Systematic re-testing found **two real,
independent bugs**, both now fixed:

1. **`LAUNCH_ATTEMPT_TIMEOUT` was wrongly shortened to 5 seconds** on the assumption that
   WinAppDriver continues the server-side launch after the client disconnects. Testing
   showed this assumption was false in practice: with a short client timeout, the launch
   never reached the app's own log at all (zero new `App_Startup()` entries), while an
   unhurried request (full ~35s) reliably got a real HTTP 500 response from WinAppDriver
   itself (`"Failed to locate opened application window..."`) after the app had
   genuinely started. **Fixed: restored to 35s.** The client must stay connected for
   approximately WinAppDriver's own internal window-detection window.

2. **Running test code as an inline `python -c "..."` one-liner is unreliable in this
   environment; running the identical logic as a real `.py` file is not.** This was the
   single biggest source of apparent "random" crashes during both the original and the
   post-reset investigation -- the exact same `_launch_then_attach` logic that
   consistently failed (sometimes with zero output, sometimes mid-way through) when
   invoked via `-c` succeeded cleanly and repeatably once moved into an actual script
   file invoked as `python path\to\script.py`. Root cause not fully isolated (plausibly
   related to how a long, complex inline command string is quoted/passed through nested
   shell invocations), but the practical rule going forward is simple and absolute:
   **never test or run this framework's code via `python -c`; always use a real .py
   file**, including `tools/launch_target_app.py` itself and any future test/debug
   scripts.

With both fixes applied, the full `DriverFactory.get_app_driver()` path (prerequisites ->
kill existing -> launch -> poll -> attach -> `page_source`) completed cleanly and
repeatably: kill (~2s) -> launch POST returns real HTTP 500 after ~10-20s (not a client
timeout) -> window found within ~1.5s of that -> attach succeeds (200) -> `page_source`
length ~12,500+ chars, matching the confirmed-good tree size from Risk item 1.

### Other confirmed operational findings from this round

- **Killing an elevated WinAppDriver.exe from a non-elevated context silently does
  nothing** -- `Stop-Process -Force` against it returns without error but the process
  (same PID, same start time) is still alive afterward. Unlike the target app process
  (also elevated), which non-elevated `Stop-Process -Force` has reliably killed all
  session. To actually kill an elevated WinAppDriver, the kill command itself must also
  run elevated (`Start-Process powershell -Verb RunAs -ArgumentList 'Stop-Process ...'`).
- **A WinAppDriver instance left running for hours across many launch/crash cycles can
  become unable to launch the app at all** (confirmed once: a launch attempt produced
  zero trace in the app's own log, not even a timeout-with-real-response -- genuinely
  nothing happened). Restarting WinAppDriver fully resolved it. Framework implication:
  consider periodic WinAppDriver restarts for long test sessions, not just "is the port
  open" as the health check.
- **Simplified the elevated WinAppDriver startup mechanism.** The original stdin-keep-open
  `.ps1` script (needed because WinAppDriver's "Press ENTER to exit" prompt gets immediate
  EOF under a null-stdin harness) turned out to be unnecessary in practice: a plain
  `Start-Process -FilePath <path> -Verb RunAs` keeps WinAppDriver alive fine. The WebView2
  accessibility flag is now supplied via a **persisted `User`-scope environment variable**
  (`[System.Environment]::SetEnvironmentVariable(...,"User")`, written once via
  `ensure_webview2_accessibility_env_var()`) rather than the launching process's own
  environment -- necessary because an elevated ("runas") process does not inherit the
  calling process's in-memory environment, but does read persisted env vars fresh from
  the registry at creation time regardless of elevation. The old `.ps1` launcher script
  was deleted.
- **WinAppDriver's `/screenshot` endpoint captures the full foreground desktop, not
  specifically the attached window's content.** A screenshot taken while another window
  (e.g. an editor) has focus will show that window, even though the session is correctly
  attached to the app (confirmed separately via `GetWindowThreadProcessId` matching the
  expected PID). Bring the target window to the foreground
  (`ShowWindow`/`SetForegroundWindow` via a small P/Invoke helper, or clicking it) before
  relying on a screenshot for visual verification; don't mistake this for a mis-attached
  session.

## Full authentication flow automated end-to-end (2026-10-05, `flows/target/authentication/sign_in_flow.py`)

Confirmed via live testing (and a user-supplied reference screenshot walkthrough covering
the complete sequence) that the whole Target PC sign-in flow can be automated purely
through WinAppDriver -- **no Selenium, no CDP/remote-debugging-port setup needed at all**.
Chrome's own UIA/accessibility tree is directly queryable by attaching a second
WinAppDriver session to its top-level window, exactly the same `appTopLevelWindow`
mechanism already used for the app. This resolves Risk item 2 (previously "not yet
tested") for the Chrome case specifically.

**Confirmed sequence** (see `SignInFlow.run()`):
1. Click the app's sign-in button (`//Button[@Name="Continue"]`, same locator confirmed
   earlier) -> external browser opens, app shows its "Sign in to MyDell to continue" modal.
2. Attach a `BrowserSession` to the browser's window (found by process name, same
   `_find_main_window_hwnd`-style PowerShell query as the app uses).
3. **Email step** (`Edit[@Name="Email or Mobile Number"]` + a "Continue" button) --
   **conditionally present**: skipped entirely if the browser profile already has a Dell
   session (as it did during this test, since the same Chrome profile had been used
   earlier in the day). Locators here are inferred from the user's reference screenshots
   only, not yet independently confirmed live -- flagged in code comments.
4. **Password step** (`Edit[@Name="Password"]` + "Sign In" button) -- same conditional/
   unconfirmed status as the email step.
5. **Two-step email-OTP verification** -- confirmed live. Six separate single-digit boxes,
   `//*[@Name="Verify Passcode One"]` through `"...Six"` (`AutomationId="otpBoxmfaOtpBox1"`
   through `6`, `ClassName="otpBox phone-otp-verify-otpbox"`), plus a
   `//*[@Name="Verify"]` button. The static OTP (`123456`, see earlier finding) is typed in
   digit-by-digit.
6. Back in the app: a **"Connect to a trusted network"** dialog appears (confirms this is
   a distinct step from the sign-in modal) -- confirmed button locator
   `//*[@Name="Trust Network"]`.
7. App proceeds to **"We're looking for your other PC"** -- confirmed heading locator
   `//*[@Name="We're looking for your other PC"]`. This is `SignInFlow`'s confirmed
   end-state: reaching it means sign-in succeeded and the app is now in pairing-discovery
   mode. Actually waiting for/detecting the Source PC's arrival here is pairing-flow work
   (not yet built), not part of sign-in.

**Retries were needed in testing, but the root cause was session/OTP expiration, not UI
click flakiness** (correction: an earlier pass at this write-up attributed it to a general
WebView2/Chromium click-flakiness pattern -- the user clarified the actual cause was that
the session/OTP had expired between attempts, likely from the delay while other things
were being debugged in between). The retry *behavior* observed (first attempt failed,
second succeeded) is real, but don't read it as evidence of an unreliable click mechanism
across both WPF/WebView2 and Chromium -- that theory is now retracted. **`SignInFlow`
still builds in bounded retries with explicit post-condition checks** at each retry-worthy
step (did the browser appear? did the OTP page go away?) since retrying is still the
right defensive behavior for a real-world transient failure like OTP/session expiry --
just note the mechanism is different from what was first assumed. A practical implication:
keep the gap between OTP generation and submission short in real runs, and consider
re-fetching/re-triggering a fresh OTP on retry rather than resubmitting the same one if a
live (non-static) OTP source is ever used.

**Design decision carried into `components/base_component.py`**: `BaseComponent.exists()`
was added (distinct from the find-or-raise `_find()`) specifically so flow code can probe
"is this screen/step present right now" without treating absence as a failure -- needed for
the conditional email/password steps above, and generally useful for any adaptive,
screen-state-dependent flow logic going forward.

## Hard constraint, not a bug: a manual UAC prompt appears after OTP success, and automation cannot see or interact with it

Confirmed by the user directly: after OTP verification succeeds, Windows shows a User
Access Control (UAC) elevation prompt that **must be manually approved by a human** before
the flow continues to "Starting the migration assistant" / the trust-network dialog. This
is almost certainly the migration engine (`DellDataManager.exe`) requesting its own
elevation for a specific action at this point (plausibly related to the confirmed
`AutomaticallyAddFirewallRule=true` config, or a network-trust operation) -- distinct from
the app's own up-front elevation requirement (Sec 5.1), which is already satisfied by the
time this point in the flow is reached.

**This is not something to work around -- it categorically cannot be automated.** UAC
prompts render on Windows' secure desktop, which is deliberately isolated from the normal
desktop's UI Automation tree by design (a core OS security boundary, not an
app-specific or WinAppDriver-specific limitation). No UIA-based tool -- WinAppDriver,
Selenium-attached-via-CDP, Playwright, anything -- can see or click a secure-desktop UAC
dialog. The only way past it is a human clicking "Yes," or disabling UAC entirely at the
OS level (not recommended, and not something this project should do unilaterally).

**Framework implication**: `SignInFlow.run()`'s `overall_timeout` default was raised
substantially (90s -> 300s) specifically to give a human realistic time to notice and
approve this prompt, and the flow now prints an explicit console message right before
this wait begins, so whoever's running it knows to go check. Any future fully-unattended
run (no human present) will hang here indefinitely until someone resolves it -- that's
an inherent limitation of this app's design, not something the automation framework can
paper over. Worth raising with whoever owns the app: is this UAC prompt avoidable (e.g.
by having the whole app run elevated from launch, so no secondary elevation is needed
mid-flow), since it currently makes fully-unattended Target PC automation impossible past
this point.

## Confirmed real bug: send_keys only stuck the last character on a React-controlled input

During a full fresh-launch test of `SignInFlow`, the user observed the email field ended up
containing just `"m"` (the last character of `sospigorda@necub.com`) instead of the full
address. Root cause: `WinAppDriverElement.send_keys()` sent the entire string in one
`/value` call (`{"value": list(text)}`). Against a React-controlled input, the
component's re-render can't keep up with a whole batch of characters arriving at once --
only the final character lands in the component's actual state before the DOM settles.

**Fixed** in `factory/driver_factory.py`'s `WinAppDriverElement.send_keys()`: click to
focus, clear any existing content, then send **one character per request with a small
delay** (0.05s) between each, so every keystroke is a discrete event the component
actually processes. Slower, but reliable. This fix is shared by both the app-side and the
browser-side element wrapper (`BrowserSession` in `sign_in_flow.py` reuses the same
`WinAppDriverElement` class), so it applies everywhere `type_text`/`send_keys` is used,
not just the email field where it was first noticed.

**Re-verified**: a subsequent full-flow run with this fix in place got all the way through
email, password, OTP entry, and the trust-network dialog successfully (only the final
pairing-discovery screen check failed on that run -- a separate, not-yet-isolated issue,
not a typing problem).

**Investigated and ruled out: a Selenium/Playwright-style single-call `send_keys`.**
WinAppDriver 1.2.1 does not support the W3C Actions API's `"key"` input source type --
confirmed directly: `POST /session/{id}/actions` with a `type: "key"` action source
returns `{"status":104,"value":{"error":"unsupported operation","message":"Currently key
input source type is not supported"}}`. There is no protocol-level way to replicate
Selenium/Playwright's bulk text-entry semantics against this driver. The
character-by-character `/value` loop in `WinAppDriverElement.send_keys()` is therefore
the correct and only reliable mechanism available here, not a workaround to eventually
replace -- don't re-attempt the Actions API route without new information (e.g. a newer
WinAppDriver version that adds support).

## Prerequisites update required in the main plan (DONE)

`factory/prerequisites.py` now automates: WinAppDriver elevated-launch requirement, Developer
Mode, WinAppDriver install, Python packages, and (separately) Node.js for the mock-server mode.
See PROJECT_PLAN.md Sec 4.9 and Sec 7 for the current state.

## Source PC build — Phase 0 findings (2026-10-06)

Covers the downloaded installer `Dell Data Assistant (2).exe`. Full detail lives
co-located with the code each finding produced, not duplicated here -- this section is
an index, not the source of truth.

- **It's a self-extracting installer, not the app itself.** Running it installs to (and
  launches) `C:\Dell\DellDataAssistant\DellDataAssistant.exe`, process name
  `DellDataAssistant`. Point `DDA_SOURCE_BUILD_PATH` at the installed exe, not the
  original downloaded installer, so repeated runs don't re-trigger installation/UAC. See
  `factory/config.py`'s `SOURCE_EXE_NAME`/`SOURCE_PROCESS_NAME`.
- **WebView2 UIA tree was rich immediately**, no elevation dance needed in the one
  session tested -- but that test reused an already-elevated WinAppDriver instance from
  a prior Target run, so this is NOT an independently confirmed "Source never needs
  elevation" result. Re-verify from a cold WinAppDriver state before relying on it.
- **Confirmed screen sequence**: Welcome ("Welcome to Dell Migrate.") -> "Let's get
  started" -> trust-network dialog (conditional, confirmed only from a user screenshot,
  not yet seen live) -> "We're searching for your new PC." (does NOT advance on a fixed
  timeout -- confirmed by waiting 15s+ with no change; only advances once a real Target
  becomes network-discoverable) -> "Let's finish linking your PCs." (pairing-code
  screen). See `components/source/*.py` and `locators/source/*.py` for real locators.
- **Real app bug, the core Source-side finding**: the pairing code's 6-box ListView only
  ever exposes some of its 6 digit elements to UI Automation at a time (confirmed: as few
  as 3 of 6; the whole element subtree, container included, is genuinely absent, not
  just unreadable). The app's own logs redact the code value, so log-scraping can't
  help. Full writeup, the OCR-based workaround (and why an isolated single-digit OCR
  crop fails but a neighbor-aware crop succeeds), and self-verification approach are in
  `components/source/pairing_code_screen.py`'s module docstring.
- **The code rotates roughly every 60-63s**, confirmed via the app's own log timestamps.
- **The WebView2 renderer crash already documented above for Target also affects
  Source** -- observed directly, not just inferred from shared architecture.
- **Running Source and Target on the SAME physical machine hits a real conflict**: both
  depend on a shared `DellDataManager` backend process that only one instance of can run
  at a time (the app itself shows "We need to close an application -- Currently running:
  DellDataManager"). This is a genuine environmental constraint, not an automation bug --
  confirmed working correctly across two separate physical machines instead (see
  `coordination_service/README.md`).
- **Coordination Service**: `factory/coordination_client.py` + `coordination_service/app.py`
  relay the pairing code between the two independent Source/Target processes over plain
  HTTP. Verified end-to-end across two real, separate Windows machines, address resolved
  via plain Windows hostname (NetBIOS/LLMNR), no DNS server or static IP needed.

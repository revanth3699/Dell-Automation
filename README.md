# Dell Data Assistant Automation Framework

See PROJECT_PLAN.md for the full design, architecture, phased roadmap, and Phase 0 findings.
See tools/phase0_inspection_notes.md for raw inspection notes and confirmed locators.

Status: sign-in, pairing (via the Coordination Service), and transfer are implemented
and have run live for both Target and Source PCs; per-run HTML reporting is wired into
every real entry point. Data/category selection and full unattended end-to-end polish
are still open. See `tracking/IMPLEMENTATION_STATUS.md` for the authoritative,
file-by-file current status.

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/) (not plain pip/venv).

1. Install uv, if you don't already have it: `pip install uv`
2. From the repo root, create the virtual environment and install everything
   (`pyproject.toml` + `uv.lock` pin exact versions, so this is reproducible):
   ```
   uv sync
   ```
3. Copy `.env.example` to `.env` and fill in the machine-specific paths
   (`DDA_TARGET_BUILD_PATH` / `DDA_SOURCE_BUILD_PATH`, and `DDA_COORDINATION_SERVICE_URL`
   once you know which machine hosts the Coordination Service). Credentials
   (`DDA_TARGET_SIGNIN_USERNAME` etc.) are real environment variables only -- never put
   them in `.env`. See **Environment variables** below for exactly what each machine
   needs.
4. Run anything through uv, e.g.:
   ```
   uv run python -m orchestration.role_runner --role target --run-id <id>
   uv run python -m orchestration.role_runner --role source --run-id <id>
   uv run python utils/run_coordination_service.py
   ```

**WinAppDriver, Windows Developer Mode, and required Python packages are all
auto-detected and auto-installed/enabled on first run** -- `utils/prerequisites.py`'s
`ensure_target_prerequisites()` runs at the start of every `role_runner` invocation and
installs WinAppDriver via `winget` if it's missing (one admin approval prompt), enables
Developer Mode if it's off (another admin prompt), and confirms WinAppDriver can launch
elevated as a one-time self-test (then closes it again) -- `factory/session.py` starts
the real instance independently, elevated, the moment automation actually needs it.
Nothing needs to be installed by hand beyond uv and this repo's own
dependencies.

## Project structure

```
dell-automation/
├── assertions/              Expected-text constants (NOT locators) -- the single
│   └── target/              source of truth for text a flow/locator needs to match,
│                            e.g. error-banner copy, transition-screen phrases polled
│                            from raw page source. No assertions/source/ yet.
│
├── components/              Page Objects -- one class per screen/dialog.
│   ├── base_component.py    The shared template every component builds on: find
│   │                        (explicit wait) -> act -> screenshot -> record, via
│   │                        utils.retry / utils.wait_utils / reports.action_reporter.
│   ├── shared/               Reserved for cross-role components; empty today (Source
│   │                        has no sign-in step, so nothing ended up here in practice).
│   ├── source/               Welcome/trust-network/searching/pairing-code/transfer
│   │                        screens for the Source PC.
│   └── target/                Welcome/sign-in/pairing/transfer/migration-summary
│                            screens and shared dialogs (ConfirmAccounts, CloseApps,
│                            TrustNetwork, SignInFailed, SignInWaiting) for Target PC.
│
├── coordination_service/    Standalone FastAPI relay (app.py: PUT/GET
│                            /runs/{run_id}/{key}) -- the only channel between the two
│                            independent per-machine automation processes. Run once,
│                            reachable by both machines (utils/run_coordination_service.py).
│
├── factory/                 Drivers, sessions, config -- nothing else.
│   ├── capabilities.py       WinAppDriver desired-capabilities builders.
│   ├── config.py             Centralized env-driven config (one source of truth for
│   │                        hosts/ports/exe names/paths); loads .env via python-dotenv.
│   ├── driver_factory.py     WinAppDriverSession/WinAppDriverElement (the raw REST
│   │                        client) AND the sole owner of the real WinAppDriver
│   │                        process's lifecycle: find/is-running/launch-elevated/kill.
│   ├── logger_factory.py     Idempotent loguru console + per-role rotating file sinks.
│   └── session.py            Session: owns one role's full lifecycle (app process +
│                            WinAppDriver attach + browser attach), idempotent reuse,
│                            unconditional all-or-nothing teardown via close().
│
├── flows/                    Business-logic chains built on Components, per role.
│   ├── source/                pairing_flow.py, transfer_flow.py,
│   │                        data_selection_flow.py (still a stub).
│   └── target/                 authentication/sign_in_flow.py, pairing_flow.py,
│                            transfer_flow.py.
│
├── locators/                 XPath/AutomationId constants only, one module per
│   ├── source/               screen/dialog, mirrored source/target. No business logic.
│   └── target/                A locator may import a shared string from assertions/
│                            (e.g. error_banner.py) rather than duplicate it.
│
├── orchestration/
│   └── role_runner.py         THE real entry point: `python -m orchestration.role_runner
│                            --role {target,source} --run-id <id>`. Chains prerequisites
│                            -> Session -> that role's flows -> report, for one machine.
│
├── reports/                   Per-run HTML reporting (no jsonl/meta sidecar files).
│   ├── report_models.py        ActionRecord / RunReport dataclasses.
│   ├── action_reporter.py      ActionReporter: process-global in-memory singleton;
│   │                        every BaseComponent action records here.
│   ├── html_report_builder.py  Renders one self-contained
│   │                        reports/output/<run_id>_<role>_<timestamp>.html (screenshots
│   │                        embedded as base64) + refreshes reports/output/index.html.
│   └── output/                 Generated reports land here (gitignored).
│
├── tests/
│   └── conftest.py            Pytest fixtures (Session + credentials) and the
│                            reporting hooks (pytest_configure/pytest_sessionfinish).
│                            No test_*.py files today -- superseded by
│                            orchestration/role_runner.py's own live run + reporting.
│
├── tools/                     Manual/dev scripts (launch_target_app.py,
│                            run_sign_in_flow.py, several _test_*.py one-off
│                            diagnostic scripts) -- NOT part of the real run path;
│                            useful for piecemeal debugging only.
│
├── tracking/
│   └── IMPLEMENTATION_STATUS.md   Authoritative, maintained "what's actually built vs.
│                                planned" doc -- check this, not this README, for
│                                current per-file/per-phase status.
│
└── utils/                      Supporting utilities, deliberately separate from
    │                           factory/ (2026-10-07): factory/ is drivers/sessions/
    │                           config; these are the helpers everything else reaches for.
    ├── prerequisites.py         Standalone one-time pass/fail gate, run once before
    │                           automation starts.
    ├── coordination_client.py   The pairing-code hand-off client (talks to
    │                           coordination_service/app.py).
    ├── mock_server.py           GlassFloor entitlement mock-server launcher (dev use).
    ├── ocr.py                   Windows-native OCR fallback for UIA reads that come
    │                           back incomplete.
    ├── retry.py                 The one shared @retry decorator for flaky WinAppDriver
    │                           interactions.
    ├── wait_utils.py             poll_until(...) -- the one shared explicit-wait primitive.
    ├── keep_app_alive.py         Dev script: watches for and relaunches a crashed
    │                           app/WinAppDriver pair.
    └── run_coordination_service.py  Starts the Coordination Service and prints the
                                   address to give the other machine.
```

## Architecture: layers and import direction

Five layers, imports flow one direction only (lower layers never import from higher ones):

```
Locators  -->  Components  -->  Flows  -->  Orchestration (role_runner.py)
   |               |              |
   `--- assertions/ (shared expected-text constants, read-only) ---'

Factory (driver_factory.py, session.py, capabilities.py, config.py, logger_factory.py)
  -- used by Components/Flows/Orchestration, never imports from them.

Utils (prerequisites.py, coordination_client.py, mock_server.py, ocr.py, retry.py,
  wait_utils.py) -- standalone helpers, used by Components/Flows/Orchestration/Factory.
  factory/session.py imports factory/driver_factory.py for the real WinAppDriver
  process lifecycle; utils/prerequisites.py imports that SAME driver_factory code for
  its own one-time launch-then-close self-test. Neither factory/ file imports anything
  from utils/prerequisites.py, by explicit design (2026-10-07) -- prerequisites.py is a
  standalone gate, not a Factory-layer dependency.

Reports (report_models.py -> action_reporter.py -> html_report_builder.py) -- only
  components/base_component.py (every click/type/get_text) and the two real entry
  points (orchestration/role_runner.py, tests/conftest.py) touch this layer directly.
```

Concrete import examples, so this isn't just a diagram:
- `locators/target/error_banner.py` imports `assertions.target.error_banner.COMMON_PREFIX`
  (one shared string, not duplicated).
- `components/base_component.py` imports `factory.logger_factory`, `utils.retry`,
  `utils.wait_utils`, `reports.action_reporter` -- never `flows/` or `orchestration/`.
- `flows/target/pairing_flow.py` and `flows/source/pairing_flow.py` each import
  `utils.coordination_client.CoordinationClient` independently -- there's no shared
  `flows/shared/` base class; Source and Target flows are parallel, not inherited.
- `orchestration/role_runner.py` is the only file that imports from every layer at once:
  `utils.prerequisites`, `factory.session`, every `flows/*` module, and `reports/*`.

## Code flow: one `role_runner` run, end to end

Both machines run `python -m orchestration.role_runner --role {target|source} --run-id <id>`
as fully independent processes -- there is no single process holding both machines'
sessions. `RoleRunner.run()` does the same four things for either role:

1. **`ensure_target_prerequisites()`** (`utils/prerequisites.py`) -- enables Developer
   Mode and installs WinAppDriver if needed (each a one-time admin-approval prompt),
   confirms WinAppDriver can actually launch on this machine via a launch-then-close
   self-test (`factory.driver_factory.ensure_winappdriver_running()` +
   `kill_winappdriver()`), ensures required Python packages are present, and cleans up
   browser profile state. Raises if a step needed an approval that wasn't given.
2. **`ActionReporter.start_run(run_id, role)`** -- every action recorded from here on
   belongs to this run.
3. **`Session.get(role, build_path)`** (`factory/session.py`) -- idempotently
   launches/reuses WinAppDriver (elevated, via `factory.driver_factory`) and
   launch-then-attaches the app process, exposing `session.app` (a `WinAppDriverSession`)
   to every flow below.
4. Role-specific flow sequence, then **`session.close()`** unconditionally in a
   `finally` (tears down browser + app + WinAppDriver together, even on success), then
   **`build_report()`** in `RoleRunner.run()`'s own outer `finally`.

**Target role** (`RoleRunner._run_target`):
`SignInFlow(session, username, password, otp).run()` (browser-based OIDC sign-in +
OTP, with retry/cancel handling) -> `wait_for_source_pc()` (pairing-discovery finds a
Source PC on the network) -> `TargetPairingFlow.enter_pairing_code_from_coordination_service(run_id)`
(waits for the code-entry screen, then `CoordinationClient.wait_for(run_id,
"pairing_code")` to fetch the code Source published, types it in) ->
`TargetTransferFlow.start_transfer()` (races ConfirmAccountsDialog/CloseAppsDialog the
whole time, clicks "Migrate now" with a periodic re-click + a final re-check right
before each click) -> `wait_for_completion()` (waits out the transfer, then checks the
migration-summary/migration-complete screens, each independently).

**Source role** (`RoleRunner._run_source`):
`SourcePairingFlow(session.app, run_id, coordination_client).run()` (clicks through
Welcome, races the trust-network dialog continuously, waits for Target to become
discoverable, then loops: reads the on-screen pairing code -- which rotates every
~59s -- and `CoordinationClient.publish(run_id, "pairing_code", code)`s it, until
Target pairs) -> `SourceTransferFlow.wait_for_transfer_to_start()` ->
`wait_for_migration_to_complete()`.

**The only cross-machine channel**: both flows talk exclusively to
`coordination_service/app.py` (a separately-run FastAPI relay) through
`utils/coordination_client.py`'s `publish()`/`wait_for()` -- never to each other directly.

**Reporting, throughout**: every `BaseComponent` click/click_at_center/type_text/get_text
times itself, captures a screenshot (base64-encoded, never written to disk on its own),
and calls `ActionReporter.current().record(...)`. `build_report()` renders everything
accumulated so far into one self-contained `reports/output/<run_id>_<role>_<timestamp>.html`
and refreshes `reports/output/index.html` (a cross-run list) -- called from
`RoleRunner.run()`'s `finally` for a live run, or `pytest_sessionfinish` for a pytest run.

## Environment variables

Target PC and Source PC are two independent machines, each running their own
`role_runner` invocation -- they don't need the same `.env`, just the ones relevant to
their own role (plus `DDA_COORDINATION_SERVICE_URL`, which both must agree on). See
`.env.example` for the full file with defaults and comments.

| Variable | Target PC | Source PC | Notes |
|---|---|---|---|
| `DDA_TARGET_BUILD_PATH` | **Required** | not used | Path to `DellDataAssistant.TargetPc.exe` on this machine (no installer exists for this build). |
| `DDA_SOURCE_BUILD_PATH` | not used | **Required** | Path to the *already-installed* `DellDataAssistant.exe` (the Source build is a self-extracting installer -- point at what it produces, not the original downloaded installer). |
| `DDA_TARGET_SIGNIN_USERNAME` | **Required** | not used | Real environment variable only -- never put credentials in `.env`. |
| `DDA_TARGET_SIGNIN_PASSWORD` | **Required** | not used | Same as above. |
| `DDA_TARGET_OTP_STATIC_VALUE` | **Required** | not used | Same as above. |
| `DDA_COORDINATION_SERVICE_URL` | **Required** | **Required** | Must point to wherever the Coordination Service is actually hosted (either machine, or a third host) -- both processes for a given `--run-id` must agree on this address. |
| `DDA_WINAPPDRIVER_HOST` / `DDA_WINAPPDRIVER_PORT` | default OK | default OK | Only change if WinAppDriver needs to run on a non-default host/port. |
| `DDA_TARGET_EXE_NAME` / `DDA_TARGET_PROCESS_NAME` | default OK | not used | Only change if a different Target build/process name is in play. |
| `DDA_SOURCE_EXE_NAME` / `DDA_SOURCE_PROCESS_NAME` | not used | default OK | Only change if a different Source build/process name is in play. |
| `DDA_BROWSER_PROCESS_NAMES` | default OK | not used | Target-only -- Source has no browser-based sign-in step. Comma-separated, checked in order (the OS default browser varies per machine). |
| `DDA_WINAPPDRIVER_INSTALL_PATHS` | default OK | default OK | Semicolon-separated search paths used by the auto-install check. |
| `DDA_NODE_INSTALL_PATHS` | default OK | not used | Only needed for the GlassFloor mock-server dev launch mode, not a normal run. |
| `DDA_MOCK_SERVER_PORT` | default OK | not used | Same as above -- dev-only. |

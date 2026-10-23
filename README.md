# Dell Data Assistant Automation Framework

See [CLAUDE.md](CLAUDE.md) for the code architecture: which layer new code goes in and
the conventions every module follows.
See [DIALOG_HANDLING.md](DIALOG_HANDLING.md) for a full catalog of every unpredictable
dialog/condition this automation watches for -- where it's checked, how long, and
whether it's fatal or clicked through.
See [TEST_SCENARIOS.md](TEST_SCENARIOS.md) for what scenarios/test cases this
automation actually drives and verifies end to end, and what's confirmed live vs. not.
See [FULL_TRANSFER_FLOW.md](FULL_TRANSFER_FLOW.md) for a precise, code-accurate
flowchart of the full transfer scenario, one diagram per method, for reviewing or
improving the automation itself.
See [TARGET_STATE_MACHINE.md](TARGET_STATE_MACHINE.md) for the Target app's full
screen/dialog transition table (from the backend code) that the YAML scenario runner
is built on -- see **State-machine scenario runner** below for how to run it.

Status (2026-10-20): two entry points exist. `orchestration/scenario_runner.py` is the
preferred one -- it drives YAML scenarios through the app's transition table, and
`full_transfer` has run live on two PCs through sign-in, pairing, the transfer, the
skipped-files Retry round, the PDF report validator, feedback, the erase page and the
Source's Try Again (see the status note at the end of **State-machine scenario runner**
for exactly what is and is not confirmed). `orchestration/role_runner.py` is the
original hand-written flow, unchanged and still runnable. PROJECT_PLAN.md and
`tracking/IMPLEMENTATION_STATUS.md` are local-only, gitignored history and predate the
state-machine work -- do not treat them as current.

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
   once you know which machine hosts the Coordination Service). `factory/config.py`
   loads `.env` before anything else reads the environment, so the Target's sign-in
   credentials (`DDA_TARGET_SIGNIN_USERNAME` etc.) can go either in the shell
   environment or in `.env`. `.env` is gitignored and must stay that way: only the
   dedicated test account belongs there, never a real one. See **Environment
   variables** below for exactly what each machine needs.
4. Run anything through uv, e.g.:
   ```
   uv run python utils/run_coordination_service.py
   uv run python -m orchestration.role_runner --role target --run-id <id>
   uv run python -m orchestration.role_runner --role source --run-id <id>
   uv run python -m orchestration.scenario_runner --role target --run-id <id> --scenario full_transfer
   uv run python -m orchestration.scenario_runner --role source --run-id <id> --scenario full_transfer
   ```
   `scenario_runner` drives a YAML scenario from `scenarios/` (see **State-machine
   scenario runner** for the full checklist); `role_runner` is the original hand-written
   flow, kept unchanged.
   Target also takes `--launch {exe,mock,simulator}` (default `exe`): `simulator`
   launches the Target PC UI app indirectly via the CDM Simulator WPF app (mimics Dell
   SupportAssist, which isn't really integrated yet) instead of launching it directly --
   requires `DDA_CDM_SIMULATOR_PATH`. Ignored for `--role source`.

**WinAppDriver, Windows Developer Mode, and required Python packages are all
auto-detected and auto-installed/enabled on first run** -- `utils/prerequisites.py`'s
`ensure_prerequisites()` runs at the start of every `role_runner`/`scenario_runner`
invocation (`--skip-prerequisites` bypasses it on a machine already set up) and
installs WinAppDriver via `winget` if it's missing (one admin approval prompt), enables
Developer Mode if it's off (another admin prompt), and confirms WinAppDriver can launch
elevated as a one-time self-test (then closes it again) -- `factory/session.py` starts
the real instance independently, elevated, the moment automation actually needs it.
Nothing needs to be installed by hand beyond uv and this repo's own
dependencies.

## Project structure

```
dell-automation/
├── assertions/              Expected texts + their existence-check locators +
│   ├── source/              is_showing()-style poll functions, one module per screen
│   └── target/              or dialog for each role (every screen the state machine
│                            observes has one; see CLAUDE.md for the assertion /
│                            locator / component split). Never click targets.
│
├── components/              Page Objects -- one class per screen/dialog, actions only
│   ├── base_component.py    (click/type/read, no existence checks). base_component.py
│   │                        is the shared template: find (explicit wait) -> act ->
│   │                        screenshot -> record, via utils.retry / utils.wait_utils /
│   │                        reports.action_reporter.
│   ├── shared/               Reserved for cross-role components; empty today.
│   ├── source/               Welcome, trust-network, pairing-code, transfer-progress
│   │                        (all five endings, Try Again, Close), confirm-cancel and
│   │                        the network/battery/region dialogs of the Source PC.
│   └── target/                Every Target screen from Welcome to Migration Done and
│                            the erase page (incl. ready-to-move, choose-what-to-move,
│                            drive mapping, skipped files, feedback), the sign-in
│                            modals, all interrupting dialogs (common_dialogs.py), the
│                            window chrome (app_window.py) and the CDM Simulator.
│
├── screen_catalog/          Browsable catalog of every Target-app screen and popup, rendered
│                            by the app's own React code (read from the Rebit repo via
│                            REBIT_WEB_SRC) for screen-text validation. Separate Node
│                            project -- see screen_catalog/README.md.
│
├── coordination_service/    Standalone FastAPI relay (app.py: PUT/GET/DELETE
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
│   ├── source/                pairing_flow.py, transfer_flow.py.
│   └── target/                 authentication/sign_in_flow.py, pairing_flow.py,
│                            transfer_flow.py.
│
├── locators/                 XPath/AutomationId constants only, one module per
│   ├── source/               screen/dialog, mirrored source/target. No business logic.
│   └── target/                A locator may import a shared string from assertions/
│                            (e.g. error_banner.py) rather than duplicate it.
│
├── orchestration/
│   ├── role_runner.py         Original entry point: `python -m orchestration.role_runner
│   │                        --role {target,source} --run-id <id>`. Chains prerequisites
│   │                        -> Session -> that role's hand-written flows -> report.
│   ├── scenario_runner.py     State-machine entry point (2026-10-19): `python -m
│   │                        orchestration.scenario_runner --role --run-id --scenario
│   │                        <name>`; drives a YAML scenario from scenarios/ through
│   │                        the transition table. See "State-machine scenario runner".
│   └── statemachine/          model.py (State/Action/Model), observer.py (snapshot,
│                            probe and the default hybrid observer), scenario.py (YAML
│                            loader, step groups, validation + lint), runner.py (the
│                            one observe->policy->act loop: re-clicks, rewinds, peer
│                            and app-alive checks), peer.py (publish / wait_for_peer /
│                            step-group conditions / own-key clearing / peer-failed
│                            detection over the coordination service), context.py
│                            (the per-run RunContext handed to every action),
│                            target_model.py / source_model.py (the transition tables,
│                            composite actions such as type_code, retry_if_offered,
│                            close_app).
│
├── scenarios/                 YAML scenarios for scenario_runner.py, one file per
│                            end-to-end case (full_transfer, cancel_during_transfer,
│                            old_pc_cancels, ...); _common.yaml holds the shared
│                            dialog-policy sets. Validated by tests/statemachine.
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
│   ├── conftest.py            Pytest fixtures (Session + credentials) and the
│   │                        reporting hooks (pytest_configure/pytest_sessionfinish).
│   ├── statemachine/          Hardware-free unit tests for the runner, models, loader,
│   │                        policies, peer sync, step groups, graceful close and
│   │                        failure handling, plus validation + lint of every
│   │                        scenarios/*.yaml against the real models.
│   └── report_validation/     Unit tests for the PDF validator's registry comparison.
│                            `uv run pytest tests/statemachine tests/report_validation`
│                            needs no hardware.
│
├── tools/, tracking/          Local-only, gitignored: one-off dev scripts and the old
│                            status doc. Not part of any run path; absent from a clone.
│
├── utils/                      Supporting utilities, deliberately separate from
│   │                           factory/ (2026-10-07): factory/ is drivers/sessions/
│   │                           config; these are the helpers everything else reaches for.
│   ├── prerequisites.py         Standalone one-time pass/fail gate, run once before
│   │                           automation starts.
│   ├── environment.py           Named steps a scenario can run outside the app:
│   │                           open/close Notepad, disable/enable the network adapter,
│   │                           Public/Private network profile, Windows region (all
│   │                           PowerShell-based, unverified live) and
│   │                           validate_migration_report (runs validation/, confirmed
│   │                           live 2026-10-20).
│   ├── coordination_client.py   publish / wait_for / clear against
│   │                           coordination_service/app.py.
│   ├── mock_server.py           GlassFloor entitlement mock-server launcher (dev use).
│   ├── ocr.py                   Windows-native OCR fallback for UIA reads that come
│   │                           back incomplete.
│   ├── retry.py                 The one shared @retry decorator for flaky WinAppDriver
│   │                           interactions.
│   ├── wait_utils.py             poll_until(...) -- the one shared explicit-wait primitive.
│   ├── keep_app_alive.py         Dev script: watches for and relaunches a crashed
│   │                           app/WinAppDriver pair.
│   └── run_coordination_service.py  Starts the Coordination Service and prints the
│                                  address to give the other machine.
│
└── validation/                 PDF-migration-report validator: run manually on the
    │                           Target PC, or as the `validate_migration_report` step
    │                           of a scenario (full_transfer does, after each Download
    │                           PDF). See "PDF migration-report validation" below.
    └── output/                   Generated HTML reports land here (gitignored).
```

## Architecture: layers and import direction

Five layers, imports flow one direction only (lower layers never import from higher ones):

```
Locators  -->  Components  -->  Flows  -->  Orchestration (role_runner.py)
   |               |              |
   |               `------------------>  Orchestration (statemachine/ + scenario_runner.py,
   |                                     driven by scenarios/*.yaml; imports components/,
   |                                     assertions/ and the browser part of flows/)
   `--- assertions/ (shared expected-text constants, read-only) ---'

Factory (driver_factory.py, session.py, capabilities.py, config.py, logger_factory.py)
  -- used by Components/Flows/Orchestration, never imports from them.

Utils (prerequisites.py, coordination_client.py, environment.py, mock_server.py,
  ocr.py, retry.py, wait_utils.py) -- standalone helpers, used by
  Components/Flows/Orchestration/Factory.
  factory/session.py imports factory/driver_factory.py for the real WinAppDriver
  process lifecycle; utils/prerequisites.py imports that SAME driver_factory code for
  its own one-time launch-then-close self-test. Neither factory/ file imports anything
  from utils/prerequisites.py, by explicit design (2026-10-07) -- prerequisites.py is a
  standalone gate, not a Factory-layer dependency.

Reports (report_models.py -> action_reporter.py -> html_report_builder.py) -- only
  components/base_component.py (every click/type/get_text), the state-machine runner
  (one row per observed state change and per step action) and the real entry points
  (orchestration/role_runner.py, orchestration/scenario_runner.py, tests/conftest.py)
  touch this layer directly.
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

## Code flow: one `role_runner` run, end to end (the original hand-written path)

This section describes `role_runner.py`, which predates the state-machine runner and
is unchanged. For the YAML-driven path see **State-machine scenario runner** below.

Both machines run `python -m orchestration.role_runner --role {target|source} --run-id <id>
--scenario full_transfer` as fully independent processes -- there is no single process
holding both machines' sessions. A scenario function (`full_transfer` is the only one
in `role_runner`) resolves `role` into a concrete runner class (`TargetRunner`/`SourceRunner`, see
`orchestration/role_runner.py`) and a per-role post-pairing step list, then calls
`RoleRunner.run()`, the thin wrapper that does the same three things regardless of role
or scenario:

1. **`ensure_prerequisites()`** (`utils/prerequisites.py`) -- enables Developer
   Mode and installs WinAppDriver if needed (each a one-time admin-approval prompt),
   confirms WinAppDriver can actually launch on this machine via a launch-then-close
   self-test (`factory.driver_factory.ensure_winappdriver_running()` +
   `kill_winappdriver()`), ensures required Python packages are present, and cleans up
   browser profile state. Raises if a step needed an approval that wasn't given.
2. **`ActionReporter.start_run(run_id, role)`** -- every action recorded from here on
   belongs to this run.
3. Calls into `TargetRunner.run()`/`SourceRunner.run()`, each of which opens its own
   **`Session.get(role, build_path)`** (`factory/session.py`) -- idempotently
   launches/reuses WinAppDriver (elevated, via `factory.driver_factory`) and
   launch-then-attaches the app process, exposing `session.app` (a `WinAppDriverSession`)
   to every flow below -- runs that role's fixed prefix (sign-in+pairing, or pairing),
   then its scenario-supplied post-pairing steps, then **`session.close()`**
   unconditionally in a `finally` (tears down browser + app + WinAppDriver together,
   even on success). `RoleRunner.run()`'s own outer `finally` then calls
   **`build_report()`**.

**Target role** (`TargetRunner.run()`, via the `full_transfer` scenario):
`SignInFlow(session, username, password, otp).run()` (browser-based OIDC sign-in +
OTP, with retry/cancel handling) -> `wait_for_source_pc()` (pairing-discovery finds a
Source PC on the network) -> `TargetPairingFlow.enter_pairing_code_from_coordination_service(run_id)`
(waits for the code-entry screen, then `CoordinationClient.wait_for(run_id,
"pairing_code")` to fetch the code Source published, types it in) ->
`TargetTransferFlow.start_transfer()` (races ConfirmAccountsDialog/CloseAppsDialog the
whole time, clicks "Migrate now" with a periodic re-click + a final re-check right
before each click) -> `wait_for_completion()` (waits out the transfer, then checks the
migration-summary/migration-complete screens, each independently).

**Source role** (`SourceRunner.run()`, via the `full_transfer` scenario):
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

## State-machine scenario runner

`orchestration/scenario_runner.py` is the second entry point, added 2026-10-19 alongside
`role_runner.py` (which is unchanged). Instead of hand-written flows, it drives the app
from a transition table (`orchestration/statemachine/target_model.py` and
`source_model.py` -- the data form of [TARGET_STATE_MACHINE.md](TARGET_STATE_MACHINE.md))
and a YAML scenario (`scenarios/*.yaml`) that lists the steps and the policy for every
dialog that may interrupt them.

### Running a scenario end to end

1. **Pick a scenario** from `scenarios/` (the table in [TEST_SCENARIOS.md](TEST_SCENARIOS.md)
   says which need a Source PC, admin rights, or manual setup). Check it before launching
   anything -- this needs no hardware:
   ```
   uv run python -m orchestration.scenario_runner --scenario full_transfer --validate-only
   ```
   This refuses unknown states/actions and also prints a `WARNING:` for any ending the
   app can reach that no later step handles (e.g. skipped files after a transfer) --
   fix those before running; the test suite requires every shipped scenario to be clean.
2. **Start the Coordination Service** once, on either machine or a third one, and put its
   address in both machines' `.env` as `DDA_COORDINATION_SERVICE_URL`:
   ```
   uv run python utils/run_coordination_service.py
   ```
3. **Target PC** -- `.env` needs `DDA_TARGET_BUILD_PATH` (and `DDA_CDM_SIMULATOR_PATH` for
   `--launch simulator`) plus the sign-in credentials. Use the same run id on both
   machines. A run id may be reused: each role deletes its own keys on the coordination
   service when it starts (see "Reused run ids" below), which needs the service running
   from the current build.
   ```
   uv run python -m orchestration.scenario_runner --role target --run-id r1 --scenario full_transfer
   ```
4. **Source PC** -- `.env` needs `DDA_SOURCE_BUILD_PATH` (the already-installed exe):
   ```
   uv run python -m orchestration.scenario_runner --role source --run-id r1 --scenario full_transfer
   ```
   Start order does not matter: each side waits for the other through the coordination
   service (the Target waits for the pairing code; `wait_for_peer` steps wait for the
   other side's published state).
5. **Watch for a UAC prompt** on the Target after the browser sign-in -- automation
   cannot see or click it; approve it by hand.
6. **Validation**: `full_transfer` runs the PDF migration-report validator (see the
   next section) as a step on the Target against every report the run produces: the
   first transfer's report before the Retry click, the "(Retry - 1)" report after the
   retry round's Download PDF, and the second migration's report after its Download PDF
   (one report, checked once, on a clean run). A missing file or a registry mismatch
   fails the run, and the HTML comparison lands in `validation/output/`. Any scenario
   can do the same with `env: validate_migration_report`.
7. **Results**: the console ends with `Scenario '<name>' (<role>) PASSED` (the app is
   then closed the way a user does, see below) or `SCENARIO FAILED: <reason> during step
   N [screen=... overlay=...]` (exit code 1; 2 for an invalid scenario file). The HTML
   report, with a screenshot at every state change and step action, is written to
   `reports/output/<run_id>_<role>_<timestamp>.html` on each machine.

What `full_transfer` does, per role: the Target signs in (skipped when the login is
cached), pairs with the code the Source publishes, migrates everything, and walks the
results: summary -> View details -> one Retry round when files were skipped -> the
outcome (`target_outcome=partial` or `clean`) -> Finish / Go to summary -> Migration
Done -> Download PDF -> validator -> feedback -> Erase your old PC -> Back to Home. The
Source clicks through pairing, announces every ending, and keeps its app open until the
Target is done. When the outcome is still partial after the Retry round, the Source
clicks Try Again (its final screen after the Target's Back to Home), both pair again
from the home screen and the whole migration runs a second time, ending the same way.
There is no third round. On a clean outcome neither side retries.

Useful flags: `--launch {exe,mock,simulator}` (Target only; the scenario's own `launch:`
is the default), `--observer {hybrid,snapshot,probe}`, `--skip-prerequisites` to bypass
the WinAppDriver/Developer-Mode checks on a machine already set up, `--validate-only`.

Scenarios that need the machine prepared (`setup:` steps such as `set_network_public`,
`disable_network`, `set_region_unsupported`) must run from an **elevated** terminal;
`teardown:` restores the setting even when the run fails.

How a run works: each tick the observer reads one `page_source` snapshot and names the
current (screen, overlay, close prompt). The runner performs the step's action when its
target is showing; applies the scenario's policy when something else is stacked on top
(click it, wait for it to clear, or fail); keeps waiting while the app is on a screen it
can legitimately pass through; and fails with the exact observed state otherwise
(`expected resultsSummary ... got screen=migrating overlay=failure`). The default
`--observer hybrid` falls back to per-locator `find_element` probing whenever `/source`
fails or recognises nothing for a few ticks -- confirmed necessary live (2026-10-19):
WinAppDriver answered `/source` with HTTP 400 on the code-entry screen after serving the
earlier screens fine. `--observer snapshot` / `probe` force one method only.

If the app has not moved 10 s after a step's action, the runner performs the action
again, up to 4 times in total (`defaults: {reclick_after: 10, max_action_attempts: 4}`
per role) -- the guard for WebView2 clicks that report success without doing anything.
Browser sign-in, pairing-code entry, peer publishes and environment steps are exempt;
they carry their own handling.

If something sends the app **back** to a screen an earlier step was written for (a
"Cancel transfer" policy landing on Welcome, a session reset after a network blip), the
runner resumes from that earlier step instead of failing, re-running the steps in
between -- up to `max_rewinds` (default 2) per role; `0` disables it. A screen that no
earlier step knows is still a failure. Caveat for two-machine scenarios: the Source does
not know the Target rewound, so a Target rewind past pairing only works where the Source
script is written to pair again (the cancel scenarios); in `full_transfer` it covers
resets after pairing.

A run that PASSES closes the app the way a user does before teardown: the Target's
caption Close button (answering the desktop-shortcut offer with No thanks), the
Source's Close button or window icon, then a wait for the process to exit, so
`Session.close()`'s process kill finds nothing to kill. A failed run keeps the
immediate kill. Both models expose this as a `close_app` action on every screen, so a
scenario can also close explicitly (the Source scripts end with it).

When one side fails, both stop: the failing role publishes `<role>_state=failed` and
kills its app; every wait on the other side (step waits every 10 s, `wait_for_peer`,
the pairing-code loops) checks for that and ends with `PeerFailed`, after which that
side closes its app gracefully and tears down. An app or WinAppDriver crash is caught
on the side it happens: a step whose app cannot be observed for 60 s, or whose process
is gone, fails with `AppGone` at once instead of waiting out its timeout.

Scenario files: `scenarios/_common.yaml` holds the shared policy sets; the step keys
(`at`, `do`, `env`, `args`, `optional`, `wait_before`, `expect`, `timeout`, `done`) are
documented in `orchestration/statemachine/scenario.py`. Environment steps (`setup:`,
`teardown:`, a step's `env:`) come from `utils/environment.py`. Peer sync is the
`publish` / `wait_for_peer` action every state has, over the coordination service only;
both take an optional `key:` argument for a fact other than `<role>_state`.

A **step group** branches a script on such a fact: `when: {key: target_outcome, is:
partial, among: [partial, clean]}` plus `steps:`. When the group is reached the runner
waits until the key holds one of `among` and runs the inner steps only if it is `is`,
otherwise skips them all. `full_transfer` uses one in each role for the second
migration after a partial outcome: the Target publishes `target_outcome` from the
results screen, the Source branches on it to click Try Again and pair again.

Reused run ids: the coordination service keeps a run's values until they are deleted,
so each role deletes the keys it publishes (`<role>_state`, any `publish key:`, and
the Source's `pairing_code`) before it publishes `started`. The service must be
running from the current build for that (`DELETE /runs/{run_id}/{key}`, restart it
after pulling); against an older service the runner warns and falls back to
stale-value detection only (a value present at start is ignored until it changes).

Every scenario is validated and linted against the models by
`tests/statemachine/test_scenarios.py`; `uv run pytest tests/statemachine
tests/report_validation` needs no hardware.

Status (2026-10-20, after the day's live runs of `full_transfer`): confirmed live on
real hardware -- the cached-login path, pairing with a fresh code (stale codes ignored),
the account-mismatch / install-browser / close-applications policies, the transfer, the
results summary and skipped-files screens, the Retry round, the outcome publish, Go to
summary, Download PDF + the validator on a partial report, feedback, the erase page,
Back to Home, the second-round start up to the code screen; on the Source, code
publishing, every ending, the wait for the outcome, the Try Again click and the
searching -> pairing-code screens; and the peer-failed stop on the Target when the
Source was interrupted. Not yet seen live: the second migration running to its end, the
graceful close at the end of a passing run, the app-gone detection, rewinds, the other
scenarios, and the network/region environment steps.

## PDF migration-report validation

A standalone tool (`validation/`) that can also run as a scenario step
(`env: validate_migration_report`; `full_transfer` runs it on the Target against every
report the run produces and fails the run on a mismatch). Run it manually, ON the Target PC, any
time after a migration finishes. It cross-checks
a Dell Migrate `MigrationReport-*.pdf`'s own claims (which files and settings
categories it says it copied) against what's **actually** on this PC: files checked for
real existence on disk, and settings checked by reading the live Windows registry.

### Usage

```
uv run python -m validation.validate_migration
uv run python -m validation.validate_migration --report "<path to a specific .pdf>"
uv run python -m validation.validate_migration --no-html
```

- No args: auto-picks the most recently modified `MigrationReport-*/*.pdf` under
  `C:\ProgramData\Dell\SupportAssist\CDM\Reports\MigrationReports\`.
- `--report <path>`: validates one specific report instead of auto-picking.
- `--no-html`: console output only, skips writing the HTML report.

Prints a console summary and (unless `--no-html`) writes a self-contained HTML report
(donut chart, collapsible per-category detail -- same self-contained style as the main
run reports, no external files needed to view it) to
`validation/output/<report-name>_validation_<timestamp>.html`. Exit code `0` if every
checkable item matched; `1` if anything didn't, or the report/backup data couldn't be
found or parsed at all.

### What it actually checks

- **Files**: every path under the report's "Files copied" section is checked for real
  existence on disk (size is reported too). "Files not migrated" is printed as
  informational context only -- the report itself already says those failed, so
  there's nothing to re-check.
- **Settings**: the PDF report only gives category *names* ("High Contrast", "Taskbar
  Settings", etc.) under "Settings copied" -- it does **not** give the actual values
  that were supposed to be applied. Those come from
  `C:\ProgramData\Dell\SupportAssist\CDM\SettingsBackup\<GUID>\Registry\*.reg` -- Dell's
  own `.reg` export of the expected values (captured on the Source PC, SID-swapped to
  Target, left behind as a byproduct of the real migration) -- matched to each category
  *name* via the GUID-to-name mapping recorded in
  `C:\ProgramData\Dell\SupportAssist\CDM\logs\TargetPc\DellDataAssistant-*.log`. Each
  expected registry value is then read live (via `winreg`) and compared against what the
  backup says it should be.

### Known limitations

- `SettingsBackup\` is a single shared folder that reflects only the **most recent**
  migration run (confirmed live) -- always validate the report that matches the most
  recent migration, not an older one picked from history.
- A small set of known-volatile value names (e.g. `TaskbarStateLastRun`, `WSENudge*`)
  are deliberately excluded from comparison -- they change on their own regardless of
  whether the migration was correct.
- A mismatch is re-confirmed by re-reading the same value up to 3 times, 0.3s apart,
  before being reported, which catches a value that's genuinely flapping *while the
  validator is running*. It cannot catch, and isn't meant to catch, drift *between*
  separate validator runs (e.g. something else on the PC changing a value in the
  minutes between two runs). A result flagged `unstable` means the re-reads themselves
  disagreed with each other.
- Some settings categories aren't registry-based at all (backed up via other file
  types) or have no GUID/log mapping available -- these are reported with an
  explanatory note instead of a match/mismatch verdict, since there's nothing to
  compare yet.
- `REG_MULTI_SZ` values are compared element by element: the `.reg` export writes
  them with `\0` separators, which the live registry hands back as a list.

Requires `pypdf` -- already pinned in `pyproject.toml`/`uv.lock`, so a plain `uv sync`
is all that's needed; no separate install step.

## Environment variables

Target PC and Source PC are two independent machines, each running their own
`scenario_runner`/`role_runner` invocation -- they don't need the same `.env`, just the
ones relevant to their own role (plus `DDA_COORDINATION_SERVICE_URL`, which both must
agree on). See `.env.example` for the full file with defaults and comments.

| Variable | Target PC | Source PC | Notes |
|---|---|---|---|
| `DDA_TARGET_BUILD_PATH` | **Required** | not used | Path to `MyDellExperience.exe` on this machine (no installer exists for this build; renamed from `DellDataAssistant.TargetPc.exe`, confirmed 2026-10-19). |
| `DDA_SOURCE_BUILD_PATH` | not used | **Required** | Path to the *already-installed* `DellDataAssistant.exe` (the Source build is a self-extracting installer -- point at what it produces, not the original downloaded installer). |
| `DDA_TARGET_SIGNIN_USERNAME` | **Required** | not used | Shell environment or the gitignored `.env` (`factory/config.py` loads it). Only the dedicated test account, never a real one; only needed when the app has no cached login. |
| `DDA_TARGET_SIGNIN_PASSWORD` | **Required** | not used | Same as above. |
| `DDA_TARGET_OTP_STATIC_VALUE` | **Required** | not used | Same as above -- the test account's static one-time code. |
| `DDA_COORDINATION_SERVICE_URL` | **Required** | **Required** | Must point to wherever the Coordination Service is actually hosted (either machine, or a third host) -- both processes for a given `--run-id` must agree on this address. |
| `DDA_WINAPPDRIVER_HOST` / `DDA_WINAPPDRIVER_PORT` | default OK | default OK | Only change if WinAppDriver needs to run on a non-default host/port. |
| `DDA_TARGET_EXE_NAME` / `DDA_TARGET_PROCESS_NAME` | default OK | not used | Only change if a different Target build/process name is in play. |
| `DDA_SOURCE_EXE_NAME` / `DDA_SOURCE_PROCESS_NAME` | not used | default OK | Only change if a different Source build/process name is in play. |
| `DDA_BROWSER_PROCESS_NAMES` | default OK | not used | Target-only -- Source has no browser-based sign-in step. Comma-separated, checked in order (the OS default browser varies per machine). |
| `DDA_WINAPPDRIVER_INSTALL_PATHS` | default OK | default OK | Semicolon-separated search paths used by the auto-install check. |
| `DDA_NODE_INSTALL_PATHS` | default OK | not used | Only needed for the GlassFloor mock-server dev launch mode, not a normal run. |
| `DDA_MOCK_SERVER_PORT` | default OK | not used | Same as above -- dev-only. |
| `DDA_CDM_SIMULATOR_PATH` | **Required if `--launch simulator`** | not used | Path to `CDMSimulatorWPF.exe` -- the WPF app that mimics Dell SupportAssist (not really integrated yet) and launches the Target PC UI app on its own behalf. Not needed for `--launch exe`/`mock` (the default). |
| `DDA_CDM_SIMULATOR_EXE_NAME` / `DDA_CDM_SIMULATOR_PROCESS_NAME` | default OK | not used | Only change if a different CDM Simulator build/process name is in play. |

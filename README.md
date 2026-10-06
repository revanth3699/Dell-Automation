# Dell Data Assistant Automation Framework

See PROJECT_PLAN.md for the full design, architecture, phased roadmap, and Phase 0 findings.
See tools/phase0_inspection_notes.md for raw inspection notes and confirmed locators.

Status: Phase 0 (Target PC) substantially complete; Phase 1 skeleton in progress.

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
auto-detected and auto-installed/enabled on first run** -- `factory/prerequisites.py`'s
`ensure_target_prerequisites()` runs at the start of every `role_runner` invocation and
installs WinAppDriver via `winget` if it's missing (one admin approval prompt), enables
Developer Mode if it's off (another admin prompt), and starts WinAppDriver itself,
elevated. Nothing needs to be installed by hand beyond uv and this repo's own
dependencies.

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

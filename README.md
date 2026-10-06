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
   them in `.env`.
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

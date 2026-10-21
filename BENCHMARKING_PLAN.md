# BENCHMARKING_PLAN.md — Migration performance benchmarking package

**Status:** plan (not yet implemented). **Owner:** _TBD_. **Date:** 2026-10-22.
**Scope:** add a self-contained `benchmark/` package that, while an automation run
executes, samples OS resource usage of the migration processes, harvests the
performance data the rebit/Cdm backend already writes, and renders one HTML report
per run. **External-only** — no changes to the rebit (C#) backend.

This document is the implementation spec and the unit-test plan. Read
`CLAUDE.md` (this repo) first for the layer rules and "Both machines, one channel".

---

## 1. Goal

When `full_transfer` (or any scenario) runs on the **Target PC**, automatically:

1. **Start** a resource sampler at the start of the run.
2. **Stop** it at the end, then harvest the backend's own metrics and render a report
   (the `benchmark/sample_report.html` layout, fed with real data).

The report answers: how fast did it go, **what was the bottleneck** (disk vs network vs
CPU), where did the time go per phase, and what settings were in effect — so we can find
and relieve bottlenecks.

The parameters themselves are already inventoried; see the three planes in §4. This plan
is about **collecting** them during an automation run and **presenting** them.

---

## 2. The multi-migration reality (why "per run" ≠ "per migration")

`full_transfer` is **not** one migration. Within a single automation run there are up to
**three migration episodes** (confirmed from `scenarios/full_transfer.yaml`):

| # | Episode | Trigger (YAML) | `CDM.db` identity |
|---|---|---|---|
| 1 | Primary migration | `migrate_now` → `migrating` (target publishes `migrating`) | new `MigrationId` |
| 2 | In-app **Retry** round (skipped files) | `retry_if_offered` → target publishes `retrying`; transfer restarts (summary→migrating→summary) | **same** `MigrationId`, `isMigrationRetry` set |
| 3 | **Try Again** second migration | `when target_outcome == partial`: re-pair from Welcome, full re-run | **new** `MigrationId` |

Consequences for this package:

- The sampler runs **once, continuously, for the whole run** (spans all three episodes) —
  not once per migration.
- The **report is one HTML per run**, internally **segmented into episodes**. Segmentation
  is driven by the Target's `CDM.db` (`MigrationStatusAudit` / `MigrationStatus` rows keyed
  by `MigrationId`), cross-checked against the coordination markers the YAML already
  publishes (`migrating`, `retrying`, `migrating`). The in-app Retry (episode 2) reuses the
  episode-1 `MigrationId`, so it is sub-segmented by the repeated `MigrationStarted` audit
  marker rather than by id.
- The report's UI (the existing tabbed layout) gains an **episode selector** (1 / 2 / 3 /
  "whole run") above the tabs. Each episode shows its own throughput, resource, and phase
  segment; "whole run" shows the rollup.

### Cross-machine constraint (do not design around it)

The Target and Source are **separate machines with separate filesystems**; the only channel
between them is the coordination relay (`utils/coordination_client.py`), a tiny key/value
store — never bulk data (see `CLAUDE.md` "Both machines, one channel"). Therefore:

- The **Target-side report is the complete one**: the bulk transfer runs rclone on the new
  PC, so the throughput/file-count tables (`RealTimeTransferStatistics`, `MigrationFileCount`)
  and the rclone log live in the **Target's** `CDM.db` and logs. Target resources + Target
  `CDM.db` + Target rclone log = a full picture, all local.
- The **Source** can run the same sampler via its own `source.setup/teardown` and produce a
  **separate** resource-only report on the Source machine. It is **optional** and out of scope
  for v1 (the user scoped Target). The plan keeps the package role-agnostic so Source is a
  one-line YAML addition later.

---

## 3. Package layout

```
benchmark/
  __init__.py
  resource_sampler.py     # OS resource sampler (runs as its own subprocess)
  harvest.py              # read CDM.db + parse rclone log -> normalized series + episodes
  correlate.py            # join resources + throughput + phases -> per-episode metrics + verdict
  report.py               # render the HTML (sample_report.html layout) with real data
  paths.py                # locate CDM.db, rclone log, report output dir (env-overridable)
  models.py               # dataclasses: Sample, Episode, ThroughputPoint, PhaseSpan, RunReport
  report_template.html    # the sample_report.html layout, data-injected at render time
  output/                 # per-run output (gitignored)
  tests/                  # unit tests (see §9)
```

Two **env steps** are added to `utils/environment.py` (`start_benchmark`,
`stop_benchmark_report`) and wired into `scenarios/full_transfer.yaml` as the Target role's
`setup`/`teardown`. The package otherwise does not touch the orchestration layer.

Dependency to add to `pyproject.toml`: **`psutil`** (resource sampling). The repo already
has `loguru`, `pyyaml`, `pypdf`.

---

## 4. The parameters (recap — what each module produces)

**Plane A — OS resources (sampled by `resource_sampler`, NOT in the backend):** per-process
CPU %, RSS/private memory, disk read/write MB/s, network sent/recv MB/s (NIC-level; psutil
has no per-process net on Windows), thread/handle counts; plus system-wide baselines.
Processes: `DellDataManager` (engine), `DellFileTransferUtil` (rclone), `MyDellExperience`
(Target UI), `Everything` (file scan). Names come from `factory/config.py`
(`TARGET_PROCESS_NAME`, etc.).

**Plane B — throughput (harvested from the Target's `CDM.db` + rclone log):** copy speed
series (5 s, from the rclone `--stats-one-line` log), per-drive bytes/counts
(`RealTimeTransferStatistics`, 60 s), file counts (`MigrationFileCount`), per-path results
(`FileTransferResults`), totals + avg speed (`MigrationStatus.RunTime`,
`MigrationStartTime/EndTime`).

**Plane C — phase timing (harvested from `MigrationStatusAudit`):** per-boundary timeline
for pairing/pre-check/compatibility/enumeration/settings/transfer. Gaps (discovery, J-PAKE
internals, duplicate-check, report-gen) are shown as "estimated" — grey in the report.

**Plane D — tuning config (read from the deployed engine `.exe.config`):** `--transfers`,
`--bwlimit`, `--multi-thread-streams`, etc. Displayed, not changed.

---

## 5. Module specs

### 5.1 `resource_sampler.py`

Runs as a **standalone subprocess** (`python -m benchmark.resource_sampler ...`), not a
thread — the main process is busy driving WinAppDriver, and a separate process keeps
sampling cadence steady and avoids GIL contention.

CLI:
```
python -m benchmark.resource_sampler \
  --run-id <id> --role target --out benchmark/output/<id> \
  --interval 1.0 --stop-file benchmark/output/<id>/STOP_target \
  --processes MyDellExperience,DellDataManager,DellFileTransferUtil,Everything
```

Behaviour:
- Each tick (default 1 s): enumerate processes whose name matches the list (case-insensitive,
  catches **multiple** rclone instances), read `cpu_percent`, `memory_info().rss`,
  `io_counters()` (read/write bytes), `num_threads`, `num_handles`; read system-wide
  `cpu_percent`, `virtual_memory`, `disk_io_counters`, `net_io_counters`.
- Convert monotonic counters (IO bytes, net bytes) to **rates** by diffing against the prior
  tick and dividing by measured elapsed time.
- Write one JSONL line per (scope,name) per tick to `resources_<role>.jsonl`; first line is a
  **meta** record (interval, host, role, run-id, start wall + monotonic clock, process list).
- Stop on: `--stop-file` appearing, `SIGINT`/`SIGTERM`, or `--duration` elapsed. Flush and exit 0.
- Robust to `psutil.NoSuchProcess`/`AccessDenied` (process vanished mid-tick — rclone
  restarts) by skipping that process for the tick, never crashing.

Record schema (`models.Sample`):
```json
{"ts_wall":"2026-10-22T14:03:01.2Z","ts_mono":182.4,"scope":"process",
 "name":"DellFileTransferUtil","pid":1234,"cpu_pct":37.0,"rss_mb":612.0,
 "disk_read_mbps":12.1,"disk_write_mbps":86.0,"threads":41,"handles":880}
```
System scope records carry `cpu_pct`, `mem_used_mb`, `disk_read/write_mbps`,
`net_sent/recv_mbps`.

**Factor the pure logic out** of the loop so it is unit-testable without a real process:
- `compute_rate(prev_bytes, cur_bytes, elapsed_s) -> mbps`
- `match_processes(all_procs, names) -> list` (name-matching + dedupe)
- `sample_process(proc) -> dict` / `sample_system(prev, now) -> dict`

### 5.2 `paths.py`

- `find_cdm_db() -> Path` — default `C:\ProgramData\Dell\SupportAssist\CDM\CDM.db`; overridable
  by `DDA_CDM_DB_PATH`. Mirror the discovery style in `validation/validate_migration.py`
  (`find_latest_report`).
- `find_rclone_log() -> Path | None` — the log4net "FileTransfer" log under the CDM logs dir;
  overridable by `DDA_RCLONE_LOG_PATH`. Returns `None` if absent (report degrades gracefully).
- `find_engine_config() -> Path | None` — the deployed `DellDataManager`/`MyDellExperience`
  `.exe.config` for Plane D (optional; `DDA_ENGINE_CONFIG_PATH`).
- `output_dir(run_id) -> Path` — `benchmark/output/<run_id>/`.

All lookups are **read-only** and wrapped so a missing/locked file never raises past the
harvester (the engine holds `CDM.db`; open it read-only with a busy-retry, same spirit as the
backend's own retry).

### 5.3 `harvest.py`

Input: Target `CDM.db` path, rclone log path, resource JSONL path. Output: `models.RunReport`
with a list of `Episode`s.

- `read_episodes(db) -> list[Episode]` — from `MigrationStatus` + `MigrationStatusAudit`:
  one episode per `MigrationId`; within an id, sub-split on a repeated `MigrationStarted`
  marker to surface the in-app Retry round. Each episode carries start/end wall-clock,
  `RunTime`, `MigratedFrom/To`, `Network`.
- `read_throughput(db, log) -> list[ThroughputPoint]` — per-drive series from
  `RealTimeTransferStatistics`; the 5 s speed series by parsing the rclone log line
  (`transferred / total, %, speed, <|ETA|> …(xfr#n/m)`). Reuse the exact field positions the
  backend uses (see rebit `ProcessFileTransfer.cs`). Also surface rclone's otherwise-discarded
  `xfr#n/m` and error counts.
- `read_file_counts(db) -> …` — `MigrationFileCount` (success/backedup/skipped/already) and
  `FileTransferResults` skip-reason histogram (bucket by `ErrorCode`/`SkippingReason`).
- `read_tuning(config) -> dict` — Plane D from the engine config, applying the known runtime
  override for `--transfers` (CPU-core count; see `CdmConfiguration.cs`), clearly labelled.
- `assign_samples_to_episodes(samples, episodes)` — bucket resource JSONL rows into episode
  time windows by wall clock.

Everything is a pure function of (db rows, log text, json lines) → values, so it is testable
against a seeded temp SQLite DB and fixture text.

### 5.4 `correlate.py`

- `resource_profile(episode) -> dict` — during that episode's **transfer window**, compute per
  resource: avg and peak % busy (CPU, disk, network as % of an observed or configured ceiling),
  effective throughput (bytes ÷ transfer seconds).
- `bottleneck_verdict(profile) -> Verdict` — rule: the resource with the highest sustained %
  busy during transfer is the bottleneck; produce the plain-language sentence the report shows
  (e.g. "new-PC disk 95–100% busy while network ~35% → disk-bound"). Deterministic + unit-tested.
- Handles episodes with **no resource overlap** (e.g. sampler started late) by marking the
  profile "insufficient data" rather than inventing numbers.

### 5.5 `report.py`

- `render(run_report, out_html) -> Path` — inject the harvested/correlated data into
  `report_template.html` (the `sample_report.html` layout) and write
  `benchmark/output/<run_id>/report_<role>.html`.
- The template's `<script>` sample-data block is replaced by a `window.__BENCHMARK__ = {…}`
  payload (one object per episode + a rollup); the existing chart code reads from it. Add the
  **episode selector** that swaps the active payload.
- Missing planes degrade gracefully: no rclone log → throughput tab shows "no transfer log
  found"; `CDM.db` missing → resource-only report with a banner.

### 5.6 `utils/environment.py` — two new env steps

```python
def start_benchmark(ctx) -> None:
    """Target setup: launch the resource sampler subprocess for this run."""
    # out = benchmark.paths.output_dir(ctx.run_id); spawn `python -m benchmark.resource_sampler`
    # store popen handle + out dir + stop-file path in ctx.scratch["benchmark"]
    # never block the run; log the pid.

def stop_benchmark_report(ctx) -> None:
    """Target teardown: stop the sampler, harvest, render the report. Must never raise
    (teardown swallows exceptions, but keep it clean): log and return on any failure."""
    # touch stop-file; wait briefly for the subprocess to exit (then terminate as a backstop)
    # harvest -> correlate -> render; log the output path.
```

Register both in `STEPS`. Add to `scenarios/full_transfer.yaml` under the **target** role:

```yaml
  target:
    defaults: {step_timeout: 300, tick: 0.5}
    policies: {base: happy_path}
    setup: [start_benchmark]
    teardown: [stop_benchmark_report]
    steps:
      ...
```

Why `setup`/`teardown` and not first/last `env:` steps:
- `setup` runs **after launch, before the first step** (`scenario_runner.py:145`), so the app
  process already exists when sampling starts.
- `teardown` runs in a **guaranteed `finally`** (`scenario_runner.py:157-165`) even when the run
  fails, and teardown-step exceptions are swallowed — so the sampler is always stopped and a
  report is attempted no matter how the run ends. This is strictly more robust than an in-step
  `env:` at the last state (which a failure could skip).
- It is literally "start and end of the Target PC," as requested.

`ctx` gives the step everything it needs: `ctx.run_id`, `ctx.role`, `ctx.scratch`,
`ctx.log`, `ctx.coordination` (`orchestration/statemachine/context.py`).

---

## 6. End-to-end sequence (Target)

1. `scenario_runner.run()` launches the app, builds `ctx`.
2. `setup: start_benchmark` → sampler subprocess starts, writes `resources_target.jsonl`.
3. Runner drives the scenario through all 1–3 migration episodes; the engine writes `CDM.db`
   and the rclone log as usual.
4. Run ends (pass or fail) → `finally` → `teardown: stop_benchmark_report`:
   - stop sampler (stop-file, then terminate backstop),
   - `harvest` (Target `CDM.db` + rclone log + the JSONL),
   - `correlate`, `render` → `benchmark/output/<run_id>/report_target.html`.
5. `session.close()` + existing `build_report()` run as before (unchanged).

---

## 7. Failure handling / robustness

- Sampler crash must not affect the run (separate process; `start_benchmark` only spawns).
- `stop_benchmark_report` must never fail the teardown: wrap all work, log and return on error.
- `CDM.db` locked by the engine → open read-only with busy-retry; if still unreadable, emit a
  resource-only report with a banner.
- Sampler never started / JSONL empty → report renders from `CDM.db` only (no resource tabs).
- Reused `run_id` → write into a fresh `output/<run_id>/` (clear stale files first), mirroring
  how `scenario_runner` clears coordination keys on reuse.

---

## 8. Dependencies, config, static verification

- Add `psutil` to `pyproject.toml`; `uv sync`.
- New env overrides (all optional): `DDA_CDM_DB_PATH`, `DDA_RCLONE_LOG_PATH`,
  `DDA_ENGINE_CONFIG_PATH`, `DDA_BENCHMARK_INTERVAL`, `DDA_BENCHMARK_PROCESSES`. Document in
  `.env.example` and `README.md`.
- Static check (no hardware), per repo convention:
  ```
  uv run python -c "import benchmark.resource_sampler, benchmark.harvest, benchmark.correlate, benchmark.report, benchmark.paths, benchmark.models; print('IMPORTS OK')"
  uv run python -m benchmark.resource_sampler --help
  uv run pytest benchmark/tests tests/statemachine
  ```
  `tests/statemachine/test_scenarios.py` must still pass (new env steps registered;
  `full_transfer.yaml` still valid).

---

## 9. Unit-test coverage

All tests live in `benchmark/tests/` (pytest, matching the repo). No live hardware: the
sampler's pure functions are tested with a **fake psutil**, the harvester against a **temp
SQLite DB seeded with the real table schemas** and **fixture rclone-log text**, and the env
steps with `subprocess`/harvest **mocked**.

### 9.1 `resource_sampler`
- `compute_rate`: normal delta, zero elapsed (guard, no div-by-zero), counter reset/decrease
  (clamp ≥ 0), first sample (no prev → 0).
- `match_processes`: matches by name case-insensitively; returns **multiple** rclone instances;
  ignores non-matching; empty list.
- `sample_process`: maps psutil fields → schema; tolerates `NoSuchProcess`/`AccessDenied`
  (returns `None`/skips, never raises). Uses a fake process object.
- `sample_system`: computes net/disk rates from two fake counter snapshots.
- meta record written first; JSONL lines are valid JSON; stop-file triggers clean exit
  (run the loop with a fake clock + a stop-file, assert it terminates and flushes).

### 9.2 `paths`
- Env override wins over default; default path shape is correct; missing file → `None` for the
  optional ones; `output_dir` creates/returns the per-run dir.

### 9.3 `harvest`
- `read_episodes`: seed `MigrationStatus` + `MigrationStatusAudit` with **(a)** one clean
  migration, **(b)** one migration + in-app retry (same `MigrationId`, double `MigrationStarted`)
  → 1 episode with 2 sub-segments, **(c)** two `MigrationId`s (Try-Again) → 2 episodes. Assert
  counts, boundaries, and sub-segmentation.
- `read_throughput`: parse fixture rclone `--stats-one-line` text → correct speed/transferred/
  total series incl. `xfr#n/m` and error count; a malformed line is skipped, not fatal; no log
  → empty series.
- `read_file_counts`: `MigrationFileCount` mapped; `FileTransferResults` skip reasons bucketed
  and ranked; empty tables → zeros.
- `read_tuning`: parse a sample `.exe.config`; `--transfers` shows the CPU-override label; missing
  config → defaults with a flag.
- `assign_samples_to_episodes`: samples bucketed into the right episode window by wall clock;
  samples outside any window dropped; boundary timestamps handled.
- DB locked / missing: raises a typed, caught error → caller degrades (tested via a deleted/locked
  temp file).

### 9.4 `correlate`
- `resource_profile`: avg/peak % busy and effective throughput from a known sample set;
  transfer-window filtering (ignores enumeration/settings samples).
- `bottleneck_verdict`: disk-bound set → "disk"; network-bound set → "network"; CPU-bound →
  "CPU"; balanced/low → "no clear bottleneck". Deterministic strings asserted.
- Insufficient-overlap episode → "insufficient data", no invented numbers.

### 9.5 `report`
- `render` with 0 / 1 / 3 episodes → valid HTML, `window.__BENCHMARK__` payload has the right
  episode count, episode selector present; missing-plane banners appear when a plane is empty.
- Template placeholder fully replaced (no leftover sample-data block).

### 9.6 env steps (`utils/environment.py`)
- `start_benchmark`: spawns the sampler (mock `subprocess.Popen`), stores handle/paths in
  `ctx.scratch["benchmark"]`, logs pid, returns fast; does not raise if spawn fails (logs).
- `stop_benchmark_report`: touches stop-file, waits/terminates (mock), calls harvest+render
  (mock), logs output path; **never raises** even when harvest throws (teardown safety) — assert
  it returns normally on a forced harvest exception.
- Registration: both names in `environment.STEPS`; `resolve` returns them.

### 9.7 scenario integration
- `tests/statemachine/test_scenarios.py` still passes: `full_transfer.yaml` validates with the
  new `setup`/`teardown` (the validator already checks setup/teardown names against
  `environment.STEPS`, `scenario.py:331-333`).

**Coverage goal:** ≥ 90% line coverage on `harvest`, `correlate`, `report`, `paths`, and the
pure helpers of `resource_sampler`; the sampler's I/O loop and the env-step subprocess glue are
covered by the mocked tests above (the thin OS-touching remainder is acceptable as uncovered).

---

## 10. Build order (suggested)

1. `models.py` + `paths.py` + tests.
2. `resource_sampler.py` (pure helpers first, then the loop) + tests; verify `--help` and a
   10 s live capture by hand.
3. `harvest.py` against a seeded temp DB + fixture log + tests.
4. `correlate.py` + tests.
5. `report.py` + `report_template.html` (port `sample_report.html`, add episode selector) + tests.
6. `start_benchmark` / `stop_benchmark_report` env steps + register + tests.
7. Wire `setup`/`teardown` into `full_transfer.yaml`; run `test_scenarios`.
8. One live `full_transfer` run on the rig → confirm `report_target.html` with 1–3 episodes.

## 11. Decisions (resolved 2026-10-22) + remaining assumptions

**Resolved:**
- **% busy ceilings — BOTH.** Default is **relative** (observed peak during the run = 100%, no
  config, works on any rig). When `DDA_BENCHMARK_LINK_MBPS` (network) and/or a disk-ceiling
  override is set, `correlate.resource_profile` switches that resource to **absolute** %. The
  report labels which mode each bar uses ("relative to peak" vs "of <ceiling>"). Covered by
  `correlate` tests (§9.4): relative set, absolute-with-override set, mixed.
- **Report location — `benchmark/output/<run_id>/`.** Separate from `reports/output/`;
  `benchmark/output/` is gitignored.

**Remaining assumptions (verify on the rig):**
- **`CDM.db` path — not yet confirmed.** Use the default `C:\ProgramData\Dell\SupportAssist\CDM\
  CDM.db`, always overridable via `DDA_CDM_DB_PATH`; confirm the real path (the MyDellExperience
  DDA namespace may differ) during the first rig run and pin the env var if so. `paths.find_cdm_db`
  must fail with a clear message naming the path it tried.
- **Source-side report:** out of scope for v1 (Target only, per direction). Package stays
  role-agnostic so `source.setup/teardown` is a later one-liner.

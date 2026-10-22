"""Read the performance data the backend already writes -- the Target's CDM.db and the
rclone --stats-one-line log -- plus the sampler's JSONL, and normalise it into
models.RunReport. Everything is read-only; every reader is a pure function of its input
(db rows / log text / json lines) so it can be tested with a seeded temp DB and fixtures.

Schemas follow rebit Cdm/CdmDatabase/Entity (MigrationStatus, MigrationStatusAudit,
MigrationFileCount, RealTimeTransferStatistics, FileTransferResults). The log parse follows
ProcessFileTransfer.cs: marker ', <|ETA|> ', fields transferred / total, percent, speed,
then (xfr#n/m).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from benchmark import paths
from benchmark.models import (Episode, FileCounts, PhaseSpan, RunReport, Sample, Segment,
                              ThroughputPoint, Tuning, TuningRow)

RCLONE_MARKER = ", <|ETA|> "
MIGRATION_STARTED = "MigrationStarted"
_DOTNET_MIN_DATETIME = datetime(1, 1, 1)  # .NET's DateTime.MinValue, written as "0001-01-01 00:00:00"


class CdmDbError(Exception):
    """CDM.db could not be read (locked past the retries, corrupt, unreadable)."""


# --------------------------------------------------------------------- time helpers

_FRAC = re.compile(r"(\.\d{6})\d+")


def parse_ts(value: Any, *, assume_utc: bool = False) -> datetime | None:
    """Parse a CDM.db / JSONL timestamp into a naive local datetime. Accepts 'T' or space
    separators, up to 7 fractional digits (EF/.NET ticks) and a trailing Z/offset (converted
    to local time). Returns None for anything unparseable.

    assume_utc: treat a string with NO trailing Z/offset as UTC anyway, instead of already-local.
    Needed specifically for MigrationStatus.timeCreated and MigrationStatusAudit.timeCreated:
    confirmed live (2026-10-22) by cross-referencing 4 separate benchmark runs against CDM.db --
    those two columns store a UTC moment with no timezone marker at all, while
    MigrationStartTime/MigrationEndTime are naive but already local, and timeUpdated is UTC WITH
    an explicit trailing Z. Applying this blindly to every timestamp would wrongly re-shift the
    columns that are already correct (and the sampler's own already-local ts_wall) -- it must stay
    opt-in, per column, not a global default."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = _FRAC.sub(r"\1", text)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    elif assume_utc:
        text += "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def parse_runtime(text: str | None) -> float | None:
    """'hh:mm:ss[.fff]' or 'd.hh:mm:ss' -> seconds; None if it is not in that shape."""
    if not text:
        return None
    m = re.fullmatch(r"(?:(\d+)\.)?(\d+):(\d{2}):(\d{2})(?:\.\d+)?", text.strip())
    if not m:
        return None
    d, h, mi, s = (int(g or 0) for g in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def parse_eta(text: str) -> float | None:
    """rclone ETA ('6m36s', '1h2m3s', '-') -> seconds, None when unknown."""
    text = (text or "").strip()
    m = re.fullmatch(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", text)
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (float(g) if g else 0.0 for g in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


# --------------------------------------------------------------------- sampler JSONL

def read_samples(jsonl: Path | None) -> tuple[dict, list[Sample]]:
    """(meta record, samples). Missing file -> ({}, []); bad lines are skipped."""
    meta: dict = {}
    samples: list[Sample] = []
    if jsonl is None or not Path(jsonl).is_file():
        return meta, samples
    with Path(jsonl).open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("scope") == "meta":
                meta = data
                continue
            sample = Sample.from_dict(data, parse_ts)
            if sample is not None:
                samples.append(sample)
    return meta, samples


# --------------------------------------------------------------------- CDM.db access

def _rows(db_path: Path, sql: str, params: tuple = (), *, retries: int = 5, delay: float = 0.4,
          sleep: Callable[[float], None] = time.sleep) -> list[sqlite3.Row]:
    """Read-only query with busy-retry. A missing table yields []; anything else that
    persists past the retries raises CdmDbError."""
    last: Exception | None = None
    for attempt in range(retries):
        conn = None
        try:
            conn = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True, timeout=2.0)
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            last = exc
        except sqlite3.DatabaseError as exc:
            last = exc
        finally:
            if conn is not None:
                conn.close()
        if attempt < retries - 1:
            sleep(delay)
    raise CdmDbError(f"could not read CDM.db at {db_path}: {last}")


# --------------------------------------------------------------------- episodes

PHASE_DEFS: list[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
    # name, start statuses/prefixes, end statuses/prefixes (last match wins), fallback ends
    ("Compatibility", ("LocaleCompatibility", "Compatibility"), ("LocaleCompatibility", "Compatibility"), ()),
    # Named "Migration info", not "Pre-check / migration info" -- it only matches MigrationInfo*
    # prefixes. PreCheck*/Pairing* statuses match no phase at all and fall into "Unmeasured /
    # other" (confirmed live 2026-10-22: that bucket is consistently the largest segment in every
    # phase chart checked, partly because of this). The old name implied PreCheck coverage that
    # was never actually there.
    ("Migration info", ("MigrationInfo",), ("MigrationInfo",), ()),
    ("Time estimate", ("MigrationEstimatedTime",), ("MigrationEstimatedTime",), ()),
    ("Settings migration", ("SettingMigrationStarted",), ("SettingMigrationEnded",), ()),
    ("File transfer", ("FileMigrationStarted",), ("FileCopyCompleted",), ("FileMigrationEnded",)),
    ("Transfer reporting", ("FileCopyCompleted",), ("FileTransferReportingCompleted",), ("FileMigrationEnded",)),
    ("Migration report", ("MigrationReport", "MigrationDetailedReport"), ("MigrationReport", "MigrationDetailedReport"), ()),
]
TRANSFER_PHASE = "File transfer"


def compute_phases(audits: list[tuple[str, datetime]], start: datetime, end: datetime) -> list[PhaseSpan]:
    """Phase spans from the audit rows inside [start, end]. Phases the audit trail does not
    cover are folded into one estimated 'Unmeasured / other' span (grey in the report)."""
    inside = [(s, t) for s, t in audits if start <= t <= end]
    spans: list[PhaseSpan] = []
    for name, starts, ends, fallback in PHASE_DEFS:
        s_times = [t for s, t in inside if s.startswith(starts)]
        if not s_times:
            continue
        p_start = min(s_times)
        e_times = [t for s, t in inside if s.startswith(ends) and t >= p_start]
        if not e_times and fallback:
            e_times = [t for s, t in inside if s.startswith(fallback) and t >= p_start]
        if not e_times and name == TRANSFER_PHASE:
            e_times = [end]
        p_end = max(e_times) if e_times else p_start
        spans.append(PhaseSpan(name, p_start, p_end, False, name == TRANSFER_PHASE))
    gap = (end - start).total_seconds() - sum(p.seconds for p in spans)
    if gap > 1.0:
        spans.append(PhaseSpan("Unmeasured / other", start, start + timedelta(seconds=gap), True))
    return spans


def read_episodes(db_path: Path) -> list[Episode]:
    """One Episode per MigrationId (ordered by start). A repeated MigrationStarted audit row
    inside one id (the in-app Retry round) becomes an extra Segment of that episode."""
    statuses = {int(r["id"]): r for r in _rows(db_path, "SELECT * FROM MigrationStatus")}
    audit_rows = _rows(db_path, "SELECT migrationId, status, timeCreated FROM MigrationStatusAudit "
                                "ORDER BY timeCreated, id")
    audits: dict[int, list[tuple[str, datetime]]] = {}
    for r in audit_rows:
        ts = parse_ts(r["timeCreated"], assume_utc=True)
        if ts is not None:
            audits.setdefault(int(r["migrationId"]), []).append((str(r["status"]), ts))

    def col(row: sqlite3.Row | None, name: str) -> Any:
        if row is None:
            return None
        return row[name] if name in row.keys() else None

    episodes: list[Episode] = []
    for mid in sorted(set(statuses) | set(audits)):
        row, trail = statuses.get(mid), audits.get(mid, [])
        if not trail and parse_ts(col(row, "MigrationStartTime")) is None \
                and parse_ts(col(row, "MigrationEndTime")) is None:
            updated = parse_ts(col(row, "timeUpdated"))
            if updated is None or updated == _DOTNET_MIN_DATETIME:
                continue  # a bare stub row the app created and abandoned -- no real migration ever
                          # happened under this id. Confirmed live (2026-10-22): the real CDM.db
                          # creates one of these (migrationState 'Init', zero audit rows, no
                          # start/end, timeUpdated left at .NET's DateTime.MinValue) right before
                          # the actual migration gets a fresh id -- keeping it around as an
                          # "episode" pushed the real, only migration into the "Try Again" label
                          # purely by list position, even though nothing was ever retried.
        # MigrationStartTime/MigrationEndTime are naive-but-already-local; the audit trail's own
        # timestamps are naive-but-actually-UTC (parsed above with assume_utc=True, so they're
        # correctly in local time here too) -- once both sides are parsed correctly they agree
        # within about a minute of each other, so max()/min() across both is a safe way to pick
        # whichever signal is most complete. (An earlier version of this trusted the trail alone
        # because the two looked ~5.5h apart -- that was this exact timezone bug, not corruption;
        # see parse_ts's assume_utc docstring.)
        starts = [t for t in (parse_ts(col(row, "MigrationStartTime")), trail[0][1] if trail else None) if t]
        ends = [t for t in (parse_ts(col(row, "MigrationEndTime")), trail[-1][1] if trail else None) if t]
        starts = starts or [t for t in [parse_ts(col(row, "timeCreated"), assume_utc=True)] if t]
        ends = ends or [t for t in [parse_ts(col(row, "timeUpdated"))] if t]
        if not starts:
            continue
        start = min(starts)
        end = max(max(ends), start) if ends else start
        marks = [t for s, t in trail if s == MIGRATION_STARTED]
        if len(marks) > 1:
            bounds = [start] + marks[1:] + [end]
            segments = [Segment(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
        else:
            segments = [Segment(start, end)]
        episodes.append(Episode(
            index=0, kind="primary", label="", migration_id=mid, start=start, end=end,
            run_time=col(row, "runTime"), migrated_from=col(row, "migratedFrom"),
            migrated_to=col(row, "MigratedTo"), network=col(row, "Network"),
            segments=segments, audits=trail, phases=compute_phases(trail, start, end)))
    episodes.sort(key=lambda e: (e.start, e.migration_id or 0))
    return episodes


def scope_to_run(episodes: list[Episode], run_start: datetime | None, run_end: datetime | None) -> list[Episode]:
    """Keep only migrations that overlap [run_start, run_end] -- the sampler's own observed
    window (its meta start_wall through its last sample's ts_wall). CDM.db is a persistent store
    the real app keeps appending to across every migration ever attempted on the machine, not a
    per-run file -- without this, an unrelated migration from a prior day/week shows up as an
    "episode" of today's run (and inflates the rollup's total time to match). With accurate
    start/end times (see parse_ts's assume_utc docstring -- a prior version of this file had the
    timezone handling wrong, making every migration look ~5.5h later/longer than it really was,
    which both motivated and then obscured testing of this function) a real migration's window is
    normally just minutes long and maps to exactly one run, so BOTH bounds matter equally: a lower
    bound alone would still let a migration from hours earlier leak in if nothing capped how far
    back "still relevant" reaches, and an upper bound alone would do the same looking forward.

    Both bounds come from THIS run's own resources_<role>.jsonl (meta.start_wall, and the latest
    sample's ts_wall) rather than datetime.now() at harvest time, so a later re-harvest of an older
    run doesn't shift its window to match whenever harvest_run happens to be re-invoked. Missing
    either bound (no sampler meta, or zero samples) disables the filter entirely rather than
    guess."""
    if run_start is None or run_end is None:
        return episodes
    return [e for e in episodes if e.start <= run_end and e.end >= run_start]


_KIND_LABEL = {"primary": "Primary migration", "retry": "In-app Retry", "try_again": "Try Again migration"}


def expand_segments(episodes: list[Episode]) -> list[Episode]:
    """The report's selectable windows: one per Segment, numbered 1..n in time order, so a
    primary migration + in-app Retry + Try Again migration shows as episodes 1, 2, 3."""
    windows: list[Episode] = []
    for ep_no, ep in enumerate(episodes):
        for seg_no, seg in enumerate(ep.segments or [Segment(ep.start, ep.end)]):
            kind = "retry" if seg_no > 0 else ("primary" if ep_no == 0 else "try_again")
            index = len(windows) + 1
            windows.append(replace(
                ep, index=index, kind=kind, label=f"Episode {index} - {_KIND_LABEL[kind]}",
                start=seg.start, end=seg.end, segments=[seg],
                phases=compute_phases(ep.audits, seg.start, seg.end),
                samples=[], rclone=[], drive_stats=[], profile=None, verdict=None))
    return windows


def assign_samples_to_episodes(samples: Iterable[Sample], episodes: list[Episode]) -> int:
    """Bucket samples into episode windows by wall clock (start and end inclusive; a sample on
    a shared boundary goes to the earlier window). Returns how many fell in no window."""
    for ep in episodes:
        ep.samples = []
    dropped = 0
    for s in samples:
        for ep in episodes:
            if ep.start <= s.ts_wall <= ep.end:
                ep.samples.append(s)
                break
        else:
            dropped += 1
    return dropped


# --------------------------------------------------------------------- throughput

_TS = re.compile(r"(\d{4})[/-](\d{2})[/-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})")
_STATS = re.compile(r"(\d+)\s*/\s*(\d+),\s*(\d+)\s*%,\s*(-?[\d.]+),\s*<\|\s*ETA\s*\|>\s*([^\s(]*)\s*"
                    r"(?:\(xfr#(\d+)/(\d+)\))?")


def parse_rclone_log(lines: Iterable[str]) -> list[ThroughputPoint]:
    """Parse rclone --stats-one-line progress lines (see module docstring). Lines that carry the
    marker but do not parse are skipped; ERROR lines are counted cumulatively into `errors`."""
    points: list[ThroughputPoint] = []
    errors = 0
    for line in lines:
        if " ERROR" in line or line.startswith("ERROR"):
            errors += 1
        if RCLONE_MARKER not in line and "<|ETA|>" not in line:
            continue
        m = _STATS.search(line)
        if not m:
            continue
        ts_m = _TS.search(line)
        ts = datetime(*(int(g) for g in ts_m.groups())) if ts_m else None
        try:
            points.append(ThroughputPoint(
                kind="rclone", ts=ts, transferred=int(m.group(1)), total=int(m.group(2)),
                percent=float(m.group(3)), speed_bps=float(m.group(4)), eta_s=parse_eta(m.group(5)),
                xfr_n=int(m.group(6)) if m.group(6) else None,
                xfr_m=int(m.group(7)) if m.group(7) else None, errors=errors))
        except (ValueError, OverflowError):
            continue
    return points


def read_drive_stats(db_path: Path) -> list[ThroughputPoint]:
    """Latest RealTimeTransferStatistics row per (MigrationId, drive). That table has no
    timestamp, so these are per-migration totals, not a time series."""
    rows = _rows(db_path, "SELECT * FROM RealTimeTransferStatistics ORDER BY id")
    latest: dict[tuple[int, str], sqlite3.Row] = {}
    for r in rows:
        latest[(int(r["migrationId"]), str(r["driveInfo"]))] = r
    return [ThroughputPoint(
        kind="drive", migration_id=mid, drive=drive,
        transferred=int(r["completedTransferSizePerDrive"] or 0), total=int(r["totalTransferSizePerDrive"] or 0),
        already_existing=int(r["alreadyExistingSizePerDrive"] or 0),
        files_copied=int(r["FilesCopiedPerDrive"] or 0), files_failed=int(r["FailedFilesPerDrive"] or 0),
        files_existing=int(r["AlreadyExistingFilesPerDrive"] or 0))
        for (mid, drive), r in sorted(latest.items())]


def read_throughput(db_path: Path | None, log_path: Path | Iterable[Path] | None) -> list[ThroughputPoint]:
    """rclone speed series from the log(s) (empty when there are none) followed by the per-drive
    rows from CDM.db (skipped when db_path is None). log_path accepts one path or several -- a
    run's transfer log can rotate mid-run (or by the time of a later re-harvest), splitting its
    real lines across more than one *FileTransfer*.log* file; see paths.find_rclone_logs."""
    points: list[ThroughputPoint] = []
    paths_ = [log_path] if isinstance(log_path, (str, Path)) else list(log_path or [])
    for p in paths_:
        if p is not None and Path(p).is_file():
            with Path(p).open(encoding="utf-8", errors="replace") as fh:
                points += parse_rclone_log(fh)
    if db_path is not None:
        points += read_drive_stats(db_path)
    return points


# --------------------------------------------------------------------- file counts

_BUCKETS: list[tuple[tuple[str, ...], str]] = [
    (("permission", "access is denied", "access denied", "denied"), "Permission denied"),
    (("in use", "being used", "locked", "sharing violation"), "File in use"),
    (("too long",), "Path too long"),
    (("network", "connection", "connectivity", "timed out", "timeout"), "Network / connection"),
    (("external drive", "volume", "device", "diskette", "filename, directory name"), "Drive removed"),
    (("disk space", "not enough space", "no space"), "Disk full"),
]


def bucket_skip_reason(reason: str | None, error_code: int | None = None) -> str:
    text = (reason or "").strip().lower()
    if not text:
        return f"Error code {error_code}" if error_code else "Other"
    for needles, label in _BUCKETS:
        if any(n in text for n in needles):
            return label
    return "Other"


def read_file_counts(db_path: Path) -> dict[int, FileCounts]:
    """MigrationFileCount (latest row per id) + skip-reason histogram from FileTransferResults,
    keyed by MigrationId. Empty tables give an empty dict (callers treat missing as zeros)."""
    out: dict[int, FileCounts] = {}
    for r in _rows(db_path, "SELECT * FROM MigrationFileCount ORDER BY id"):
        out[int(r["migrationId"])] = FileCounts(
            success=int(r["successFilesCount"] or 0), backedup=int(r["backedupFilesCount"] or 0),
            skipped=int(r["skippedFilesCount"] or 0), already_existing=int(r["alreadyExistingFilesCount"] or 0))
    hist: dict[int, Counter] = {}
    for r in _rows(db_path, "SELECT migrationId, skippingReason, errorCode FROM FileTransferResults "
                            "WHERE isSkipped = 1"):
        hist.setdefault(int(r["migrationId"]), Counter())[bucket_skip_reason(r["skippingReason"], r["errorCode"])] += 1
    for mid, counter in hist.items():
        fc = out.setdefault(mid, FileCounts())
        fc.skip_reasons = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return out


# --------------------------------------------------------------------- tuning (Plane D)

TUNING_SPEC: list[tuple[str, str, str, str]] = [
    ("FileTransferUtilParallelTransferCount", "--transfers", "Number of files copied in parallel", "4"),
    ("FileTransferUtilMultiThreadStreamCount", "--multi-thread-streams", "Parallel streams used per large file", "0"),
    ("FileTransferUtilLargeFileThreshold", "--multi-thread-cutoff", "File size treated as large", "1024M"),
    ("FileTransferUtilBandwidthLimit", "--bwlimit", "Cap on network speed (0 = unlimited)", "0"),
    ("FileTransferUtilMaxBacklog", "--max-backlog", "How many items can queue up", "102400"),
    ("FileTransferUtilStatsDurationMillis", "--stats", "How often progress is reported (ms)", "5000"),
    ("FileTransferUtilLowLevelRetriesNewPC", "--low-level-retries", "Block-level retry count", "3"),
    ("FileTransferUtilHighLevelRetriesNewPC", "--retries", "Whole-file retry count", "1"),
]


def read_tuning(config_path: Path | None, cpu_count: int | None = None) -> Tuning:
    """Plane D: the engine's rclone settings. Defaults are the CdmConfiguration.cs defaults and are
    flagged as such. --transfers is overridden at runtime by the CPU count (capped at 8)."""
    values: dict[str, str] = {}
    note_src = "defaults (engine config not found)"
    from_defaults = True
    if config_path is not None and Path(config_path).is_file():
        try:
            root = ET.parse(config_path).getroot()
            for add in root.iter("add"):
                key, val = add.get("key"), add.get("value")
                if key and val is not None:
                    values[key] = val
            from_defaults = False
            note_src = str(config_path)
        except ET.ParseError:
            note_src = f"defaults (could not parse {config_path})"
    cores = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    rows: list[TuningRow] = []
    for key, flag, desc, default in TUNING_SPEC:
        value = values.get(key)
        note = "" if value is not None else ("default" if not from_defaults else "default (no config read)")
        shown = value if value is not None else default
        if flag == "--transfers":
            effective = min(max(cores, 1), 8)
            note = f"runtime override: CPU count ({cores}) capped at 8; config value {shown} is not used"
            shown = f"{effective} (CPU count)"
        rows.append(TuningRow(flag, desc, shown, note))
    return Tuning(rows=rows, from_defaults=from_defaults, source=note_src)


# --------------------------------------------------------------------- orchestration

def harvest_run(run_id: str, role: str, out_dir: Path, env: Mapping[str, str] | None = None, *,
                db_path: Path | None = None, log_path: Path | None = None,
                config_path: Path | None = None) -> RunReport:
    """Gather every plane into a RunReport. Never raises for a missing/locked source: the
    corresponding plane is left empty and a banner explains why."""
    report = RunReport(run_id=run_id, role=role, generated=datetime.now())
    meta, samples = read_samples(Path(out_dir) / f"resources_{role}.jsonl")
    report.meta, report.samples = meta, samples
    if not samples:
        report.banners.append("No resource samples were captured (the sampler did not run or wrote nothing); "
                              "resource tabs are empty.")

    windows: list[Episode] = []
    drive_points: list[ThroughputPoint] = []
    counts: dict[int, FileCounts] = {}
    try:
        db = db_path or paths.find_cdm_db(env)
        run_start = parse_ts(meta.get("start_wall"))
        run_end = max((s.ts_wall for s in samples), default=None)
        windows = expand_segments(scope_to_run(read_episodes(db), run_start, run_end))
        drive_points = read_drive_stats(db)
        counts = read_file_counts(db)
        report.has_db = True
    except (paths.CdmDbNotFound, CdmDbError) as exc:
        report.banners.append(f"CDM.db unavailable ({exc}); showing a resource-only report.")
        logger.warning(f"benchmark: {exc}")

    try:
        log = log_path if log_path is not None else paths.find_rclone_logs(env)
        if log:
            report.rclone = read_throughput(None, log)
            report.has_rclone_log = bool(report.rclone)
    except OSError as exc:  # a protected/unreadable log dir must not sink the whole report
        logger.warning(f"benchmark: could not read the transfer log: {exc}")
    if not report.has_rclone_log:
        report.banners.append("No transfer log found (or it had no progress lines); throughput tab is empty.")

    try:
        cfg = config_path if config_path is not None else paths.find_engine_config(env)
    except OSError as exc:
        logger.warning(f"benchmark: could not read the engine config: {exc}")
        cfg = None
    report.tuning = read_tuning(cfg)
    if report.tuning.from_defaults:
        report.banners.append("Engine config not read; transfer settings shown are defaults, not confirmed values.")

    assign_samples_to_episodes(samples, windows)
    for ep in windows:
        ep.rclone = [p for p in report.rclone if p.ts is not None and ep.start <= p.ts <= ep.end]
        ep.drive_stats = [d for d in drive_points if d.migration_id == ep.migration_id]
        ep.file_counts = counts.get(ep.migration_id)
    report.episodes = windows
    return report

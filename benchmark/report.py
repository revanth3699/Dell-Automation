"""Render one HTML report per run: the report_template.html layout (ported from
sample_report.html) with a window.__BENCHMARK__ payload -- one view per episode plus a
whole-run rollup -- injected in place of the template's placeholder. The page's episode
selector swaps the active view client-side."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmark import correlate, paths
from benchmark.harvest import parse_runtime
from benchmark.models import Episode, RunReport, Sample

TEMPLATE = Path(__file__).resolve().parent / "report_template.html"
PLACEHOLDER = "/*__BENCHMARK_DATA__*/"
MB = 1024 * 1024
GB = 1024 ** 3
MAX_POINTS = 120

PROC_INFO = {
    "DellDataManager": ("DellDataManager (engine)", "coordinates the whole migration."),
    "DellFileTransferUtil": ("DellFileTransferUtil / rclone", "the program that actually copies the files."),
    "MyDellExperience": ("App window (UI)", "the screen the user sees."),
    "Everything": ("Everything", "scans and lists the files before copying."),
}
PROC_ORDER = ["DellDataManager", "DellFileTransferUtil", "MyDellExperience", "Everything"]


def reconciled_run_seconds(run_time: str | None, window_seconds: float) -> float:
    """MigrationStatus.runTime, parsed, but ONLY when it roughly agrees with the episode's own
    [start, end] window -- otherwise the "Total migration time" tile's headline value could
    contradict the window shown right below it in the same tile's description. Confirmed via a
    synthetic 40GB-scale stress test (2026-10-22): every real runTime seen this session has been
    an unparseable bare integer (no colons), so this path has never actually fired against real
    data -- a validly-formatted but wildly different runTime (e.g. "02:14:00" against a real
    37-minute window) rendered as a visibly self-contradictory tile. Tolerance is the larger of
    60s or 10% of the window, to allow for rounding without masking a genuine mismatch."""
    parsed = parse_runtime(run_time)
    if parsed is None:
        return window_seconds
    if window_seconds > 0 and abs(parsed - window_seconds) <= max(60.0, 0.1 * window_seconds):
        return parsed
    return window_seconds


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    s = round(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m {sec:02d}s" if h else (f"{m}m {sec:02d}s" if m else f"{sec}s")


def _bucketize(points: list[tuple[float, float]], width: float, count: int) -> list[float | None]:
    sums, counts = [0.0] * count, [0] * count
    for t, v in points:
        i = min(count - 1, max(0, int(t // width)))
        sums[i] += v
        counts[i] += 1
    return [round(sums[i] / counts[i], 2) if counts[i] else None for i in range(count)]


def _proc_series(samples: list[Sample], start: datetime, width: float, count: int,
                 value: Callable[[Sample], float | None]) -> dict[str, list[float | None]]:
    """Per process name: mean per pid per bucket, summed across pids (rclone restarts/workers)."""
    cells: dict[tuple[str, int, int], list[float]] = {}
    for s in samples:
        if s.scope != "process":
            continue
        v = value(s)
        if v is None:
            continue
        i = min(count - 1, max(0, int((s.ts_wall - start).total_seconds() // width)))
        cells.setdefault((s.name, i, s.pid or 0), []).append(v)
    out: dict[str, list[float | None]] = {}
    for (name, i, _pid), vals in cells.items():
        row = out.setdefault(name, [None] * count)
        row[i] = round((row[i] or 0.0) + sum(vals) / len(vals), 2)
    return out


def _system_series(samples: list[Sample], start: datetime, width: float, count: int,
                   value: Callable[[Sample], float | None]) -> list[float | None]:
    pts = [((s.ts_wall - start).total_seconds(), v) for s in samples
           if s.scope == "system" and (v := value(s)) is not None]
    return _bucketize(pts, width, count)


def _phases_for(ep: Episode, report: RunReport) -> list[list[Any]]:
    if ep.kind == "rollup":
        totals: dict[str, list[Any]] = {}
        for e in report.episodes:
            for p in e.phases:
                row = totals.setdefault(p.name, [p.name, 0.0, _phase_kind(p)])
                row[1] += p.seconds
        rows = list(totals.values())
    else:
        rows = [[p.name, p.seconds, _phase_kind(p)] for p in ep.phases]
    return [[n, round(s, 1), k] for n, s, k in rows]


def _phase_kind(p) -> str:
    return "x" if p.is_transfer else ("e" if p.estimated else "m")


def build_view(ep: Episode, report: RunReport) -> dict[str, Any]:
    seconds = max(ep.seconds, 1.0)
    width = max(1.0, seconds / MAX_POINTS)
    count = max(1, math.ceil(seconds / width))
    labels = [f"{i * width / 60:.1f}m" for i in range(count)]
    empty: dict[str, str | None] = {}

    # throughput + ETA
    inst: list[tuple[float, float]] = []
    eta: list[tuple[float, float]] = []
    for p in ep.rclone:
        if p.ts is None or p.speed_bps is None:
            continue
        t = (p.ts - ep.start).total_seconds()
        inst.append((t, p.speed_bps / MB))
        if p.eta_s is not None:
            eta.append((t, p.eta_s / 60))
    instant = _bucketize(inst, width, count)
    running, seen, avg = 0.0, 0, []
    for v in instant:
        if v is not None:
            running, seen = running + v, seen + 1
        avg.append(round(running / seen, 2) if seen else None)
    thr = {"instant": instant, "avg": avg, "eta": _bucketize(eta, width, count)}
    empty["thr"] = None if inst else "No transfer log found for this window (no rclone progress lines)."

    # resources
    samples = ep.samples
    has_samples = any(s.scope == "system" for s in samples)
    msg = None if has_samples else "No resource samples overlap this window."
    names = sorted({s.name for s in samples if s.scope == "process"},
                   key=lambda n: (PROC_ORDER.index(n) if n in PROC_ORDER else len(PROC_ORDER), n))
    procs = [{"name": n, "label": PROC_INFO.get(n, (n, "tracked process."))[0],
              "desc": PROC_INFO.get(n, (n, "tracked process."))[1]} for n in names]
    sys_cpu = _system_series(samples, ep.start, width, count, lambda s: s.cpu_pct)
    res = {
        "cpu": {"procs": _proc_series(samples, ep.start, width, count, lambda s: s.cpu_pct), "system": sys_cpu},
        "mem": {"procs": _proc_series(samples, ep.start, width, count, lambda s: s.rss_mb)},
        "disk": {"procs": _proc_series(samples, ep.start, width, count,
                                       lambda s: (s.disk_read_mbps or 0.0) + (s.disk_write_mbps or 0.0)),
                 "system": _system_series(samples, ep.start, width, count,
                                          lambda s: (s.disk_read_mbps or 0.0) + (s.disk_write_mbps or 0.0))},
        "net": {"recv": _system_series(samples, ep.start, width, count, lambda s: s.net_recv_mbps),
                "sent": _system_series(samples, ep.start, width, count, lambda s: s.net_sent_mbps)},
    }
    for tab in ("cpu", "mem", "disk", "net"):
        empty[tab] = msg

    # phases / drives / files / skips
    phases = _phases_for(ep, report)
    if phases:
        empty["phase"] = None
    elif not report.has_db:
        empty["phase"] = "No phase timing available (CDM.db not read)."
    else:
        # has_db is True -- CDM.db was read fine, there's just no migration overlapping this
        # window. The old message always blamed "CDM.db not read" regardless of which was true,
        # which actively misleads someone debugging an empty phase tab on an otherwise-working run.
        empty["phase"] = "No phase timing available for this window (no migration recorded here)."
    # already_existing is NOT part of `total` -- confirmed live (2026-10-22): already_existing is
    # consistently 10-20x larger than total across every migration checked (it's a cumulative
    # figure for this destination drive, not this session's selected set), so `total -
    # transferred - already_existing` was always a large negative number silently clamped to 0.
    # `total` instead behaves like "bytes this session attempted" (roughly completed + failed),
    # so remaining/failed is `total - transferred` alone.
    drives = {"labels": [d.drive for d in ep.drive_stats],
              "copied": [round(d.transferred / GB, 2) for d in ep.drive_stats],
              "existed": [round(d.already_existing / GB, 2) for d in ep.drive_stats],
              "rem": [round(max(0, d.total - d.transferred) / GB, 2) for d in ep.drive_stats]}
    empty["drive"] = None if ep.drive_stats else "No per-drive statistics (RealTimeTransferStatistics is empty)."
    fc = ep.file_counts
    files = {"labels": ["Copied", "Already existed", "Skipped", "Backed up"],
             "values": [fc.success, fc.already_existing, fc.skipped, fc.backedup] if fc else []}
    empty["files"] = None if fc else "No file counts (MigrationFileCount is empty)."
    skips = {"labels": [r for r, _ in (fc.skip_reasons if fc else [])][:10],
             "v": [n for _, n in (fc.skip_reasons if fc else [])][:10]}
    empty["skip"] = None if skips["labels"] else "No skipped files recorded."

    # overview
    prof = ep.profile
    run_seconds = reconciled_run_seconds(ep.run_time, ep.seconds)
    peak_speed = max((v for _, v in inst), default=None)
    avg_speed = prof.effective_mbps if prof and prof.effective_mbps else None
    tiles = [
        {"l": "Total migration time", "v": fmt_duration(run_seconds),
         "d": f"{ep.start:%d %b %H:%M:%S} to {ep.end:%H:%M:%S}"},
        {"l": "Data moved", "v": f"{ep.bytes_moved / GB:.1f} GB" if ep.drive_stats else "n/a",
         # total can be smaller than transferred for a small fraction of real migrations (confirmed
         # live 2026-10-22: 4 of 173 drive rows checked, one by 672 MB) -- clamp the shown
         # denominator so the tile never reads as "moved more than attempted", which is impossible
         # to make sense of regardless of what `total` actually means.
         "d": f"of {max(ep.bytes_selected, ep.bytes_moved) / GB:.1f} GB attempted this session"
              if ep.drive_stats else "no drive statistics"},
        {"l": "Avg throughput", "v": f"{avg_speed:.1f} MB/s" if avg_speed else "n/a",
         "d": f"peak {peak_speed:.1f} MB/s" if peak_speed else "no transfer log"},
        {"l": "Files copied", "v": f"{fc.success:,}" if fc else "n/a", "d": f"{fc.skipped:,} skipped" if fc else ""},
    ]
    busy = []
    if prof and prof.sufficient:
        busy = [{"key": k, "label": correlate.RESOURCE_LABEL[k], "avg": b.avg_pct, "peak": b.peak_pct,
                 "mode": b.mode_label} for k, b in prof.busy.items()]
    verdict = ep.verdict
    return {
        "id": ep.index, "label": ep.label, "kind": ep.kind, "migration_id": ep.migration_id,
        "window": {"start": ep.start.isoformat(timespec="seconds"), "end": ep.end.isoformat(timespec="seconds")},
        "tiles": tiles, "busy": busy,
        "verdict": {"kind": verdict.bottleneck, "text": verdict.text} if verdict else None,
        "labels": labels, "thr": thr, "res": res, "procs": procs, "phases": phases, "drives": drives,
        "files": files, "skips": skips, "empty": empty,
        "info": {"from": ep.migrated_from, "to": ep.migrated_to, "network": ep.network},
    }


def build_payload(report: RunReport) -> dict[str, Any]:
    if report.rollup is None:
        correlate.annotate(report)
    first = report.episodes[0] if report.episodes else None
    parts = [f"Run {report.run_id}", f"role {report.role}"]
    if first and (first.migrated_from or first.migrated_to):
        parts.append(f"{first.migrated_from or '?'} to {first.migrated_to or '?'}")
    if first and first.network:
        parts.append(f"network {first.network}")
    parts.append(f"{report.generated:%d %b %Y}")
    return {
        "run_id": report.run_id, "role": report.role, "sub": " | ".join(parts),
        "banners": list(report.banners),
        "rollup": build_view(report.rollup, report),
        "episodes": [build_view(e, report) for e in report.episodes],
        "tuning": {"rows": [[r.flag, r.description, r.value, r.note] for r in report.tuning.rows],
                   "from_defaults": report.tuning.from_defaults, "source": report.tuning.source},
    }


def render(report: RunReport, out_html: Path | None = None) -> Path:
    """Write the report HTML and return its path (default benchmark/output/<run_id>/report_<role>.html)."""
    payload = build_payload(report)
    blob = json.dumps(payload, separators=(",", ":"), allow_nan=False, default=str)
    blob = blob.replace("</", "<\\/").replace("<!--", "<\\!--")
    html = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise ValueError(f"template {TEMPLATE} has no {PLACEHOLDER} placeholder")
    html = html.replace(PLACEHOLDER, f"window.__BENCHMARK__ = {blob};", 1)
    out = Path(out_html) if out_html else paths.output_dir(report.run_id) / f"report_{report.role}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out

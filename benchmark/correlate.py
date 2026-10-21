"""Join resources + throughput + phases into per-episode metrics and a bottleneck verdict.

% busy ceilings: CPU is already a percentage (ceiling 100, absolute). Disk and network are
RELATIVE by default (the peak observed anywhere in the run = 100%, no config needed) and
switch to ABSOLUTE when DDA_BENCHMARK_DISK_MBPS (MB/s) / DDA_BENCHMARK_LINK_MBPS (megabits/s,
converted to MB/s) is set. Each bar carries a mode label so the report says which it is.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from benchmark.models import (Episode, FileCounts, PhaseSpan, ResourceBusy, ResourceProfile,
                              RunReport, Sample, Verdict)

MIN_SAMPLES = 3            # system samples needed in the transfer window
SUSTAINED_BUSY_PCT = 70.0  # a resource must average at least this busy to be called the bottleneck
BALANCE_MARGIN_PCT = 10.0  # runner-up within this many points of the leader -> no single bottleneck
RESOURCE_LABEL = {"cpu": "CPU", "disk": "new-PC disk", "network": "network"}
BOTTLENECK_NAME = {"cpu": "CPU-bound", "disk": "disk-bound", "network": "network-bound"}


def ceilings_from_env(env: Mapping[str, str]) -> tuple[float | None, float | None]:
    """(link_mbps in megabits/s, disk_mbps in MB/s); unset/invalid/non-positive -> None."""
    def num(key: str) -> float | None:
        try:
            value = float(env.get(key, ""))
        except ValueError:
            return None
        return value if value > 0 else None
    return num("DDA_BENCHMARK_LINK_MBPS"), num("DDA_BENCHMARK_DISK_MBPS")


def transfer_windows(episode: Episode) -> list[tuple[datetime, datetime]]:
    """The File transfer phase span(s); the whole episode window when no phase is known."""
    spans = [(p.start, p.end) for p in episode.phases if p.is_transfer and p.end > p.start]
    return spans or [(episode.start, episode.end)]


def _system_series(samples: list[Sample], windows: list[tuple[datetime, datetime]]) -> dict[str, list[float]]:
    series: dict[str, list[float]] = {"cpu": [], "disk": [], "network": []}
    for s in samples:
        if s.scope != "system" or not any(a <= s.ts_wall <= b for a, b in windows):
            continue
        series["cpu"].append(s.cpu_pct or 0.0)
        series["disk"].append((s.disk_read_mbps or 0.0) + (s.disk_write_mbps or 0.0))
        series["network"].append((s.net_sent_mbps or 0.0) + (s.net_recv_mbps or 0.0))
    return series


def _peak(samples: list[Sample], key: str) -> float:
    vals = []
    for s in samples:
        if s.scope != "system":
            continue
        if key == "disk":
            vals.append((s.disk_read_mbps or 0.0) + (s.disk_write_mbps or 0.0))
        else:
            vals.append((s.net_sent_mbps or 0.0) + (s.net_recv_mbps or 0.0))
    return max(vals, default=0.0)


def resource_profile(episode: Episode, *, link_mbps: float | None = None, disk_mbps: float | None = None,
                     peak_samples: list[Sample] | None = None, min_samples: int = MIN_SAMPLES) -> ResourceProfile:
    """Avg/peak % busy of CPU, disk and network during the episode's transfer window plus the
    effective throughput (bytes moved / transfer seconds). Too few samples -> insufficient."""
    windows = transfer_windows(episode)
    seconds = sum((b - a).total_seconds() for a, b in windows)
    series = _system_series(episode.samples, windows)
    count = len(series["cpu"])
    effective = (episode.bytes_moved / seconds / (1024 * 1024)) if seconds > 0 and episode.bytes_moved else None
    if count < min_samples:
        return ResourceProfile(False, f"only {count} resource sample(s) overlap the transfer window "
                                      f"(need {min_samples})", count, seconds, {}, effective)
    pool = peak_samples if peak_samples is not None else episode.samples
    ceilings: dict[str, tuple[float, str, str]] = {"cpu": (100.0, "absolute", "of 100% CPU")}
    for key, override, observed_key in (("disk", disk_mbps, "disk"),
                                        ("network", link_mbps / 8 if link_mbps else None, "network")):
        if override:
            ceilings[key] = (override, "absolute", f"of {override:.0f} MB/s ceiling")
        else:
            ceilings[key] = (_peak(pool, observed_key), "relative", "relative to observed peak")
    busy: dict[str, ResourceBusy] = {}
    for key, values in series.items():
        ceiling, mode, label = ceilings[key]
        avg, peak = sum(values) / len(values), max(values)
        pct = (lambda v: min(100.0, v / ceiling * 100.0) if ceiling > 0 else 0.0)
        busy[key] = ResourceBusy(round(pct(avg), 1), round(pct(peak), 1), round(avg, 2), round(peak, 2),
                                 "%" if key == "cpu" else "MB/s", mode, ceiling, label)
    return ResourceProfile(True, "", count, seconds, busy, effective)


def bottleneck_verdict(profile: ResourceProfile) -> Verdict:
    """Deterministic rule: the resource with the highest average % busy during transfer is the
    bottleneck if it averages at least SUSTAINED_BUSY_PCT and leads the runner-up by more than
    BALANCE_MARGIN_PCT; otherwise there is no clear bottleneck."""
    if not profile.sufficient:
        return Verdict("insufficient", f"Insufficient data to name a bottleneck: {profile.reason}.")
    ranked = sorted(profile.busy.items(), key=lambda kv: (-kv[1].avg_pct, kv[0]))
    top_key, top = ranked[0]
    others = [f"{RESOURCE_LABEL[k]} {b.avg_pct:.0f}%" for k, b in ranked[1:]]
    relative = any(b.mode == "relative" for b in profile.busy.values())
    suffix = (" (disk and network are relative to the observed peak; set DDA_BENCHMARK_LINK_MBPS / "
              "DDA_BENCHMARK_DISK_MBPS for absolute ceilings.)") if relative else ""
    if top.avg_pct < SUSTAINED_BUSY_PCT:
        return Verdict("none", f"No clear bottleneck: the busiest resource, {RESOURCE_LABEL[top_key]}, "
                               f"averaged only {top.avg_pct:.0f}% busy during transfer.{suffix}")
    runner_up = ranked[1][1]
    if top.avg_pct - runner_up.avg_pct <= BALANCE_MARGIN_PCT and runner_up.avg_pct >= SUSTAINED_BUSY_PCT:
        return Verdict("none", f"No clear bottleneck: {RESOURCE_LABEL[top_key]} ({top.avg_pct:.0f}%) and "
                               f"{RESOURCE_LABEL[ranked[1][0]]} ({runner_up.avg_pct:.0f}%) were both heavily "
                               f"busy during transfer.{suffix}")
    return Verdict(top_key, f"{RESOURCE_LABEL[top_key]} averaged {top.avg_pct:.0f}% busy "
                            f"(peak {top.peak_pct:.0f}%) during transfer while {', '.join(others)} "
                            f"-> {BOTTLENECK_NAME[top_key]}.{suffix}")


def build_rollup(report: RunReport) -> Episode:
    """The 'whole run' pseudo-episode (index 0): every sample, every transfer window, summed counts."""
    eps = report.episodes
    times = [s.ts_wall for s in report.samples] + [t for e in eps for t in (e.start, e.end)]
    start, end = (min(times), max(times)) if times else (report.generated, report.generated)
    phases: list[PhaseSpan] = []
    for e in eps:
        phases += [p for p in e.phases if p.is_transfer]
    counts: FileCounts | None = None
    seen: set[int | None] = set()
    reasons: dict[str, int] = {}
    drives = []
    for e in eps:
        if e.migration_id in seen:
            continue                      # in-app Retry shares its MigrationId's totals
        seen.add(e.migration_id)
        drives += e.drive_stats
        if e.file_counts:
            counts = counts or FileCounts()
            counts.success += e.file_counts.success
            counts.backedup += e.file_counts.backedup
            counts.skipped += e.file_counts.skipped
            counts.already_existing += e.file_counts.already_existing
            for reason, n in e.file_counts.skip_reasons:
                reasons[reason] = reasons.get(reason, 0) + n
    if counts:
        counts.skip_reasons = sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))
    return Episode(index=0, kind="rollup", label="Whole run", migration_id=None, start=start, end=end,
                   phases=phases, samples=list(report.samples), rclone=list(report.rclone),
                   drive_stats=drives, file_counts=counts)


def annotate(report: RunReport, env: Mapping[str, str] | None = None) -> RunReport:
    """Fill profile + verdict on every episode and on the whole-run rollup (report.rollup)."""
    import os
    link, disk = ceilings_from_env(os.environ if env is None else env)
    report.rollup = build_rollup(report)
    for ep in [*report.episodes, report.rollup]:
        ep.profile = resource_profile(ep, link_mbps=link, disk_mbps=disk, peak_samples=report.samples or None)
        ep.verdict = bottleneck_verdict(ep.profile)
    return report

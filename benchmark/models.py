"""Plain dataclasses shared by the sampler, harvester, correlator and report."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class Sample:
    """One resource-sampler record (one JSONL line). scope is 'process' or 'system'."""
    ts_wall: datetime
    ts_mono: float
    scope: str
    name: str = "system"
    pid: int | None = None
    cpu_pct: float | None = None
    rss_mb: float | None = None
    disk_read_mbps: float | None = None
    disk_write_mbps: float | None = None
    threads: int | None = None
    handles: int | None = None
    mem_used_mb: float | None = None
    net_sent_mbps: float | None = None
    net_recv_mbps: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], parse_ts) -> "Sample | None":
        ts = parse_ts(data.get("ts_wall"))
        if ts is None or data.get("scope") not in ("process", "system"):
            return None
        fields = {k: data.get(k) for k in (
            "pid", "cpu_pct", "rss_mb", "disk_read_mbps", "disk_write_mbps", "threads",
            "handles", "mem_used_mb", "net_sent_mbps", "net_recv_mbps")}
        return cls(ts_wall=ts, ts_mono=float(data.get("ts_mono") or 0.0), scope=data["scope"],
                   name=str(data.get("name") or "system"), **fields)

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["ts_wall"] = self.ts_wall.isoformat(timespec="milliseconds")
        return {k: v for k, v in out.items() if v is not None}


@dataclass
class ThroughputPoint:
    """kind 'rclone': one --stats-one-line sample. kind 'drive': latest per-drive row of
    RealTimeTransferStatistics (that table has no timestamp column)."""
    kind: str
    ts: datetime | None = None
    migration_id: int | None = None
    drive: str | None = None
    transferred: int = 0          # bytes (rclone: transferred so far; drive: completed)
    total: int = 0                # bytes
    percent: float | None = None
    speed_bps: float | None = None
    eta_s: float | None = None
    xfr_n: int | None = None
    xfr_m: int | None = None
    errors: int = 0               # cumulative ERROR lines seen in the log so far
    already_existing: int = 0     # drive rows: bytes already on the new PC
    files_copied: int = 0
    files_failed: int = 0
    files_existing: int = 0


@dataclass
class PhaseSpan:
    name: str
    start: datetime
    end: datetime
    estimated: bool = False
    is_transfer: bool = False

    @property
    def seconds(self) -> float:
        return max(0.0, (self.end - self.start).total_seconds())


@dataclass
class Segment:
    start: datetime
    end: datetime


@dataclass
class FileCounts:
    success: int = 0
    backedup: int = 0
    skipped: int = 0
    already_existing: int = 0
    skip_reasons: list[tuple[str, int]] = field(default_factory=list)   # ranked, desc


@dataclass
class ResourceBusy:
    avg_pct: float
    peak_pct: float
    avg_value: float
    peak_value: float
    unit: str
    mode: str                      # 'absolute' | 'relative'
    ceiling: float | None
    mode_label: str


@dataclass
class ResourceProfile:
    sufficient: bool
    reason: str = ""
    sample_count: int = 0
    transfer_seconds: float = 0.0
    busy: dict[str, ResourceBusy] = field(default_factory=dict)   # cpu / disk / network
    effective_mbps: float | None = None


@dataclass
class Verdict:
    bottleneck: str                # disk | network | cpu | none | insufficient
    text: str


@dataclass
class Episode:
    index: int                     # 1-based; 0 is the whole-run rollup
    kind: str                      # primary | retry | try_again | rollup
    label: str
    migration_id: int | None
    start: datetime
    end: datetime
    run_time: str | None = None
    migrated_from: str | None = None
    migrated_to: str | None = None
    network: str | None = None
    segments: list[Segment] = field(default_factory=list)
    audits: list[tuple[str, datetime]] = field(default_factory=list)   # (status, ts) from MigrationStatusAudit
    phases: list[PhaseSpan] = field(default_factory=list)
    samples: list[Sample] = field(default_factory=list)
    rclone: list[ThroughputPoint] = field(default_factory=list)
    drive_stats: list[ThroughputPoint] = field(default_factory=list)
    file_counts: FileCounts | None = None
    profile: ResourceProfile | None = None
    verdict: Verdict | None = None

    @property
    def seconds(self) -> float:
        return max(0.0, (self.end - self.start).total_seconds())

    @property
    def bytes_moved(self) -> int:
        return sum(d.transferred for d in self.drive_stats)

    @property
    def bytes_selected(self) -> int:
        return sum(d.total for d in self.drive_stats)


@dataclass
class TuningRow:
    flag: str
    description: str
    value: str
    note: str = ""


@dataclass
class Tuning:
    rows: list[TuningRow] = field(default_factory=list)
    from_defaults: bool = True
    source: str = ""


@dataclass
class RunReport:
    run_id: str
    role: str
    generated: datetime
    episodes: list[Episode] = field(default_factory=list)
    samples: list[Sample] = field(default_factory=list)
    rclone: list[ThroughputPoint] = field(default_factory=list)
    tuning: Tuning = field(default_factory=Tuning)
    meta: dict[str, Any] = field(default_factory=dict)
    banners: list[str] = field(default_factory=list)
    has_db: bool = False
    has_rclone_log: bool = False
    rollup: Episode | None = None

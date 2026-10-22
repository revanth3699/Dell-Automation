"""OS resource sampler -- runs as its own subprocess (python -m benchmark.resource_sampler).

A separate process (not a thread) keeps the cadence steady while the main process is busy
driving WinAppDriver. Each tick it writes one JSONL line per matched process plus one
system-wide line to resources_<role>.jsonl; the first line is a meta record.

Units: MB = MiB (1024*1024 bytes); *_mbps are MB per second (not megabits). Process cpu_pct
is normalised to whole-machine percent (psutil's per-core figure divided by the CPU count)
so every cpu_pct is 0-100. Timestamps in ts_wall are local naive ISO strings (the same
convention CDM.db uses) -- see harvest.parse_ts.

Pure helpers (compute_rate, match_processes, sample_process, sample_system) are separate
from the loop so they can be unit-tested with fake process objects.
"""

from __future__ import annotations

import argparse
import json
import signal
import socket
import sys
import time
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from loguru import logger

MB = 1024 * 1024
_PROC_ERRORS = (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess)


# --------------------------------------------------------------------- pure helpers

def compute_rate(prev_bytes: float | None, cur_bytes: float, elapsed_s: float) -> float:
    """Counter delta -> MB/s. No previous sample, zero/negative elapsed, or a counter that
    went backwards (reset / wrap) all yield 0.0 rather than an error or a negative rate."""
    if prev_bytes is None or elapsed_s <= 0:
        return 0.0
    delta = cur_bytes - prev_bytes
    if delta < 0:
        return 0.0
    return delta / elapsed_s / MB


def _canonical(name: str) -> str:
    name = name.lower()
    return name.removesuffix(".exe")


def _proc_name(proc: Any) -> str | None:
    try:
        info = getattr(proc, "info", None)
        if info and info.get("name"):
            return str(info["name"])
        return str(proc.name())
    except _PROC_ERRORS:
        return None


def match_processes(all_procs: Iterable[Any], names: Iterable[str]) -> list[tuple[str, Any]]:
    """(configured name, proc) for every process whose exe name matches one of `names`,
    case-insensitively and ignoring .exe. Several instances (rclone restarts, workers) all
    match; a pid is returned once."""
    wanted = {_canonical(n): n for n in names if n}
    seen: set[int] = set()
    matched: list[tuple[str, Any]] = []
    for proc in all_procs:
        name = _proc_name(proc)
        if name is None:
            continue
        configured = wanted.get(_canonical(name))
        if configured is None:
            continue
        pid = getattr(proc, "pid", None)
        if pid in seen:
            continue
        seen.add(pid)
        matched.append((configured, proc))
    return matched


def sample_process(name: str, proc: Any, prev: dict | None, ts_mono: float, ts_wall: datetime,
                   ncpu: int = 1) -> tuple[dict | None, dict | None]:
    """(record, new_state) for one process; (None, None) if it vanished or is not readable.
    `prev` is the state returned by the previous call for the same pid (or None)."""
    try:
        cpu = proc.cpu_percent(interval=None)
        rss = proc.memory_info().rss
        io = proc.io_counters()
        threads = proc.num_threads()
        try:
            handles = proc.num_handles()
        except (AttributeError, NotImplementedError):
            handles = None
        pid = proc.pid
    except _PROC_ERRORS:
        return None, None
    elapsed = ts_mono - prev["mono"] if prev else 0.0
    record = {
        "ts_wall": ts_wall.isoformat(timespec="milliseconds"), "ts_mono": round(ts_mono, 3),
        "scope": "process", "name": name, "pid": pid,
        "cpu_pct": round(min(100.0, cpu / max(1, ncpu)), 2),
        "rss_mb": round(rss / MB, 1),
        "disk_read_mbps": round(compute_rate(prev["read"] if prev else None, io.read_bytes, elapsed), 3),
        "disk_write_mbps": round(compute_rate(prev["write"] if prev else None, io.write_bytes, elapsed), 3),
        "threads": threads, "handles": handles,
    }
    return record, {"mono": ts_mono, "read": io.read_bytes, "write": io.write_bytes}


def read_system_counters(ts_mono: float, psutil_mod: Any = psutil) -> dict:
    disk = psutil_mod.disk_io_counters()
    net = psutil_mod.net_io_counters()
    return {
        "mono": ts_mono,
        "cpu_pct": psutil_mod.cpu_percent(interval=None),
        "mem_used_mb": psutil_mod.virtual_memory().used / MB,
        "disk_read": disk.read_bytes if disk else 0, "disk_write": disk.write_bytes if disk else 0,
        "net_sent": net.bytes_sent if net else 0, "net_recv": net.bytes_recv if net else 0,
    }


def sample_system(prev: dict | None, now: dict, ts_wall: datetime) -> dict:
    """System-scope record from two counter snapshots (prev may be None on the first tick)."""
    elapsed = now["mono"] - prev["mono"] if prev else 0.0

    def rate(key: str) -> float:
        return round(compute_rate(prev[key] if prev else None, now[key], elapsed), 3)

    return {
        "ts_wall": ts_wall.isoformat(timespec="milliseconds"), "ts_mono": round(now["mono"], 3),
        "scope": "system", "name": "system",
        "cpu_pct": round(now["cpu_pct"], 2), "mem_used_mb": round(now["mem_used_mb"], 1),
        "disk_read_mbps": rate("disk_read"), "disk_write_mbps": rate("disk_write"),
        "net_sent_mbps": rate("net_sent"), "net_recv_mbps": rate("net_recv"),
    }


# --------------------------------------------------------------------- loop

def run_sampler(out_dir: Path, role: str, run_id: str, interval: float, stop_file: Path | None,
                names: list[str], duration: float | None = None, *,
                clock: Callable[[], float] = time.monotonic,
                sleep: Callable[[float], None] = time.sleep,
                now: Callable[[], datetime] = datetime.now,
                process_iter: Callable[[], Iterable[Any]] | None = None,
                system_counters: Callable[[float], dict] = read_system_counters,
                ncpu: int | None = None,
                should_stop: Callable[[], bool] = lambda: False) -> Path:
    """Samples until the stop file appears, should_stop() is true, or `duration` elapses.
    Returns the JSONL path. Never raises for a vanished/unreadable process."""
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / f"resources_{role}.jsonl"
    ncpu = ncpu or psutil.cpu_count() or 1
    process_iter = process_iter or (lambda: psutil.process_iter(["name"]))
    start_mono = clock()
    states: dict[int, dict] = {}
    prev_sys: dict | None = None
    with jsonl.open("w", encoding="utf-8") as fh:
        meta = {"scope": "meta", "run_id": run_id, "role": role, "interval": interval,
                "host": socket.gethostname(), "start_wall": now().isoformat(timespec="milliseconds"),
                "start_mono": round(start_mono, 3), "processes": names, "cpu_count": ncpu,
                "cpu_pct_normalized": True}
        fh.write(json.dumps(meta) + "\n")
        fh.flush()
        while True:
            tick_start = clock()
            if should_stop() or (stop_file is not None and stop_file.exists()):
                break
            if duration is not None and tick_start - start_mono >= duration:
                break
            ts_wall = now()
            live: set[int] = set()
            try:
                for name, proc in match_processes(process_iter(), names):
                    record, state = sample_process(name, proc, states.get(proc.pid), tick_start, ts_wall, ncpu)
                    if record is None:
                        continue
                    states[proc.pid] = state
                    live.add(proc.pid)
                    fh.write(json.dumps(record) + "\n")
                snap = system_counters(tick_start)
                fh.write(json.dumps(sample_system(prev_sys, snap, ts_wall)) + "\n")
                prev_sys = snap
            except Exception as exc:  # a bad tick must never kill the sampler
                logger.warning(f"benchmark sampler: tick skipped ({exc})")
            for pid in set(states) - live:
                del states[pid]
            fh.flush()
            sleep(max(0.0, interval - (clock() - tick_start)))
    return jsonl


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m benchmark.resource_sampler",
                                description="Sample OS resource usage of the migration processes to JSONL.")
    p.add_argument("--run-id", required=True)
    p.add_argument("--role", default="target", choices=["target", "source"])
    p.add_argument("--out", required=True, help="output directory (benchmark/output/<run-id>)")
    p.add_argument("--interval", type=float, default=1.0, help="seconds between ticks (default 1.0)")
    p.add_argument("--stop-file", default=None, help="exit cleanly when this file appears")
    p.add_argument("--duration", type=float, default=None, help="exit after this many seconds")
    p.add_argument("--processes", default=",".join(["MyDellExperience", "DellDataManager",
                                                    "DellFileTransferUtil", "Everything"]),
                   help="comma-separated process names (case-insensitive, .exe optional)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stopped = {"flag": False}

    def _handle(signum, _frame):
        stopped["flag"] = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle)
        except (ValueError, OSError):
            pass
    names = [n.strip() for n in args.processes.split(",") if n.strip()]
    path = run_sampler(Path(args.out), args.role, args.run_id, max(0.1, args.interval),
                       Path(args.stop_file) if args.stop_file else None, names, args.duration,
                       should_stop=lambda: stopped["flag"])
    logger.info(f"benchmark sampler finished: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

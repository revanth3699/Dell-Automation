from datetime import timedelta

import pytest

from benchmark import correlate
from benchmark.models import FileCounts, ResourceProfile, RunReport, ThroughputPoint
from benchmark.tests.helpers import T0, make_episode, steady_samples, sys_sample

MB = 1024 * 1024


def episode_with(**kw):
    return make_episode(samples=steady_samples(**kw), bytes_moved=3000 * MB)


def test_ceilings_from_env():
    assert correlate.ceilings_from_env({}) == (None, None)
    assert correlate.ceilings_from_env({"DDA_BENCHMARK_LINK_MBPS": "1000", "DDA_BENCHMARK_DISK_MBPS": "500"}) == (1000.0, 500.0)
    assert correlate.ceilings_from_env({"DDA_BENCHMARK_LINK_MBPS": "x", "DDA_BENCHMARK_DISK_MBPS": "-1"}) == (None, None)


def test_transfer_windows_phase_or_whole_episode():
    ep = make_episode()
    assert correlate.transfer_windows(ep) == [(ep.phases[0].start, ep.phases[0].end)]
    assert correlate.transfer_windows(make_episode(transfer=False)) == [(ep.start, ep.end)]


def test_profile_relative_mode_and_effective_throughput():
    ep = episode_with(cpu=40.0, disk_w=80.0, net_r=20.0)
    p = correlate.resource_profile(ep)
    assert p.sufficient and p.sample_count == 20
    assert p.busy["disk"].mode == "relative" and p.busy["disk"].avg_pct == 100.0   # steady == its own peak
    assert p.busy["cpu"].mode == "absolute" and p.busy["cpu"].avg_pct == 40.0
    assert p.busy["disk"].mode_label == "relative to observed peak"
    assert p.effective_mbps == pytest.approx(3000 / 280)                          # window is 280 s
    assert p.transfer_seconds == 280


def test_profile_absolute_with_overrides():
    ep = episode_with(cpu=40.0, disk_w=100.0, net_r=10.0, net_s=2.5)
    p = correlate.resource_profile(ep, link_mbps=1000, disk_mbps=400)
    assert p.busy["disk"].avg_pct == 25.0 and p.busy["disk"].mode == "absolute"
    assert p.busy["network"].avg_pct == 10.0                  # 12.5 MB/s of 125 MB/s
    assert p.busy["network"].mode_label == "of 125 MB/s ceiling"


def test_profile_mixed_modes():
    ep = episode_with(disk_w=50.0, net_r=10.0)
    p = correlate.resource_profile(ep, disk_mbps=100)          # network stays relative
    assert p.busy["disk"].mode == "absolute" and p.busy["network"].mode == "relative"


def test_profile_ignores_samples_outside_transfer_window():
    inside = steady_samples(n=10, cpu=90.0)
    outside = [sys_sample(T0 + timedelta(seconds=1 + i), cpu=5.0) for i in range(5)]    # before transfer starts
    p = correlate.resource_profile(make_episode(samples=outside + inside))
    assert p.sample_count == 10 and p.busy["cpu"].avg_pct == 90.0


def test_profile_peak_samples_pool_sets_relative_ceiling():
    ep = episode_with(disk_w=50.0)
    burst = [sys_sample(T0 + timedelta(seconds=5), disk_w=200.0)]
    p = correlate.resource_profile(ep, peak_samples=ep.samples + burst)
    assert p.busy["disk"].avg_pct == 25.0


def test_profile_zero_ceiling_is_zero_percent():
    p = correlate.resource_profile(episode_with(disk_w=0.0, net_r=0.0))
    assert p.busy["disk"].avg_pct == 0.0 and p.busy["network"].avg_pct == 0.0


def test_insufficient_overlap_no_invented_numbers():
    ep = make_episode(samples=steady_samples(n=2))
    p = correlate.resource_profile(ep)
    assert not p.sufficient and p.busy == {} and "only 2 resource sample" in p.reason
    v = correlate.bottleneck_verdict(p)
    assert v.bottleneck == "insufficient" and v.text.startswith("Insufficient data")
    assert correlate.resource_profile(make_episode(samples=[])).effective_mbps is None


def verdict(**kw):
    link = kw.pop("link", None)
    disk = kw.pop("disk", None)
    ep = episode_with(**kw)
    return correlate.bottleneck_verdict(correlate.resource_profile(ep, link_mbps=link, disk_mbps=disk))


def test_verdict_disk_bound():
    v = verdict(cpu=40.0, disk_w=190.0, net_r=5.0, link=1000, disk=200)
    assert v.bottleneck == "disk"
    assert v.text == ("new-PC disk averaged 95% busy (peak 95%) during transfer while CPU 40%, network 4% "
                      "-> disk-bound.")


def test_verdict_network_bound():
    v = verdict(cpu=20.0, disk_w=20.0, net_r=12.0, link=100, disk=200)
    assert v.bottleneck == "network" and v.text.endswith("-> network-bound.")
    assert v.text.startswith("network averaged 96% busy")


def test_verdict_cpu_bound():
    v = verdict(cpu=95.0, disk_w=20.0, net_r=2.0, link=1000, disk=200)
    assert v.bottleneck == "cpu"
    assert v.text == "CPU averaged 95% busy (peak 95%) during transfer while new-PC disk 10%, network 2% -> CPU-bound."


def test_verdict_low_everything_is_none():
    v = verdict(cpu=10.0, disk_w=10.0, net_r=1.0, link=1000, disk=200)
    assert v.bottleneck == "none" and "averaged only" in v.text and "CPU" in v.text


def test_verdict_balanced_is_none():
    v = verdict(cpu=20.0, disk_w=180.0, net_r=11.5, link=100, disk=200)
    assert v.bottleneck == "none" and "were both heavily busy" in v.text


def test_verdict_relative_mode_adds_hint():
    v = verdict(cpu=10.0, disk_w=10.0, net_r=1.0)
    assert "DDA_BENCHMARK_LINK_MBPS" in v.text
    assert "DDA_BENCHMARK" not in verdict(cpu=95.0, disk_w=20.0, net_r=2.0, link=1000, disk=200).text


def test_build_rollup_and_annotate():
    ep1 = episode_with(cpu=95.0, disk_w=20.0, net_r=2.0)
    ep2 = make_episode(start=T0 + timedelta(seconds=1000), samples=[], transfer=True)
    ep2.index, ep2.migration_id = 2, 2
    ep1.file_counts = FileCounts(10, 1, 2, 3, [("A", 2)])
    ep2.file_counts = FileCounts(5, 0, 1, 0, [("A", 1), ("B", 1)])
    retry = make_episode(start=T0 + timedelta(seconds=300), samples=[])
    retry.index, retry.kind = 3, "retry"
    retry.file_counts = ep1.file_counts                    # same MigrationId totals: not double counted
    report = RunReport("r", "target", T0, episodes=[ep1, ep2, retry], samples=ep1.samples)
    correlate.annotate(report, {"DDA_BENCHMARK_LINK_MBPS": "1000", "DDA_BENCHMARK_DISK_MBPS": "200"})
    roll = report.rollup
    assert roll.index == 0 and roll.kind == "rollup" and roll.file_counts.success == 15
    assert roll.file_counts.skip_reasons == [("A", 3), ("B", 1)]
    assert len(roll.phases) == 3 and roll.verdict.bottleneck == "cpu"
    assert ep2.verdict.bottleneck == "insufficient" and ep1.verdict.bottleneck == "cpu"


def test_build_rollup_rclone_scoped_to_episodes_not_whole_log():
    """rclone, like drives/counts/phases, must come from the episodes' own already time-scoped
    lists -- not report.rclone (the whole parsed log file). Confirmed live (2026-10-22): using
    report.rclone directly let a stale transfer-log line from an unrelated migration hours outside
    this run's window leak into the rollup's throughput chart and "peak" tile."""
    ep = make_episode()
    ep.rclone = [ThroughputPoint(kind="rclone", ts=T0 + timedelta(seconds=50), speed_bps=10.0)]
    stale = ThroughputPoint(kind="rclone", ts=T0 + timedelta(seconds=99999), speed_bps=999.0)
    report = RunReport("r", "target", T0, episodes=[ep], samples=[], rclone=[*ep.rclone, stale])
    roll = correlate.build_rollup(report)
    assert roll.rclone == ep.rclone


def test_build_rollup_empty_run():
    r = RunReport("r", "target", T0)
    roll = correlate.build_rollup(r)
    assert roll.start == roll.end == T0 and roll.file_counts is None
    correlate.annotate(r)
    assert r.rollup.verdict.bottleneck == "insufficient"


def test_profile_dataclass_defaults():
    assert ResourceProfile(False).busy == {}

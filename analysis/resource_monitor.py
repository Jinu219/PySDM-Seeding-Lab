from __future__ import annotations

"""Lightweight sampled process-RSS monitoring for bounded benchmark sections."""

import gc
import threading
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Dict, List


ENSEMBLE_MEMORY_COMPARISON_BUILD_ID = (
    "ensemble-memory-ab-comparison-v1-20260715"
)
ENSEMBLE_EXECUTION_BACKEND_COMPARISON_BUILD_ID = (
    "ensemble-execution-backend-ab-v1-20260715"
)

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only in minimal installations
    psutil = None


@dataclass
class ProcessRSSMonitor:
    """Sample current-process RSS in a background thread."""

    sample_interval_seconds: float = 0.02
    include_children: bool = False
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _process: Any = field(default=None, init=False)
    _rss_before: int | None = field(default=None, init=False)
    _rss_after: int | None = field(default=None, init=False)
    _peak_rss: int | None = field(default=None, init=False)
    _tree_rss_before: int | None = field(default=None, init=False)
    _tree_rss_after: int | None = field(default=None, init=False)
    _peak_tree_rss: int | None = field(default=None, init=False)
    _samples: int = field(default=0, init=False)
    _started_at: float | None = field(default=None, init=False)
    _elapsed_seconds: float = field(default=0.0, init=False)

    def __enter__(self) -> "ProcessRSSMonitor":
        self._stop_event.clear()
        self._started_at = perf_counter()
        if psutil is None:
            return self
        self._process = psutil.Process()
        self._rss_before = int(self._process.memory_info().rss)
        self._peak_rss = self._rss_before
        self._tree_rss_before = self._sample_process_tree_rss()
        self._peak_tree_rss = self._tree_rss_before
        self._samples = 1
        self._thread = threading.Thread(
            target=self._sample_loop,
            name="ensemble-rss-monitor",
            daemon=True,
        )
        self._thread.start()
        return self

    def _sample_loop(self) -> None:
        while not self._stop_event.wait(max(float(self.sample_interval_seconds), 0.001)):
            try:
                rss = int(self._process.memory_info().rss)
            except (OSError, RuntimeError):
                break
            self._peak_rss = max(int(self._peak_rss or 0), rss)
            tree_rss = self._sample_process_tree_rss()
            if tree_rss is not None:
                self._peak_tree_rss = max(int(self._peak_tree_rss or 0), tree_rss)
            self._samples += 1

    def _sample_process_tree_rss(self) -> int | None:
        if self._process is None:
            return None
        processes = [self._process]
        if self.include_children:
            try:
                processes.extend(self._process.children(recursive=True))
            except Exception:
                pass
        total = 0
        sampled = 0
        for process in processes:
            try:
                total += int(process.memory_info().rss)
                sampled += 1
            except Exception:
                continue
        return int(total) if sampled else None

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(0.1, self.sample_interval_seconds * 4))
        if self._process is not None:
            try:
                self._rss_after = int(self._process.memory_info().rss)
                self._peak_rss = max(int(self._peak_rss or 0), self._rss_after)
                self._tree_rss_after = self._sample_process_tree_rss()
                if self._tree_rss_after is not None:
                    self._peak_tree_rss = max(
                        int(self._peak_tree_rss or 0), self._tree_rss_after
                    )
                self._samples += 1
            except (OSError, RuntimeError):
                pass
        if self._started_at is not None:
            self._elapsed_seconds = perf_counter() - self._started_at

    def summary(self) -> Dict[str, Any]:
        available = self._rss_before is not None and self._peak_rss is not None
        return {
            "available": available,
            "backend": "psutil" if available else "unavailable",
            "sample_interval_seconds": float(self.sample_interval_seconds),
            "n_samples": int(self._samples),
            "elapsed_seconds": float(self._elapsed_seconds),
            "rss_before_bytes": self._rss_before,
            "rss_after_bytes": self._rss_after,
            "peak_rss_bytes": self._peak_rss,
            "peak_rss_increase_bytes": (
                int(self._peak_rss - self._rss_before) if available else None
            ),
            "process_tree": {
                "available": self._tree_rss_before is not None
                and self._peak_tree_rss is not None,
                "include_children": bool(self.include_children),
                "rss_before_bytes": self._tree_rss_before,
                "rss_after_bytes": self._tree_rss_after,
                "peak_rss_bytes": self._peak_tree_rss,
                "peak_rss_increase_bytes": (
                    int(self._peak_tree_rss - self._tree_rss_before)
                    if self._tree_rss_before is not None
                    and self._peak_tree_rss is not None
                    else None
                ),
                "scope": (
                    "Sampled sum of RSS for the benchmark parent and all live descendants. "
                    "The peak may fall between samples."
                    if self.include_children
                    else "Child inclusion was disabled; this equals parent-process RSS."
                ),
            },
            "scope": (
                "Sampled resident set size for the whole Python process during the monitored context. "
                "The peak may fall between samples."
            ),
        }


@dataclass
class ProcessRSSCheckpointProfiler:
    """Record process and Python-runtime state at ensemble progress boundaries."""

    tracked_stages: tuple[str, ...] = (
        "ensemble_member_complete_pre_gc",
        "ensemble_member_complete",
        "ensemble_aggregation_start",
        "ensemble_aggregation_complete",
        "ensemble_complete",
    )
    _process: Any = field(default=None, init=False)
    _started_at: float = field(default_factory=perf_counter, init=False)
    _checkpoints: List[Dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._process = psutil.Process() if psutil is not None else None
        self.record("run_start", 0, 1, "Benchmark process checkpoint profiler started")

    def __call__(self, stage: str, current: int, total: int, message: str) -> None:
        if stage in self.tracked_stages:
            self.record(stage, current, total, message)

    def record(self, stage: str, current: int, total: int, message: str) -> None:
        rss = uss = vms = threads = None
        if self._process is not None:
            try:
                memory = self._process.memory_info()
                rss = int(memory.rss)
                vms = int(memory.vms)
                threads = int(self._process.num_threads())
                try:
                    uss = int(self._process.memory_full_info().uss)
                except (AttributeError, OSError, RuntimeError):
                    uss = None
            except (OSError, RuntimeError):
                pass
        try:
            from matplotlib import pyplot as plt

            open_figures = int(len(plt.get_fignums()))
        except (ImportError, RuntimeError):
            open_figures = None
        gc_counts = gc.get_count()
        previous_rss = self._checkpoints[-1].get("rss_bytes") if self._checkpoints else None
        baseline_rss = self._checkpoints[0].get("rss_bytes") if self._checkpoints else rss
        self._checkpoints.append(
            {
                "checkpoint_index": len(self._checkpoints),
                "elapsed_seconds": float(perf_counter() - self._started_at),
                "stage": str(stage),
                "current": int(current),
                "total": int(total),
                "message": str(message),
                "rss_bytes": rss,
                "uss_bytes": uss,
                "vms_bytes": vms,
                "num_threads": threads,
                "rss_delta_from_previous_bytes": (
                    int(rss - previous_rss)
                    if rss is not None and previous_rss is not None
                    else None
                ),
                "rss_increase_from_start_bytes": (
                    int(rss - baseline_rss)
                    if rss is not None and baseline_rss is not None
                    else None
                ),
                "gc_generation_counts": [int(value) for value in gc_counts],
                "gc_tracked_objects": int(len(gc.get_objects())),
                "matplotlib_open_figures": open_figures,
            }
        )

    @property
    def checkpoints(self) -> List[Dict[str, Any]]:
        return [dict(row) for row in self._checkpoints]

    @staticmethod
    def _linear_slope(points: List[tuple[float, float]]) -> float | None:
        if len(points) < 2:
            return None
        x_mean = sum(point[0] for point in points) / len(points)
        y_mean = sum(point[1] for point in points) / len(points)
        denominator = sum((point[0] - x_mean) ** 2 for point in points)
        if denominator == 0:
            return None
        return float(
            sum((x - x_mean) * (y - y_mean) for x, y in points) / denominator
        )

    def summary(self) -> Dict[str, Any]:
        member_rows = [
            row
            for row in self._checkpoints
            if row["stage"] == "ensemble_member_complete"
            and row.get("rss_bytes") is not None
        ]
        member_points = [
            (float(row["current"]), float(row["rss_bytes"])) for row in member_rows
        ]
        first_member_rss = member_rows[0]["rss_bytes"] if member_rows else None
        last_member_rss = member_rows[-1]["rss_bytes"] if member_rows else None

        pre_gc = {
            int(row["current"]): row
            for row in self._checkpoints
            if row["stage"] == "ensemble_member_complete_pre_gc"
        }
        gc_reclaimed = []
        gc_rss_changes = []
        for row in member_rows:
            before = pre_gc.get(int(row["current"]), {}).get("rss_bytes")
            after = row.get("rss_bytes")
            if before is not None and after is not None:
                gc_rss_changes.append(int(after - before))
                gc_reclaimed.append(max(0, int(before - after)))

        return {
            "available": bool(self._process is not None and self._checkpoints),
            "n_checkpoints": int(len(self._checkpoints)),
            "n_member_boundaries": int(len(member_rows)),
            "first_member_rss_bytes": first_member_rss,
            "last_member_rss_bytes": last_member_rss,
            "member_boundary_rss_increase_bytes": (
                int(last_member_rss - first_member_rss)
                if first_member_rss is not None and last_member_rss is not None
                else None
            ),
            "member_boundary_rss_slope_bytes_per_member": self._linear_slope(
                member_points
            ),
            "gc_reclaimed_rss_bytes": gc_reclaimed,
            "gc_reclaimed_rss_total_bytes": int(sum(gc_reclaimed)),
            "gc_rss_change_bytes": gc_rss_changes,
            "maximum_matplotlib_open_figures": max(
                (
                    int(row["matplotlib_open_figures"])
                    for row in self._checkpoints
                    if row.get("matplotlib_open_figures") is not None
                ),
                default=None,
            ),
            "scope": (
                "RSS/USS, GC-tracked objects, threads, and open Matplotlib figures sampled "
                "at ensemble member, aggregation, and completion progress boundaries."
            ),
        }


def _improvement_percent(
    baseline: float | int | None,
    candidate: float | int | None,
) -> float | None:
    """Return positive percentages when the candidate uses fewer resources."""
    if baseline is None or candidate is None or float(baseline) == 0.0:
        return None
    return float((float(baseline) - float(candidate)) / abs(float(baseline)) * 100.0)


def compare_ensemble_memory_benchmarks(
    baseline: Dict[str, Any],
    explicit_gc: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare matched standard runs without and with member-boundary GC.

    This comparison reports observed A/B differences. It does not claim allocator
    ownership: unchanged retained RSS only rules out GC-reclaimable Python cycles as
    the dominant explanation for this matched workload.
    """
    baseline_workload = baseline.get("workload", {})
    gc_workload = explicit_gc.get("workload", {})
    matched_workload = bool(
        baseline.get("profile") == explicit_gc.get("profile")
        and baseline_workload == gc_workload
    )
    if not matched_workload:
        raise ValueError(
            "Ensemble memory A/B inputs must have identical profile and workload settings."
        )
    if baseline.get("collect_garbage_between_members") is not False:
        raise ValueError(
            "Baseline evidence must have member-boundary garbage collection disabled."
        )
    if explicit_gc.get("collect_garbage_between_members") is not True:
        raise ValueError(
            "Explicit-GC evidence must have member-boundary garbage collection enabled."
        )

    baseline_rss = baseline.get("full_process_rss", {})
    gc_rss = explicit_gc.get("full_process_rss", {})
    baseline_checkpoints = baseline.get("memory_checkpoint_summary", {})
    gc_checkpoints = explicit_gc.get("memory_checkpoint_summary", {})

    baseline_peak = baseline_rss.get("peak_rss_increase_bytes")
    gc_peak = gc_rss.get("peak_rss_increase_bytes")
    baseline_retained = baseline_checkpoints.get("member_boundary_rss_increase_bytes")
    gc_retained = gc_checkpoints.get("member_boundary_rss_increase_bytes")
    baseline_slope = baseline_checkpoints.get("member_boundary_rss_slope_bytes_per_member")
    gc_slope = gc_checkpoints.get("member_boundary_rss_slope_bytes_per_member")
    baseline_wall = baseline.get("full_run_elapsed_seconds")
    gc_wall = explicit_gc.get("full_run_elapsed_seconds")

    peak_improvement = _improvement_percent(baseline_peak, gc_peak)
    retained_improvement = _improvement_percent(baseline_retained, gc_retained)
    slope_improvement = _improvement_percent(baseline_slope, gc_slope)
    wall_overhead = (
        float((float(gc_wall) - float(baseline_wall)) / float(baseline_wall) * 100.0)
        if baseline_wall not in (None, 0) and gc_wall is not None
        else None
    )
    observed_reduction = bool(
        peak_improvement is not None
        and retained_improvement is not None
        and peak_improvement > 0.0
        and retained_improvement > 0.0
    )
    conclusion = (
        "observed_peak_and_retained_rss_reduction"
        if observed_reduction
        else "no_observed_peak_and_retained_rss_reduction"
    )

    return {
        "build_id": ENSEMBLE_MEMORY_COMPARISON_BUILD_ID,
        "matched_workload": matched_workload,
        "profile": baseline.get("profile"),
        "workload": baseline_workload,
        "baseline": {
            "full_run_elapsed_seconds": baseline_wall,
            "peak_rss_increase_bytes": baseline_peak,
            "member_boundary_rss_increase_bytes": baseline_retained,
            "member_boundary_rss_slope_bytes_per_member": baseline_slope,
        },
        "explicit_gc": {
            "full_run_elapsed_seconds": gc_wall,
            "peak_rss_increase_bytes": gc_peak,
            "member_boundary_rss_increase_bytes": gc_retained,
            "member_boundary_rss_slope_bytes_per_member": gc_slope,
            "gc_reclaimed_rss_total_bytes": gc_checkpoints.get(
                "gc_reclaimed_rss_total_bytes"
            ),
        },
        "observed_differences": {
            "peak_rss_improvement_percent": peak_improvement,
            "member_boundary_rss_improvement_percent": retained_improvement,
            "member_boundary_slope_improvement_percent": slope_improvement,
            "wall_time_overhead_percent": wall_overhead,
        },
        "conclusion": conclusion,
        "recommend_collect_garbage_between_members_default": observed_reduction,
        "interpretation": (
            "Positive improvement means the explicit-GC run used less RSS. The summed GC "
            "reclamation is event-level and can include memory allocated again by later members; "
            "it is not a net end-of-run saving. A matched A/B without peak and retained-RSS "
            "reduction does not support enabling explicit GC by default."
        ),
    }


def _benchmark_process_tree_peak(evidence: Dict[str, Any]) -> float | int | None:
    full_rss = evidence.get("full_process_rss", {})
    return full_rss.get("process_tree", {}).get(
        "peak_rss_increase_bytes",
        full_rss.get("peak_rss_increase_bytes"),
    )


def compare_ensemble_execution_backends(
    in_process: Dict[str, Any],
    subprocess_run: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare matched ensemble workloads across member execution backends."""
    baseline_workload = in_process.get("workload", {})
    isolated_workload = subprocess_run.get("workload", {})
    matched_workload = bool(
        in_process.get("profile") == subprocess_run.get("profile")
        and baseline_workload == isolated_workload
    )
    if not matched_workload:
        raise ValueError(
            "Ensemble backend A/B inputs must have identical profile and workload settings."
        )
    if in_process.get("member_execution_backend", "in_process") != "in_process":
        raise ValueError("Baseline evidence must use the in_process member backend.")
    if subprocess_run.get("member_execution_backend") != "subprocess":
        raise ValueError("Isolated evidence must use the subprocess member backend.")

    baseline_peak = _benchmark_process_tree_peak(in_process)
    isolated_peak = _benchmark_process_tree_peak(subprocess_run)
    baseline_retained = in_process.get("memory_checkpoint_summary", {}).get(
        "member_boundary_rss_increase_bytes"
    )
    isolated_retained = subprocess_run.get("memory_checkpoint_summary", {}).get(
        "member_boundary_rss_increase_bytes"
    )
    baseline_wall = in_process.get("full_run_elapsed_seconds")
    isolated_wall = subprocess_run.get("full_run_elapsed_seconds")
    peak_improvement = _improvement_percent(baseline_peak, isolated_peak)
    retained_improvement = _improvement_percent(baseline_retained, isolated_retained)
    wall_overhead = (
        float(
            (float(isolated_wall) - float(baseline_wall))
            / float(baseline_wall)
            * 100.0
        )
        if baseline_wall not in (None, 0) and isolated_wall is not None
        else None
    )
    observed_parent_release = bool(
        retained_improvement is not None and retained_improvement > 0.0
    )
    acceptable_peak = bool(peak_improvement is None or peak_improvement >= -10.0)
    recommend_opt_in = bool(observed_parent_release and acceptable_peak)

    child_resources = subprocess_run.get("member_process_resources", {})
    return {
        "build_id": ENSEMBLE_EXECUTION_BACKEND_COMPARISON_BUILD_ID,
        "matched_workload": matched_workload,
        "profile": in_process.get("profile"),
        "workload": baseline_workload,
        "in_process": {
            "full_run_elapsed_seconds": baseline_wall,
            "process_tree_peak_rss_increase_bytes": baseline_peak,
            "member_boundary_rss_increase_bytes": baseline_retained,
        },
        "subprocess": {
            "full_run_elapsed_seconds": isolated_wall,
            "process_tree_peak_rss_increase_bytes": isolated_peak,
            "member_boundary_rss_increase_bytes": isolated_retained,
            "max_child_process_tree_rss_bytes": child_resources.get(
                "max_child_process_tree_rss_bytes"
            ),
            "median_child_process_tree_rss_bytes": child_resources.get(
                "median_child_process_tree_rss_bytes"
            ),
        },
        "observed_differences": {
            "process_tree_peak_rss_improvement_percent": peak_improvement,
            "member_boundary_rss_improvement_percent": retained_improvement,
            "wall_time_overhead_percent": wall_overhead,
        },
        "conclusion": (
            "observed_parent_retained_rss_release"
            if observed_parent_release
            else "no_observed_parent_retained_rss_release"
        ),
        "recommend_subprocess_for_memory_bounded_ensembles": recommend_opt_in,
        "recommend_subprocess_as_default": False,
        "interpretation": (
            "Process-tree peak includes the parent and live descendants, while member-boundary "
            "RSS measures what remains in the parent after each child exits. Subprocess remains "
            "opt-in because interpreter/JIT startup can increase wall time even when retention falls."
        ),
    }

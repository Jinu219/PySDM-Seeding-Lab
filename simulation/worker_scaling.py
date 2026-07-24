from __future__ import annotations

"""Matched worker-scaling benchmark planning and evidence helpers."""

import hashlib
import json
import os
import platform
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

from simulation.config import load_config
from simulation.experiment_manager import load_scenario_config
from simulation.run_plan import estimate_run_plan
from simulation.schema import normalize_config

try:
    import psutil
except ImportError:  # pragma: no cover - requirements.txt includes psutil
    psutil = None


WORKER_SCALING_BUILD_ID = "worker-scaling-benchmark-v1-20260724"
DEFAULT_GIB_PER_WORKER = 1.25
DEFAULT_RESERVE_GIB = 1.0
GIB = 1024**3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_benchmark_config(path: str | Path) -> Dict[str, Any]:
    """Load either a normal config YAML or a saved scenario wrapper."""
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if isinstance(payload, dict) and isinstance(payload.get("config"), dict):
        return normalize_config(load_scenario_config(source))
    return load_config(source)


def normalized_worker_counts(values: Iterable[int]) -> List[int]:
    workers: List[int] = []
    for raw in values:
        value = int(raw)
        if value < 1:
            raise ValueError("Worker counts must be positive integers.")
        if value not in workers:
            workers.append(value)
    if not workers:
        raise ValueError("At least one worker count is required.")
    return workers


def matched_workload_fingerprint(config: Dict[str, Any]) -> str:
    """Hash the workload while intentionally excluding the trial worker count."""
    payload = deepcopy(config)
    payload.setdefault("execution", {}).pop("max_workers", None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def capture_machine_environment(project_root: Path) -> Dict[str, Any]:
    virtual_memory = psutil.virtual_memory() if psutil is not None else None
    cpu_physical = psutil.cpu_count(logical=False) if psutil is not None else None
    cpu_logical = psutil.cpu_count(logical=True) if psutil is not None else os.cpu_count()

    def git_output(*args: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=str(project_root),
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout.strip()

    git_status = git_output("status", "--porcelain")
    return {
        "captured_at_utc": utc_now(),
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "cpu_physical": cpu_physical,
        "cpu_logical": cpu_logical,
        "memory_total_bytes": (
            int(virtual_memory.total) if virtual_memory is not None else None
        ),
        "memory_available_bytes": (
            int(virtual_memory.available) if virtual_memory is not None else None
        ),
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_dirty": bool(git_status) if git_status is not None else None,
        "psutil_available": psutil is not None,
    }


def build_benchmark_plan(
    config: Dict[str, Any],
    worker_counts: Iterable[int],
    *,
    source_path: Path,
    project_root: Path,
    estimated_gib_per_worker: float = DEFAULT_GIB_PER_WORKER,
    reserve_gib: float = DEFAULT_RESERVE_GIB,
    available_memory_bytes: int | None = None,
) -> Dict[str, Any]:
    workers = normalized_worker_counts(worker_counts)
    run_plan = estimate_run_plan(config, results_dir=project_root / "results")
    if run_plan.mode != "parameter_sweep":
        raise ValueError(
            "Worker scaling requires experiment.mode=parameter_sweep because "
            "execution.max_workers applies to independent sweep cases."
        )
    if run_plan.case_count < 2:
        raise ValueError("Worker scaling requires at least two sweep cases.")
    if float(estimated_gib_per_worker) <= 0 or float(reserve_gib) < 0:
        raise ValueError("Memory planning values must be non-negative.")

    if available_memory_bytes is None and psutil is not None:
        available_memory_bytes = int(psutil.virtual_memory().available)

    trials = []
    for configured in workers:
        effective = min(configured, run_plan.case_count)
        required_gib = float(reserve_gib) + effective * float(estimated_gib_per_worker)
        required_bytes = int(required_gib * GIB)
        trials.append(
            {
                "configured_workers": configured,
                "effective_workers": effective,
                "case_count": run_plan.case_count,
                "total_model_runs": run_plan.total_model_runs,
                "estimated_required_memory_gib": required_gib,
                "memory_preflight_passed": (
                    required_bytes <= available_memory_bytes
                    if available_memory_bytes is not None
                    else None
                ),
            }
        )

    return {
        "build_id": WORKER_SCALING_BUILD_ID,
        "created_at_utc": utc_now(),
        "source_path": str(source_path.resolve()),
        "matched_workload_sha256": matched_workload_fingerprint(config),
        "adapter": run_plan.adapter,
        "mode": run_plan.mode,
        "case_count": run_plan.case_count,
        "ensemble_members": run_plan.ensemble_members,
        "control_factor": run_plan.control_factor,
        "total_model_runs": run_plan.total_model_runs,
        "worker_counts": workers,
        "memory_planning": {
            "estimated_gib_per_effective_worker": float(estimated_gib_per_worker),
            "reserve_gib": float(reserve_gib),
            "available_memory_bytes_at_plan": available_memory_bytes,
            "scope": (
                "Conservative preflight estimate only. Final qualification uses "
                "sampled parent/process-tree RSS from each measured trial."
            ),
        },
        "trials": trials,
    }


def prepare_trial_config(config: Dict[str, Any], workers: int) -> Dict[str, Any]:
    trial = deepcopy(config)
    trial.setdefault("execution", {})["max_workers"] = int(workers)
    return trial


def read_trial_evidence(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def summarize_trials(
    plan: Dict[str, Any],
    environment: Dict[str, Any],
    trials: List[Dict[str, Any]],
) -> Dict[str, Any]:
    baseline = next(
        (
            row
            for row in trials
            if int(row.get("configured_workers", 0)) == 1
            and row.get("qualification_status") == "success"
        ),
        None,
    )
    baseline_seconds = (
        float(baseline["elapsed_seconds"]) if baseline is not None else None
    )
    total_cases = int(plan["case_count"])
    total_model_runs = int(plan["total_model_runs"])
    rows = []
    for trial in trials:
        row = dict(trial)
        elapsed = row.get("elapsed_seconds")
        effective = max(int(row.get("effective_workers", 1)), 1)
        if elapsed not in (None, 0) and row.get("qualification_status") == "success":
            row["case_throughput_per_second"] = total_cases / float(elapsed)
            row["model_run_throughput_per_second"] = total_model_runs / float(elapsed)
            row["speedup_vs_serial"] = (
                baseline_seconds / float(elapsed)
                if baseline_seconds is not None
                else None
            )
            row["parallel_efficiency_vs_serial"] = (
                baseline_seconds / float(elapsed) / effective
                if baseline_seconds is not None
                else None
            )
        else:
            row["case_throughput_per_second"] = None
            row["model_run_throughput_per_second"] = None
            row["speedup_vs_serial"] = None
            row["parallel_efficiency_vs_serial"] = None
        rows.append(row)

    matched_trial_scope = all(
        row.get("matched_workload_sha256") == plan["matched_workload_sha256"]
        and row.get("machine_hostname") == environment.get("hostname")
        and row.get("git_commit") == environment.get("git_commit")
        and row.get("python_version") == environment.get("python_version")
        for row in rows
    )
    successful = [row for row in rows if row.get("qualification_status") == "success"]
    best = (
        min(successful, key=lambda row: float(row["elapsed_seconds"]))
        if successful
        else None
    )
    all_requested_completed = bool(
        len(successful) == len(plan["trials"]) and matched_trial_scope
    )
    return {
        "build_id": WORKER_SCALING_BUILD_ID,
        "generated_at_utc": utc_now(),
        "matched_workload_sha256": plan["matched_workload_sha256"],
        "machine_environment": environment,
        "workload": {
            "source_path": plan["source_path"],
            "adapter": plan["adapter"],
            "case_count": total_cases,
            "ensemble_members": plan["ensemble_members"],
            "control_factor": plan["control_factor"],
            "total_model_runs": total_model_runs,
        },
        "trials": rows,
        "qualification": {
            "all_requested_trials_successful": all_requested_completed,
            "all_trial_scopes_matched": matched_trial_scope,
            "serial_baseline_available": baseline is not None,
            "measured_candidate_workers": (
                int(best["configured_workers"]) if best is not None else None
            ),
            "conclusion": (
                "measured_candidate_available"
                if all_requested_completed and baseline is not None
                else "incomplete_evidence"
            ),
            "scope": (
                "The candidate is the fastest successful measured setting for this "
                "machine and workload only; it is not a universal default."
            ),
        },
    }


def render_markdown(evidence: Dict[str, Any]) -> str:
    environment = evidence["machine_environment"]
    workload = evidence["workload"]
    qualification = evidence["qualification"]
    lines = [
        "# Worker Scaling Benchmark",
        "",
        f"- Generated (UTC): `{evidence['generated_at_utc']}`",
        f"- Host: `{environment.get('hostname')}`",
        f"- Commit: `{environment.get('git_commit')}`",
        f"- Git dirty at capture: `{environment.get('git_dirty')}`",
        f"- Adapter: `{workload['adapter']}`",
        f"- Cases / model runs: `{workload['case_count']}` / `{workload['total_model_runs']}`",
        f"- Workload SHA-256: `{evidence['matched_workload_sha256']}`",
        "",
        "| Workers | Effective | Status | Wall s | Speedup | Efficiency | Peak tree GiB | Failed cases |",
        "|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in evidence["trials"]:
        peak = row.get("process_tree_peak_rss_bytes")
        values = {
            "elapsed": (
                f"{float(row['elapsed_seconds']):.3f}"
                if row.get("elapsed_seconds") is not None
                else "-"
            ),
            "speedup": (
                f"{float(row['speedup_vs_serial']):.3f}"
                if row.get("speedup_vs_serial") is not None
                else "-"
            ),
            "efficiency": (
                f"{float(row['parallel_efficiency_vs_serial']):.3f}"
                if row.get("parallel_efficiency_vs_serial") is not None
                else "-"
            ),
            "peak": f"{int(peak) / GIB:.3f}" if peak is not None else "-",
        }
        lines.append(
            f"| {row.get('configured_workers')} | {row.get('effective_workers')} | "
            f"{row.get('qualification_status')} | {values['elapsed']} | "
            f"{values['speedup']} | {values['efficiency']} | {values['peak']} | "
            f"{row.get('failed_cases', '-')} |"
        )
    lines.extend(
        [
            "",
            "## Bounded recommendation",
            "",
            f"- Evidence status: `{qualification['conclusion']}`",
            f"- Fastest measured candidate: `{qualification['measured_candidate_workers']}` workers",
            f"- Scope: {qualification['scope']}",
            "",
            "Inspect each trial's `stdout.log`, `stderr.log`, `status.json`, and "
            "`trial.json` before adopting the candidate.",
        ]
    )
    return "\n".join(lines) + "\n"

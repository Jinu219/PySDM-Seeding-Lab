from __future__ import annotations

"""Run matched serial/parallel PySDM sweep trials with durable evidence."""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulation.worker_scaling import (
    DEFAULT_GIB_PER_WORKER,
    DEFAULT_RESERVE_GIB,
    atomic_write_json,
    build_benchmark_plan,
    capture_machine_environment,
    load_benchmark_config,
    prepare_trial_config,
    read_trial_evidence,
    render_markdown,
    summarize_trials,
)

try:
    import psutil
except ImportError:  # pragma: no cover - requirements.txt includes psutil
    psutil = None


def _default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "artifacts" / "worker_scaling" / stamp


def _process_rss(process: Any) -> int | None:
    try:
        return int(process.memory_info().rss)
    except Exception:
        return None


def _process_tree_rss(process: Any) -> int | None:
    try:
        processes = [process, *process.children(recursive=True)]
    except Exception:
        processes = [process]
    values = [value for item in processes if (value := _process_rss(item)) is not None]
    return int(sum(values)) if values else None


def run_trial(
    config: Dict[str, Any],
    *,
    configured_workers: int,
    effective_workers: int,
    trial_dir: Path,
    sample_interval_seconds: float,
    matched_workload_sha256: str,
    environment: Dict[str, Any],
) -> Dict[str, Any]:
    trial_dir.mkdir(parents=True, exist_ok=False)
    config_path = trial_dir / "config.yaml"
    status_path = trial_dir / "status.json"
    stdout_path = trial_dir / "stdout.log"
    stderr_path = trial_dir / "stderr.log"
    with config_path.open("w", encoding="utf-8") as config_handle:
        yaml.safe_dump(
            prepare_trial_config(config, configured_workers),
            config_handle,
            sort_keys=False,
            allow_unicode=True,
        )
    command = [
        sys.executable,
        "-m",
        "simulation.worker_scaling_trial",
        "--config",
        str(config_path),
        "--output-dir",
        str(trial_dir / "results"),
        "--status-file",
        str(status_path),
    ]
    creationflags = (
        int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    )
    started = time.perf_counter()
    parent_peak = None
    tree_peak = None
    samples = 0
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        child = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=creationflags,
        )
        monitored = psutil.Process(child.pid) if psutil is not None else None
        while child.poll() is None:
            if monitored is not None:
                parent = _process_rss(monitored)
                tree = _process_tree_rss(monitored)
                parent_peak = max(int(parent_peak or 0), int(parent or 0))
                tree_peak = max(int(tree_peak or 0), int(tree or 0))
                samples += 1
            time.sleep(max(0.01, float(sample_interval_seconds)))
        return_code = int(child.returncode)
    elapsed = time.perf_counter() - started

    status = read_trial_evidence(status_path) or {}
    result_dir = Path(str(status.get("result_dir", "")))
    summary_path = result_dir / "summary.json"
    summary = read_trial_evidence(summary_path) or {}
    execution = summary.get("execution", {})
    execution_status = execution.get("status")
    qualified = bool(
        return_code == 0
        and status.get("success") is True
        and execution_status == "success"
    )
    evidence = {
        "configured_workers": int(configured_workers),
        "effective_workers": int(effective_workers),
        "matched_workload_sha256": str(matched_workload_sha256),
        "machine_hostname": environment.get("hostname"),
        "git_commit": environment.get("git_commit"),
        "python_version": environment.get("python_version"),
        "qualification_status": "success" if qualified else "failed",
        "return_code": return_code,
        "elapsed_seconds": float(elapsed),
        "parent_peak_rss_bytes": parent_peak,
        "process_tree_peak_rss_bytes": tree_peak,
        "rss_samples": samples,
        "sample_interval_seconds": float(sample_interval_seconds),
        "result_dir": str(result_dir) if status.get("result_dir") else "",
        "execution_status": execution_status,
        "requested_cases": execution.get("requested_cases"),
        "successful_cases": execution.get("successful_cases"),
        "partial_cases": execution.get("partial_cases"),
        "failed_cases": execution.get("failed_cases"),
        "error": status.get("error_message") or status.get("error") or "",
        "artifacts": {
            "config": "config.yaml",
            "stdout": "stdout.log",
            "stderr": "stderr.log",
            "status": "status.json",
        },
    }
    atomic_write_json(trial_dir / "trial.json", evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or execute matched parameter-sweep trials that differ only in "
            "execution.max_workers."
        )
    )
    parser.add_argument(
        "--config",
        default="experiments/scenarios/marine_showcase_ofat_v1.yaml",
        help="Normal config YAML or saved scenario YAML.",
    )
    parser.add_argument("--workers", nargs="+", type=int, default=[1, 4, 8])
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run physical trials. Without this flag only a dry-run plan is written.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse successful trial.json files already present in output-dir.",
    )
    parser.add_argument(
        "--allow-memory-oversubscription",
        action="store_true",
        help="Explicitly bypass failed RAM preflight checks.",
    )
    parser.add_argument(
        "--allow-dirty-worktree",
        action="store_true",
        help="Explicitly run from a dirty Git worktree (not recommended for evidence).",
    )
    parser.add_argument(
        "--estimated-gib-per-worker",
        type=float,
        default=DEFAULT_GIB_PER_WORKER,
    )
    parser.add_argument("--memory-reserve-gib", type=float, default=DEFAULT_RESERVE_GIB)
    parser.add_argument("--sample-interval-seconds", type=float, default=0.1)
    args = parser.parse_args()

    source_path = Path(args.config)
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path
    output_dir = Path(args.output_dir).resolve() if args.output_dir else _default_output_dir()
    config = load_benchmark_config(source_path)
    environment = capture_machine_environment(PROJECT_ROOT)
    plan = build_benchmark_plan(
        config,
        args.workers,
        source_path=source_path,
        project_root=PROJECT_ROOT,
        estimated_gib_per_worker=args.estimated_gib_per_worker,
        reserve_gib=args.memory_reserve_gib,
        available_memory_bytes=environment.get("memory_available_bytes"),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "plan.json", plan)
    atomic_write_json(output_dir / "environment.json", environment)

    print(f"Benchmark directory: {output_dir}")
    print(
        f"Matched workload: {plan['case_count']} cases, "
        f"{plan['total_model_runs']} model runs, adapter={plan['adapter']}"
    )
    for trial in plan["trials"]:
        state = trial["memory_preflight_passed"]
        print(
            f"workers={trial['configured_workers']} "
            f"(effective={trial['effective_workers']}): "
            f"estimated {trial['estimated_required_memory_gib']:.2f} GiB, "
            f"memory preflight={state}"
        )

    if not args.execute:
        print("Dry run only. Review plan.json, then repeat with --execute.")
        return 0

    blocked = [
        trial
        for trial in plan["trials"]
        if trial["memory_preflight_passed"] is False
    ]
    if blocked and not args.allow_memory_oversubscription:
        workers = ", ".join(str(row["configured_workers"]) for row in blocked)
        print(
            f"Execution blocked: RAM preflight failed for workers={workers}. "
            "Choose a smaller --workers list or explicitly use "
            "--allow-memory-oversubscription.",
            file=sys.stderr,
        )
        return 2
    if psutil is None:
        print(
            "Execution blocked: psutil is required for process-tree RSS evidence.",
            file=sys.stderr,
        )
        return 2
    if environment.get("git_dirty") is True and not args.allow_dirty_worktree:
        print(
            "Execution blocked: the Git worktree is dirty. Commit/stash unrelated "
            "changes or explicitly use --allow-dirty-worktree.",
            file=sys.stderr,
        )
        return 2

    trial_rows = []
    for trial_plan in plan["trials"]:
        workers = int(trial_plan["configured_workers"])
        trial_dir = output_dir / f"workers_{workers}"
        previous = read_trial_evidence(trial_dir / "trial.json")
        if args.resume and previous and previous.get("qualification_status") == "success":
            resume_scope_matches = bool(
                previous.get("matched_workload_sha256")
                == plan["matched_workload_sha256"]
                and previous.get("machine_hostname") == environment.get("hostname")
                and previous.get("git_commit") == environment.get("git_commit")
                and previous.get("python_version") == environment.get("python_version")
            )
            if not resume_scope_matches:
                print(
                    f"Execution blocked: successful workers={workers} evidence "
                    "belongs to a different workload, machine, commit, or Python "
                    "version. Use a new --output-dir.",
                    file=sys.stderr,
                )
                return 2
            print(f"Reusing successful workers={workers} trial.")
            trial_rows.append(previous)
            continue
        if trial_dir.exists():
            if not args.resume:
                print(
                    f"Execution blocked: {trial_dir} already exists. "
                    "Use a new --output-dir or --resume after inspecting it.",
                    file=sys.stderr,
                )
                return 2
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            archived = trial_dir.with_name(f"{trial_dir.name}_attempt_{stamp}")
            if archived.exists():
                print(
                    f"Execution blocked: retry archive already exists at {archived}.",
                    file=sys.stderr,
                )
                return 2
            trial_dir.rename(archived)
            print(f"Preserved incomplete/failed trial at {archived}.")
        print(f"Running workers={workers} ...")
        trial_rows.append(
            run_trial(
                config,
                configured_workers=workers,
                effective_workers=int(trial_plan["effective_workers"]),
                trial_dir=trial_dir,
                sample_interval_seconds=args.sample_interval_seconds,
                matched_workload_sha256=plan["matched_workload_sha256"],
                environment=environment,
            )
        )
        evidence = summarize_trials(plan, environment, trial_rows)
        atomic_write_json(output_dir / "worker_scaling.json", evidence)
        (output_dir / "worker_scaling.md").write_text(
            render_markdown(evidence),
            encoding="utf-8",
        )
        if trial_rows[-1]["qualification_status"] != "success":
            print(
                f"workers={workers} failed. Inspect {trial_dir / 'stderr.log'}; "
                "later trials were not started.",
                file=sys.stderr,
            )
            return 1

    evidence = summarize_trials(plan, environment, trial_rows)
    atomic_write_json(output_dir / "worker_scaling.json", evidence)
    (output_dir / "worker_scaling.md").write_text(
        render_markdown(evidence),
        encoding="utf-8",
    )
    print(f"Evidence: {output_dir / 'worker_scaling.json'}")
    print(f"Report: {output_dir / 'worker_scaling.md'}")
    return 0 if evidence["qualification"]["all_requested_trials_successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

"""Run a reproducible real-PySDM ensemble and record end-to-end RSS evidence."""

import argparse
import json
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from analysis.resource_monitor import ProcessRSSCheckpointProfiler, ProcessRSSMonitor
from analysis.result_files import describe_result_files
from simulation.config import load_config
from simulation.progress import StdoutProgressReporter
from simulation.runner import run_experiment
from simulation.schema import normalize_config
from simulation.validation import validate_config_detailed


ENSEMBLE_BENCHMARK_BUILD_ID = "pysdm-ensemble-benchmark-v3-process-isolation-20260715"
BENCHMARK_PROFILES: Dict[str, Dict[str, int]] = {
    "pilot": {
        "n_members": 3,
        "duration_seconds": 60,
        "timestep_seconds": 15,
        "background_superdroplets": 50,
        "seeding_superdroplets": 50,
    },
    "standard": {
        "n_members": 12,
        "duration_seconds": 300,
        "timestep_seconds": 10,
        "background_superdroplets": 200,
        "seeding_superdroplets": 200,
    },
    "large": {
        "n_members": 24,
        "duration_seconds": 600,
        "timestep_seconds": 10,
        "background_superdroplets": 400,
        "seeding_superdroplets": 400,
    },
}


def build_benchmark_config(
    base_config: Dict[str, Any],
    *,
    profile: str,
    collect_garbage_between_members: bool = False,
    member_execution_backend: str = "in_process",
) -> Dict[str, Any]:
    """Build a deterministic single-mode ensemble workload for resource measurement."""
    if profile not in BENCHMARK_PROFILES:
        raise ValueError(f"Unknown benchmark profile: {profile}")
    settings = BENCHMARK_PROFILES[profile]
    cfg = normalize_config(deepcopy(base_config))
    cfg.setdefault("experiment", {})["name"] = f"ensemble_benchmark_{profile}"
    cfg["experiment"]["mode"] = "single"
    cfg.setdefault("simulation", {})["adapter"] = "pysdm_parcel"
    cfg.setdefault("environment", {})["duration"] = settings["duration_seconds"]
    cfg["environment"]["timestep"] = settings["timestep_seconds"]
    cfg.setdefault("background_aerosol", {})["number_superdroplets"] = settings[
        "background_superdroplets"
    ]
    cfg.setdefault("seeding", {})["number_superdroplets"] = settings[
        "seeding_superdroplets"
    ]
    cfg["seeding"]["injection_start"] = settings["duration_seconds"] // 3
    cfg["seeding"]["injection_end"] = 2 * settings["duration_seconds"] // 3
    cfg.setdefault("ensemble", {}).update(
        {
            "enabled": True,
            "n_members": settings["n_members"],
            "seed_start": 7000,
            "seed_step": 17,
            "execution_backend": str(member_execution_backend),
            "collect_garbage_between_members": bool(
                collect_garbage_between_members
            ),
        }
    )
    cfg["benchmark"] = {
        "build_id": ENSEMBLE_BENCHMARK_BUILD_ID,
        "profile": profile,
        "workload": settings,
        "scope": (
            "Real PySDM condensation/seeding ensemble. Collision remains whatever the base "
            "configuration declares; this benchmark measures software resources, not efficacy."
        ),
        "collect_garbage_between_members": bool(
            collect_garbage_between_members
        ),
        "member_execution_backend": str(member_execution_backend),
    }
    return normalize_config(cfg)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark a real PySDM ensemble.")
    parser.add_argument("--config", default="configs/marine.yaml")
    parser.add_argument("--profile", choices=sorted(BENCHMARK_PROFILES), default="standard")
    parser.add_argument("--output-dir", default="artifacts/ensemble_benchmark")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--gc-between-members",
        action="store_true",
        help="Run gc.collect() after every member for an A/B retained-memory benchmark.",
    )
    parser.add_argument(
        "--member-execution-backend",
        choices=["in_process", "subprocess"],
        default="in_process",
        help="Run members in the benchmark parent or in one isolated child process per member.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    cfg = build_benchmark_config(
        load_config(config_path),
        profile=args.profile,
        collect_garbage_between_members=args.gc_between_members,
        member_execution_backend=args.member_execution_backend,
    )
    errors = [issue for issue in validate_config_detailed(cfg) if issue.severity == "error"]
    if errors:
        raise SystemExit("; ".join(f"{issue.field}: {issue.message}" for issue in errors))
    plan = {
        **cfg["benchmark"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "adapter": cfg["simulation"]["adapter"],
        "ensemble": cfg["ensemble"],
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        return

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    reporter = StdoutProgressReporter(enabled=not args.quiet)
    checkpoint_profiler = ProcessRSSCheckpointProfiler()

    def progress(stage: str, current: int, total: int, message: str) -> None:
        reporter(stage, current, total, message)
        checkpoint_profiler(stage, current, total, message)

    full_run_monitor = ProcessRSSMonitor(
        sample_interval_seconds=0.05,
        include_children=True,
    )
    with full_run_monitor:
        started = time.perf_counter()
        result_dir = run_experiment(cfg, output_dir, progress_callback=progress)
        full_run_seconds = time.perf_counter() - started
    checkpoint_profiler.record(
        "benchmark_return",
        cfg["ensemble"]["n_members"],
        cfg["ensemble"]["n_members"],
        "Benchmark runner returned to CLI",
    )

    aggregation = _read_json(result_dir / "ensemble_aggregation_diagnostics.json")
    result_summary = _read_json(result_dir / "summary.json")
    member_process_resources = result_summary.get("ensemble", {}).get(
        "member_process_resources", {}
    )
    checkpoint_payload = {
        "build_id": ENSEMBLE_BENCHMARK_BUILD_ID,
        "summary": checkpoint_profiler.summary(),
        "checkpoints": checkpoint_profiler.checkpoints,
    }
    _write_json(result_dir / "ensemble_memory_checkpoints.json", checkpoint_payload)
    evidence = {
        **plan,
        "result_dir": str(result_dir),
        "full_run_elapsed_seconds": float(full_run_seconds),
        "full_process_rss": full_run_monitor.summary(),
        "streaming_aggregation": aggregation,
        "memory_checkpoint_summary": checkpoint_payload["summary"],
        "member_execution_backend": str(args.member_execution_backend),
        "member_process_resources": member_process_resources,
        "garbage_collection_between_members": bool(args.gc_between_members),
        "interpretation": (
            "full_process_rss separates parent RSS from a parent-plus-live-children process-tree peak. "
            "streaming_aggregation.process_rss covers only the aggregation window. "
            "memory_checkpoint_summary estimates parent member-boundary retention and optional "
            "explicit-GC reclamation; member_process_resources summarizes isolated children."
        ),
    }
    _write_json(result_dir / "ensemble_benchmark.json", evidence)

    metadata = _read_json(result_dir / "metadata.json")
    metadata.setdefault("result_files", {})["ensemble_benchmark"] = "ensemble_benchmark.json"
    metadata["result_files"][
        "ensemble_memory_checkpoints"
    ] = "ensemble_memory_checkpoints.json"
    metadata["file_roles"] = describe_result_files(
        list(metadata["result_files"].values())
    )
    metadata["ensemble_benchmark"] = evidence
    _write_json(result_dir / "metadata.json", metadata)
    manifest = _read_json(result_dir / "result_manifest.json")
    manifest.setdefault("files", {})["ensemble_benchmark"] = "ensemble_benchmark.json"
    manifest["files"][
        "ensemble_memory_checkpoints"
    ] = "ensemble_memory_checkpoints.json"
    _write_json(result_dir / "result_manifest.json", manifest)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

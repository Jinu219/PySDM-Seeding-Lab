from __future__ import annotations

"""Run a reproducible timestep and super-droplet qualification sweep."""

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from simulation.config import load_config
from simulation.progress import StdoutProgressReporter
from simulation.runner import run_experiment
from simulation.schema import normalize_config
from simulation.sweep import count_sweep_cases
from simulation.validation import validate_config_detailed


QUALIFICATION_BUILD_ID = "numerical-qualification-v1-20260714"
QUALIFICATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "pilot": {
        "description": "Fast workflow qualification; not sufficient for publication claims.",
        "timestep_seconds": [5, 10],
        "seeding_superdroplets": [20, 40],
        "background_superdroplets": [20, 40],
        "duration_seconds": 60,
        "injection_start_seconds": 20,
        "injection_end_seconds": 40,
    },
    "standard": {
        "description": "Three-level numerical qualification for research interpretation.",
        "timestep_seconds": [5, 10, 15],
        "seeding_superdroplets": [100, 200, 400],
        "background_superdroplets": [100, 200, 400],
        "duration_seconds": None,
        "injection_start_seconds": None,
        "injection_end_seconds": None,
    },
}


def build_qualification_config(
    base_config: Dict[str, Any],
    *,
    profile: str,
    adapter: str | None = None,
    duration_seconds: int | None = None,
) -> Dict[str, Any]:
    """Return a normalized Cartesian sweep used by the OFAT convergence diagnostic."""
    if profile not in QUALIFICATION_PROFILES:
        raise ValueError(f"Unknown qualification profile: {profile}")
    profile_settings = QUALIFICATION_PROFILES[profile]
    cfg = normalize_config(deepcopy(base_config))
    cfg.setdefault("experiment", {})["mode"] = "parameter_sweep"
    cfg["experiment"]["name"] = f"qualification_{profile}"
    cfg["experiment"]["description"] = profile_settings["description"]
    if adapter is not None:
        cfg.setdefault("simulation", {})["adapter"] = adapter

    profile_duration = profile_settings.get("duration_seconds")
    selected_duration = duration_seconds if duration_seconds is not None else profile_duration
    if selected_duration is not None:
        cfg.setdefault("environment", {})["duration"] = int(selected_duration)
    if profile_settings.get("injection_start_seconds") is not None:
        cfg.setdefault("seeding", {})["injection_start"] = int(
            profile_settings["injection_start_seconds"]
        )
        cfg["seeding"]["injection_end"] = int(profile_settings["injection_end_seconds"])

    cfg["sweep"] = {
        "run_mode": "control_vs_seeding",
        "max_runs": 100,
        "ranking_metric": "comparison.efficiency.seeding_efficiency_score",
        "parameters": [
            {
                "name": "environment.timestep",
                "values": list(profile_settings["timestep_seconds"]),
            },
            {
                "name": "seeding.number_superdroplets",
                "values": list(profile_settings["seeding_superdroplets"]),
            },
            {
                "name": "background_aerosol.number_superdroplets",
                "values": list(profile_settings["background_superdroplets"]),
            },
        ],
    }
    convergence = cfg.setdefault("diagnostics", {}).setdefault("numerical_convergence", {})
    convergence["enabled"] = True
    convergence.setdefault("relative_tolerance_percent", 5.0)
    convergence.setdefault("metrics", [])
    return normalize_config(cfg)


def qualification_plan(config: Dict[str, Any], *, profile: str) -> Dict[str, Any]:
    """Create a serializable execution and interpretation contract."""
    adapter = config.get("simulation", {}).get("adapter", "unknown")
    return {
        "build_id": QUALIFICATION_BUILD_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "description": QUALIFICATION_PROFILES[profile]["description"],
        "adapter": adapter,
        "case_count": count_sweep_cases(config),
        "model_execution_count": 2 * count_sweep_cases(config),
        "parameters": config.get("sweep", {}).get("parameters", []),
        "acceptance_rule": (
            "For every configured metric and numerical axis, compare the next-finest level "
            "with the finest reference while the other axes remain at their finest values."
        ),
        "relative_tolerance_percent": config.get("diagnostics", {})
        .get("numerical_convergence", {})
        .get("relative_tolerance_percent", 5.0),
        "evidence_scope": (
            "placeholder_warm_cloud qualifies only the software workflow; pysdm_parcel is "
            "required before making physical or publication-facing claims."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the standard numerical-qualification workflow."
    )
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--profile", choices=sorted(QUALIFICATION_PROFILES), default="pilot")
    parser.add_argument(
        "--adapter",
        choices=["placeholder_warm_cloud", "pysdm_parcel"],
        default=None,
    )
    parser.add_argument("--duration", type=int, default=None, help="Override simulation duration [s].")
    parser.add_argument("--output-dir", default="artifacts/numerical_qualification")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without running models.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    cfg = build_qualification_config(
        load_config(config_path),
        profile=args.profile,
        adapter=args.adapter,
        duration_seconds=args.duration,
    )
    errors = [issue for issue in validate_config_detailed(cfg) if issue.severity == "error"]
    if errors:
        messages = "; ".join(f"{issue.field}: {issue.message}" for issue in errors)
        raise SystemExit(f"Qualification configuration is invalid: {messages}")

    plan = qualification_plan(cfg, profile=args.profile)
    cfg["qualification"] = plan
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        return

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    reporter = StdoutProgressReporter(enabled=not args.quiet)
    result_dir = run_experiment(cfg, output_dir=output_dir, progress_callback=reporter)
    print(f"Qualification result directory: {result_dir}")


if __name__ == "__main__":
    main()

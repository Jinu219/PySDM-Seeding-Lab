from __future__ import annotations

"""Run a reproducible timestep and super-droplet qualification sweep."""

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from simulation.config import load_config
from analysis.numerical_convergence import (
    DEFAULT_CONVERGENCE_METRICS,
    build_numerical_convergence_table,
    convergence_metrics,
    plot_numerical_convergence,
    summarize_numerical_convergence,
)
from analysis.qualification_evidence import build_qualification_evidence
from analysis.reporting import (
    build_html_report,
    build_markdown_report,
    build_pdf_report,
    figure_to_png_bytes,
)
from simulation.progress import StdoutProgressReporter
from simulation.runner import run_experiment
from simulation.schema import normalize_config
from simulation.sweep import count_sweep_cases
from simulation.sweep import flatten_nested_dict
from simulation.validation import validate_config_detailed


QUALIFICATION_BUILD_ID = "numerical-qualification-v3-rain-ofat-20260715"
QUALIFICATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "pilot": {
        "description": "Fast workflow qualification; not sufficient for publication claims.",
        "timestep_seconds": [5, 10],
        "seeding_superdroplets": [20, 40],
        "background_superdroplets": [20, 40],
        "duration_seconds": 60,
        "injection_start_seconds": 20,
        "injection_end_seconds": 40,
        "rain_signal_required": False,
    },
    "standard": {
        "description": "Three-level numerical qualification for research interpretation.",
        "timestep_seconds": [5, 10, 15],
        "seeding_superdroplets": [100, 200, 400],
        "background_superdroplets": [100, 200, 400],
        "duration_seconds": None,
        "injection_start_seconds": None,
        "injection_end_seconds": None,
        "rain_signal_required": False,
    },
    "rain_pilot": {
        "description": (
            "Collision-ON rain-signal workflow check; not sufficient for final "
            "tolerance claims."
        ),
        "timestep_seconds": [10, 15],
        "seeding_superdroplets": [60, 100],
        "background_superdroplets": [60, 100],
        "duration_seconds": 900,
        "injection_start_seconds": 300,
        "injection_end_seconds": 600,
        "collision": True,
        "rain_signal_required": True,
        "rain_signal_floor_kg_kg": 1.0e-8,
    },
    "rain_standard": {
        "description": (
            "Collision-ON, rain-producing three-level numerical qualification "
            "for research interpretation."
        ),
        "timestep_seconds": [5, 10, 15],
        "seeding_superdroplets": [100, 200, 400],
        "background_superdroplets": [100, 200, 400],
        "duration_seconds": 1500,
        "injection_start_seconds": 900,
        "injection_end_seconds": 1200,
        "collision": True,
        "rain_signal_required": True,
        "rain_signal_floor_kg_kg": 1.0e-8,
    },
}


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_qualification_result(result_dir: Path) -> Dict[str, Any]:
    """Rebuild convergence evidence from stored case summaries without rerunning PySDM."""
    result_dir = Path(result_dir)
    sweep_path = result_dir / "sweep_summary.csv"
    if not sweep_path.exists():
        raise FileNotFoundError(f"Missing sweep_summary.csv: {result_dir}")
    sweep = pd.read_csv(sweep_path)
    for row_index, row in sweep.iterrows():
        case_dir = result_dir / str(row.get("result_dir", ""))
        case_summary = _read_json(case_dir / "summary.json")
        flat = flatten_nested_dict(case_summary)
        for metric in DEFAULT_CONVERGENCE_METRICS:
            sweep.loc[row_index, metric] = flat.get(metric)
    sweep.to_csv(sweep_path, index=False)

    config = yaml.safe_load((result_dir / "config.yaml").read_text(encoding="utf-8")) or {}
    convergence = build_numerical_convergence_table(sweep, config)
    convergence.to_csv(result_dir / "numerical_convergence.csv", index=False)
    evidence = build_qualification_evidence(convergence, config)
    _write_json(result_dir / "qualification_evidence.json", evidence)

    summary = _read_json(result_dir / "summary.json")
    summary["numerical_convergence"] = summarize_numerical_convergence(convergence)
    summary["numerical_convergence_evidence"] = evidence
    _write_json(result_dir / "summary.json", summary)
    metadata = _read_json(result_dir / "metadata.json")
    metadata.setdefault("result_files", {})[
        "qualification_evidence"
    ] = "qualification_evidence.json"
    _write_json(result_dir / "metadata.json", metadata)
    manifest = _read_json(result_dir / "result_manifest.json")
    if manifest:
        manifest.setdefault("files", {})[
            "qualification_evidence"
        ] = "qualification_evidence.json"
        _write_json(result_dir / "result_manifest.json", manifest)
    validation = json.loads(
        (result_dir / "validation_report.json").read_text(encoding="utf-8")
    )
    (result_dir / "report.md").write_text(
        build_markdown_report(
            summary=summary,
            metadata=metadata,
            validation_rows=validation,
            config=config,
        ),
        encoding="utf-8",
    )
    (result_dir / "report.html").write_text(
        build_html_report(
            summary=summary,
            metadata=metadata,
            validation_rows=validation,
            config=config,
        ),
        encoding="utf-8",
    )
    figures = []
    metrics = convergence_metrics(convergence)
    if metrics:
        figure = plot_numerical_convergence(convergence, metric=metrics[0])
        figures.append((f"Numerical convergence - {metrics[0]}", figure_to_png_bytes(figure)))
    (result_dir / "report.pdf").write_bytes(
        build_pdf_report(
            summary=summary,
            metadata=metadata,
            validation_rows=validation,
            config=config,
            figures=figures,
        )
    )
    return evidence


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

    # Numerical convergence varies deterministic resolution axes. Inheriting an
    # unrelated UI ensemble would multiply the model count and mix stochastic
    # uncertainty into the OFAT resolution test.
    cfg.setdefault("ensemble", {})["enabled"] = False

    profile_duration = profile_settings.get("duration_seconds")
    selected_duration = duration_seconds if duration_seconds is not None else profile_duration
    if selected_duration is not None:
        cfg.setdefault("environment", {})["duration"] = int(selected_duration)
    if profile_settings.get("injection_start_seconds") is not None:
        cfg.setdefault("seeding", {})["injection_start"] = int(
            profile_settings["injection_start_seconds"]
        )
        cfg["seeding"]["injection_end"] = int(profile_settings["injection_end_seconds"])
    if "collision" in profile_settings:
        cfg.setdefault("microphysics", {})["collision"] = bool(
            profile_settings["collision"]
        )

    cfg["sweep"] = {
        "design": "one_factor_at_reference",
        "run_mode": "control_vs_seeding",
        "max_runs": 100,
        "ranking_metric": "comparison.efficiency.seeding_efficiency_score",
        "parameters": [
            {
                "name": "environment.timestep",
                "values": list(profile_settings["timestep_seconds"]),
                "reference": "min",
            },
            {
                "name": "seeding.number_superdroplets",
                "values": list(profile_settings["seeding_superdroplets"]),
                "reference": "max",
            },
            {
                "name": "background_aerosol.number_superdroplets",
                "values": list(profile_settings["background_superdroplets"]),
                "reference": "max",
            },
        ],
    }
    convergence = cfg.setdefault("diagnostics", {}).setdefault("numerical_convergence", {})
    convergence["enabled"] = True
    convergence.setdefault("relative_tolerance_percent", 5.0)
    convergence.setdefault("relative_reference_floor", 1.0e-12)
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
        "sweep_design": config.get("sweep", {}).get("design", "cartesian"),
        "acceptance_rule": (
            "For every configured metric and numerical axis, compare the next-finest level "
            "with the finest reference while the other axes remain at their finest values."
        ),
        "relative_tolerance_percent": config.get("diagnostics", {})
        .get("numerical_convergence", {})
        .get("relative_tolerance_percent", 5.0),
        "relative_reference_floor": config.get("diagnostics", {})
        .get("numerical_convergence", {})
        .get("relative_reference_floor", 1.0e-12),
        "ensemble_enabled": bool(config.get("ensemble", {}).get("enabled", False)),
        "microphysics": dict(config.get("microphysics", {})),
        "rain_signal_required": bool(
            QUALIFICATION_PROFILES[profile].get("rain_signal_required", False)
        ),
        "rain_signal_floor_kg_kg": float(
            QUALIFICATION_PROFILES[profile].get("rain_signal_floor_kg_kg", 1.0e-8)
        ),
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
    parser.add_argument(
        "--refresh-result",
        default=None,
        help="Rebuild qualification evidence from an existing result without rerunning models.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.refresh_result:
        result_dir = Path(args.refresh_result)
        if not result_dir.is_absolute():
            result_dir = PROJECT_ROOT / result_dir
        print(json.dumps(refresh_qualification_result(result_dir), ensure_ascii=False, indent=2))
        return

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
    refresh_qualification_result(result_dir)
    print(f"Qualification result directory: {result_dir}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import yaml

from analysis.comparison import build_difference_dataframe, summarize_comparison
from analysis.growth_pathway_diagnostics import add_growth_pathway_diagnostics, diagnostic_health_rows
from analysis.metrics import summarize_timeseries
from analysis.ensemble_statistics import (
    build_ensemble_statistics,
    ensemble_summary_metrics,
    member_seed_list,
    member_summary_rows,
)
from simulation.builder import build_run_spec
from simulation.progress import ProgressCallback, emit_progress
from simulation.pysdm_adapter import run_adapter
from simulation.schema import normalize_config
from simulation.sweep import build_sweep_row, generate_sweep_cases
from simulation.validation import validation_report_rows, validation_summary
from simulation.types import AdapterResult


def _write_json(path: Path, payload: Dict[str, Any] | list[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ["_", "-", "."] else "_" for ch in value)



def _apply_growth_pathway_diagnostics_to_result(result: AdapterResult, config: Dict[str, Any]) -> AdapterResult:
    """Return an AdapterResult with Exper2-style diagnostic columns added."""
    diagnostics_cfg = config.get("diagnostics", {})
    enabled = diagnostics_cfg.get("growth_pathway_mode", diagnostics_cfg.get("exper2_mode", True))
    if not enabled:
        return result

    enriched = add_growth_pathway_diagnostics(result.require_timeseries(), config)

    summary = {
        **result.summary,
        "growth_pathway_diagnostics_enabled": True,
        "growth_pathway_diagnostic_columns": [
            column
            for column in enriched.columns
            if column not in result.timeseries.columns
        ],
    }

    metadata = {
        **result.metadata,
        "growth_pathway_diagnostics_enabled": True,
    }

    return AdapterResult(timeseries=enriched, metadata=metadata, summary=summary)

def run_experiment(
    config: Dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback = None,
) -> Path:
    """
    Run an experiment according to `experiment.mode`.

    Supported modes:
    - single
    - control_vs_seeding
    - parameter_sweep, reserved for Step 10
    """
    cfg = normalize_config(config)
    mode = cfg.get("experiment", {}).get("mode", "single")

    if mode == "parameter_sweep":
        return run_parameter_sweep(cfg, output_dir, progress_callback=progress_callback)

    if cfg.get("ensemble", {}).get("enabled", False):
        return run_ensemble_experiment(cfg, output_dir, progress_callback=progress_callback)

    if mode == "control_vs_seeding":
        return run_control_vs_seeding(cfg, output_dir, progress_callback=progress_callback)

    return run_single_experiment(cfg, output_dir, progress_callback=progress_callback)


def run_single_experiment(
    config: Dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback = None,
) -> Path:
    """
    Run a single experiment and save a full result directory.

    Result structure:

    results/
    └── <run_id>/
        ├── config.yaml
        ├── timeseries.csv
        ├── summary.json
        ├── metadata.json
        └── validation_report.json
    """
    total_stages = 5

    emit_progress(progress_callback, "runner", 1, total_stages, "Normalizing configuration")
    cfg = normalize_config(config)

    emit_progress(progress_callback, "runner", 2, total_stages, "Building run specification")
    spec = build_run_spec(cfg)

    run_dir = output_dir / spec.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    emit_progress(progress_callback, "runner", 3, total_stages, f"Running adapter: {spec.adapter_name}")
    result = run_adapter(spec, progress_callback=progress_callback)
    result = _apply_growth_pathway_diagnostics_to_result(result, spec.config)

    emit_progress(progress_callback, "runner", 4, total_stages, "Writing result files")
    timeseries = result.require_timeseries()

    _write_single_result_files(run_dir, spec, result)
    emit_progress(progress_callback, "model_run_complete", 1, 1, f"Completed single run: {spec.case_name}")

    emit_progress(progress_callback, "runner", 5, total_stages, f"Finished: {run_dir}")

    return run_dir


def run_control_vs_seeding(
    config: Dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback = None,
) -> Path:
    """
    Run paired control and seeding simulations and save a comparison directory.

    Result structure:

    results/
    └── <run_id>/
        ├── config.yaml
        ├── metadata.json
        ├── summary.json
        ├── comparison.csv
        ├── validation_report.json
        ├── control/
        │   ├── config.yaml
        │   ├── timeseries.csv
        │   ├── summary.json
        │   └── metadata.json
        └── seeding/
            ├── config.yaml
            ├── timeseries.csv
            ├── summary.json
            └── metadata.json
    """
    total_stages = 8

    emit_progress(progress_callback, "comparison", 1, total_stages, "Preparing control and seeding configurations")
    cfg = normalize_config(config)

    experiment_name = _safe_name(str(cfg.get("experiment", {}).get("name", "experiment")))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{timestamp}_{experiment_name}_control_vs_seeding"
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    control_cfg = copy.deepcopy(cfg)
    control_cfg.setdefault("experiment", {})["mode"] = "single"
    control_cfg.setdefault("simulation", {})["case_name"] = "control"
    control_cfg.setdefault("seeding", {})["enabled"] = False

    seeding_cfg = copy.deepcopy(cfg)
    seeding_cfg.setdefault("experiment", {})["mode"] = "single"
    seeding_cfg.setdefault("simulation", {})["case_name"] = "seeding"
    seeding_cfg.setdefault("seeding", {})["enabled"] = True

    emit_progress(progress_callback, "comparison", 2, total_stages, "Running control simulation")
    control_dir = run_dir / "control"
    control_spec = build_run_spec(control_cfg)
    control_result = run_adapter(control_spec, progress_callback=progress_callback)
    control_result = _apply_growth_pathway_diagnostics_to_result(control_result, control_spec.config)
    _write_single_result_files(control_dir, control_spec, control_result)
    emit_progress(progress_callback, "model_run_complete", 1, 1, "Completed control run")

    emit_progress(progress_callback, "comparison", 3, total_stages, "Running seeding simulation")
    seeding_dir = run_dir / "seeding"
    seeding_spec = build_run_spec(seeding_cfg)
    seeding_result = run_adapter(seeding_spec, progress_callback=progress_callback)
    seeding_result = _apply_growth_pathway_diagnostics_to_result(seeding_result, seeding_spec.config)
    _write_single_result_files(seeding_dir, seeding_spec, seeding_result)
    emit_progress(progress_callback, "model_run_complete", 1, 1, "Completed seeding run")

    emit_progress(progress_callback, "comparison", 4, total_stages, "Building comparison dataframe")
    control_df = control_result.require_timeseries()
    seeding_df = seeding_result.require_timeseries()
    difference_df = build_difference_dataframe(control_df, seeding_df)

    emit_progress(progress_callback, "comparison", 5, total_stages, "Computing comparison summary")
    comparison_summary = summarize_comparison(control_df, seeding_df, difference_df)

    emit_progress(progress_callback, "comparison", 6, total_stages, "Writing comparison files")
    _write_yaml(run_dir / "config.yaml", cfg)
    difference_df.to_csv(run_dir / "comparison.csv", index=False)
    _write_json(run_dir / "validation_report.json", validation_report_rows(cfg))

    metadata_payload = {
        "run_id": run_id,
        "created_at": timestamp,
        "experiment_name": experiment_name,
        "experiment_mode": "control_vs_seeding",
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "control_vs_seeding",
        "result_type": "comparison",
        "result_files": {
            "config": "config.yaml",
            "comparison": "comparison.csv",
            "summary": "summary.json",
            "metadata": "metadata.json",
            "validation_report": "validation_report.json",
            "control": "control/",
            "seeding": "seeding/",
        },
    }

    summary_payload = {
        "run_id": run_id,
        "experiment_name": experiment_name,
        "experiment_mode": "control_vs_seeding",
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "control_vs_seeding",
        "comparison": comparison_summary,
        "validation": validation_summary(cfg),
    }

    _write_json(run_dir / "metadata.json", metadata_payload)
    _write_json(run_dir / "summary.json", summary_payload)

    emit_progress(progress_callback, "comparison", 7, total_stages, "Comparison run files completed")
    emit_progress(progress_callback, "comparison", 8, total_stages, f"Finished: {run_dir}")

    return run_dir




def _with_ensemble_disabled(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a config copy with ensemble recursion disabled."""
    cfg = copy.deepcopy(config)
    cfg.setdefault("ensemble", {})["enabled"] = False
    return cfg


def _read_primary_member_dataframe(member_dir: Path, mode: str) -> pd.DataFrame:
    """Read the dataframe that should be aggregated for one ensemble member."""
    if mode == "control_vs_seeding":
        path = member_dir / "comparison.csv"
    else:
        path = member_dir / "timeseries.csv"

    if not path.exists():
        raise FileNotFoundError(f"Missing ensemble aggregation source: {path}")

    return pd.read_csv(path)


def run_ensemble_experiment(
    config: Dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback = None,
) -> Path:
    """
    Run an ensemble for either single or control_vs_seeding mode.

    Result structure:

    results/
    └── <run_id>_ensemble/
        ├── config.yaml
        ├── metadata.json
        ├── summary.json
        ├── ensemble_statistics.csv
        ├── member_summary.csv
        ├── validation_report.json
        └── members/
            ├── member_001/
            └── ...
    """
    cfg = normalize_config(config)
    mode = cfg.get("experiment", {}).get("mode", "single")
    if mode == "parameter_sweep":
        raise ValueError("Ensemble wrapper should not directly wrap parameter_sweep. Sweep cases can use ensemble.")

    seeds = member_seed_list(cfg)
    n_members = len(seeds)

    experiment_name = _safe_name(str(cfg.get("experiment", {}).get("name", "experiment")))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{timestamp}_{experiment_name}_{mode}_ensemble"

    run_dir = output_dir / run_id
    members_dir = run_dir / "members"
    run_dir.mkdir(parents=True, exist_ok=True)
    members_dir.mkdir(parents=True, exist_ok=True)

    emit_progress(progress_callback, "ensemble", 1, n_members + 2, f"Running ensemble with {n_members} members")

    member_records = []
    member_dfs = []

    for idx, seed in enumerate(seeds, start=1):
        emit_progress(progress_callback, "ensemble", idx + 1, n_members + 2, f"Running ensemble member {idx}/{n_members}")

        member_cfg = _with_ensemble_disabled(cfg)
        member_cfg.setdefault("experiment", {})["random_seed"] = int(seed)
        member_cfg.setdefault("simulation", {})["case_name"] = f"member_{idx:03d}"

        member_parent = members_dir / f"member_{idx:03d}"
        member_parent.mkdir(parents=True, exist_ok=True)

        try:
            if mode == "control_vs_seeding":
                member_result_dir = run_control_vs_seeding(member_cfg, member_parent, progress_callback=progress_callback)
            else:
                member_result_dir = run_single_experiment(member_cfg, member_parent, progress_callback=progress_callback)

            member_df = _read_primary_member_dataframe(member_result_dir, mode)
            member_dfs.append(member_df)

            member_records.append(
                {
                    "member_index": idx,
                    "random_seed": int(seed),
                    "success": True,
                    "result_dir": str(member_result_dir.relative_to(run_dir)),
                    "error": "",
                }
            )
        except Exception as exc:
            member_records.append(
                {
                    "member_index": idx,
                    "random_seed": int(seed),
                    "success": False,
                    "result_dir": "",
                    "error": repr(exc),
                }
            )

    emit_progress(progress_callback, "ensemble", n_members + 2, n_members + 2, "Writing ensemble statistics")

    member_summary_df = member_summary_rows(member_records)
    stats_df = build_ensemble_statistics(member_dfs)

    _write_yaml(run_dir / "config.yaml", cfg)
    member_summary_df.to_csv(run_dir / "member_summary.csv", index=False)
    stats_df.to_csv(run_dir / "ensemble_statistics.csv", index=False)
    _write_json(run_dir / "validation_report.json", validation_report_rows(cfg))

    n_success = int(member_summary_df["success"].sum()) if "success" in member_summary_df.columns else 0
    n_failed = int(len(member_summary_df) - n_success)

    metadata_payload = {
        "run_id": run_id,
        "created_at": timestamp,
        "experiment_name": experiment_name,
        "experiment_mode": mode,
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "ensemble",
        "result_type": "ensemble",
        "n_members_requested": n_members,
        "n_success": n_success,
        "n_failed": n_failed,
        "result_files": {
            "config": "config.yaml",
            "ensemble_statistics": "ensemble_statistics.csv",
            "member_summary": "member_summary.csv",
            "summary": "summary.json",
            "metadata": "metadata.json",
            "validation_report": "validation_report.json",
            "members": "members/",
        },
    }

    summary_payload = {
        "run_id": run_id,
        "experiment_name": experiment_name,
        "experiment_mode": mode,
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "ensemble",
        "result_type": "ensemble",
        "ensemble": {
            "n_members_requested": n_members,
            "n_success": n_success,
            "n_failed": n_failed,
            "member_seeds": seeds,
            "metrics": ensemble_summary_metrics(stats_df),
        },
        "validation": validation_summary(cfg),
    }

    _write_json(run_dir / "metadata.json", metadata_payload)
    _write_json(run_dir / "summary.json", summary_payload)

    return run_dir

def run_parameter_sweep(
    config: Dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback = None,
) -> Path:
    """
    Run a parameter sweep.

    Each generated case is executed using `sweep.run_mode`.
    The default case mode is `control_vs_seeding`, so each case produces
    a paired control/seeding comparison and an efficiency score.

    Result structure:

    results/
    └── <run_id>_parameter_sweep/
        ├── config.yaml
        ├── metadata.json
        ├── summary.json
        ├── sweep_summary.csv
        ├── validation_report.json
        └── cases/
            ├── <case run dir>/
            └── ...
    """
    cfg = normalize_config(config)
    sweep = cfg.get("sweep", {})
    ranking_metric = str(
        sweep.get(
            "ranking_metric",
            "comparison.efficiency.seeding_efficiency_score",
        )
    )

    cases = generate_sweep_cases(cfg)
    total_cases = len(cases)

    experiment_name = _safe_name(str(cfg.get("experiment", {}).get("name", "experiment")))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{timestamp}_{experiment_name}_parameter_sweep"

    sweep_dir = output_dir / run_id
    cases_dir = sweep_dir / "cases"
    sweep_dir.mkdir(parents=True, exist_ok=True)
    cases_dir.mkdir(parents=True, exist_ok=True)

    emit_progress(
        progress_callback,
        "sweep",
        1,
        total_cases + 2,
        f"Generated {total_cases} sweep cases",
    )

    rows = []

    for idx, case in enumerate(cases, start=1):
        emit_progress(
            progress_callback,
            "sweep",
            idx + 1,
            total_cases + 2,
            f"Running sweep case {idx}/{total_cases}: {case.case_name}",
        )

        case_result_dir = run_experiment(
            case.config,
            cases_dir,
            progress_callback=progress_callback,
        )

        summary_path = case_result_dir / "summary.json"
        if summary_path.exists():
            with summary_path.open("r", encoding="utf-8") as f:
                case_summary = json.load(f)
        else:
            case_summary = {}

        rows.append(
            build_sweep_row(
                case=case,
                result_dir=str(case_result_dir.relative_to(sweep_dir)),
                summary=case_summary,
                ranking_metric=ranking_metric,
            )
        )

    sweep_df = pd.DataFrame(rows)

    if "ranking_value" in sweep_df.columns:
        sweep_df = sweep_df.sort_values(
            by="ranking_value",
            ascending=False,
            na_position="last",
        ).reset_index(drop=True)
        sweep_df.insert(0, "rank", range(1, len(sweep_df) + 1))

    emit_progress(
        progress_callback,
        "sweep",
        total_cases + 2,
        total_cases + 2,
        "Writing sweep summary",
    )

    sweep_df.to_csv(sweep_dir / "sweep_summary.csv", index=False)
    _write_yaml(sweep_dir / "config.yaml", cfg)
    _write_json(sweep_dir / "validation_report.json", validation_report_rows(cfg))

    best_case = None
    if len(sweep_df) > 0:
        best_case = sweep_df.iloc[0].to_dict()

    metadata_payload = {
        "run_id": run_id,
        "created_at": timestamp,
        "experiment_name": experiment_name,
        "experiment_mode": "parameter_sweep",
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "parameter_sweep",
        "result_type": "parameter_sweep",
        "n_cases": total_cases,
        "ranking_metric": ranking_metric,
        "result_files": {
            "config": "config.yaml",
            "sweep_summary": "sweep_summary.csv",
            "summary": "summary.json",
            "metadata": "metadata.json",
            "validation_report": "validation_report.json",
            "cases": "cases/",
        },
    }

    summary_payload = {
        "run_id": run_id,
        "experiment_name": experiment_name,
        "experiment_mode": "parameter_sweep",
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "parameter_sweep",
        "n_cases": total_cases,
        "ranking_metric": ranking_metric,
        "best_case": best_case,
        "validation": validation_summary(cfg),
    }

    _write_json(sweep_dir / "metadata.json", metadata_payload)
    _write_json(sweep_dir / "summary.json", summary_payload)

    return sweep_dir


def _write_single_result_files(
    run_dir: Path,
    spec,
    result,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    timeseries = result.require_timeseries()

    timeseries_path = run_dir / "timeseries.csv"
    config_path = run_dir / "config.yaml"
    summary_path = run_dir / "summary.json"
    metadata_path = run_dir / "metadata.json"
    validation_path = run_dir / "validation_report.json"
    diagnostic_health_path = run_dir / "diagnostic_health.json"

    _write_yaml(config_path, spec.config)
    timeseries.to_csv(timeseries_path, index=False)

    metrics_summary = summarize_timeseries(timeseries)
    validation_summary_payload = validation_summary(spec.config)
    summary_payload = {
        "run_id": spec.run_id,
        "experiment_name": spec.experiment_name,
        "experiment_mode": spec.experiment_mode,
        "adapter_name": spec.adapter_name,
        "case_name": spec.case_name,
        "adapter_summary": result.summary,
        "metrics": metrics_summary,
        "validation": validation_summary_payload,
    }

    metadata_payload = {
        **spec.metadata,
        **result.metadata,
        "result_type": "single",
        "result_files": {
            "config": str(config_path.name),
            "timeseries": str(timeseries_path.name),
            "summary": str(summary_path.name),
            "metadata": str(metadata_path.name),
            "validation_report": str(validation_path.name),
            "diagnostic_health": str(diagnostic_health_path.name),
        },
    }

    _write_json(summary_path, summary_payload)
    _write_json(metadata_path, metadata_payload)
    _write_json(validation_path, validation_report_rows(spec.config))
    _write_json(diagnostic_health_path, diagnostic_health_rows(timeseries))

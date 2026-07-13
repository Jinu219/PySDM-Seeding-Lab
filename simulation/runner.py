from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml

from analysis.comparison import build_difference_dataframe, summarize_comparison
from analysis.metrics import summarize_timeseries
from simulation.builder import build_run_spec
from simulation.progress import ProgressCallback, emit_progress
from simulation.pysdm_adapter import run_adapter
from simulation.schema import normalize_config
from simulation.validation import validation_report_rows, validation_summary


def _write_json(path: Path, payload: Dict[str, Any] | list[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ["_", "-", "."] else "_" for ch in value)


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

    if mode == "control_vs_seeding":
        return run_control_vs_seeding(cfg, output_dir, progress_callback=progress_callback)

    if mode == "parameter_sweep":
        raise NotImplementedError("parameter_sweep mode is reserved for Step 10.")

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

    emit_progress(progress_callback, "runner", 4, total_stages, "Writing result files")
    timeseries = result.require_timeseries()

    _write_single_result_files(run_dir, spec, result)

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
    _write_single_result_files(control_dir, control_spec, control_result)

    emit_progress(progress_callback, "comparison", 3, total_stages, "Running seeding simulation")
    seeding_dir = run_dir / "seeding"
    seeding_spec = build_run_spec(seeding_cfg)
    seeding_result = run_adapter(seeding_spec, progress_callback=progress_callback)
    _write_single_result_files(seeding_dir, seeding_spec, seeding_result)

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
        },
    }

    _write_json(summary_path, summary_payload)
    _write_json(metadata_path, metadata_payload)
    _write_json(validation_path, validation_report_rows(spec.config))

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml

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


def run_experiment(
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

    emit_progress(progress_callback, "runner", 5, total_stages, f"Finished: {run_dir}")

    return run_dir

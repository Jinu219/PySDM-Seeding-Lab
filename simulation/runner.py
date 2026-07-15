from __future__ import annotations

import copy
import gc
import json
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import yaml
from matplotlib import pyplot as plt

from analysis.comparison import build_difference_dataframe, summarize_comparison
from analysis.case_diagnostic_comparison import (
    build_threshold_robustness_comparison,
    build_water_budget_comparison,
    build_wet_radius_spectrum_comparison,
    summarize_spectrum_comparison,
)
from analysis.growth_pathway_diagnostics import (
    add_growth_pathway_diagnostics,
    diagnostic_health_rows,
    diagnostic_provenance_rows,
)
from analysis.metrics import summarize_timeseries
from analysis.numerical_convergence import (
    DEFAULT_CONVERGENCE_METRICS,
    MEMBER_CONVERGENCE_METRIC_PREFIX,
    build_common_seed_convergence_input,
    build_numerical_convergence_table,
    convergence_metrics,
    plot_numerical_convergence,
    summarize_common_seed_case_coverage,
    summarize_numerical_convergence,
)
from analysis.qualification_evidence import build_qualification_evidence
from analysis.result_files import describe_result_files
from analysis.reporting import (
    build_html_report,
    build_markdown_report,
    build_pdf_report,
    figure_to_png_bytes,
)
from analysis.result_manifest import build_result_manifest
from analysis.spectrum_transition import (
    build_spectrum_transition_table,
    build_transition_onset_robustness,
    plot_spectrum_transition,
    summarize_spectrum_transition,
)
from analysis.water_budget import (
    WATER_BUDGET_TABLE_NAME,
    build_water_budget_table,
    plot_water_budget,
    summarize_water_budget,
)
from analysis.ensemble_statistics import (
    ENSEMBLE_BUILD_ID,
    benchmark_ensemble_statistics_from_paths,
    ensemble_summary_metrics,
    member_seed_list,
    member_summary_rows,
)
from simulation.builder import build_run_spec
from simulation.member_process import (
    MemberProcessExecutionError,
    run_member_subprocess,
)
from simulation.path_policy import (
    COMPARISON_RESULT_DESCENDANT_RESERVE,
    ENSEMBLE_RESULT_DESCENDANT_RESERVE,
    SINGLE_RESULT_DESCENDANT_RESERVE,
    SWEEP_RESULT_DESCENDANT_RESERVE,
    filesystem_token,
    resolve_result_directory,
)
from simulation.progress import ProgressCallback, emit_progress
from simulation.pysdm_adapter import run_adapter
from simulation.run_timing import record_run_timing
from simulation.schema import normalize_config
from simulation.sweep import build_sweep_row, flatten_nested_dict, generate_sweep_cases
from simulation.validation import validation_report_rows, validation_summary
from simulation.types import AdapterResult, SimulationRunSpec


# Timing history is intentionally centralized at the project's top-level results
# directory (not per-sweep-case or per-ensemble-member subfolders), so that
# runtime estimates in simulation/run_plan.py stay meaningful regardless of
# where an individual run's output_dir happens to point.
TIMING_HISTORY_ROOT = Path("results")
ENSEMBLE_MEMBER_SUMMARY_METRICS = {
    "seeding_efficiency_score": "comparison.efficiency.seeding_efficiency_score",
    "accumulated_rain_enhancement": "comparison.efficiency.accumulated_rain_enhancement",
    "rain_enhancement_final": "comparison.efficiency.rain_enhancement_final",
    "rain_onset_time_shift_s": "comparison.efficiency.rain_onset_time_shift_s",
    "cloud_to_rain_conversion_delta": "comparison.efficiency.cloud_to_rain_conversion_delta",
}


class ExperimentExecutionError(RuntimeError):
    """Raised after durable failure artifacts have been written."""

    def __init__(self, message: str, *, result_dir: Path):
        super().__init__(message)
        self.result_dir = Path(result_dir)


def _exception_fields(exc: Exception) -> Dict[str, Any]:
    """Return CSV/JSON-safe exception details without discarding the OS error code."""
    return {
        "error": repr(exc),
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "error_errno": getattr(exc, "errno", None),
        "error_winerror": getattr(exc, "winerror", None),
    }


def _member_result_metrics(result_dir: Path) -> Dict[str, Any]:
    """Extract ranking-relevant scalar metrics from one successful member result."""
    summary_path = Path(result_dir) / "summary.json"
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    flat = flatten_nested_dict(payload)
    metrics = {
        f"metric.{short_name}": flat.get(dotted_name)
        for short_name, dotted_name in ENSEMBLE_MEMBER_SUMMARY_METRICS.items()
    }
    metrics.update(
        {
            f"{MEMBER_CONVERGENCE_METRIC_PREFIX}{metric}": flat.get(metric)
            for metric in DEFAULT_CONVERGENCE_METRICS
        }
    )
    return metrics


def _summarize_member_metrics(member_summary_df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Summarize successful member scalar metrics for ensemble-aware sweep ranking."""
    summaries: Dict[str, Dict[str, Any]] = {}
    if member_summary_df.empty:
        return summaries
    for column in member_summary_df.columns:
        if not column.startswith("metric."):
            continue
        values = pd.to_numeric(member_summary_df[column], errors="coerce").dropna()
        if values.empty:
            continue
        short_name = column.removeprefix("metric.")
        summaries[short_name] = {
            "mean": float(values.mean()),
            "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            "min": float(values.min()),
            "max": float(values.max()),
            "n": int(len(values)),
        }
    return summaries


def _estimate_n_sd_total(spec: SimulationRunSpec) -> int | None:
    """Best-effort super-droplet count for a run, used only as timing metadata."""
    try:
        aero = spec.settings.get("background_aerosol", {}) or {}
        seed = spec.settings.get("seeding", {}) or {}
        n_initial = int(aero.get("number_superdroplets", 0) or 0)
        n_seed = int(seed.get("number_superdroplets", 0) or 0) if seed.get("enabled", True) else 0
        return n_initial + n_seed
    except (TypeError, ValueError):
        return None


def _run_adapter_timed(
    spec: SimulationRunSpec,
    progress_callback: ProgressCallback = None,
) -> AdapterResult:
    """
    Run the adapter while measuring wall-clock duration.

    The measured duration is (a) attached to the result summary so it is
    visible per-run in summary.json, and (b) recorded to the local timing
    history so that `simulation.run_plan.estimate_run_plan` can give a
    grounded runtime estimate for upcoming sweep/ensemble runs.
    """
    started_at = time.perf_counter()
    result = run_adapter(spec, progress_callback=progress_callback)
    elapsed_seconds = time.perf_counter() - started_at

    n_sd_total = _estimate_n_sd_total(spec)

    record_run_timing(
        TIMING_HISTORY_ROOT,
        adapter=spec.adapter_name,
        mode=spec.experiment_mode,
        elapsed_seconds=elapsed_seconds,
        n_sd_total=n_sd_total,
    )

    timed_summary = {
        **result.summary,
        "timing": {
            "elapsed_seconds": round(elapsed_seconds, 3),
            "n_superdroplets_total": n_sd_total,
        },
    }

    return AdapterResult(
        timeseries=result.timeseries,
        metadata=result.metadata,
        summary=timed_summary,
        tables=result.tables,
    )


def _write_json(path: Path, payload: Dict[str, Any] | list[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)


def _figure_payload(title: str, figure: Any) -> tuple[str, bytes]:
    """Convert a report figure to PNG and always release its Matplotlib resources."""
    try:
        return title, figure_to_png_bytes(figure)
    finally:
        plt.close(figure)


def _apply_growth_pathway_diagnostics_to_result(result: AdapterResult, config: Dict[str, Any]) -> AdapterResult:
    """Return an AdapterResult with Exper2-style diagnostic columns added."""
    diagnostics_cfg = config.get("diagnostics", {})
    enabled = diagnostics_cfg.get("growth_pathway_mode", diagnostics_cfg.get("exper2_mode", True))
    if not enabled:
        return result

    # Capture raw adapter columns *before* enrichment fills in proxy columns,
    # so provenance classification can tell native output apart from
    # heuristics added by add_growth_pathway_diagnostics().
    raw_columns = list(result.require_timeseries().columns)
    provenance_rows = diagnostic_provenance_rows(raw_columns, config)

    enriched = add_growth_pathway_diagnostics(result.require_timeseries(), config)

    summary = {
        **result.summary,
        "growth_pathway_diagnostics_enabled": True,
        "growth_pathway_diagnostic_columns": [
            column
            for column in enriched.columns
            if column not in result.timeseries.columns
        ],
        "growth_pathway_diagnostic_provenance": provenance_rows,
    }

    metadata = {
        **result.metadata,
        "growth_pathway_diagnostics_enabled": True,
    }

    return AdapterResult(
        timeseries=enriched,
        metadata=metadata,
        summary=summary,
        tables=result.tables,
    )


def _apply_water_budget_diagnostics_to_result(
    result: AdapterResult,
    config: Dict[str, Any],
) -> AdapterResult:
    """Attach total-water conservation diagnostics when native water columns exist."""
    budget_cfg = config.get("diagnostics", {}).get("water_budget", {})
    if not bool(budget_cfg.get("enabled", True)):
        return result

    budget_table = build_water_budget_table(result.require_timeseries(), config)
    budget_summary = summarize_water_budget(budget_table, config)
    tables = dict(result.tables)
    if not budget_table.empty:
        tables[WATER_BUDGET_TABLE_NAME] = budget_table

    return AdapterResult(
        timeseries=result.timeseries,
        metadata={
            **result.metadata,
            "water_budget_diagnostics_enabled": True,
        },
        summary={
            **result.summary,
            "water_budget": budget_summary,
        },
        tables=tables,
    )

def run_experiment(
    config: Dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback = None,
    *,
    result_dir_name: str | None = None,
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
        return run_parameter_sweep(
            cfg,
            output_dir,
            progress_callback=progress_callback,
            result_dir_name=result_dir_name,
        )

    if cfg.get("ensemble", {}).get("enabled", False):
        return run_ensemble_experiment(
            cfg,
            output_dir,
            progress_callback=progress_callback,
            result_dir_name=result_dir_name,
        )

    if mode == "control_vs_seeding":
        return run_control_vs_seeding(
            cfg,
            output_dir,
            progress_callback=progress_callback,
            result_dir_name=result_dir_name,
        )

    return run_single_experiment(
        cfg,
        output_dir,
        progress_callback=progress_callback,
        result_dir_name=result_dir_name,
    )


def run_single_experiment(
    config: Dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback = None,
    *,
    result_dir_name: str | None = None,
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

    run_dir = resolve_result_directory(
        output_dir,
        spec.run_id,
        result_dir_name,
        descendant_reserve=SINGLE_RESULT_DESCENDANT_RESERVE,
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    emit_progress(progress_callback, "runner", 3, total_stages, f"Running adapter: {spec.adapter_name}")
    result = _run_adapter_timed(spec, progress_callback=progress_callback)
    result = _apply_growth_pathway_diagnostics_to_result(result, spec.config)
    result = _apply_water_budget_diagnostics_to_result(result, spec.config)

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
    *,
    result_dir_name: str | None = None,
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

    experiment_name = str(cfg.get("experiment", {}).get("name", "experiment"))
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
    run_id = f"{timestamp}_{filesystem_token(experiment_name)}_control_vs_seeding"
    run_dir = resolve_result_directory(
        output_dir,
        run_id,
        result_dir_name,
        descendant_reserve=COMPARISON_RESULT_DESCENDANT_RESERVE,
    )
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
    control_result = _run_adapter_timed(control_spec, progress_callback=progress_callback)
    control_result = _apply_growth_pathway_diagnostics_to_result(control_result, control_spec.config)
    control_result = _apply_water_budget_diagnostics_to_result(control_result, control_spec.config)
    _write_single_result_files(control_dir, control_spec, control_result)
    emit_progress(progress_callback, "model_run_complete", 1, 1, "Completed control run")

    emit_progress(progress_callback, "comparison", 3, total_stages, "Running seeding simulation")
    seeding_dir = run_dir / "seeding"
    seeding_spec = build_run_spec(seeding_cfg)
    seeding_result = _run_adapter_timed(seeding_spec, progress_callback=progress_callback)
    seeding_result = _apply_growth_pathway_diagnostics_to_result(seeding_result, seeding_spec.config)
    seeding_result = _apply_water_budget_diagnostics_to_result(seeding_result, seeding_spec.config)
    _write_single_result_files(seeding_dir, seeding_spec, seeding_result)
    emit_progress(progress_callback, "model_run_complete", 1, 1, "Completed seeding run")

    emit_progress(progress_callback, "comparison", 4, total_stages, "Building comparison dataframe")
    control_df = control_result.require_timeseries()
    seeding_df = seeding_result.require_timeseries()
    difference_df = build_difference_dataframe(control_df, seeding_df)

    spectrum_comparison = build_wet_radius_spectrum_comparison(
        control_result.tables.get("wet_radius_spectrum", pd.DataFrame()),
        seeding_result.tables.get("wet_radius_spectrum", pd.DataFrame()),
    )
    threshold_comparison = build_threshold_robustness_comparison(
        control_result.tables.get("threshold_robustness", pd.DataFrame()),
        seeding_result.tables.get("threshold_robustness", pd.DataFrame()),
    )
    water_budget_comparison = build_water_budget_comparison(
        control_result.tables.get(WATER_BUDGET_TABLE_NAME, pd.DataFrame()),
        seeding_result.tables.get(WATER_BUDGET_TABLE_NAME, pd.DataFrame()),
    )
    transition_table = build_spectrum_transition_table(threshold_comparison, cfg)
    transition_robustness = build_transition_onset_robustness(threshold_comparison, cfg)

    emit_progress(progress_callback, "comparison", 5, total_stages, "Computing comparison summary")
    comparison_summary = summarize_comparison(control_df, seeding_df, difference_df)
    comparison_summary["research_quality"] = {
        "water_budget": {
            "control": control_result.summary.get("water_budget", {}),
            "seeding": seeding_result.summary.get("water_budget", {}),
        },
        "wet_radius_spectrum": summarize_spectrum_comparison(spectrum_comparison),
        "spectrum_transition": summarize_spectrum_transition(
            transition_table,
            transition_robustness,
        ),
    }

    emit_progress(progress_callback, "comparison", 6, total_stages, "Writing comparison files")
    _write_yaml(run_dir / "config.yaml", cfg)
    difference_df.to_csv(run_dir / "comparison.csv", index=False)
    _write_json(run_dir / "validation_report.json", validation_report_rows(cfg))

    diagnostic_comparison_files: Dict[str, str] = {}
    for table_name, table, filename in (
        (
            "wet_radius_spectrum_comparison",
            spectrum_comparison,
            "wet_radius_spectrum_comparison.csv",
        ),
        (
            "threshold_robustness_comparison",
            threshold_comparison,
            "threshold_robustness_comparison.csv",
        ),
        (
            "water_budget_comparison",
            water_budget_comparison,
            "water_budget_comparison.csv",
        ),
        (
            "spectrum_transition",
            transition_table,
            "spectrum_transition.csv",
        ),
        (
            "spectrum_transition_onset_robustness",
            transition_robustness,
            "spectrum_transition_onset_robustness.csv",
        ),
    ):
        if table.empty:
            continue
        table.to_csv(run_dir / filename, index=False)
        diagnostic_comparison_files[table_name] = filename

    metadata_payload = {
        "run_id": run_id,
        "created_at": now.isoformat(timespec="seconds"),
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
            "report": "report.md",
            "report_html": "report.html",
            "report_pdf": "report.pdf",
            "result_manifest": "result_manifest.json",
            **diagnostic_comparison_files,
        },
        "file_roles": describe_result_files(
            [
                "config.yaml",
                "comparison.csv",
                "summary.json",
                "metadata.json",
                "validation_report.json",
                "report.md",
                "report.html",
                "report.pdf",
                "result_manifest.json",
                *diagnostic_comparison_files.values(),
            ]
        ),
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
    (run_dir / "report.md").write_text(
        build_markdown_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(cfg),
            config=cfg,
        ),
        encoding="utf-8",
    )
    (run_dir / "report.html").write_text(
        build_html_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(cfg),
            config=cfg,
        ),
        encoding="utf-8",
    )
    comparison_figures = []
    if not transition_table.empty:
        comparison_figures.append(
            _figure_payload(
                "Spectrum-based cloud-to-rain transition",
                plot_spectrum_transition(transition_table),
            )
        )
    (run_dir / "report.pdf").write_bytes(
        build_pdf_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(cfg),
            config=cfg,
            figures=comparison_figures,
        )
    )
    _write_json(
        run_dir / "result_manifest.json",
        build_result_manifest(
            result_type="comparison",
            primary_data="comparison.csv",
            result_files=metadata_payload["result_files"],
            run_id=run_id,
        ),
    )

    emit_progress(progress_callback, "comparison", 7, total_stages, "Comparison run files completed")
    emit_progress(progress_callback, "comparison", 8, total_stages, f"Finished: {run_dir}")

    return run_dir




def _with_ensemble_disabled(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a config copy with ensemble recursion disabled."""
    cfg = copy.deepcopy(config)
    cfg.setdefault("ensemble", {})["enabled"] = False
    return cfg


def _primary_member_data_path(member_dir: Path, mode: str) -> Path:
    """Return the CSV that should be aggregated for one ensemble member."""
    if mode == "control_vs_seeding":
        path = member_dir / "comparison.csv"
    else:
        path = member_dir / "timeseries.csv"

    if not path.exists():
        raise FileNotFoundError(f"Missing ensemble aggregation source: {path}")

    return path


def _summarize_member_process_resources(
    member_summary_df: pd.DataFrame,
    execution_backend: str,
) -> Dict[str, Any]:
    """Summarize isolated-child cost without mixing it with parent RSS."""
    payload: Dict[str, Any] = {
        "execution_backend": execution_backend,
        "member_process_isolation": execution_backend == "subprocess",
        "successful_child_processes": 0,
        "max_child_process_tree_rss_bytes": None,
        "median_child_process_tree_rss_bytes": None,
        "total_child_elapsed_seconds": None,
        "median_child_elapsed_seconds": None,
        "scope": (
            "Child peak values sum the isolated member process and its descendants. "
            "Parent-process RSS is measured separately by the benchmark profiler."
            if execution_backend == "subprocess"
            else "Members executed in the parent Python process; no child-process telemetry exists."
        ),
    }
    if execution_backend != "subprocess" or member_summary_df.empty:
        return payload

    return_codes = pd.to_numeric(
        member_summary_df.get("member_process_return_code"), errors="coerce"
    )
    peak_rss = pd.to_numeric(
        member_summary_df.get("member_process_peak_tree_rss_bytes"), errors="coerce"
    ).dropna()
    elapsed = pd.to_numeric(
        member_summary_df.get("member_process_elapsed_seconds"), errors="coerce"
    ).dropna()
    payload.update(
        {
            "successful_child_processes": int((return_codes == 0).sum()),
            "max_child_process_tree_rss_bytes": (
                int(peak_rss.max()) if not peak_rss.empty else None
            ),
            "median_child_process_tree_rss_bytes": (
                float(peak_rss.median()) if not peak_rss.empty else None
            ),
            "total_child_elapsed_seconds": (
                float(elapsed.sum()) if not elapsed.empty else None
            ),
            "median_child_elapsed_seconds": (
                float(elapsed.median()) if not elapsed.empty else None
            ),
        }
    )
    return payload


def run_ensemble_experiment(
    config: Dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback = None,
    *,
    result_dir_name: str | None = None,
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

    experiment_name = str(cfg.get("experiment", {}).get("name", "experiment"))
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
    run_id = f"{timestamp}_{filesystem_token(experiment_name)}_{mode}_ensemble"

    run_dir = resolve_result_directory(
        output_dir,
        run_id,
        result_dir_name,
        descendant_reserve=ENSEMBLE_RESULT_DESCENDANT_RESERVE,
    )
    members_dir = run_dir / "members"
    run_dir.mkdir(parents=True, exist_ok=True)
    members_dir.mkdir(parents=True, exist_ok=True)

    emit_progress(progress_callback, "ensemble", 1, n_members + 2, f"Running ensemble with {n_members} members")

    member_records = []
    member_data_paths: list[Path] = []
    collect_garbage = bool(
        cfg.get("ensemble", {}).get("collect_garbage_between_members", False)
    )
    execution_backend = str(
        cfg.get("ensemble", {}).get("execution_backend", "in_process")
    )

    for idx, seed in enumerate(seeds, start=1):
        emit_progress(progress_callback, "ensemble", idx + 1, n_members + 2, f"Running ensemble member {idx}/{n_members}")

        member_cfg = _with_ensemble_disabled(cfg)
        member_cfg.setdefault("experiment", {})["random_seed"] = int(seed)
        member_cfg.setdefault("simulation", {})["case_name"] = f"member_{idx:03d}"

        member_parent = members_dir / f"member_{idx:03d}"
        member_parent.mkdir(parents=True, exist_ok=True)

        process_telemetry: Dict[str, Any] = {}
        try:
            if execution_backend == "subprocess":
                member_result_dir, process_telemetry = run_member_subprocess(
                    member_cfg,
                    member_parent,
                    mode=mode,
                )
            elif mode == "control_vs_seeding":
                member_result_dir = run_control_vs_seeding(
                    member_cfg,
                    member_parent,
                    progress_callback=progress_callback,
                    result_dir_name="comparison",
                )
            else:
                member_result_dir = run_single_experiment(
                    member_cfg,
                    member_parent,
                    progress_callback=progress_callback,
                    result_dir_name="single",
                )

            member_data_paths.append(_primary_member_data_path(member_result_dir, mode))

            member_record = {
                "member_index": idx,
                "random_seed": int(seed),
                "success": True,
                "execution_backend": execution_backend,
                "result_dir": str(member_result_dir.relative_to(run_dir)),
                "error": "",
                "error_type": "",
                "error_message": "",
                "error_errno": None,
                "error_winerror": None,
            }
            member_record.update(process_telemetry)
            member_record.update(_member_result_metrics(member_result_dir))
            member_records.append(member_record)
        except Exception as exc:
            error_fields = _exception_fields(exc)
            if isinstance(exc, MemberProcessExecutionError):
                process_telemetry = exc.telemetry
                for key in (
                    "error",
                    "error_type",
                    "error_message",
                    "error_errno",
                    "error_winerror",
                ):
                    if exc.status.get(key) not in (None, ""):
                        error_fields[key] = exc.status[key]
            member_records.append(
                {
                    "member_index": idx,
                    "random_seed": int(seed),
                    "success": False,
                    "execution_backend": execution_backend,
                    "result_dir": "",
                    **process_telemetry,
                    **error_fields,
                }
            )

        emit_progress(
            progress_callback,
            "ensemble_member_complete_pre_gc",
            idx,
            n_members,
            f"Completed ensemble member {idx}/{n_members} before optional garbage collection",
        )
        collected_objects = int(gc.collect()) if collect_garbage else 0
        member_records[-1]["gc_collected_objects"] = collected_objects
        emit_progress(
            progress_callback,
            "ensemble_member_complete",
            idx,
            n_members,
            f"Completed ensemble member {idx}/{n_members}; gc_collected={collected_objects}",
        )

    emit_progress(progress_callback, "ensemble", n_members + 2, n_members + 2, "Writing ensemble statistics")
    emit_progress(
        progress_callback,
        "ensemble_aggregation_start",
        0,
        1,
        "Starting streaming ensemble aggregation",
    )

    member_summary_df = member_summary_rows(member_records)
    stats_df, aggregation_diagnostics = benchmark_ensemble_statistics_from_paths(
        member_data_paths
    )
    emit_progress(
        progress_callback,
        "ensemble_aggregation_complete",
        1,
        1,
        "Completed streaming ensemble aggregation",
    )

    _write_yaml(run_dir / "config.yaml", cfg)
    member_summary_df.to_csv(run_dir / "member_summary.csv", index=False)
    stats_df.to_csv(run_dir / "ensemble_statistics.csv", index=False)
    _write_json(run_dir / "validation_report.json", validation_report_rows(cfg))
    _write_json(run_dir / "ensemble_aggregation_diagnostics.json", aggregation_diagnostics)

    n_success = int(member_summary_df["success"].sum()) if "success" in member_summary_df.columns else 0
    n_failed = int(len(member_summary_df) - n_success)
    member_metric_summary = _summarize_member_metrics(member_summary_df)
    member_process_resources = _summarize_member_process_resources(
        member_summary_df,
        execution_backend,
    )
    execution_status = (
        "failed"
        if n_success == 0
        else "partial"
        if n_failed > 0
        else "success"
    )
    first_member_errors = [
        str(record.get("error_message") or record.get("error") or "")
        for record in member_records
        if not record.get("success")
    ][:5]
    execution_payload = {
        "status": execution_status,
        "requested_members": n_members,
        "successful_members": n_success,
        "failed_members": n_failed,
        "execution_backend": execution_backend,
        "first_errors": first_member_errors,
    }

    metadata_payload = {
        "run_id": run_id,
        "created_at": now.isoformat(timespec="seconds"),
        "experiment_name": experiment_name,
        "experiment_mode": mode,
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "ensemble",
        "result_type": "ensemble",
        "n_members_requested": n_members,
        "n_success": n_success,
        "n_failed": n_failed,
        "execution_status": execution_status,
        "execution": execution_payload,
        "ensemble_execution_backend": execution_backend,
        "member_process_resources": member_process_resources,
        "member_metric_summary": member_metric_summary,
        "ensemble_statistics_build_id": ENSEMBLE_BUILD_ID,
        "ensemble_aggregation_method": "column_streaming_from_member_csv",
        "ensemble_aggregation_diagnostics": aggregation_diagnostics,
        "result_files": {
            "config": "config.yaml",
            "ensemble_statistics": "ensemble_statistics.csv",
            "member_summary": "member_summary.csv",
            "summary": "summary.json",
            "metadata": "metadata.json",
            "validation_report": "validation_report.json",
            "members": "members/",
            "report": "report.md",
            "report_html": "report.html",
            "report_pdf": "report.pdf",
            "ensemble_aggregation_diagnostics": "ensemble_aggregation_diagnostics.json",
            "result_manifest": "result_manifest.json",
        },
        "file_roles": describe_result_files(
            [
                "config.yaml",
                "ensemble_statistics.csv",
                "member_summary.csv",
                "summary.json",
                "metadata.json",
                "validation_report.json",
                "report.md",
                "report.html",
                "report.pdf",
                "ensemble_aggregation_diagnostics.json",
                "result_manifest.json",
            ]
        ),
    }

    summary_payload = {
        "run_id": run_id,
        "experiment_name": experiment_name,
        "experiment_mode": mode,
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "ensemble",
        "result_type": "ensemble",
        "execution": execution_payload,
        "ensemble": {
            "n_members_requested": n_members,
            "n_success": n_success,
            "n_failed": n_failed,
            "execution_backend": execution_backend,
            "member_process_resources": member_process_resources,
            "aggregation_method": "column_streaming_from_member_csv",
            "aggregation": aggregation_diagnostics,
            "member_seeds": seeds,
            "member_metrics": member_metric_summary,
            "metrics": ensemble_summary_metrics(stats_df),
        },
        "validation": validation_summary(cfg),
    }

    _write_json(run_dir / "metadata.json", metadata_payload)
    _write_json(run_dir / "summary.json", summary_payload)
    (run_dir / "report.md").write_text(
        build_markdown_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(cfg),
            config=cfg,
        ),
        encoding="utf-8",
    )
    (run_dir / "report.html").write_text(
        build_html_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(cfg),
            config=cfg,
        ),
        encoding="utf-8",
    )
    (run_dir / "report.pdf").write_bytes(
        build_pdf_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(cfg),
            config=cfg,
        )
    )
    _write_json(
        run_dir / "result_manifest.json",
        build_result_manifest(
            result_type="ensemble",
            primary_data="ensemble_statistics.csv",
            result_files=metadata_payload["result_files"],
            run_id=run_id,
        ),
    )

    emit_progress(
        progress_callback,
        "ensemble_complete",
        n_members,
        n_members,
        "Completed ensemble result and reports",
    )

    if n_success == 0:
        first_error = first_member_errors[0] if first_member_errors else "unknown member failure"
        raise ExperimentExecutionError(
            f"All {n_members} ensemble members failed. First error: {first_error}",
            result_dir=run_dir,
        )

    return run_dir


def _execute_sweep_case(
    case_config: Dict[str, Any],
    cases_dir: Path,
    case_directory_name: str,
    progress_callback: ProgressCallback = None,
) -> Dict[str, str]:
    """Execute one sweep case and return a process-safe status payload."""
    case_status = "success"
    case_error = ""
    try:
        case_result_dir = run_experiment(
            case_config,
            cases_dir,
            progress_callback=progress_callback,
            result_dir_name=case_directory_name,
        )
    except ExperimentExecutionError as exc:
        case_result_dir = exc.result_dir
        case_status = "failed"
        case_error = str(exc)
    except Exception as exc:
        case_result_dir = cases_dir / case_directory_name
        case_result_dir.mkdir(parents=True, exist_ok=True)
        case_status = "failed"
        case_error = repr(exc)

    return {
        "result_dir": str(case_result_dir),
        "case_status": case_status,
        "case_error": case_error,
    }


def _failed_parallel_case_payload(
    cases_dir: Path,
    case_directory_name: str,
    exc: BaseException,
) -> Dict[str, str]:
    """Preserve a directory and diagnostic when a worker future itself fails."""
    case_result_dir = cases_dir / case_directory_name
    case_result_dir.mkdir(parents=True, exist_ok=True)
    return {
        "result_dir": str(case_result_dir),
        "case_status": "failed",
        "case_error": f"Parallel worker failure: {exc!r}",
    }


def run_parameter_sweep(
    config: Dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback = None,
    *,
    result_dir_name: str | None = None,
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

    experiment_name = str(cfg.get("experiment", {}).get("name", "experiment"))
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
    run_id = f"{timestamp}_{filesystem_token(experiment_name)}_parameter_sweep"

    sweep_dir = resolve_result_directory(
        output_dir,
        run_id,
        result_dir_name,
        descendant_reserve=SWEEP_RESULT_DESCENDANT_RESERVE,
    )
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

    configured_workers = max(int(cfg.get("execution", {}).get("max_workers", 1)), 1)
    effective_workers = min(configured_workers, total_cases)
    outcomes: list[Dict[str, str] | None] = [None] * total_cases

    if effective_workers == 1:
        for idx, case in enumerate(cases, start=1):
            emit_progress(
                progress_callback,
                "sweep",
                idx + 1,
                total_cases + 2,
                f"Running sweep case {idx}/{total_cases}: {case.case_name}",
            )
            outcomes[idx - 1] = _execute_sweep_case(
                case.config,
                cases_dir,
                f"case_{idx:03d}",
                progress_callback=progress_callback,
            )
    else:
        emit_progress(
            progress_callback,
            "sweep",
            1,
            total_cases + 2,
            f"Starting {total_cases} sweep cases with {effective_workers} worker processes",
        )
        spawn_context = mp.get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=effective_workers,
            mp_context=spawn_context,
        ) as executor:
            future_map = {
                executor.submit(
                    _execute_sweep_case,
                    case.config,
                    cases_dir,
                    f"case_{idx:03d}",
                ): (idx, case)
                for idx, case in enumerate(cases, start=1)
            }
            completed_cases = 0
            for future in as_completed(future_map):
                idx, case = future_map[future]
                try:
                    outcomes[idx - 1] = future.result()
                except Exception as exc:
                    outcomes[idx - 1] = _failed_parallel_case_payload(
                        cases_dir,
                        f"case_{idx:03d}",
                        exc,
                    )
                completed_cases += 1
                emit_progress(
                    progress_callback,
                    "sweep",
                    completed_cases + 1,
                    total_cases + 2,
                    f"Completed sweep case {idx}/{total_cases}: {case.case_name}",
                )

                case_mode = str(case.config.get("sweep", {}).get("run_mode", "control_vs_seeding"))
                control_factor = 2 if case_mode == "control_vs_seeding" else 1
                ensemble_cfg = case.config.get("ensemble", {})
                member_factor = (
                    max(int(ensemble_cfg.get("n_members", 1)), 1)
                    if bool(ensemble_cfg.get("enabled", False))
                    else 1
                )
                for completed_unit in range(control_factor * member_factor):
                    emit_progress(
                        progress_callback,
                        "model_run_complete",
                        completed_unit + 1,
                        control_factor * member_factor,
                        f"Completed parallel case unit: {case.case_name}",
                    )

    rows = []
    for case, outcome in zip(cases, outcomes):
        if outcome is None:
            outcome = _failed_parallel_case_payload(
                cases_dir,
                f"case_{case.case_index:03d}",
                RuntimeError("No worker outcome was returned."),
            )
        case_result_dir = Path(outcome["result_dir"])
        case_status = outcome["case_status"]
        case_error = outcome["case_error"]

        summary_path = case_result_dir / "summary.json"
        if summary_path.exists():
            with summary_path.open("r", encoding="utf-8") as f:
                case_summary = json.load(f)
        else:
            case_summary = {}

        nested_status = str(case_summary.get("execution", {}).get("status", "")).lower()
        if case_status == "success" and nested_status in {"partial", "failed"}:
            case_status = nested_status
        if not case_error and nested_status == "failed":
            first_errors = case_summary.get("execution", {}).get("first_errors", [])
            case_error = str(first_errors[0]) if first_errors else "Nested case execution failed."

        row = build_sweep_row(
            case=case,
            result_dir=str(case_result_dir.relative_to(sweep_dir)),
            summary=case_summary,
            ranking_metric=ranking_metric,
        )
        row.update(
            {
                "case_status": case_status,
                "case_success": case_status == "success",
                "case_error": case_error,
            }
        )
        rows.append(row)

    sweep_df = pd.DataFrame(rows)

    if "ranking_value" in sweep_df.columns:
        sweep_df = sweep_df.sort_values(
            by="ranking_value",
            ascending=False,
            na_position="last",
        ).reset_index(drop=True)
        sweep_df.insert(0, "rank", range(1, len(sweep_df) + 1))

    status_counts = (
        sweep_df["case_status"].value_counts().to_dict()
        if "case_status" in sweep_df.columns
        else {"success": len(sweep_df)}
    )
    n_successful_cases = int(status_counts.get("success", 0))
    n_partial_cases = int(status_counts.get("partial", 0))
    n_failed_cases = int(status_counts.get("failed", 0))
    sweep_execution_status = (
        "failed"
        if n_failed_cases == total_cases
        else "partial"
        if n_failed_cases > 0 or n_partial_cases > 0
        else "success"
    )
    execution_payload = {
        "status": sweep_execution_status,
        "requested_cases": total_cases,
        "successful_cases": n_successful_cases,
        "partial_cases": n_partial_cases,
        "failed_cases": n_failed_cases,
        "configured_case_workers": configured_workers,
        "effective_case_workers": effective_workers,
    }
    convergence_input = (
        sweep_df[sweep_df["case_status"] != "failed"].copy()
        if "case_status" in sweep_df.columns
        else sweep_df
    )
    common_seed_pairing = bool(
        cfg.get("qualification", {}).get("common_random_seed_pairing", False)
    )
    common_seed_input = (
        build_common_seed_convergence_input(convergence_input, sweep_dir)
        if common_seed_pairing
        else pd.DataFrame()
    )
    convergence_source = (
        common_seed_input if not common_seed_input.empty else convergence_input
    )
    if common_seed_pairing:
        cfg.setdefault("qualification", {})[
            "common_seed_case_coverage"
        ] = summarize_common_seed_case_coverage(
            common_seed_input,
            cfg,
            n_cases=total_cases,
        )
    convergence_table = build_numerical_convergence_table(convergence_source, cfg)
    convergence_summary = summarize_numerical_convergence(convergence_table)
    qualification_evidence = build_qualification_evidence(convergence_table, cfg)

    emit_progress(
        progress_callback,
        "sweep",
        total_cases + 2,
        total_cases + 2,
        "Writing sweep summary",
    )

    sweep_df.to_csv(sweep_dir / "sweep_summary.csv", index=False)
    if not common_seed_input.empty:
        common_seed_input.to_csv(sweep_dir / "paired_seed_metrics.csv", index=False)
    if not convergence_table.empty:
        convergence_table.to_csv(sweep_dir / "numerical_convergence.csv", index=False)
    _write_yaml(sweep_dir / "config.yaml", cfg)
    _write_json(sweep_dir / "validation_report.json", validation_report_rows(cfg))
    qualification_payload = cfg.get("qualification")
    if isinstance(qualification_payload, dict) and qualification_payload:
        _write_json(sweep_dir / "qualification_plan.json", qualification_payload)
        _write_json(sweep_dir / "qualification_evidence.json", qualification_evidence)

    best_case = None
    usable_cases = (
        sweep_df[sweep_df["case_status"] != "failed"]
        if "case_status" in sweep_df.columns
        else sweep_df
    )
    if len(usable_cases) > 0:
        best_case = usable_cases.iloc[0].to_dict()

    metadata_payload = {
        "run_id": run_id,
        "created_at": now.isoformat(timespec="seconds"),
        "experiment_name": experiment_name,
        "experiment_mode": "parameter_sweep",
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "parameter_sweep",
        "result_type": "parameter_sweep",
        "n_cases": total_cases,
        "execution_status": sweep_execution_status,
        "execution": execution_payload,
        "ranking_metric": ranking_metric,
        "result_files": {
            "config": "config.yaml",
            "sweep_summary": "sweep_summary.csv",
            "summary": "summary.json",
            "metadata": "metadata.json",
            "validation_report": "validation_report.json",
            "cases": "cases/",
            "report": "report.md",
            "report_html": "report.html",
            "report_pdf": "report.pdf",
            "result_manifest": "result_manifest.json",
            **(
                {"qualification_plan": "qualification_plan.json"}
                if isinstance(qualification_payload, dict) and qualification_payload
                else {}
            ),
            **(
                {"qualification_evidence": "qualification_evidence.json"}
                if isinstance(qualification_payload, dict) and qualification_payload
                else {}
            ),
            **(
                {"paired_seed_metrics": "paired_seed_metrics.csv"}
                if not common_seed_input.empty
                else {}
            ),
            **(
                {"numerical_convergence": "numerical_convergence.csv"}
                if not convergence_table.empty
                else {}
            ),
        },
        "file_roles": describe_result_files(
            [
                "config.yaml",
                "sweep_summary.csv",
                "summary.json",
                "metadata.json",
                "validation_report.json",
                "report.md",
                "report.html",
                "report.pdf",
                "result_manifest.json",
                *(
                    ["paired_seed_metrics.csv"]
                    if not common_seed_input.empty
                    else []
                ),
                *(
                    ["qualification_plan.json"]
                    if isinstance(qualification_payload, dict) and qualification_payload
                    else []
                ),
                *(
                    ["qualification_evidence.json"]
                    if isinstance(qualification_payload, dict) and qualification_payload
                    else []
                ),
                *(["numerical_convergence.csv"] if not convergence_table.empty else []),
            ]
        ),
    }

    summary_payload = {
        "run_id": run_id,
        "experiment_name": experiment_name,
        "experiment_mode": "parameter_sweep",
        "adapter_name": cfg.get("simulation", {}).get("adapter"),
        "case_name": "parameter_sweep",
        "n_cases": total_cases,
        "execution": execution_payload,
        "ranking_metric": ranking_metric,
        "best_case": best_case,
        "numerical_convergence": convergence_summary,
        "numerical_convergence_evidence": qualification_evidence,
        "validation": validation_summary(cfg),
    }

    _write_json(sweep_dir / "metadata.json", metadata_payload)
    _write_json(sweep_dir / "summary.json", summary_payload)
    (sweep_dir / "report.md").write_text(
        build_markdown_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(cfg),
            config=cfg,
        ),
        encoding="utf-8",
    )
    (sweep_dir / "report.html").write_text(
        build_html_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(cfg),
            config=cfg,
        ),
        encoding="utf-8",
    )
    sweep_figures = []
    available_convergence_metrics = convergence_metrics(convergence_table)
    if available_convergence_metrics:
        selected_metric = available_convergence_metrics[0]
        sweep_figures.append(
            _figure_payload(
                f"Numerical convergence - {selected_metric}",
                plot_numerical_convergence(convergence_table, metric=selected_metric),
            )
        )
    (sweep_dir / "report.pdf").write_bytes(
        build_pdf_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(cfg),
            config=cfg,
            figures=sweep_figures,
        )
    )
    _write_json(
        sweep_dir / "result_manifest.json",
        build_result_manifest(
            result_type="parameter_sweep",
            primary_data="sweep_summary.csv",
            result_files=metadata_payload["result_files"],
            run_id=run_id,
        ),
    )

    if n_failed_cases == total_cases:
        raise ExperimentExecutionError(
            f"All {total_cases} sweep cases failed. Review case_status and case_error in "
            "sweep_summary.csv.",
            result_dir=sweep_dir,
        )

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
    diagnostic_provenance_path = run_dir / "diagnostic_provenance.json"
    report_path = run_dir / "report.md"
    html_report_path = run_dir / "report.html"
    pdf_report_path = run_dir / "report.pdf"
    manifest_path = run_dir / "result_manifest.json"

    _write_yaml(config_path, spec.config)
    timeseries.to_csv(timeseries_path, index=False)

    metrics_summary = summarize_timeseries(timeseries)
    validation_summary_payload = validation_summary(spec.config)
    # Populated by _apply_growth_pathway_diagnostics_to_result(); absent when
    # growth-pathway diagnostics are disabled for this run.
    provenance_rows = result.summary.get("growth_pathway_diagnostic_provenance", [])

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

    result_file_names = {
        "config": str(config_path.name),
        "timeseries": str(timeseries_path.name),
        "summary": str(summary_path.name),
        "metadata": str(metadata_path.name),
        "validation_report": str(validation_path.name),
        "diagnostic_health": str(diagnostic_health_path.name),
        "diagnostic_provenance": str(diagnostic_provenance_path.name),
        "report": str(report_path.name),
        "report_html": str(html_report_path.name),
        "report_pdf": str(pdf_report_path.name),
        "result_manifest": str(manifest_path.name),
    }

    table_file_names = {
        "wet_radius_spectrum": "wet_radius_spectrum.csv",
        "threshold_robustness": "threshold_robustness.csv",
        "water_budget": "water_budget.csv",
    }
    for table_name, filename in table_file_names.items():
        table = result.tables.get(table_name)
        if table is None:
            continue
        table_path = run_dir / filename
        table.to_csv(table_path, index=False)
        result_file_names[table_name] = filename

    metadata_payload = {
        **spec.metadata,
        **result.metadata,
        "result_type": "single",
        "result_files": result_file_names,
        # Self-documenting: explains what each file in result_files is *for*,
        # so summary.json / metadata.json / validation_report.json don't have
        # to be reverse-engineered later. See analysis/result_files.py.
        "file_roles": describe_result_files(list(result_file_names.values())),
    }

    _write_json(summary_path, summary_payload)
    _write_json(metadata_path, metadata_payload)
    _write_json(validation_path, validation_report_rows(spec.config))
    _write_json(diagnostic_health_path, diagnostic_health_rows(timeseries))
    _write_json(diagnostic_provenance_path, provenance_rows)
    report_path.write_text(
        build_markdown_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(spec.config),
            config=spec.config,
        ),
        encoding="utf-8",
    )
    html_report_path.write_text(
        build_html_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(spec.config),
            config=spec.config,
        ),
        encoding="utf-8",
    )
    report_figures = []
    water_budget_table = result.tables.get(WATER_BUDGET_TABLE_NAME, pd.DataFrame())
    if not water_budget_table.empty:
        report_figures.append(
            _figure_payload("Total-water budget", plot_water_budget(water_budget_table))
        )
    pdf_report_path.write_bytes(
        build_pdf_report(
            summary=summary_payload,
            metadata=metadata_payload,
            validation_rows=validation_report_rows(spec.config),
            config=spec.config,
            figures=report_figures,
        )
    )
    _write_json(
        manifest_path,
        build_result_manifest(
            result_type="single",
            primary_data="timeseries.csv",
            result_files=metadata_payload["result_files"],
            run_id=spec.run_id,
        ),
    )

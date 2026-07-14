from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from analysis.ensemble_statistics import ensemble_variable_bases
from analysis.growth_pathway_diagnostics import (
    GROWTH_PATHWAY_VARIABLE_GROUPS,
    GROWTH_PATHWAY_PREFERRED_ORDER,
    PROVENANCE_LABELS_KO,
)
from analysis.result_files import describe_result_files
from analysis.result_manifest import inspect_result_compatibility
from analysis.spectrum_transition import plot_spectrum_transition
from analysis.numerical_convergence import (
    convergence_metrics,
    plot_numerical_convergence,
)
from analysis.water_budget import plot_water_budget
from analysis.publication_plots import (
    DEFAULT_PATHWAY_VARIABLES,
    PUBLICATION_PLOTS_BUILD_ID,
    PUBLICATION_STYLE_PRESETS,
    apply_publication_style,
    matched_collision_cases,
    one_factor_sensitivity_slices,
    plot_collision_off_on_panel,
    plot_ensemble_uncertainty_panel,
    plot_growth_pathway_four_panel,
    plot_one_factor_sensitivity_panel,
    publication_parameter_label,
    publication_provenance_note,
    publication_variable_label,
)
from analysis.wet_radius_plots import (
    ROBUSTNESS_METRIC_LABELS,
    SPECTRUM_VALUE_LABELS,
    plot_threshold_robustness,
    plot_threshold_robustness_difference,
    plot_wet_radius_spectrum,
    plot_wet_radius_spectrum_difference,
    spectrum_checkpoint_times,
    threshold_robustness_metrics,
)

DASHBOARD_BUILD_ID = "qualification-benchmark-report-migration-20260714"


@dataclass(frozen=True)
class ResultEntry:
    """A discovered simulation result."""

    path: Path
    label: str
    is_run_directory: bool
    result_type: str


def _representative_diagnostic_provenance_path(result_root: Path) -> Path | None:
    """Find one diagnostic provenance file representative of a structured result."""
    direct_candidates = [
        result_root / "diagnostic_provenance.json",
        result_root / "control" / "diagnostic_provenance.json",
        result_root / "seeding" / "diagnostic_provenance.json",
    ]
    for candidate in direct_candidates:
        if candidate.exists():
            return candidate

    try:
        return next(iter(sorted(result_root.rglob("diagnostic_provenance.json"))), None)
    except OSError:
        return None


def discover_results(result_dir: Path) -> List[ResultEntry]:
    """Find structured run directories and legacy CSV outputs."""
    result_dir.mkdir(exist_ok=True)

    entries: List[ResultEntry] = []

    for path in sorted([p for p in result_dir.iterdir() if p.is_dir()], reverse=True):
        if (path / "ensemble_statistics.csv").exists():
            entries.append(
                ResultEntry(
                    path=path,
                    label=f"[ensemble] {path.name}",
                    is_run_directory=True,
                    result_type="ensemble",
                )
            )
        elif (path / "sweep_summary.csv").exists():
            entries.append(
                ResultEntry(
                    path=path,
                    label=f"[sweep] {path.name}",
                    is_run_directory=True,
                    result_type="parameter_sweep",
                )
            )
        elif (path / "comparison.csv").exists():
            entries.append(
                ResultEntry(
                    path=path,
                    label=f"[comparison] {path.name}",
                    is_run_directory=True,
                    result_type="comparison",
                )
            )
        elif (path / "timeseries.csv").exists():
            entries.append(
                ResultEntry(
                    path=path,
                    label=f"[single] {path.name}",
                    is_run_directory=True,
                    result_type="single",
                )
            )

    for path in sorted(result_dir.glob("*.csv"), reverse=True):
        entries.append(
            ResultEntry(
                path=path,
                label=f"[legacy csv] {path.name}",
                is_run_directory=False,
                result_type="legacy_csv",
            )
        )

    return entries


def load_result(entry: ResultEntry) -> Dict[str, Any]:
    """Load a result directory or legacy CSV into a common dictionary."""
    compatibility = inspect_result_compatibility(entry.path)
    if entry.result_type == "ensemble":
        stats_path = entry.path / "ensemble_statistics.csv"
        member_summary_path = entry.path / "member_summary.csv"
        summary_path = entry.path / "summary.json"
        metadata_path = entry.path / "metadata.json"
        config_path = entry.path / "config.yaml"
        validation_path = entry.path / "validation_report.json"
        report_path = entry.path / "report.md"
        html_report_path = entry.path / "report.html"
        pdf_report_path = entry.path / "report.pdf"
        aggregation_diagnostics_path = entry.path / "ensemble_aggregation_diagnostics.json"
        ensemble_benchmark_path = entry.path / "ensemble_benchmark.json"
        diagnostic_provenance_path = _representative_diagnostic_provenance_path(entry.path)

        stats_df = safe_read_csv(stats_path)
        member_summary_df = safe_read_csv(member_summary_path)

        return {
            "entry": entry,
            "timeseries": stats_df,
            "ensemble": stats_df,
            "member_summary": member_summary_df,
            "sweep": pd.DataFrame(),
            "comparison": pd.DataFrame(),
            "control": pd.DataFrame(),
            "seeding": pd.DataFrame(),
            "wet_radius_spectrum": pd.DataFrame(),
            "threshold_robustness": pd.DataFrame(),
            "summary": _read_json(summary_path),
            "metadata": _read_json(metadata_path),
            "config": _read_yaml(config_path),
            "validation": _read_json(validation_path),
            "diagnostic_provenance": (
                _read_json(diagnostic_provenance_path) if diagnostic_provenance_path else []
            ) or [],
            "report_markdown": _read_text(report_path),
            "report_html": _read_text(html_report_path),
            "report_pdf": _read_bytes(pdf_report_path),
            "ensemble_aggregation_diagnostics": _read_json(aggregation_diagnostics_path),
            "ensemble_benchmark": _read_json(ensemble_benchmark_path),
            "result_compatibility": compatibility,
            "files": {
                "ensemble_statistics": stats_path,
                "member_summary": member_summary_path,
                "summary": summary_path,
                "metadata": metadata_path,
                "config": config_path,
                "validation": validation_path,
                "diagnostic_provenance": diagnostic_provenance_path,
                "report": report_path,
                "report_html": html_report_path,
                "report_pdf": pdf_report_path,
                "ensemble_aggregation_diagnostics": aggregation_diagnostics_path,
                "ensemble_benchmark": ensemble_benchmark_path,
            },
        }

    if entry.result_type == "parameter_sweep":
        sweep_path = entry.path / "sweep_summary.csv"
        convergence_path = entry.path / "numerical_convergence.csv"
        report_path = entry.path / "report.md"
        html_report_path = entry.path / "report.html"
        pdf_report_path = entry.path / "report.pdf"
        summary_path = entry.path / "summary.json"
        metadata_path = entry.path / "metadata.json"
        config_path = entry.path / "config.yaml"
        validation_path = entry.path / "validation_report.json"
        diagnostic_provenance_path = _representative_diagnostic_provenance_path(entry.path)

        sweep_df = safe_read_csv(sweep_path)

        return {
            "entry": entry,
            "timeseries": sweep_df,
            "sweep": sweep_df,
            "comparison": pd.DataFrame(),
            "control": pd.DataFrame(),
            "seeding": pd.DataFrame(),
            "wet_radius_spectrum": pd.DataFrame(),
            "threshold_robustness": pd.DataFrame(),
            "numerical_convergence": safe_read_csv(convergence_path),
            "summary": _read_json(summary_path),
            "metadata": _read_json(metadata_path),
            "config": _read_yaml(config_path),
            "validation": _read_json(validation_path),
            "diagnostic_provenance": (
                _read_json(diagnostic_provenance_path) if diagnostic_provenance_path else []
            ) or [],
            "report_markdown": _read_text(report_path),
            "report_html": _read_text(html_report_path),
            "report_pdf": _read_bytes(pdf_report_path),
            "result_compatibility": compatibility,
            "files": {
                "sweep_summary": sweep_path,
                "numerical_convergence": convergence_path,
                "summary": summary_path,
                "metadata": metadata_path,
                "config": config_path,
                "validation": validation_path,
                "diagnostic_provenance": diagnostic_provenance_path,
                "report": report_path,
                "report_html": html_report_path,
                "report_pdf": pdf_report_path,
            },
        }

    if entry.result_type == "comparison":
        comparison_path = entry.path / "comparison.csv"
        summary_path = entry.path / "summary.json"
        metadata_path = entry.path / "metadata.json"
        config_path = entry.path / "config.yaml"
        validation_path = entry.path / "validation_report.json"
        control_path = entry.path / "control" / "timeseries.csv"
        seeding_path = entry.path / "seeding" / "timeseries.csv"
        control_spectrum_path = entry.path / "control" / "wet_radius_spectrum.csv"
        seeding_spectrum_path = entry.path / "seeding" / "wet_radius_spectrum.csv"
        control_robustness_path = entry.path / "control" / "threshold_robustness.csv"
        seeding_robustness_path = entry.path / "seeding" / "threshold_robustness.csv"
        control_water_budget_path = entry.path / "control" / "water_budget.csv"
        seeding_water_budget_path = entry.path / "seeding" / "water_budget.csv"
        spectrum_comparison_path = entry.path / "wet_radius_spectrum_comparison.csv"
        threshold_comparison_path = entry.path / "threshold_robustness_comparison.csv"
        water_budget_comparison_path = entry.path / "water_budget_comparison.csv"
        transition_path = entry.path / "spectrum_transition.csv"
        transition_robustness_path = entry.path / "spectrum_transition_onset_robustness.csv"
        report_path = entry.path / "report.md"
        html_report_path = entry.path / "report.html"
        pdf_report_path = entry.path / "report.pdf"
        # Provenance is identical for control and seeding runs of the same
        # comparison (same adapter, same diagnostics config), so either
        # subdirectory's provenance file is representative; control is used
        # because it always exists when a comparison result exists.
        diagnostic_provenance_path = _representative_diagnostic_provenance_path(entry.path)

        comparison_df = safe_read_csv(comparison_path)
        control_df = safe_read_csv(control_path)
        seeding_df = safe_read_csv(seeding_path)

        return {
            "entry": entry,
            "timeseries": comparison_df,
            "sweep": pd.DataFrame(),
            "comparison": comparison_df,
            "control": control_df,
            "seeding": seeding_df,
            "control_wet_radius_spectrum": safe_read_csv(control_spectrum_path),
            "seeding_wet_radius_spectrum": safe_read_csv(seeding_spectrum_path),
            "control_threshold_robustness": safe_read_csv(control_robustness_path),
            "seeding_threshold_robustness": safe_read_csv(seeding_robustness_path),
            "control_water_budget": safe_read_csv(control_water_budget_path),
            "seeding_water_budget": safe_read_csv(seeding_water_budget_path),
            "wet_radius_spectrum_comparison": safe_read_csv(spectrum_comparison_path),
            "threshold_robustness_comparison": safe_read_csv(threshold_comparison_path),
            "water_budget_comparison": safe_read_csv(water_budget_comparison_path),
            "spectrum_transition": safe_read_csv(transition_path),
            "spectrum_transition_onset_robustness": safe_read_csv(transition_robustness_path),
            "summary": _read_json(summary_path),
            "metadata": _read_json(metadata_path),
            "config": _read_yaml(config_path),
            "validation": _read_json(validation_path),
            "diagnostic_provenance": (
                _read_json(diagnostic_provenance_path) if diagnostic_provenance_path else []
            ) or [],
            "report_markdown": _read_text(report_path),
            "report_html": _read_text(html_report_path),
            "report_pdf": _read_bytes(pdf_report_path),
            "result_compatibility": compatibility,
            "files": {
                "comparison": comparison_path,
                "summary": summary_path,
                "metadata": metadata_path,
                "config": config_path,
                "validation": validation_path,
                "control_timeseries": control_path,
                "seeding_timeseries": seeding_path,
                "control_wet_radius_spectrum": control_spectrum_path,
                "seeding_wet_radius_spectrum": seeding_spectrum_path,
                "control_threshold_robustness": control_robustness_path,
                "seeding_threshold_robustness": seeding_robustness_path,
                "control_water_budget": control_water_budget_path,
                "seeding_water_budget": seeding_water_budget_path,
                "wet_radius_spectrum_comparison": spectrum_comparison_path,
                "threshold_robustness_comparison": threshold_comparison_path,
                "water_budget_comparison": water_budget_comparison_path,
                "spectrum_transition": transition_path,
                "spectrum_transition_onset_robustness": transition_robustness_path,
                "diagnostic_provenance": diagnostic_provenance_path,
                "report": report_path,
                "report_html": html_report_path,
                "report_pdf": pdf_report_path,
            },
        }

    if entry.is_run_directory:
        timeseries_path = entry.path / "timeseries.csv"
        summary_path = entry.path / "summary.json"
        metadata_path = entry.path / "metadata.json"
        config_path = entry.path / "config.yaml"
        validation_path = entry.path / "validation_report.json"
        diagnostic_provenance_path = entry.path / "diagnostic_provenance.json"
        spectrum_path = entry.path / "wet_radius_spectrum.csv"
        robustness_path = entry.path / "threshold_robustness.csv"
        water_budget_path = entry.path / "water_budget.csv"
        report_path = entry.path / "report.md"
        html_report_path = entry.path / "report.html"
        pdf_report_path = entry.path / "report.pdf"

        df = safe_read_csv(timeseries_path)

        return {
            "entry": entry,
            "timeseries": df,
            "ensemble": pd.DataFrame(),
            "member_summary": pd.DataFrame(),
            "sweep": pd.DataFrame(),
            "comparison": pd.DataFrame(),
            "control": pd.DataFrame(),
            "seeding": pd.DataFrame(),
            "wet_radius_spectrum": safe_read_csv(spectrum_path),
            "threshold_robustness": safe_read_csv(robustness_path),
            "water_budget": safe_read_csv(water_budget_path),
            "summary": _read_json(summary_path),
            "metadata": _read_json(metadata_path),
            "config": _read_yaml(config_path),
            "validation": _read_json(validation_path),
            "diagnostic_provenance": _read_json(diagnostic_provenance_path) or [],
            "report_markdown": _read_text(report_path),
            "report_html": _read_text(html_report_path),
            "report_pdf": _read_bytes(pdf_report_path),
            "result_compatibility": compatibility,
            "files": {
                "timeseries": timeseries_path,
                "summary": summary_path,
                "metadata": metadata_path,
                "config": config_path,
                "validation": validation_path,
                "diagnostic_provenance": diagnostic_provenance_path,
                "wet_radius_spectrum": spectrum_path,
                "threshold_robustness": robustness_path,
                "water_budget": water_budget_path,
                "report": report_path,
                "report_html": html_report_path,
                "report_pdf": pdf_report_path,
            },
        }

    df = safe_read_csv(entry.path)
    return {
        "entry": entry,
        "timeseries": df,
        "sweep": pd.DataFrame(),
        "comparison": pd.DataFrame(),
        "control": pd.DataFrame(),
        "seeding": pd.DataFrame(),
        "wet_radius_spectrum": pd.DataFrame(),
        "threshold_robustness": pd.DataFrame(),
        "water_budget": pd.DataFrame(),
        "numerical_convergence": pd.DataFrame(),
        "summary": {},
        "metadata": {"source": "legacy_csv", "filename": entry.path.name},
        "config": {},
        "validation": [],
        "diagnostic_provenance": [],
        "report_markdown": "",
        "report_html": "",
        "report_pdf": b"",
        "result_compatibility": compatibility,
        "files": {
            "timeseries": entry.path,
        },
    }


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _read_bytes(path: Path) -> bytes:
    if not path.exists():
        return b""
    try:
        return path.read_bytes()
    except OSError:
        return b""


def safe_read_csv(path: Path) -> pd.DataFrame:
    """
    Read a CSV without crashing the dashboard.

    Returns an empty DataFrame when:
    - file does not exist
    - file exists but is zero-byte / headerless
    - pandas raises EmptyDataError
    """
    path = Path(path)

    if not path.exists():
        return pd.DataFrame()

    try:
        if path.stat().st_size == 0:
            return pd.DataFrame()
    except OSError:
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except FileNotFoundError:
        return pd.DataFrame()


def flatten_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten nested summary dictionaries for metric cards."""
    flat: Dict[str, Any] = {}

    def walk(prefix: str, obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                walk(next_prefix, value)
        else:
            flat[prefix] = obj

    walk("", summary)
    return flat


def format_metric_value(value: Any) -> str:
    """Format metric values for compact dashboard cards."""
    if value is None:
        return "None"

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, int):
        return f"{value:d}"

    if isinstance(value, float):
        if value == 0:
            return "0"
        abs_value = abs(value)
        if abs_value < 1.0e-3 or abs_value >= 1.0e4:
            return f"{value:.3e}"
        return f"{value:.4g}"

    return str(value)


def available_numeric_columns(df: pd.DataFrame) -> List[str]:
    """Return numeric columns except time."""
    return [
        col
        for col in df.columns
        if col != "time_s" and pd.api.types.is_numeric_dtype(df[col])
    ]


def recommended_column_groups(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Return dashboard-friendly column groups based on available outputs."""
    groups = {
        "Thermodynamic response": [
            "water_vapour_mixing_ratio",
            "supersaturation_percent",
            "relative_humidity_percent",
            "temperature_K",
        ],
        "Water content": [
            "cloud_water_mixing_ratio",
            "rain_water_mixing_ratio",
        ],
        "Radius": [
            "effective_radius_um",
            "mean_radius_m",
        ],
        "Number concentration": [
            "droplet_number_concentration_cm3",
            "droplet_number_concentration",
            "rain_drop_number_concentration",
            "superdroplet_count",
        ],
        "Supersaturation": [
            "supersaturation",
            "supersaturation_percent",
        ],
        "Exper2 number concentration": [
            "cloud_droplet_concentration",
            "rain_droplet_concentration",
            "all_activated_concentration",
        ],
        "Exper2 effective radius": [
            "effective_radius_cloud_um",
            "effective_radius_rain_um",
            "effective_radius_all_um",
        ],
    }

    return {
        group_name: [col for col in columns if col in df.columns]
        for group_name, columns in groups.items()
        if any(col in df.columns for col in columns)
    }


def comparison_base_variables(comparison_df: pd.DataFrame) -> List[str]:
    """Return physically meaningful base variable names available in a comparison dataframe."""
    excluded = {"seeding_active"}

    preferred_order = GROWTH_PATHWAY_PREFERRED_ORDER + [
        "rain_water_mixing_ratio",
        "cloud_water_mixing_ratio",
        "supersaturation",
        "effective_radius_um",
        "mean_radius_m",
        "droplet_number_concentration_cm3",
        "droplet_number_concentration",
        "rain_drop_number_concentration",
        "superdroplet_count",
    ]

    bases = []
    for col in comparison_df.columns:
        if col.endswith("_control"):
            base = col[: -len("_control")]
            if base in excluded:
                continue
            if f"{base}_seeding" in comparison_df.columns and f"{base}_diff" in comparison_df.columns:
                bases.append(base)

    ordered = [base for base in preferred_order if base in bases]
    ordered += sorted([base for base in bases if base not in ordered])
    return ordered


def _seeding_intervals(df: pd.DataFrame) -> List[tuple[float, float]]:
    """Find continuous intervals where seeding_active == 1."""
    if "time_s" not in df.columns or "seeding_active" not in df.columns:
        return []

    active = df["seeding_active"].fillna(0).astype(int).to_numpy()
    time = df["time_s"].to_numpy()

    intervals: List[tuple[float, float]] = []
    start = None

    for idx, is_active in enumerate(active):
        if is_active and start is None:
            start = float(time[idx])

        is_last = idx == len(active) - 1
        if start is not None and ((not is_active) or is_last):
            end_idx = idx if is_active and is_last else max(idx - 1, 0)
            end = float(time[end_idx])
            intervals.append((start, end))
            start = None

    return intervals


def _seeding_intervals_from_comparison(comparison_df: pd.DataFrame) -> List[tuple[float, float]]:
    for candidate in ["seeding_active_seeding", "seeding_active"]:
        if candidate in comparison_df.columns:
            temp = pd.DataFrame(
                {
                    "time_s": comparison_df["time_s"],
                    "seeding_active": comparison_df[candidate],
                }
            )
            return _seeding_intervals(temp)
    return []


def comparison_seeding_intervals(comparison_df: pd.DataFrame) -> List[tuple[float, float]]:
    """Public wrapper returning seeding-active intervals from comparison data."""
    return _seeding_intervals_from_comparison(comparison_df)




def _curve_palette(n: int) -> List[str]:
    """Return deterministic colors for sweep curves."""
    base_colors = list(plt.get_cmap("tab20").colors)
    colors = []
    for idx in range(max(n, 1)):
        rgb = base_colors[idx % len(base_colors)]
        colors.append("#{:02x}{:02x}{:02x}".format(
            int(rgb[0] * 255),
            int(rgb[1] * 255),
            int(rgb[2] * 255),
        ))
    return colors

def plot_time_series(
    df: pd.DataFrame,
    columns: List[str],
    *,
    title: str,
    ylabel: str | None = None,
    show_seeding_window: bool = True,
    figsize: tuple[float, float] = (7.2, 4.0),
    legend_mode: str = "outside",
):
    """Create a time-series figure with optional seeding-window shading."""
    fig, ax = plt.subplots(figsize=figsize)

    plotted = 0
    for column in columns:
        if column in df.columns:
            ax.plot(df["time_s"], df[column], label=column, linewidth=1.8)
            plotted += 1

    if show_seeding_window:
        for start, end in _seeding_intervals(df):
            ax.axvspan(start, end, alpha=0.12)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(ylabel or ", ".join(columns))
    ax.set_title(title, fontsize=12)
    ax.grid(alpha=0.2)

    if plotted > 1 and legend_mode != "none":
        handles, labels = ax.get_legend_handles_labels()
        if legend_mode == "outside":
            ncols = 2 if len(labels) >= 6 else 1
            ax.legend(
                handles,
                labels,
                fontsize=8,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.22),
                ncol=ncols,
                frameon=False,
            )
            fig.subplots_adjust(bottom=0.28)
        else:
            ax.legend(fontsize=8, loc="best", frameon=False)

    fig.tight_layout()
    return fig


def plot_selected_variable(df: pd.DataFrame, column: str):
    """Create a figure for a single selected variable."""
    return plot_time_series(
        df,
        [column],
        title=column,
        ylabel=column,
        show_seeding_window=True,
        figsize=(8.4, 4.4),
        legend_mode="none",
    )


def plot_control_vs_seeding(comparison_df: pd.DataFrame, base_variable: str):
    """Plot control and seeding curves for a base variable."""
    return plot_time_series(
        comparison_df,
        [f"{base_variable}_control", f"{base_variable}_seeding"],
        title=base_variable,
        ylabel=base_variable,
        show_seeding_window=True,
        figsize=(8.0, 4.4),
        legend_mode="outside",
    )


def plot_difference(comparison_df: pd.DataFrame, base_variable: str):
    """Plot seeding-control difference for a base variable."""
    fig, ax = plt.subplots(figsize=(8.0, 4.2))

    diff_col = f"{base_variable}_diff"

    if diff_col in comparison_df.columns:
        ax.plot(comparison_df["time_s"], comparison_df[diff_col], label="seeding - control", linewidth=1.8)

    for start, end in _seeding_intervals_from_comparison(comparison_df):
        ax.axvspan(start, end, alpha=0.12)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(f"Δ {base_variable}")
    ax.set_title(f"Δ {base_variable}", fontsize=12)
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.18), frameon=False)
    fig.subplots_adjust(bottom=0.24)
    fig.tight_layout()

    return fig


def plot_sweep_ranking(sweep_df: pd.DataFrame, metric: str = "ranking_value", top_n: int = 10):
    """Plot top-N sweep cases by ranking metric."""
    fig, ax = plt.subplots(figsize=(6.0, 3.2))

    if sweep_df.empty or metric not in sweep_df.columns:
        ax.set_title("No sweep ranking data")
        return fig

    plot_df = sweep_df.copy()
    plot_df = plot_df.dropna(subset=[metric])
    plot_df = plot_df.sort_values(metric, ascending=False).head(top_n)

    if plot_df.empty:
        ax.set_title("No non-empty sweep ranking data")
        return fig

    if "case_name" in plot_df.columns:
        labels = [str(value) for value in plot_df["case_name"]]
    elif "case_index" in plot_df.columns:
        labels = [str(value) for value in plot_df["case_index"]]
    else:
        labels = [str(value) for value in plot_df.index]

    ax.barh(labels[::-1], plot_df[metric].to_numpy()[::-1])
    ax.set_xlabel(metric)
    ax.set_ylabel("Sweep case")
    ax.set_title(f"Top {min(top_n, len(plot_df))} sweep cases")
    fig.tight_layout()

    return fig


def _format_sweep_case_label(row: pd.Series) -> str:
    """Build a compact readable label for one sweep case."""
    parts = []

    if "case_index" in row and pd.notna(row["case_index"]):
        try:
            parts.append(f"c{int(row['case_index']):03d}")
        except Exception:
            parts.append(f"c{row['case_index']}")

    radius_key = "param.seeding.dry_radius"
    if radius_key in row and pd.notna(row[radius_key]):
        try:
            parts.append(f"r={float(row[radius_key]) * 1.0e6:g}µm")
        except Exception:
            parts.append(f"r={row[radius_key]}")

    kappa_key = "param.seeding.kappa"
    if kappa_key in row and pd.notna(row[kappa_key]):
        parts.append(f"κ={row[kappa_key]}")

    injection_key = "param.seeding.injection_start"
    if injection_key in row and pd.notna(row[injection_key]):
        try:
            parts.append(f"inj={float(row[injection_key]):g}s")
        except Exception:
            parts.append(f"inj={row[injection_key]}")

    conc_key = "param.seeding.number_concentration"
    if conc_key in row and pd.notna(row[conc_key]):
        parts.append(f"Nseed={format_sweep_param_value(conc_key, row[conc_key])}")

    updraft_key = "param.environment.updraft_velocity"
    if updraft_key in row and pd.notna(row[updraft_key]):
        parts.append(f"w={float(row[updraft_key]):g}m/s")

    collision_key = "param.microphysics.collision"
    if collision_key in row and pd.notna(row[collision_key]):
        raw_collision = row[collision_key]
        if isinstance(raw_collision, str):
            collision_value = raw_collision.strip().lower() in {"true", "1", "yes", "on"}
        else:
            collision_value = bool(raw_collision)
        parts.append("coll=ON" if collision_value else "coll=OFF")

    handled_parameters = {
        radius_key,
        kappa_key,
        injection_key,
        conc_key,
        updraft_key,
        collision_key,
    }
    for parameter in [key for key in row.index if str(key).startswith("param.")]:
        if parameter in handled_parameters or pd.isna(row[parameter]):
            continue
        parts.append(
            f"{short_sweep_param_name(parameter)}={format_sweep_param_value(parameter, row[parameter])}"
        )

    if parts:
        return ", ".join(parts)

    if "case_name" in row and pd.notna(row["case_name"]):
        return str(row["case_name"])

    return "case"


def sweep_case_display_label(row: pd.Series) -> str:
    """Public wrapper for the compact sweep-case label used by the Results UI."""
    return _format_sweep_case_label(row)




def _make_unique_labels(labels: List[str]) -> List[str]:
    """Ensure legend labels remain unique and stable."""
    counts: Dict[str, int] = {}
    unique: List[str] = []

    for label in labels:
        count = counts.get(label, 0) + 1
        counts[label] = count
        if count == 1:
            unique.append(label)
        else:
            unique.append(f"{label} ({count})")

    return unique
def _resolve_sweep_case_dir(sweep_dir: Path, row: pd.Series) -> Path:
    """Resolve one case result directory from a sweep summary row."""
    if "result_dir" not in row or pd.isna(row["result_dir"]):
        raise ValueError("Sweep row does not contain a valid result_dir.")
    return sweep_dir / str(row["result_dir"])


def _read_sweep_case_dataframe(case_dir: Path, curve_source: str) -> pd.DataFrame:
    """
    Read one case dataframe.

    curve_source:
    - comparison: comparison.csv
    - control: control/timeseries.csv
    - seeding: seeding/timeseries.csv
    - ensemble: ensemble_statistics.csv
    """
    if curve_source == "ensemble":
        path = case_dir / "ensemble_statistics.csv"
    elif curve_source == "comparison":
        path = case_dir / "comparison.csv"
        if not path.exists() and (case_dir / "ensemble_statistics.csv").exists():
            path = case_dir / "ensemble_statistics.csv"
    elif curve_source == "control":
        path = case_dir / "control" / "timeseries.csv"
    elif curve_source == "seeding":
        path = case_dir / "seeding" / "timeseries.csv"
    else:
        raise ValueError(f"Unknown curve_source: {curve_source}")

    if not path.exists():
        return pd.DataFrame()

    return safe_read_csv(path)


def load_sweep_case_publication_data(
    sweep_dir: Path,
    row: pd.Series,
) -> tuple[str, pd.DataFrame]:
    """Load one sweep case as either a comparison or ensemble-statistics dataset."""
    case_dir = _resolve_sweep_case_dir(sweep_dir, row)
    comparison_path = case_dir / "comparison.csv"
    if comparison_path.exists():
        return "comparison", safe_read_csv(comparison_path)

    ensemble_path = case_dir / "ensemble_statistics.csv"
    if ensemble_path.exists():
        return "ensemble", safe_read_csv(ensemble_path)

    return "unavailable", pd.DataFrame()


def sweep_execution_status_table(
    sweep_dir: Path,
    sweep_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build case-level execution health, including inference for older sweep results."""
    columns = [
        "case_index",
        "case_name",
        "execution_status",
        "member_success",
        "member_failed",
        "data_available",
        "error",
        "result_dir",
    ]
    if sweep_df.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    for _, row in sweep_df.iterrows():
        case_dir = _resolve_sweep_case_dir(sweep_dir, row)
        member_success = pd.to_numeric(
            pd.Series([row.get("ensemble.n_success")]), errors="coerce"
        ).iloc[0]
        member_failed = pd.to_numeric(
            pd.Series([row.get("ensemble.n_failed")]), errors="coerce"
        ).iloc[0]
        success_count = int(member_success) if pd.notna(member_success) else 0
        failed_count = int(member_failed) if pd.notna(member_failed) else 0

        case_data = _read_sweep_case_dataframe(case_dir, "comparison")
        data_available = not case_data.empty and "time_s" in case_data.columns
        explicit_status = str(row.get("case_status", "")).strip().lower()
        if explicit_status in {"success", "partial", "failed"}:
            status = explicit_status
        elif success_count + failed_count > 0:
            status = (
                "failed"
                if success_count == 0
                else "partial"
                if failed_count > 0
                else "success"
            )
        else:
            status = "success" if data_available else "unknown"

        error = str(row.get("case_error", "") or "").strip()
        if not error or error.lower() == "nan":
            member_summary = safe_read_csv(case_dir / "member_summary.csv")
            if not member_summary.empty and "success" in member_summary.columns:
                success_values = member_summary["success"].astype(str).str.lower()
                failed_members = member_summary[~success_values.isin({"true", "1", "yes"})]
                if not failed_members.empty:
                    for error_column in ("error_message", "error"):
                        if error_column in failed_members.columns:
                            values = failed_members[error_column].dropna().astype(str)
                            if len(values):
                                error = values.iloc[0]
                                break

        rows.append(
            {
                "case_index": row.get("case_index"),
                "case_name": row.get("case_name", ""),
                "execution_status": status,
                "member_success": success_count,
                "member_failed": failed_count,
                "data_available": data_available,
                "error": error,
                "result_dir": str(row.get("result_dir", "")),
            }
        )

    return pd.DataFrame(rows, columns=columns)


def sweep_base_variables(
    sweep_dir: Path,
    sweep_df: pd.DataFrame,
    *,
    curve_source: str = "comparison",
) -> List[str]:
    """Find variables that can be plotted across sweep cases."""
    if sweep_df.empty:
        return []

    variables = set()

    for _, row in sweep_df.iterrows():
        case_dir = _resolve_sweep_case_dir(sweep_dir, row)
        df = _read_sweep_case_dataframe(case_dir, curve_source)
        if df.empty:
            continue

        is_ensemble_stats = "ensemble_statistics.csv" in str(case_dir / "ensemble_statistics.csv") and any(
            col.endswith("_mean") for col in df.columns
        )

        if is_ensemble_stats:
            for col in df.columns:
                if col.endswith("_mean"):
                    base = col[: -len("_mean")]
                    if base.endswith("_diff") or base in GROWTH_PATHWAY_PREFERRED_ORDER:
                        variables.add(base)
        elif curve_source == "comparison":
            for col in df.columns:
                if col.endswith("_seeding"):
                    base = col[: -len("_seeding")]
                    if f"{base}_control" in df.columns and f"{base}_diff" in df.columns:
                        if base != "seeding_active":
                            variables.add(base)
        else:
            for col in df.columns:
                if col != "time_s" and pd.api.types.is_numeric_dtype(df[col]):
                    if col != "seeding_active":
                        variables.add(col)

        if variables:
            break

    preferred = [
        "rain_water_mixing_ratio_diff",
        "cloud_water_mixing_ratio_diff",
        "all_activated_water_mixing_ratio_diff",
        "water_vapour_mixing_ratio_diff",
        "supersaturation_percent_diff",
        "effective_radius_all_um_diff",
    ] + GROWTH_PATHWAY_PREFERRED_ORDER + [
        "rain_water_mixing_ratio",
        "cloud_water_mixing_ratio",
        "supersaturation",
        "effective_radius_um",
        "mean_radius_m",
        "droplet_number_concentration_cm3",
        "droplet_number_concentration",
        "rain_drop_number_concentration",
        "superdroplet_count",
    ]

    ordered = [var for var in preferred if var in variables]
    ordered += sorted([var for var in variables if var not in ordered])
    return ordered




def _limit_sweep_cases_for_display(work_df: pd.DataFrame, max_cases: int) -> pd.DataFrame:
    """
    Pick cases for display without hiding the tail of the sweep grid.

    Old behavior used `.head(max_cases)`, which meant a 54-case grid with
    max_cases=20 only showed early radius values and could hide r=3 µm.
    This function samples evenly across the selected cases so the full
    parameter range remains visible.
    """
    if work_df.empty:
        return work_df

    work_df = work_df.copy()

    if "case_index" in work_df.columns:
        work_df = work_df.sort_values("case_index", ascending=True)
    elif "case_name" in work_df.columns:
        work_df = work_df.sort_values("case_name", ascending=True)

    if len(work_df) <= max_cases:
        return work_df

    indices = np.linspace(0, len(work_df) - 1, max_cases)
    indices = sorted(set(int(round(idx)) for idx in indices))
    return work_df.iloc[indices].reset_index(drop=True)


def short_sweep_param_name(column: str) -> str:
    """Human-friendly sweep parameter name."""
    aliases = {
        "param.seeding.dry_radius": "rseed",
        "param.seeding.kappa": "κseed",
        "param.seeding.geometric_sigma": "σg,seed",
        "param.seeding.number_concentration": "Nseed",
        "param.seeding.number_superdroplets": "NSD,seed",
        "param.seeding.injection_start": "tinj",
        "param.seeding.injection_duration": "Δtinj",
        "param.environment.updraft_velocity": "w",
        "param.environment.temperature": "T0",
        "param.environment.pressure": "p0",
        "param.environment.water_vapour_mixing_ratio": "qv0",
        "param.environment.timestep": "Δt",
        "param.background_aerosol.number_concentration": "Nbg",
        "param.background_aerosol.number_superdroplets": "NSD,bg",
        "param.background_aerosol.dry_radius": "rbg",
        "param.background_aerosol.kappa": "κbg",
        "param.background_aerosol.geometric_sigma": "σg,bg",
        "param.microphysics.collision": "collision",
    }
    return aliases.get(column, column.replace("param.", ""))


def format_sweep_param_value(column: str, value: Any) -> str:
    """Human-friendly sweep parameter value."""
    if pd.isna(value):
        return "NA"

    if column.endswith("dry_radius"):
        try:
            return f"{float(value) * 1.0e6:g} µm"
        except Exception:
            return str(value)

    if column.endswith("injection_start") or column.endswith("injection_end") or column.endswith("injection_duration"):
        try:
            return f"{float(value):g} s"
        except Exception:
            return str(value)

    if column.endswith("timestep"):
        try:
            return f"{float(value):g} s"
        except Exception:
            return str(value)

    if column.endswith("temperature"):
        try:
            return f"{float(value):g} K"
        except Exception:
            return str(value)

    if column.endswith("pressure"):
        try:
            return f"{float(value):g} Pa"
        except Exception:
            return str(value)

    if column.endswith("number_concentration"):
        try:
            return f"{float(value):g} cm⁻³"
        except Exception:
            return str(value)

    if column.endswith("number_superdroplets"):
        try:
            return f"{int(value)}"
        except Exception:
            return str(value)

    if column.endswith("water_vapour_mixing_ratio"):
        try:
            return f"{float(value):g} kg kg⁻¹"
        except Exception:
            return str(value)

    if column.endswith("geometric_sigma"):
        try:
            return f"{float(value):g}"
        except Exception:
            return str(value)

    if column.endswith("collision"):
        if isinstance(value, str):
            enabled = value.strip().lower() in {"true", "1", "yes", "on"}
        else:
            enabled = bool(value)
        return "ON" if enabled else "OFF"

    if column.endswith("kappa"):
        try:
            return f"{float(value):g}"
        except Exception:
            return str(value)

    try:
        numeric = float(value)
        if abs(numeric) < 1.0e-3 and numeric != 0:
            return f"{numeric:.3e}"
        return f"{numeric:g}"
    except Exception:
        return str(value)


def filter_sweep_dataframe(sweep_df: pd.DataFrame, filters: Dict[str, List[Any]]) -> pd.DataFrame:
    """Filter sweep summary dataframe by selected parameter values."""
    out = sweep_df.copy()
    for column, values in filters.items():
        if column not in out.columns or not values:
            continue
        out = out[out[column].isin(values)]
    return out.reset_index(drop=True)

def build_sweep_overlay_dataframe(
    sweep_dir: Path,
    sweep_df: pd.DataFrame,
    *,
    variable: str,
    curve_source: str = "comparison",
    comparison_mode: str = "diff",
    max_cases: int = 12,
) -> pd.DataFrame:
    """
    Build a wide dataframe for overlaying the same variable across sweep cases.

    For normal comparison outputs:
    - comparison_mode = control, seeding, diff, or relative_change_percent

    For ensemble case outputs:
    - the mean statistic is used by default: <variable>_mean
    """
    if sweep_df.empty:
        return pd.DataFrame()

    work_df = sweep_df.copy()
    if "rank" in work_df.columns:
        work_df = work_df.sort_values("rank", ascending=True)
    elif "ranking_value" in work_df.columns:
        work_df = work_df.sort_values("ranking_value", ascending=False, na_position="last")

    work_df = _limit_sweep_cases_for_display(work_df, max_cases)

    series_list = []
    labels = []

    for _, row in work_df.iterrows():
        case_dir = _resolve_sweep_case_dir(sweep_dir, row)
        case_df = _read_sweep_case_dataframe(case_dir, curve_source)

        if case_df.empty or "time_s" not in case_df.columns:
            continue

        is_ensemble_stats = any(col.endswith("_mean") for col in case_df.columns)

        if is_ensemble_stats:
            if f"{variable}_mean" in case_df.columns:
                value_col = f"{variable}_mean"
            elif variable in case_df.columns:
                value_col = variable
            else:
                continue
        elif curve_source == "comparison":
            if comparison_mode == "relative_change_percent":
                value_col = f"{variable}_relative_change_percent"
            else:
                value_col = f"{variable}_{comparison_mode}"
        else:
            value_col = variable

        if value_col not in case_df.columns:
            continue

        label = _format_sweep_case_label(row)
        labels.append(label)
        series = case_df[["time_s", value_col]].drop_duplicates(subset=["time_s"]).set_index("time_s")[value_col]
        series_list.append(series)

    if not series_list:
        return pd.DataFrame()

    unique_labels = _make_unique_labels(labels)
    renamed = []
    for series, label in zip(series_list, unique_labels):
        s = series.copy()
        s.name = label
        renamed.append(s)

    wide_df = pd.concat(renamed, axis=1).reset_index()
    return wide_df.sort_values("time_s").reset_index(drop=True)


def plot_sweep_overlay(
    overlay_df: pd.DataFrame,
    *,
    variable: str,
    curve_label: str,
    figsize: tuple[float, float] = (9.2, 4.8),
    show_legend: bool = False,
    legend_mode: str = "none",
    shaded_intervals: List[tuple[float, float]] | None = None,
    label_endpoints: bool = True,
):
    """
    Plot a variable over time for multiple sweep cases.

    Legends are kept out of matrix plots by default. Curve IDs are drawn near
    the right side of the curve and mapped to case settings in a separate table.
    """
    fig, ax = plt.subplots(figsize=figsize)

    if overlay_df.empty or "time_s" not in overlay_df.columns:
        ax.set_title(f"No sweep time-series data: {variable}")
        return fig

    value_cols = [col for col in overlay_df.columns if col != "time_s"]
    colors = _curve_palette(len(value_cols))

    if shaded_intervals:
        for start, end in shaded_intervals:
            ax.axvspan(start, end, alpha=0.12, label="seeding window" if start == shaded_intervals[0][0] else None)

    for idx, col in enumerate(value_cols):
        color = colors[idx]
        curve_id = idx + 1
        ax.plot(
            overlay_df["time_s"],
            overlay_df[col],
            label=f"{curve_id:02d}",
            linewidth=1.9,
            color=color,
        )

        if label_endpoints:
            series = overlay_df[col].dropna()
            if len(series) > 0:
                last_idx = series.index[-1]
                x = overlay_df.loc[last_idx, "time_s"]
                y = overlay_df.loc[last_idx, col]
                ax.annotate(
                    f"{curve_id}",
                    xy=(x, y),
                    xytext=(4, 0),
                    textcoords="offset points",
                    fontsize=7.5,
                    color=color,
                    va="center",
                )

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(variable)
    ax.set_title(f"{variable} · {curve_label}", fontsize=12)
    ax.grid(alpha=0.22)

    if show_legend and value_cols and legend_mode != "none":
        if legend_mode == "inside":
            ax.legend(fontsize=7.5, loc="best", frameon=True)
        elif legend_mode == "outside":
            ncols = 4 if len(value_cols) >= 12 else 3 if len(value_cols) >= 8 else 2
            ax.legend(
                fontsize=7.5,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.22),
                ncol=ncols,
                frameon=False,
                handlelength=1.5,
                columnspacing=0.9,
            )
            fig.subplots_adjust(bottom=0.30)

    fig.tight_layout()
    return fig

    labels = []
    for col in overlay_df.columns:
        if col == "time_s":
            continue
        ax.plot(overlay_df["time_s"], overlay_df[col], label=col, linewidth=1.9)
        labels.append(col)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(variable)
    ax.set_title(f"{variable} · {curve_label}", fontsize=12)
    ax.grid(alpha=0.22)

    if show_legend and labels and legend_mode != "none":
        if legend_mode == "inside":
            ax.legend(fontsize=7.5, loc="best", frameon=True)
        elif legend_mode == "outside":
            ncols = 3 if len(labels) >= 12 else 2 if len(labels) >= 6 else 1
            ax.legend(
                fontsize=7.5,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.22),
                ncol=ncols,
                frameon=False,
                handlelength=1.5,
                columnspacing=0.9,
            )
            fig.subplots_adjust(bottom=0.30)

    fig.tight_layout()
    return fig

    labels = []
    for col in overlay_df.columns:
        if col == "time_s":
            continue
        ax.plot(overlay_df["time_s"], overlay_df[col], label=col, linewidth=1.8)
        labels.append(col)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(variable)
    ax.set_title(f"{variable} · {curve_label}", fontsize=12)
    ax.grid(alpha=0.2)

    if show_legend and labels:
        ncols = 2 if len(labels) >= 8 else 1
        ax.legend(
            fontsize=7.5,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.24),
            ncol=ncols,
            frameon=False,
            handlelength=1.5,
            columnspacing=0.9,
        )
        fig.subplots_adjust(bottom=0.32)

    fig.tight_layout()
    return fig

    for col in overlay_df.columns:
        if col == "time_s":
            continue
        ax.plot(overlay_df["time_s"], overlay_df[col], label=col)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(variable)
    ax.set_title(f"{variable} · {curve_label}")
    ax.legend(fontsize="x-small", loc="best")
    fig.tight_layout()

    return fig


def compute_overlay_spread(overlay_df: pd.DataFrame, *, tolerance: float = 1.0e-14) -> Dict[str, Any]:
    """
    Diagnose whether sweep case curves actually differ.

    Returns spread statistics across case curves at each time.
    """
    if overlay_df.empty or "time_s" not in overlay_df.columns:
        return {
            "n_cases": 0,
            "max_abs_spread": None,
            "mean_abs_spread": None,
            "final_abs_spread": None,
            "curves_overlap": True,
        }

    value_cols = [col for col in overlay_df.columns if col != "time_s"]
    if not value_cols:
        return {
            "n_cases": 0,
            "max_abs_spread": None,
            "mean_abs_spread": None,
            "final_abs_spread": None,
            "curves_overlap": True,
        }

    values = overlay_df[value_cols]
    row_spread = values.max(axis=1, skipna=True) - values.min(axis=1, skipna=True)

    max_abs_spread = float(row_spread.max(skipna=True)) if len(row_spread) else None
    mean_abs_spread = float(row_spread.mean(skipna=True)) if len(row_spread) else None
    final_abs_spread = float(row_spread.iloc[-1]) if len(row_spread) else None

    curves_overlap = (
        max_abs_spread is None
        or not pd.notna(max_abs_spread)
        or abs(max_abs_spread) <= tolerance
    )

    return {
        "n_cases": len(value_cols),
        "max_abs_spread": max_abs_spread,
        "mean_abs_spread": mean_abs_spread,
        "final_abs_spread": final_abs_spread,
        "curves_overlap": bool(curves_overlap),
    }


def sweep_param_columns(sweep_df: pd.DataFrame) -> List[str]:
    """Return numeric sweep parameter columns."""
    return [
        col
        for col in sweep_df.columns
        if col.startswith("param.") and pd.api.types.is_numeric_dtype(sweep_df[col])
    ]


def plot_sweep_heatmap(
    sweep_df: pd.DataFrame,
    *,
    x_param: str,
    y_param: str,
    metric: str,
):
    """Plot a 2D parameter-response heatmap from sweep_summary.csv."""
    fig, ax = plt.subplots(figsize=(5.2, 3.8))

    if (
        sweep_df.empty
        or x_param not in sweep_df.columns
        or y_param not in sweep_df.columns
        or metric not in sweep_df.columns
    ):
        ax.set_title("No heatmap data")
        return fig

    pivot = sweep_df.pivot_table(
        index=y_param,
        columns=x_param,
        values=metric,
        aggfunc="mean",
    )

    if pivot.empty:
        ax.set_title("No heatmap data")
        return fig

    image = ax.imshow(pivot.to_numpy(), aspect="auto", origin="lower")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(value) for value in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(value) for value in pivot.index])
    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(metric)
    fig.colorbar(image, ax=ax, label=metric)
    fig.tight_layout()

    return fig



def build_overlay_legend_table(overlay_df: pd.DataFrame) -> pd.DataFrame:
    """Build a separate legend table for an overlay dataframe."""
    if overlay_df.empty:
        return pd.DataFrame(columns=["curve_id", "color", "case_label"])

    labels = [col for col in overlay_df.columns if col != "time_s"]
    colors = _curve_palette(len(labels))
    rows = []

    for idx, (label, color) in enumerate(zip(labels, colors), start=1):
        row: Dict[str, Any] = {
            "curve_id": idx,
            "color": color,
            "case_label": label,
        }

        parts = [part.strip() for part in str(label).split("·")]
        for part in parts:
            if part.startswith("c") and part[1:].isdigit():
                row["case"] = part
            elif part.startswith("inj="):
                row["injection_start"] = part.replace("inj=", "")
            elif part.startswith("r="):
                row["dry_radius"] = part.replace("r=", "")
            elif part.startswith("κ="):
                row["kappa"] = part.replace("κ=", "")
            elif part.startswith("N="):
                row["seeding_number"] = part.replace("N=", "")
            elif part.startswith("w="):
                row["updraft"] = part.replace("w=", "")
            elif part.startswith("coll="):
                row["collision"] = part.replace("coll=", "")

        rows.append(row)

    return pd.DataFrame(rows)


def build_curve_value_summary(overlay_df: pd.DataFrame) -> pd.DataFrame:
    """Summarize final, max, and min values for each curve."""
    if overlay_df.empty or "time_s" not in overlay_df.columns:
        return pd.DataFrame(columns=["case_label", "final", "max", "min"])

    rows = []
    for col in overlay_df.columns:
        if col == "time_s":
            continue
        series = overlay_df[col]
        rows.append(
            {
                "case_label": col,
                "final": float(series.iloc[-1]) if len(series) and pd.notna(series.iloc[-1]) else None,
                "max": float(series.max(skipna=True)) if len(series) and pd.notna(series.max(skipna=True)) else None,
                "min": float(series.min(skipna=True)) if len(series) and pd.notna(series.min(skipna=True)) else None,
            }
        )

    return pd.DataFrame(rows)



def style_curve_legend_table(legend_df: pd.DataFrame):
    """Style legend table so the color column works as a visual swatch."""
    if legend_df.empty or "color" not in legend_df.columns:
        return legend_df

    def style_color_cell(value: Any) -> str:
        if isinstance(value, str) and value.startswith("#"):
            return f"background-color: {value}; color: {value};"
        return ""

    return legend_df.style.map(style_color_cell, subset=["color"])



def sweep_seeding_intervals(sweep_dir: Path, sweep_df: pd.DataFrame) -> List[tuple[float, float]]:
    """Extract seeding-active intervals from the first readable sweep comparison case."""
    if sweep_df.empty:
        return []

    for _, row in sweep_df.iterrows():
        try:
            case_dir = _resolve_sweep_case_dir(sweep_dir, row)
            comparison_df = _read_sweep_case_dataframe(case_dir, "comparison")
            if not comparison_df.empty:
                intervals = _seeding_intervals_from_comparison(comparison_df)
                if intervals:
                    return intervals
        except Exception:
            continue

    return []



def growth_pathway_variable_groups(columns: List[str]) -> Dict[str, List[str]]:
    """Return Exper2 diagnostic groups limited to available variable names."""
    available = set(columns)
    return {
        group: [col for col in vars_ if col in available]
        for group, vars_ in GROWTH_PATHWAY_VARIABLE_GROUPS.items()
        if any(col in available for col in vars_)
    }


def growth_pathway_all_variables() -> List[str]:
    """Return preferred Exper2 variable order."""
    return list(GROWTH_PATHWAY_PREFERRED_ORDER)


def diagnostic_provenance_dataframe(provenance_rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Turn diagnostic_provenance.json rows into a display-ready DataFrame.

    Columns: variable / provenance_label / basis. Rows are already ordered by
    GROWTH_PATHWAY_PREFERRED_ORDER (see analysis.growth_pathway_diagnostics).
    """
    if not provenance_rows:
        return pd.DataFrame(columns=["variable", "provenance_label", "basis"])

    df = pd.DataFrame(provenance_rows)
    columns = [c for c in ["variable", "provenance_label", "basis"] if c in df.columns]
    return df[columns]


def diagnostic_provenance_summary_counts(provenance_rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count how many diagnostic variables are native / derived / proxy."""
    counts = {"native": 0, "derived": 0, "proxy": 0}
    for row in provenance_rows:
        provenance = row.get("provenance")
        if provenance in counts:
            counts[provenance] += 1
    return counts


def result_file_roles_dataframe(metadata: Dict[str, Any]) -> pd.DataFrame:
    """
    Return the 'what is each output file for' table for a loaded result.

    Prefers the `file_roles` already embedded in metadata.json by the runner
    (see analysis/result_files.py); falls back to computing it from
    `result_files` for older result folders written before this feature.
    """
    file_roles = metadata.get("file_roles")
    if not file_roles:
        result_files = metadata.get("result_files", {})
        file_roles = describe_result_files(list(result_files.values()))

    if not file_roles:
        return pd.DataFrame(columns=["file", "생성 시점", "무엇에 대한 답인가", "설명"])

    return pd.DataFrame(file_roles)


def figure_to_png_bytes(fig, *, dpi: int = 300) -> bytes:
    """Serialize a matplotlib figure to a publication-ready PNG byte stream."""
    return figure_to_bytes(fig, file_format="png", dpi=dpi)


def figure_to_bytes(fig, *, file_format: str, dpi: int = 300) -> bytes:
    """Serialize a matplotlib figure to PNG, SVG, or PDF."""
    normalized = str(file_format).lower()
    if normalized not in {"png", "svg", "pdf"}:
        raise ValueError("file_format must be one of: png, svg, pdf")
    buffer = io.BytesIO()
    save_kwargs = {"format": normalized, "bbox_inches": "tight"}
    if normalized == "png":
        save_kwargs["dpi"] = dpi
    fig.savefig(buffer, **save_kwargs)
    buffer.seek(0)
    return buffer.getvalue()


def figure_to_svg_bytes(fig) -> bytes:
    """Serialize a matplotlib figure to editable SVG vector bytes."""
    return figure_to_bytes(fig, file_format="svg")


def figure_to_pdf_bytes(fig) -> bytes:
    """Serialize a matplotlib figure to publication-ready PDF vector bytes."""
    return figure_to_bytes(fig, file_format="pdf")


def ensemble_available_bases(stats_df: pd.DataFrame) -> List[str]:
    """Return variables available for ensemble uncertainty plotting."""
    return ensemble_variable_bases(stats_df)


def plot_ensemble_uncertainty(
    stats_df: pd.DataFrame,
    *,
    base_variable: str,
    mode: str = "mean_std",
    figsize: tuple[float, float] = (9.5, 5.2),
):
    """Plot ensemble mean±std or median+IQR for one variable."""
    fig, ax = plt.subplots(figsize=figsize)

    if stats_df.empty or "time_s" not in stats_df.columns:
        ax.set_title(f"No ensemble statistics: {base_variable}")
        return fig

    x = stats_df["time_s"].to_numpy(dtype=float)

    if mode == "median_iqr":
        center_col = f"{base_variable}_median"
        low_col = f"{base_variable}_q25"
        high_col = f"{base_variable}_q75"
        label = "median"
        band_label = "IQR"
    else:
        center_col = f"{base_variable}_mean"
        low_col = f"{base_variable}_mean"
        high_col = f"{base_variable}_mean"
        std_col = f"{base_variable}_std"
        label = "mean"
        band_label = "±1 std"

    if center_col not in stats_df.columns:
        ax.set_title(f"Missing ensemble statistic: {center_col}")
        return fig

    center = stats_df[center_col].to_numpy(dtype=float)

    if mode == "median_iqr":
        if low_col in stats_df.columns and high_col in stats_df.columns:
            low = stats_df[low_col].to_numpy(dtype=float)
            high = stats_df[high_col].to_numpy(dtype=float)
        else:
            low = center
            high = center
    else:
        if std_col in stats_df.columns:
            std = stats_df[std_col].fillna(0).to_numpy(dtype=float)
            low = center - std
            high = center + std
        else:
            low = center
            high = center

    ax.plot(x, center, label=label, linewidth=2.0)
    ax.fill_between(x, low, high, alpha=0.22, label=band_label)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(base_variable)
    ax.set_title(f"{base_variable} · {label}", fontsize=12)
    ax.grid(alpha=0.22)
    ax.legend(fontsize=8, loc="best", frameon=False)
    fig.tight_layout()

    return fig



def recommended_sweep_variables(available_vars: List[str]) -> List[str]:
    """Return a compact recommended set for first-look sweep dashboard."""
    preferred = [
        "rain_water_mixing_ratio_diff",
        "cloud_water_mixing_ratio_diff",
        "all_activated_water_mixing_ratio_diff",
        "water_vapour_mixing_ratio_diff",
        "supersaturation_percent_diff",
        "effective_radius_all_um_diff",
        "rain_water_mixing_ratio",
        "cloud_water_mixing_ratio",
        "supersaturation_percent",
    ]
    out = [var for var in preferred if var in available_vars]
    if out:
        return out
    return available_vars[:4]



def _select_sweep_value_column(
    case_df: pd.DataFrame,
    *,
    variable: str,
    curve_source: str,
    comparison_mode: str,
) -> str | None:
    """Select a plottable value column from a case dataframe."""
    if case_df.empty:
        return None

    if any(col.endswith("_mean") for col in case_df.columns):
        candidate = f"{variable}_mean"
        if candidate in case_df.columns:
            return candidate
        if variable in case_df.columns:
            return variable
        return None

    if curve_source == "comparison":
        if comparison_mode == "relative_change_percent":
            candidate = f"{variable}_relative_change_percent"
        else:
            candidate = f"{variable}_{comparison_mode}"
        return candidate if candidate in case_df.columns else None

    return variable if variable in case_df.columns else None


def _case_numeric_parameter(row: pd.Series, parameter_column: str) -> float | None:
    if parameter_column not in row or pd.isna(row[parameter_column]):
        return None
    try:
        return float(row[parameter_column])
    except Exception:
        return None


def build_sweep_overlay_dataframe_relative_time(
    sweep_dir: Path,
    sweep_df: pd.DataFrame,
    *,
    variable: str,
    curve_source: str = "comparison",
    comparison_mode: str = "diff",
    time_reference_param: str = "param.seeding.injection_start",
    max_cases: int = 12,
) -> pd.DataFrame:
    """Build overlay dataframe with time shifted by a sweep parameter."""
    if sweep_df.empty:
        return pd.DataFrame()

    work_df = sweep_df.copy()
    if "rank" in work_df.columns:
        work_df = work_df.sort_values("rank", ascending=True)
    elif "ranking_value" in work_df.columns:
        work_df = work_df.sort_values("ranking_value", ascending=False, na_position="last")

    work_df = _limit_sweep_cases_for_display(work_df, max_cases)

    series_list = []
    labels = []

    for _, row in work_df.iterrows():
        case_dir = _resolve_sweep_case_dir(sweep_dir, row)
        case_df = _read_sweep_case_dataframe(case_dir, curve_source)

        if case_df.empty or "time_s" not in case_df.columns:
            continue

        value_col = _select_sweep_value_column(
            case_df,
            variable=variable,
            curve_source=curve_source,
            comparison_mode=comparison_mode,
        )
        if value_col is None:
            continue

        shift_value = _case_numeric_parameter(row, time_reference_param) or 0.0
        label = _format_sweep_case_label(row)
        labels.append(label)

        temp = case_df[["time_s", value_col]].copy()
        temp["time_relative_s"] = temp["time_s"] - shift_value
        series = temp[["time_relative_s", value_col]].drop_duplicates(subset=["time_relative_s"]).set_index("time_relative_s")[value_col]
        series_list.append(series)

    if not series_list:
        return pd.DataFrame()

    unique_labels = _make_unique_labels(labels)
    renamed = []
    for series, label in zip(series_list, unique_labels):
        s = series.copy()
        s.name = label
        renamed.append(s)

    wide_df = pd.concat(renamed, axis=1).reset_index().rename(columns={"time_relative_s": "time_s"})
    return wide_df.sort_values("time_s").reset_index(drop=True)


def _time_integral(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2:
        return float("nan")
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x=x))
    return float(np.trapz(y, x=x))


def sweep_case_metrics_table(
    sweep_dir: Path,
    sweep_df: pd.DataFrame,
    *,
    variable: str,
    curve_source: str = "comparison",
    comparison_mode: str = "diff",
) -> pd.DataFrame:
    """
    Summarize each sweep case's time-series into scalar final/max/min/integral/peak_time_s
    values, alongside every param.* column for that case.

    This is the shared building block for both the fixed-parameter sensitivity
    summary and the collapse-variable analysis below: both need "one row per
    case, with param columns plus a scalar response", they just plot it
    differently.
    """
    if sweep_df.empty:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []

    for _, row in sweep_df.iterrows():
        case_dir = _resolve_sweep_case_dir(sweep_dir, row)
        case_df = _read_sweep_case_dataframe(case_dir, curve_source)
        value_col = _select_sweep_value_column(
            case_df,
            variable=variable,
            curve_source=curve_source,
            comparison_mode=comparison_mode,
        )

        if case_df.empty or "time_s" not in case_df.columns or value_col is None:
            continue

        values = pd.to_numeric(case_df[value_col], errors="coerce")
        time = pd.to_numeric(case_df["time_s"], errors="coerce")
        finite_mask = np.isfinite(values.to_numpy(dtype=float)) & np.isfinite(time.to_numpy(dtype=float))

        if not finite_mask.any():
            continue

        x_values = time.to_numpy(dtype=float)[finite_mask]
        y_values = values.to_numpy(dtype=float)[finite_mask]

        metric_row: Dict[str, Any] = {
            "case_label": _format_sweep_case_label(row),
            "value_column": value_col,
            "final": float(y_values[-1]),
            "max": float(np.nanmax(y_values)),
            "min": float(np.nanmin(y_values)),
            "integral": _time_integral(x_values, y_values),
            "peak_time_s": float(x_values[int(np.nanargmax(y_values))]),
        }

        for col in sweep_df.columns:
            if col.startswith("param."):
                metric_row[col] = row[col]

        rows.append(metric_row)

    return pd.DataFrame(rows)


def varying_sweep_parameters(metrics_df: pd.DataFrame, param_cols: List[str]) -> List[str]:
    """Return which param.* columns still have more than one distinct value in metrics_df."""
    if metrics_df.empty:
        return []
    varying = []
    for col in param_cols:
        if col not in metrics_df.columns:
            continue
        if metrics_df[col].nunique(dropna=True) > 1:
            varying.append(col)
    return varying


def plot_parameter_sensitivity(
    metrics_df: pd.DataFrame,
    *,
    x_parameter: str,
    statistic: str,
    variable: str,
):
    """
    Plot statistic vs. one sweep parameter, using only cases already filtered so
    every other swept parameter is held fixed. Callers are responsible for the
    filtering (see varying_sweep_parameters) -- this function does not check it,
    since it is also useful as a raw plotting primitive.
    """
    fig, ax = plt.subplots(figsize=(8.8, 4.8))

    if metrics_df.empty or statistic not in metrics_df.columns or x_parameter not in metrics_df.columns:
        ax.set_title("No sensitivity summary data")
        return fig

    plot_df = metrics_df.copy()
    plot_df = plot_df.dropna(subset=[x_parameter, statistic])

    if plot_df.empty:
        ax.set_title("No sensitivity summary data")
        return fig

    try:
        plot_df[x_parameter] = pd.to_numeric(plot_df[x_parameter])
        plot_df = plot_df.sort_values(x_parameter)
        ax.plot(plot_df[x_parameter], plot_df[statistic], marker="o", linewidth=1.8)
    except Exception:
        plot_df[x_parameter] = plot_df[x_parameter].astype(str)
        ax.bar(plot_df[x_parameter], plot_df[statistic])

    ax.set_xlabel(short_sweep_param_name(x_parameter))
    ax.set_ylabel(f"{statistic} of {variable}")
    ax.set_title(f"{variable}: {statistic} vs {short_sweep_param_name(x_parameter)}\n(other swept parameters held fixed)", fontsize=11)
    ax.grid(alpha=0.22)
    fig.tight_layout()

    return fig


COLLAPSE_VARIABLE_COLUMN = "log10_kappa_r_dry3"


def add_kappa_koehler_collapse_variable(
    metrics_df: pd.DataFrame,
    *,
    dry_radius_col: str = "param.seeding.dry_radius",
    kappa_col: str = "param.seeding.kappa",
) -> pd.DataFrame:
    """
    Add log10(kappa * (dry_radius / 1 m)^3), a dimensionless diagnostic based
    on the kappa-times-dry-volume term in kappa-Koehler theory. A collapse onto
    this coordinate is a hypothesis to test, not a guaranteed property: the
    response can still depend on supersaturation history, injection timing,
    collisions, size-distribution width, and other conditions.

    Returns metrics_df unchanged (no new column) if either parameter column is
    absent, e.g. for sweeps that don't vary dry_radius/kappa.
    """
    if dry_radius_col not in metrics_df.columns or kappa_col not in metrics_df.columns:
        return metrics_df

    out = metrics_df.copy()
    dry_radius = pd.to_numeric(out[dry_radius_col], errors="coerce")
    kappa = pd.to_numeric(out[kappa_col], errors="coerce")
    product = kappa * (dry_radius ** 3)

    with np.errstate(divide="ignore", invalid="ignore"):
        out[COLLAPSE_VARIABLE_COLUMN] = np.where(product > 0, np.log10(product), np.nan)

    return out


def plot_collapse_variable_response(
    metrics_df: pd.DataFrame,
    *,
    statistic: str,
    variable: str,
    color_by: str | None = None,
):
    """
    Scatter statistic vs. the kappa-Koehler collapse variable across all
    dry_radius x kappa sweep cases at once (unlike plot_parameter_sensitivity,
    this intentionally does NOT require fixing other parameters -- collapsing
    onto log10(kappa * r_dry^3) is the point: if the physics holds, cases with
    different dry_radius/kappa combinations but the same collapse-variable
    value should show a similar response).
    """
    fig, ax = plt.subplots(figsize=(8.8, 4.8))

    if (
        metrics_df.empty
        or COLLAPSE_VARIABLE_COLUMN not in metrics_df.columns
        or statistic not in metrics_df.columns
    ):
        ax.set_title("No collapse-variable data (sweep does not vary both dry_radius and kappa)")
        return fig

    plot_df = metrics_df.dropna(subset=[COLLAPSE_VARIABLE_COLUMN, statistic]).copy()
    if plot_df.empty:
        ax.set_title("No collapse-variable data")
        return fig

    if color_by and color_by in plot_df.columns:
        groups = list(plot_df.groupby(color_by))
        cmap = plt.get_cmap("viridis", max(len(groups), 1))
        for idx, (group_value, group_df) in enumerate(groups):
            ax.scatter(
                group_df[COLLAPSE_VARIABLE_COLUMN],
                group_df[statistic],
                color=cmap(idx),
                label=f"{short_sweep_param_name(color_by)}={format_sweep_param_value(color_by, group_value)}",
                s=42,
                alpha=0.85,
                edgecolors="white",
                linewidths=0.4,
            )
        ax.legend(fontsize=8, loc="best")
    else:
        ax.scatter(plot_df[COLLAPSE_VARIABLE_COLUMN], plot_df[statistic], s=42, alpha=0.85, color="#2f6fb0")

    ax.set_xlabel(r"$\log_{10}[\kappa \cdot (r_{dry}/1\,\mathrm{m})^3]$")
    ax.set_ylabel(f"{statistic} of {variable}")
    ax.set_title(f"{variable}: response vs κ–dry-volume coordinate", fontsize=11)
    ax.grid(alpha=0.22)
    fig.tight_layout()

    return fig


def plot_response_surface_heatmap(
    metrics_df: pd.DataFrame,
    *,
    x_param: str,
    y_param: str,
    statistic: str,
    variable: str,
    agg: str | None = None,
):
    """
    2D response-surface heatmap of `statistic` over two swept parameters
    (e.g. dry_radius x kappa). By default, the plot refuses to average across
    additional varying parameters because that would confound the response
    surface. Callers may explicitly provide an aggregation only when pooling is
    scientifically intended.
    """
    fig, ax = plt.subplots(figsize=(7.2, 5.6))

    required = [x_param, y_param, statistic]
    if metrics_df.empty or any(col not in metrics_df.columns for col in required):
        ax.set_title("No response-surface data")
        return fig

    plot_df = metrics_df.dropna(subset=required).copy()
    if plot_df.empty:
        ax.set_title("No response-surface data")
        return fig

    other_parameter_columns = [
        col
        for col in plot_df.columns
        if col.startswith("param.") and col not in {x_param, y_param}
    ]
    confounders = [
        col for col in other_parameter_columns if plot_df[col].nunique(dropna=True) > 1
    ]
    if confounders and agg is None:
        ax.set_title(
            "Fix other swept parameters before plotting this response surface:\n"
            + ", ".join(short_sweep_param_name(col) for col in confounders),
            fontsize=10,
        )
        return fig

    try:
        plot_df[x_param] = pd.to_numeric(plot_df[x_param])
        plot_df[y_param] = pd.to_numeric(plot_df[y_param])
    except Exception:
        ax.set_title("Response surface requires numeric parameters")
        return fig

    aggregate = agg or "mean"
    pivot = plot_df.pivot_table(index=y_param, columns=x_param, values=statistic, aggfunc=aggregate)
    if pivot.empty:
        ax.set_title("No response-surface data")
        return fig

    mesh = ax.pcolormesh(pivot.columns, pivot.index, pivot.to_numpy(), cmap="viridis", shading="nearest")
    fig.colorbar(mesh, ax=ax, label=f"{statistic} of {variable}")

    ax.set_xlabel(short_sweep_param_name(x_param))
    ax.set_ylabel(short_sweep_param_name(y_param))
    ax.set_title(
        f"{variable}: {statistic} response surface\n({short_sweep_param_name(x_param)} x {short_sweep_param_name(y_param)})",
        fontsize=11,
    )
    fig.tight_layout()

    return fig


def likely_injection_time_sweep(sweep_df: pd.DataFrame) -> bool:
    """Detect whether injection timing is one of the sweep axes."""
    return any(
        col in sweep_df.columns
        for col in [
            "param.seeding.injection_start",
            "param.seeding.injection_end",
            "param.seeding.injection_duration",
        ]
    )



def result_is_readable(entry: ResultEntry) -> bool:
    """Check whether a result entry has a non-empty primary CSV."""
    primary_files = {
        "ensemble": "ensemble_statistics.csv",
        "parameter_sweep": "sweep_summary.csv",
        "comparison": "comparison.csv",
        "single": "timeseries.csv",
        "legacy_csv": "",
    }

    if entry.result_type == "legacy_csv":
        path = entry.path
    else:
        filename = primary_files.get(entry.result_type, "")
        path = entry.path / filename if filename else entry.path

    if not path.exists():
        return False

    try:
        return path.stat().st_size > 0
    except OSError:
        return False

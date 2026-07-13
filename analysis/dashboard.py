from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import pandas as pd
import yaml

DASHBOARD_BUILD_ID = "scenario-seeding-window-color-legend-20260713"


@dataclass(frozen=True)
class ResultEntry:
    """A discovered simulation result."""

    path: Path
    label: str
    is_run_directory: bool
    result_type: str


def discover_results(result_dir: Path) -> List[ResultEntry]:
    """Find structured run directories and legacy CSV outputs."""
    result_dir.mkdir(exist_ok=True)

    entries: List[ResultEntry] = []

    for path in sorted([p for p in result_dir.iterdir() if p.is_dir()], reverse=True):
        if (path / "sweep_summary.csv").exists():
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
    if entry.result_type == "parameter_sweep":
        sweep_path = entry.path / "sweep_summary.csv"
        summary_path = entry.path / "summary.json"
        metadata_path = entry.path / "metadata.json"
        config_path = entry.path / "config.yaml"
        validation_path = entry.path / "validation_report.json"

        sweep_df = pd.read_csv(sweep_path)

        return {
            "entry": entry,
            "timeseries": sweep_df,
            "sweep": sweep_df,
            "comparison": pd.DataFrame(),
            "control": pd.DataFrame(),
            "seeding": pd.DataFrame(),
            "summary": _read_json(summary_path),
            "metadata": _read_json(metadata_path),
            "config": _read_yaml(config_path),
            "validation": _read_json(validation_path),
            "files": {
                "sweep_summary": sweep_path,
                "summary": summary_path,
                "metadata": metadata_path,
                "config": config_path,
                "validation": validation_path,
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

        comparison_df = pd.read_csv(comparison_path)
        control_df = pd.read_csv(control_path) if control_path.exists() else pd.DataFrame()
        seeding_df = pd.read_csv(seeding_path) if seeding_path.exists() else pd.DataFrame()

        return {
            "entry": entry,
            "timeseries": comparison_df,
            "sweep": pd.DataFrame(),
            "comparison": comparison_df,
            "control": control_df,
            "seeding": seeding_df,
            "summary": _read_json(summary_path),
            "metadata": _read_json(metadata_path),
            "config": _read_yaml(config_path),
            "validation": _read_json(validation_path),
            "files": {
                "comparison": comparison_path,
                "summary": summary_path,
                "metadata": metadata_path,
                "config": config_path,
                "validation": validation_path,
                "control_timeseries": control_path,
                "seeding_timeseries": seeding_path,
            },
        }

    if entry.is_run_directory:
        timeseries_path = entry.path / "timeseries.csv"
        summary_path = entry.path / "summary.json"
        metadata_path = entry.path / "metadata.json"
        config_path = entry.path / "config.yaml"
        validation_path = entry.path / "validation_report.json"

        df = pd.read_csv(timeseries_path)

        return {
            "entry": entry,
            "timeseries": df,
            "sweep": pd.DataFrame(),
            "comparison": pd.DataFrame(),
            "control": pd.DataFrame(),
            "seeding": pd.DataFrame(),
            "summary": _read_json(summary_path),
            "metadata": _read_json(metadata_path),
            "config": _read_yaml(config_path),
            "validation": _read_json(validation_path),
            "files": {
                "timeseries": timeseries_path,
                "summary": summary_path,
                "metadata": metadata_path,
                "config": config_path,
                "validation": validation_path,
            },
        }

    df = pd.read_csv(entry.path)
    return {
        "entry": entry,
        "timeseries": df,
        "sweep": pd.DataFrame(),
        "comparison": pd.DataFrame(),
        "control": pd.DataFrame(),
        "seeding": pd.DataFrame(),
        "summary": {},
        "metadata": {"source": "legacy_csv", "filename": entry.path.name},
        "config": {},
        "validation": [],
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

    preferred_order = [
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

    radius_key = "param.seeding.dry_radius"
    if radius_key in row and pd.notna(row[radius_key]):
        try:
            parts.append(f"r={float(row[radius_key]) * 1.0e6:g} µm")
        except Exception:
            parts.append(f"r={row[radius_key]}")

    kappa_key = "param.seeding.kappa"
    if kappa_key in row and pd.notna(row[kappa_key]):
        parts.append(f"κ={row[kappa_key]}")

    conc_key = "param.seeding.number_concentration"
    if conc_key in row and pd.notna(row[conc_key]):
        parts.append(f"Nseed={row[conc_key]}")

    updraft_key = "param.environment.updraft_velocity"
    if updraft_key in row and pd.notna(row[updraft_key]):
        parts.append(f"w={row[updraft_key]}")

    if parts:
        return ", ".join(parts)

    if "case_name" in row and pd.notna(row["case_name"]):
        return str(row["case_name"])

    if "case_index" in row and pd.notna(row["case_index"]):
        return f"case {int(row['case_index'])}"

    return "case"




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
    """
    if curve_source == "comparison":
        path = case_dir / "comparison.csv"
    elif curve_source == "control":
        path = case_dir / "control" / "timeseries.csv"
    elif curve_source == "seeding":
        path = case_dir / "seeding" / "timeseries.csv"
    else:
        raise ValueError(f"Unknown curve_source: {curve_source}")

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


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

        if curve_source == "comparison":
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

    For comparison case outputs:
    - comparison_mode = control, seeding, diff, or relative_change_percent
    """
    if sweep_df.empty:
        return pd.DataFrame()

    work_df = sweep_df.copy()
    if "rank" in work_df.columns:
        work_df = work_df.sort_values("rank", ascending=True)
    elif "ranking_value" in work_df.columns:
        work_df = work_df.sort_values("ranking_value", ascending=False, na_position="last")

    work_df = work_df.head(max_cases)

    series_list = []
    labels = []

    for _, row in work_df.iterrows():
        case_dir = _resolve_sweep_case_dir(sweep_dir, row)
        case_df = _read_sweep_case_dataframe(case_dir, curve_source)

        if case_df.empty or "time_s" not in case_df.columns:
            continue

        if curve_source == "comparison":
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
            elif part.startswith("r="):
                row["dry_radius"] = part.replace("r=", "")
            elif part.startswith("κ="):
                row["kappa"] = part.replace("κ=", "")
            elif part.startswith("N="):
                row["seeding_number"] = part.replace("N=", "")
            elif part.startswith("w="):
                row["updraft"] = part.replace("w=", "")

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

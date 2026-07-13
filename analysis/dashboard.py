from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import pandas as pd
import yaml


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
    excluded = {
        "seeding_active",
    }

    preferred_order = [
        "rain_water_mixing_ratio",
        "cloud_water_mixing_ratio",
        "effective_radius_um",
        "droplet_number_concentration_cm3",
        "droplet_number_concentration",
        "rain_drop_number_concentration",
        "superdroplet_count",
        "mean_radius_m",
        "supersaturation",
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


def plot_time_series(
    df: pd.DataFrame,
    columns: List[str],
    *,
    title: str,
    ylabel: str | None = None,
    show_seeding_window: bool = True,
    figsize: tuple[float, float] = (5.2, 2.8),
):
    """Create a compact time-series figure with optional seeding-window shading."""
    fig, ax = plt.subplots(figsize=figsize)

    for column in columns:
        if column in df.columns:
            ax.plot(df["time_s"], df[column], label=column)

    if show_seeding_window:
        for start, end in _seeding_intervals(df):
            ax.axvspan(start, end, alpha=0.15)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(ylabel or ", ".join(columns))
    ax.set_title(title)

    if len(columns) > 1:
        ax.legend()

    return fig


def plot_selected_variable(df: pd.DataFrame, column: str):
    """Create a figure for a single selected variable."""
    return plot_time_series(
        df,
        [column],
        title=column,
        ylabel=column,
        show_seeding_window=True,
    )


def plot_control_vs_seeding(comparison_df: pd.DataFrame, base_variable: str):
    """Plot control and seeding curves for a base variable."""
    return plot_time_series(
        comparison_df,
        [f"{base_variable}_control", f"{base_variable}_seeding"],
        title=f"{base_variable}",
        ylabel=base_variable,
        show_seeding_window=True,
    )


def plot_difference(comparison_df: pd.DataFrame, base_variable: str):
    """Plot seeding-control difference for a base variable."""
    fig, ax = plt.subplots(figsize=(5.2, 2.8))

    diff_col = f"{base_variable}_diff"
    rel_col = f"{base_variable}_relative_change_percent"

    if diff_col in comparison_df.columns:
        ax.plot(comparison_df["time_s"], comparison_df[diff_col], label="difference")

    for start, end in _seeding_intervals_from_comparison(comparison_df):
        ax.axvspan(start, end, alpha=0.15)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(f"Δ {base_variable}")
    ax.set_title(f"Δ {base_variable}")
    ax.legend()

    return fig


def _seeding_intervals_from_comparison(comparison_df: pd.DataFrame) -> List[tuple[float, float]]:
    for candidate in ["seeding_active_seeding", "seeding_active"]:
        if candidate in comparison_df.columns:
            temp = pd.DataFrame({"time_s": comparison_df["time_s"], "seeding_active": comparison_df[candidate]})
            return _seeding_intervals(temp)
    return []



def plot_sweep_ranking(sweep_df: pd.DataFrame, metric: str = "ranking_value", top_n: int = 10):
    """Plot top-N sweep cases by ranking metric."""
    fig, ax = plt.subplots(figsize=(6.0, 3.2))

    if sweep_df.empty or metric not in sweep_df.columns:
        ax.set_title("No sweep ranking data")
        return fig

    plot_df = sweep_df.copy()
    plot_df = plot_df.dropna(subset=[metric])
    plot_df = plot_df.sort_values(metric, ascending=False).head(top_n)

    labels = plot_df["case_name"] if "case_name" in plot_df.columns else plot_df.index.astype(str)
    ax.barh(labels[::-1], plot_df[metric].to_numpy()[::-1])
    ax.set_xlabel(metric)
    ax.set_ylabel("Sweep case")
    ax.set_title(f"Top {min(top_n, len(plot_df))} sweep cases")

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
        labels = plot_df["case_name"].astype(str)
    elif "case_index" in plot_df.columns:
        labels = plot_df["case_index"].astype(str)
    else:
        labels = plot_df.index.astype(str)

    ax.barh(labels.iloc[::-1], plot_df[metric].to_numpy()[::-1])
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
    comparison_mode: str = "seeding",
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

    wide_df: pd.DataFrame | None = None

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
        curve = case_df[["time_s", value_col]].rename(columns={value_col: label})

        if wide_df is None:
            wide_df = curve
        else:
            wide_df = pd.merge(wide_df, curve, on="time_s", how="outer")

    if wide_df is None:
        return pd.DataFrame()

    return wide_df.sort_values("time_s").reset_index(drop=True)


def plot_sweep_overlay(
    overlay_df: pd.DataFrame,
    *,
    variable: str,
    curve_label: str,
):
    """Plot a variable over time for multiple sweep cases."""
    fig, ax = plt.subplots(figsize=(6.0, 3.2))

    if overlay_df.empty or "time_s" not in overlay_df.columns:
        ax.set_title(f"No sweep time-series data: {variable}")
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


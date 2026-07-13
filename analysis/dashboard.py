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


def discover_results(result_dir: Path) -> List[ResultEntry]:
    """Find structured run directories and legacy CSV outputs."""
    result_dir.mkdir(exist_ok=True)

    run_dirs = sorted(
        [p for p in result_dir.iterdir() if p.is_dir() and (p / "timeseries.csv").exists()],
        reverse=True,
    )
    legacy_csvs = sorted(result_dir.glob("*.csv"), reverse=True)

    entries: List[ResultEntry] = []
    for path in run_dirs:
        entries.append(
            ResultEntry(
                path=path,
                label=f"[run directory] {path.name}",
                is_run_directory=True,
            )
        )

    for path in legacy_csvs:
        entries.append(
            ResultEntry(
                path=path,
                label=f"[legacy csv] {path.name}",
                is_run_directory=False,
            )
        )

    return entries


def load_result(entry: ResultEntry) -> Dict[str, Any]:
    """Load a result directory or legacy CSV into a common dictionary."""
    if entry.is_run_directory:
        timeseries_path = entry.path / "timeseries.csv"
        summary_path = entry.path / "summary.json"
        metadata_path = entry.path / "metadata.json"
        config_path = entry.path / "config.yaml"
        validation_path = entry.path / "validation_report.json"

        df = pd.read_csv(timeseries_path)
        summary = _read_json(summary_path)
        metadata = _read_json(metadata_path)
        config = _read_yaml(config_path)
        validation = _read_json(validation_path)

        return {
            "entry": entry,
            "timeseries": df,
            "summary": summary,
            "metadata": metadata,
            "config": config,
            "validation": validation,
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
    """Flatten adapter summary, metrics, and validation for metric cards."""
    flat: Dict[str, Any] = {}

    for group_name in ["adapter_summary", "metrics", "validation"]:
        group = summary.get(group_name, {})
        if isinstance(group, dict):
            for key, value in group.items():
                flat[f"{group_name}.{key}"] = value

    for key, value in summary.items():
        if not isinstance(value, dict):
            flat[key] = value

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
):
    """Create a single time-series figure with optional seeding-window shading."""
    fig, ax = plt.subplots()

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

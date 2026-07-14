from __future__ import annotations

import time
import tracemalloc
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd

from analysis.resource_monitor import ProcessRSSMonitor


ENSEMBLE_BUILD_ID = "streaming-ensemble-statistics-rss-20260714"


def member_seed_list(config: Dict[str, Any]) -> List[int]:
    """Build deterministic ensemble seed list from config."""
    ensemble = config.get("ensemble", {})
    n_members = int(ensemble.get("n_members", 5))
    seed_start = int(ensemble.get("seed_start", config.get("experiment", {}).get("random_seed", 42)))
    seed_step = int(ensemble.get("seed_step", 1))

    return [seed_start + i * seed_step for i in range(n_members)]


def numeric_columns_for_ensemble(df: pd.DataFrame) -> List[str]:
    """Return numeric ensemble columns except time."""
    return [
        col
        for col in df.columns
        if col != "time_s" and pd.api.types.is_numeric_dtype(df[col])
    ]


def align_member_dataframes(member_dfs: List[pd.DataFrame]) -> List[pd.DataFrame]:
    """Align ensemble member dataframes on common time."""
    if not member_dfs:
        return []

    common_time = set(member_dfs[0]["time_s"])
    for df in member_dfs[1:]:
        common_time = common_time.intersection(set(df["time_s"]))

    common_time = sorted(common_time)

    return [
        df[df["time_s"].isin(common_time)].sort_values("time_s").reset_index(drop=True)
        for df in member_dfs
    ]


def _column_statistics(
    column: str,
    stack: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Return the canonical ensemble statistics for one stacked variable."""
    finite = np.isfinite(stack)
    with warnings.catch_warnings():
        # All-NaN timesteps are represented by NaN statistics plus n_finite=0;
        # this is expected diagnostic output rather than a runtime fault.
        warnings.simplefilter("ignore", category=RuntimeWarning)
        mean = np.nanmean(stack, axis=0)
        std = (
            np.nanstd(stack, axis=0, ddof=1)
            if stack.shape[0] > 1
            else np.zeros(stack.shape[1], dtype=float)
        )
        median = np.nanmedian(stack, axis=0)
        q25 = np.nanpercentile(stack, 25, axis=0)
        q75 = np.nanpercentile(stack, 75, axis=0)
    return {
        f"{column}_mean": mean,
        f"{column}_std": std,
        f"{column}_median": median,
        f"{column}_q25": q25,
        f"{column}_q75": q75,
        f"{column}_n_finite": finite.sum(axis=0),
        f"{column}_finite_fraction": finite.mean(axis=0),
    }


def build_ensemble_statistics(member_dfs: List[pd.DataFrame]) -> pd.DataFrame:
    """
    Build ensemble statistics over time.

    Output columns:
    - time_s
    - <var>_mean
    - <var>_std
    - <var>_median
    - <var>_q25
    - <var>_q75
    - <var>_n_finite
    - <var>_finite_fraction
    """
    if not member_dfs:
        return pd.DataFrame()

    aligned = align_member_dataframes(member_dfs)
    if not aligned:
        return pd.DataFrame()

    common_columns = set(numeric_columns_for_ensemble(aligned[0]))
    for df in aligned[1:]:
        common_columns = common_columns.intersection(set(numeric_columns_for_ensemble(df)))

    columns = sorted(common_columns)
    output_columns: Dict[str, np.ndarray] = {
        "time_s": aligned[0]["time_s"].to_numpy()
    }

    for column in columns:
        stack = np.vstack([
            pd.to_numeric(df[column], errors="coerce").to_numpy(dtype=float)
            for df in aligned
        ])

        output_columns.update(_column_statistics(column, stack))

    return pd.DataFrame(output_columns)


def build_ensemble_statistics_from_paths(member_paths: List[Path]) -> pd.DataFrame:
    """Aggregate member CSVs one variable at a time to bound peak memory use.

    The legacy in-memory implementation retains every member dataframe. This
    implementation first discovers common time/columns, then reads only one
    variable from all members at a time. Peak aggregation memory therefore
    scales with members x timesteps instead of members x timesteps x variables.
    """
    paths = [Path(path) for path in member_paths]
    if not paths:
        return pd.DataFrame()

    common_time: set[float] | None = None
    common_columns: set[str] | None = None
    for path in paths:
        member = pd.read_csv(path)
        if "time_s" not in member:
            raise ValueError(f"Ensemble member file has no time_s column: {path}")
        member_time = set(
            pd.to_numeric(member["time_s"], errors="coerce").dropna().astype(float)
        )
        member_columns = set(numeric_columns_for_ensemble(member))
        common_time = member_time if common_time is None else common_time.intersection(member_time)
        common_columns = (
            member_columns
            if common_columns is None
            else common_columns.intersection(member_columns)
        )

    times = sorted(common_time or set())
    columns = sorted(common_columns or set())
    if not times:
        return pd.DataFrame()

    output_columns: Dict[str, np.ndarray] = {
        "time_s": np.asarray(times, dtype=float)
    }
    for column in columns:
        member_values = []
        for path in paths:
            member = pd.read_csv(path, usecols=["time_s", column])
            member["time_s"] = pd.to_numeric(member["time_s"], errors="coerce")
            member[column] = pd.to_numeric(member[column], errors="coerce")
            aligned = (
                member.dropna(subset=["time_s"])
                .drop_duplicates(subset=["time_s"], keep="last")
                .set_index("time_s")[column]
                .reindex(times)
            )
            member_values.append(aligned.to_numpy(dtype=float))
        output_columns.update(_column_statistics(column, np.vstack(member_values)))

    return pd.DataFrame(output_columns)


def benchmark_ensemble_statistics_from_paths(
    member_paths: List[Path],
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Run streaming aggregation and return allocation plus process-RSS diagnostics."""
    paths = [Path(path) for path in member_paths]
    total_input_bytes = sum(path.stat().st_size for path in paths if path.exists())
    tracing_was_active = tracemalloc.is_tracing()
    if not tracing_was_active:
        tracemalloc.start()
        tracemalloc.reset_peak()
    rss_monitor = ProcessRSSMonitor()
    with rss_monitor:
        started = time.perf_counter()
        try:
            statistics = build_ensemble_statistics_from_paths(paths)
            elapsed_seconds = time.perf_counter() - started
            _, peak_traced_bytes = tracemalloc.get_traced_memory()
        finally:
            if not tracing_was_active:
                tracemalloc.stop()

    n_statistic_columns = max(0, len(statistics.columns) - 1)
    n_variables = n_statistic_columns // 7
    diagnostics = {
        "build_id": ENSEMBLE_BUILD_ID,
        "method": "column_streaming_from_member_csv",
        "n_member_files": len(paths),
        "total_input_bytes": int(total_input_bytes),
        "elapsed_seconds": float(elapsed_seconds),
        "python_peak_traced_bytes": int(peak_traced_bytes),
        "output_rows": int(len(statistics)),
        "output_columns": int(len(statistics.columns)),
        "aggregated_variables": int(n_variables),
        "process_rss": rss_monitor.summary(),
        "memory_scope": (
            "Python and NumPy allocations visible to tracemalloc during aggregation; "
            "whole-process RSS is reported separately under process_rss. If an outer trace "
            "was already active, its peak scope is retained."
        ),
    }
    return statistics, diagnostics


def final_stat(stats_df: pd.DataFrame, base_column: str, stat: str = "mean") -> float | None:
    column = f"{base_column}_{stat}"
    if stats_df.empty or column not in stats_df.columns:
        return None

    value = stats_df[column].iloc[-1]
    return float(value) if pd.notna(value) else None


def max_stat(stats_df: pd.DataFrame, base_column: str, stat: str = "mean") -> float | None:
    column = f"{base_column}_{stat}"
    if stats_df.empty or column not in stats_df.columns:
        return None

    value = stats_df[column].max(skipna=True)
    return float(value) if pd.notna(value) else None


def _trapezoid(y: np.ndarray, x: np.ndarray) -> float:
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x=x))
    return float(np.trapz(y, x=x))


def time_integral_stat(stats_df: pd.DataFrame, base_column: str, stat: str = "mean") -> float | None:
    column = f"{base_column}_{stat}"
    if stats_df.empty or "time_s" not in stats_df.columns or column not in stats_df.columns:
        return None

    x = stats_df["time_s"].to_numpy(dtype=float)
    y = stats_df[column].to_numpy(dtype=float)

    if len(x) < 2:
        return None

    return _trapezoid(y, x)


def ensemble_summary_metrics(stats_df: pd.DataFrame) -> Dict[str, float | None]:
    """Build compact metrics from ensemble statistics."""
    metrics: Dict[str, float | None] = {}

    preferred = [
        "rain_water_mixing_ratio_diff",
        "cloud_water_mixing_ratio_diff",
        "all_activated_water_mixing_ratio_diff",
        "water_vapour_mixing_ratio_diff",
        "supersaturation_percent_diff",
        "effective_radius_all_um_diff",
        "effective_radius_cloud_um_diff",
        "rain_water_mixing_ratio",
        "cloud_water_mixing_ratio",
    ]

    for base in preferred:
        metrics[f"{base}_final_mean"] = final_stat(stats_df, base, "mean")
        metrics[f"{base}_max_mean"] = max_stat(stats_df, base, "mean")
        metrics[f"{base}_integral_mean"] = time_integral_stat(stats_df, base, "mean")

    return metrics


def member_summary_rows(member_records: List[Dict[str, Any]]) -> pd.DataFrame:
    """Create a member summary table."""
    return pd.DataFrame(member_records)


def ensemble_variable_bases(stats_df: pd.DataFrame) -> List[str]:
    """Return base variable names available in ensemble_statistics.csv."""
    suffixes = ["_mean", "_std", "_median", "_q25", "_q75", "_n_finite", "_finite_fraction"]
    bases = set()

    for col in stats_df.columns:
        for suffix in suffixes:
            if col.endswith(suffix):
                bases.add(col[: -len(suffix)])

    preferred = [
        "rain_water_mixing_ratio_diff",
        "cloud_water_mixing_ratio_diff",
        "all_activated_water_mixing_ratio_diff",
        "water_vapour_mixing_ratio_diff",
        "supersaturation_percent_diff",
        "effective_radius_all_um_diff",
        "effective_radius_cloud_um_diff",
    ]

    ordered = [base for base in preferred if base in bases]
    ordered += sorted([base for base in bases if base not in ordered])

    return ordered

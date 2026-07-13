from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd


ENSEMBLE_BUILD_ID = "ensemble-statistics-20260713"


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
    out = pd.DataFrame({"time_s": aligned[0]["time_s"].to_numpy()})

    for column in columns:
        stack = np.vstack([
            pd.to_numeric(df[column], errors="coerce").to_numpy(dtype=float)
            for df in aligned
        ])

        finite = np.isfinite(stack)

        out[f"{column}_mean"] = np.nanmean(stack, axis=0)
        out[f"{column}_std"] = np.nanstd(stack, axis=0, ddof=1) if len(aligned) > 1 else 0.0
        out[f"{column}_median"] = np.nanmedian(stack, axis=0)
        out[f"{column}_q25"] = np.nanpercentile(stack, 25, axis=0)
        out[f"{column}_q75"] = np.nanpercentile(stack, 75, axis=0)
        out[f"{column}_n_finite"] = finite.sum(axis=0)
        out[f"{column}_finite_fraction"] = finite.mean(axis=0)

    return out


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

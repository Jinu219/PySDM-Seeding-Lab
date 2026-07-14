from __future__ import annotations

"""Closed-window total-water budget diagnostics for warm-cloud parcel runs."""

from typing import Any, Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


WATER_BUDGET_TABLE_NAME = "water_budget"


def _liquid_water_series(timeseries: pd.DataFrame) -> pd.Series | None:
    if "total_liquid_water_mixing_ratio" in timeseries:
        return pd.to_numeric(timeseries["total_liquid_water_mixing_ratio"], errors="coerce")

    partition_columns = [
        "unactivated_water_mixing_ratio",
        "cloud_water_mixing_ratio",
        "rain_water_mixing_ratio",
    ]
    if all(column in timeseries for column in partition_columns):
        return timeseries[partition_columns].apply(pd.to_numeric, errors="coerce").sum(
            axis=1,
            min_count=len(partition_columns),
        )
    return None


def build_water_budget_table(
    timeseries: pd.DataFrame,
    config: Dict[str, Any] | None,
) -> pd.DataFrame:
    """Build total-water drift only over intervals without an active seeding source."""
    columns = [
        "time_s",
        "water_vapour_mixing_ratio",
        "total_liquid_water_mixing_ratio",
        "total_water_mixing_ratio",
        "total_water_change_from_initial",
        "phase",
        "closed_window_reference_total_water",
        "closed_window_drift",
        "closed_window_relative_drift_percent",
        "liquid_partition_residual",
    ]
    if timeseries.empty or "time_s" not in timeseries or "water_vapour_mixing_ratio" not in timeseries:
        return pd.DataFrame(columns=columns)

    liquid = _liquid_water_series(timeseries)
    if liquid is None:
        return pd.DataFrame(columns=columns)

    cfg = config or {}
    seed = cfg.get("seeding", {})
    time_s = pd.to_numeric(timeseries["time_s"], errors="coerce").to_numpy(dtype=float)
    vapour = pd.to_numeric(timeseries["water_vapour_mixing_ratio"], errors="coerce").to_numpy(dtype=float)
    liquid_values = liquid.to_numpy(dtype=float)
    total = vapour + liquid_values

    finite_total = np.flatnonzero(np.isfinite(total))
    if finite_total.size == 0:
        return pd.DataFrame(columns=columns)
    initial_index = int(finite_total[0])
    initial_total = float(total[initial_index])

    enabled = bool(seed.get("enabled", False))
    injection_start = float(seed.get("injection_start", np.inf))
    injection_end = float(seed.get("injection_end", -np.inf))
    phase = np.full(len(time_s), "closed_system", dtype=object)
    closed_reference = np.full(len(time_s), initial_total, dtype=float)
    closed_drift = total - closed_reference

    if enabled:
        pre_mask = time_s < injection_start
        source_mask = (time_s >= injection_start) & (time_s <= injection_end)
        post_mask = time_s > injection_end
        phase[pre_mask] = "pre_injection_closed"
        phase[source_mask] = "injection_source_open"
        phase[post_mask] = "post_injection_closed"

        source_reference_candidates = np.flatnonzero(np.isfinite(total) & (time_s >= injection_end))
        if source_reference_candidates.size:
            post_reference = float(total[int(source_reference_candidates[0])])
        else:
            post_reference = float(total[int(finite_total[-1])])
        closed_reference[post_mask] = post_reference
        closed_drift = total - closed_reference
        closed_drift[source_mask] = np.nan

    scale = np.where(np.abs(closed_reference) > 0, np.abs(closed_reference), np.nan)
    relative_percent = 100.0 * closed_drift / scale

    partition_residual = np.full(len(timeseries), np.nan, dtype=float)
    partition_columns = [
        "unactivated_water_mixing_ratio",
        "cloud_water_mixing_ratio",
        "rain_water_mixing_ratio",
    ]
    if all(column in timeseries for column in partition_columns):
        partition_sum = (
            timeseries[partition_columns]
            .apply(pd.to_numeric, errors="coerce")
            .sum(axis=1, min_count=len(partition_columns))
            .to_numpy(dtype=float)
        )
        partition_residual = liquid_values - partition_sum

    return pd.DataFrame(
        {
            "time_s": time_s,
            "water_vapour_mixing_ratio": vapour,
            "total_liquid_water_mixing_ratio": liquid_values,
            "total_water_mixing_ratio": total,
            "total_water_change_from_initial": total - initial_total,
            "phase": phase,
            "closed_window_reference_total_water": closed_reference,
            "closed_window_drift": closed_drift,
            "closed_window_relative_drift_percent": relative_percent,
            "liquid_partition_residual": partition_residual,
        },
        columns=columns,
    )


def summarize_water_budget(
    budget_df: pd.DataFrame,
    config: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Summarize conservation drift and classify it using configured quality gates."""
    if budget_df.empty:
        return {"available": False, "status": "unavailable"}

    diagnostics = (config or {}).get("diagnostics", {})
    budget_cfg = diagnostics.get("water_budget", {})
    warning_percent = float(budget_cfg.get("warning_relative_drift_percent", 0.01))
    failure_percent = float(budget_cfg.get("failure_relative_drift_percent", 0.1))

    drift = budget_df["closed_window_relative_drift_percent"].abs()
    finite_drift = drift[np.isfinite(drift)]
    max_drift = float(finite_drift.max()) if len(finite_drift) else float("nan")
    absolute_drift = budget_df["closed_window_drift"].abs()
    finite_absolute_drift = absolute_drift[np.isfinite(absolute_drift)]

    if np.isfinite(max_drift) and max_drift >= failure_percent:
        status = "fail"
    elif np.isfinite(max_drift) and max_drift >= warning_percent:
        status = "warning"
    else:
        status = "pass"

    phase_maxima: Dict[str, float] = {}
    for phase_name, phase_df in budget_df.groupby("phase", sort=False):
        values = phase_df["closed_window_relative_drift_percent"].abs()
        values = values[np.isfinite(values)]
        if len(values):
            phase_maxima[str(phase_name)] = float(values.max())

    source_rows = budget_df[budget_df["phase"] == "injection_source_open"]
    source_change = float("nan")
    if len(source_rows):
        pre_rows = budget_df[budget_df["phase"] == "pre_injection_closed"]
        post_rows = budget_df[budget_df["phase"] == "post_injection_closed"]
        source_start = (
            pre_rows["total_water_mixing_ratio"].iloc[-1]
            if len(pre_rows)
            else budget_df["total_water_mixing_ratio"].iloc[0]
        )
        source_end = (
            post_rows["total_water_mixing_ratio"].iloc[0]
            if len(post_rows)
            else source_rows["total_water_mixing_ratio"].iloc[-1]
        )
        source_change = float(source_end - source_start)

    partition = budget_df["liquid_partition_residual"].abs()
    finite_partition = partition[np.isfinite(partition)]
    return {
        "available": True,
        "status": status,
        "warning_relative_drift_percent": warning_percent,
        "failure_relative_drift_percent": failure_percent,
        "max_abs_closed_window_relative_drift_percent": (
            max_drift if np.isfinite(max_drift) else None
        ),
        "max_abs_closed_window_drift": (
            float(finite_absolute_drift.max()) if len(finite_absolute_drift) else None
        ),
        "max_abs_liquid_partition_residual": (
            float(finite_partition.max()) if len(finite_partition) else None
        ),
        "source_window_total_water_change": (
            source_change if np.isfinite(source_change) else None
        ),
        "phase_max_abs_relative_drift_percent": phase_maxima,
        "interpretation": (
            "Seeding injection is treated as an open source window; pass/warning/fail uses only "
            "pre-injection, post-injection, or fully closed control intervals."
        ),
    }


def plot_water_budget(
    budget_df: pd.DataFrame,
    *,
    title: str = "Total-water budget",
):
    """Plot total water and closed-window relative drift."""
    fig, axes = plt.subplots(2, 1, figsize=(8.0, 6.0), sharex=True)
    if budget_df.empty:
        axes[0].set_title("Water-budget diagnostic unavailable")
        axes[0].text(0.5, 0.5, "Required native water columns are missing.", ha="center", va="center")
        axes[1].axis("off")
        fig.tight_layout()
        return fig

    time_s = budget_df["time_s"].to_numpy(dtype=float)
    axes[0].plot(time_s, budget_df["water_vapour_mixing_ratio"], label="water vapour", linewidth=1.6)
    axes[0].plot(time_s, budget_df["total_liquid_water_mixing_ratio"], label="total liquid", linewidth=1.6)
    axes[0].plot(time_s, budget_df["total_water_mixing_ratio"], label="total water", linewidth=2.0)
    axes[0].set_ylabel("Mixing ratio [kg kg$^{-1}$]")
    axes[0].set_title(title)
    axes[0].legend(frameon=False, ncol=3, fontsize=8)

    axes[1].plot(
        time_s,
        budget_df["closed_window_relative_drift_percent"],
        color="#b91c1c",
        linewidth=1.7,
    )
    source_mask = budget_df["phase"] == "injection_source_open"
    if source_mask.any():
        source_times = budget_df.loc[source_mask, "time_s"]
        axes[1].axvspan(float(source_times.min()), float(source_times.max()), color="#f59e0b", alpha=0.16)
    axes[1].axhline(0.0, color="#334155", linewidth=0.8)
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Closed-window drift [%]")

    for axis in axes:
        axis.grid(alpha=0.2)
    fig.tight_layout()
    return fig

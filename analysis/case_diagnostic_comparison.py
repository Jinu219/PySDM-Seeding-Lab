from __future__ import annotations

"""Control-versus-seeding comparison tables for research diagnostics."""

from typing import Any, Dict, Iterable

import numpy as np
import pandas as pd


def _merge_with_differences(
    control: pd.DataFrame,
    seeding: pd.DataFrame,
    *,
    keys: Iterable[str],
    numeric_columns: Iterable[str],
) -> pd.DataFrame:
    if control.empty or seeding.empty:
        return pd.DataFrame()
    key_columns = [key for key in keys if key in control.columns and key in seeding.columns]
    if not key_columns:
        return pd.DataFrame()

    value_columns = [
        column
        for column in numeric_columns
        if column in control.columns and column in seeding.columns
    ]
    left = control[key_columns + value_columns].copy()
    right = seeding[key_columns + value_columns].copy()
    merged = left.merge(
        right,
        on=key_columns,
        how="inner",
        suffixes=("_control", "_seeding"),
        validate="one_to_one",
    )
    for column in value_columns:
        merged[f"{column}_diff"] = (
            merged[f"{column}_seeding"] - merged[f"{column}_control"]
        )
    return merged


def build_wet_radius_spectrum_comparison(
    control: pd.DataFrame,
    seeding: pd.DataFrame,
) -> pd.DataFrame:
    """Return aligned seeding-minus-control wet-radius spectrum differences."""
    return _merge_with_differences(
        control,
        seeding,
        keys=(
            "time_s",
            "bin_index",
            "radius_left_um",
            "radius_right_um",
            "radius_mid_um",
            "regime",
        ),
        numeric_columns=(
            "number_concentration_m3",
            "number_concentration_cm3",
            "volume_fraction_per_dlnr",
            "bin_liquid_volume_fraction",
        ),
    )


def build_threshold_robustness_comparison(
    control: pd.DataFrame,
    seeding: pd.DataFrame,
) -> pd.DataFrame:
    """Return aligned seeding-minus-control threshold-robustness differences."""
    return _merge_with_differences(
        control,
        seeding,
        keys=(
            "time_s",
            "activation_factor",
            "rain_factor",
            "activation_threshold_um",
            "rain_threshold_um",
        ),
        numeric_columns=(
            "unactivated_number_cm3",
            "cloud_number_cm3",
            "rain_number_cm3",
            "unactivated_volume_fraction",
            "cloud_volume_fraction",
            "rain_volume_fraction",
            "activated_number_fraction",
            "rain_number_fraction_of_activated",
            "rain_volume_fraction_of_activated",
        ),
    )


def build_water_budget_comparison(
    control: pd.DataFrame,
    seeding: pd.DataFrame,
) -> pd.DataFrame:
    """Return aligned total-water and closed-window drift differences."""
    comparison = _merge_with_differences(
        control,
        seeding,
        keys=("time_s",),
        numeric_columns=(
            "water_vapour_mixing_ratio",
            "total_liquid_water_mixing_ratio",
            "total_water_mixing_ratio",
            "total_water_change_from_initial",
            "closed_window_drift",
            "closed_window_relative_drift_percent",
            "liquid_partition_residual",
        ),
    )
    if comparison.empty or "phase" not in control or "phase" not in seeding:
        return comparison
    phases = control[["time_s", "phase"]].merge(
        seeding[["time_s", "phase"]],
        on="time_s",
        how="inner",
        suffixes=("_control", "_seeding"),
        validate="one_to_one",
    )
    return comparison.merge(phases, on="time_s", how="left", validate="one_to_one")


def summarize_spectrum_comparison(comparison: pd.DataFrame) -> Dict[str, Any]:
    """Summarize final spectrum separation between seeding and control."""
    if comparison.empty:
        return {"available": False}
    final_time = float(comparison["time_s"].max())
    final = comparison[np.isclose(comparison["time_s"], final_time)]
    rain = final[final["regime"] == "rain"] if "regime" in final else pd.DataFrame()
    return {
        "available": True,
        "final_time_s": final_time,
        "final_number_l1_difference_cm3": float(
            final["number_concentration_cm3_diff"].abs().sum()
        ),
        "final_liquid_volume_l1_difference": float(
            final["bin_liquid_volume_fraction_diff"].abs().sum()
        ),
        "final_rain_number_difference_cm3": (
            float(rain["number_concentration_cm3_diff"].sum()) if len(rain) else 0.0
        ),
        "final_rain_liquid_volume_difference": (
            float(rain["bin_liquid_volume_fraction_diff"].sum()) if len(rain) else 0.0
        ),
    }

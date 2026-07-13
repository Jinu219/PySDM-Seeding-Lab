from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def final_value(df: pd.DataFrame, column: str) -> float:
    return float(df[column].iloc[-1])


def maximum_value(df: pd.DataFrame, column: str) -> float:
    return float(df[column].max())


def _time_integral(df: pd.DataFrame, column: str) -> float:
    """Integrate a time-series using NumPy trapezoid integration."""
    if "time_s" not in df.columns or column not in df.columns:
        return 0.0

    # Prefer np.trapezoid. Keep np.trapz fallback only for older NumPy versions.
    trapezoid = getattr(np, "trapezoid", np.trapz)
    return float(trapezoid(df[column].to_numpy(), x=df["time_s"].to_numpy()))


def accumulated_precipitation_proxy(
    df: pd.DataFrame,
    column: str = "rain_water_mixing_ratio",
) -> float:
    """
    Temporary accumulated precipitation proxy.

    This is not yet true surface precipitation.
    It is a time integral of rain-water mixing ratio and will be replaced
    or supplemented after sedimentation/surface rain-rate diagnostics are connected.
    """
    return _time_integral(df, column)


def rain_onset_time(
    df: pd.DataFrame,
    column: str = "rain_water_mixing_ratio",
    threshold: float = 1.0e-12,
) -> float | None:
    """Return the first time when rain-water exceeds a threshold."""
    if "time_s" not in df.columns or column not in df.columns:
        return None

    mask = df[column] > threshold
    if not mask.any():
        return None

    return float(df.loc[mask, "time_s"].iloc[0])


def summarize_timeseries(df: pd.DataFrame) -> Dict[str, float | int | None]:
    """Build a compact summary dictionary from available output columns."""
    summary: Dict[str, float | int | None] = {
        "n_rows": int(len(df)),
    }

    if "time_s" in df.columns and len(df) > 0:
        summary["start_time_s"] = float(df["time_s"].iloc[0])
        summary["end_time_s"] = float(df["time_s"].iloc[-1])

    for column in [
        "rain_water_mixing_ratio",
        "cloud_water_mixing_ratio",
        "effective_radius_um",
        "droplet_number_concentration_cm3",
        "superdroplet_count",
        "mean_radius_m",
        "supersaturation",
    ]:
        if column in df.columns:
            summary[f"final_{column}"] = float(df[column].iloc[-1])
            summary[f"max_{column}"] = float(df[column].max())

    if "rain_water_mixing_ratio" in df.columns:
        summary["rain_onset_time_s"] = rain_onset_time(df)
        summary["accumulated_rain_water_proxy"] = accumulated_precipitation_proxy(df)

    if "seeding_active" in df.columns:
        summary["n_seeding_active_steps"] = int(df["seeding_active"].sum())

    return summary

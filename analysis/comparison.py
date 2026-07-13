from __future__ import annotations

from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from analysis.metrics import summarize_timeseries


def _numeric_columns(df: pd.DataFrame) -> List[str]:
    return [
        col
        for col in df.columns
        if col != "time_s" and pd.api.types.is_numeric_dtype(df[col])
    ]


def align_on_time(
    control_df: pd.DataFrame,
    seeding_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Align control and seeding outputs using common time values."""
    if "time_s" not in control_df.columns or "time_s" not in seeding_df.columns:
        raise ValueError("Both control and seeding dataframes must contain 'time_s'.")

    common_time = sorted(set(control_df["time_s"]).intersection(set(seeding_df["time_s"])))
    if not common_time:
        raise ValueError("Control and seeding outputs do not share common time values.")

    control_aligned = (
        control_df[control_df["time_s"].isin(common_time)]
        .sort_values("time_s")
        .reset_index(drop=True)
    )
    seeding_aligned = (
        seeding_df[seeding_df["time_s"].isin(common_time)]
        .sort_values("time_s")
        .reset_index(drop=True)
    )

    return control_aligned, seeding_aligned


def build_difference_dataframe(
    control_df: pd.DataFrame,
    seeding_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a difference dataframe.

    Output columns:
    - time_s
    - <var>_control
    - <var>_seeding
    - <var>_diff
    - <var>_relative_change_percent
    """
    control_aligned, seeding_aligned = align_on_time(control_df, seeding_df)

    common_numeric = sorted(
        set(_numeric_columns(control_aligned)).intersection(set(_numeric_columns(seeding_aligned)))
    )

    out = pd.DataFrame({"time_s": control_aligned["time_s"].to_numpy()})

    for column in common_numeric:
        control_values = control_aligned[column].to_numpy()
        seeding_values = seeding_aligned[column].to_numpy()
        diff = seeding_values - control_values

        with np.errstate(divide="ignore", invalid="ignore"):
            relative = np.where(control_values != 0, diff / control_values * 100.0, np.nan)

        out[f"{column}_control"] = control_values
        out[f"{column}_seeding"] = seeding_values
        out[f"{column}_diff"] = diff
        out[f"{column}_relative_change_percent"] = relative

    return out


def summarize_comparison(
    control_df: pd.DataFrame,
    seeding_df: pd.DataFrame,
    difference_df: pd.DataFrame,
) -> Dict[str, object]:
    """Summarize control, seeding, and difference outputs."""
    control_summary = summarize_timeseries(control_df)
    seeding_summary = summarize_timeseries(seeding_df)

    comparison: Dict[str, object] = {
        "control": control_summary,
        "seeding": seeding_summary,
        "difference": summarize_timeseries_like_difference(difference_df),
    }

    for base_column in [
        "rain_water_mixing_ratio",
        "cloud_water_mixing_ratio",
        "effective_radius_um",
        "droplet_number_concentration_cm3",
        "superdroplet_count",
        "mean_radius_m",
        "supersaturation",
    ]:
        control_final_key = f"final_{base_column}"
        seeding_final_key = f"final_{base_column}"

        if control_final_key in control_summary and seeding_final_key in seeding_summary:
            control_final = control_summary[control_final_key]
            seeding_final = seeding_summary[seeding_final_key]
            delta = None if control_final is None or seeding_final is None else seeding_final - control_final

            comparison[f"delta_final_{base_column}"] = delta

            if control_final not in [None, 0]:
                comparison[f"relative_final_{base_column}_percent"] = delta / control_final * 100.0
            else:
                comparison[f"relative_final_{base_column}_percent"] = None

    if (
        "accumulated_rain_water_proxy" in control_summary
        and "accumulated_rain_water_proxy" in seeding_summary
    ):
        control_acc = control_summary["accumulated_rain_water_proxy"]
        seeding_acc = seeding_summary["accumulated_rain_water_proxy"]
        delta_acc = seeding_acc - control_acc

        comparison["delta_accumulated_rain_water_proxy"] = delta_acc
        comparison["relative_accumulated_rain_water_proxy_percent"] = (
            delta_acc / control_acc * 100.0 if control_acc not in [None, 0] else None
        )

    return comparison


def summarize_timeseries_like_difference(df: pd.DataFrame) -> Dict[str, object]:
    """Summarize diff columns in a comparison dataframe."""
    summary: Dict[str, object] = {
        "n_rows": int(len(df)),
    }

    if "time_s" in df.columns and len(df) > 0:
        summary["start_time_s"] = float(df["time_s"].iloc[0])
        summary["end_time_s"] = float(df["time_s"].iloc[-1])

    for column in _numeric_columns(df):
        if column.endswith("_diff") or column.endswith("_relative_change_percent"):
            summary[f"final_{column}"] = float(df[column].iloc[-1]) if pd.notna(df[column].iloc[-1]) else None
            max_value = df[column].max(skipna=True)
            min_value = df[column].min(skipna=True)
            summary[f"max_{column}"] = float(max_value) if pd.notna(max_value) else None
            summary[f"min_{column}"] = float(min_value) if pd.notna(min_value) else None

    return summary


def difference(seed_df: pd.DataFrame, control_df: pd.DataFrame, column: str) -> pd.Series:
    control_aligned, seeding_aligned = align_on_time(control_df, seed_df)
    return seeding_aligned[column] - control_aligned[column]


def relative_change_percent(seed_df: pd.DataFrame, control_df: pd.DataFrame, column: str) -> pd.Series:
    control_aligned, seeding_aligned = align_on_time(control_df, seed_df)
    denominator = control_aligned[column].replace(0, pd.NA)
    return (seeding_aligned[column] - control_aligned[column]) / denominator * 100.0

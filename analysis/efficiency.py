from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from analysis.metrics import accumulated_precipitation_proxy, rain_onset_time, summarize_timeseries


def _safe_final(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns or len(df) == 0:
        return None
    value = df[column].iloc[-1]
    return float(value) if pd.notna(value) else None


def _safe_max(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns or len(df) == 0:
        return None
    value = df[column].max(skipna=True)
    return float(value) if pd.notna(value) else None


def _safe_integral(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns or "time_s" not in df.columns:
        return None
    return accumulated_precipitation_proxy(df, column=column)


def _safe_delta(seeding_value: float | None, control_value: float | None) -> float | None:
    if seeding_value is None or control_value is None:
        return None
    return float(seeding_value - control_value)


def _safe_ratio(seeding_value: float | None, control_value: float | None) -> float | None:
    if seeding_value is None or control_value in [None, 0]:
        return None
    return float(seeding_value / control_value)


def _safe_relative_percent(seeding_value: float | None, control_value: float | None) -> float | None:
    if seeding_value is None or control_value in [None, 0]:
        return None
    return float((seeding_value - control_value) / control_value * 100.0)


def _bounded_positive_score(value: float | None, scale: float = 1.0) -> float:
    """
    Convert a metric into a bounded 0~1 score.

    Positive values increase the score and negative values contribute 0.
    This is intentionally conservative and only used as a first-pass ranking proxy.
    """
    if value is None or not np.isfinite(value):
        return 0.0

    return float(np.tanh(max(value, 0.0) / max(scale, 1.0e-12)))


def compute_single_run_efficiency(df: pd.DataFrame) -> Dict[str, float | int | None]:
    """
    Compute single-run microphysical efficiency proxies.

    These are not yet causal seeding-effect metrics because they do not compare
    against a control run. They are useful for reading a single simulation output.
    """
    metrics: Dict[str, float | int | None] = {}

    rain_acc = _safe_integral(df, "rain_water_mixing_ratio")
    cloud_acc = _safe_integral(df, "cloud_water_mixing_ratio")

    metrics["accumulated_rain_water_proxy"] = rain_acc
    metrics["accumulated_cloud_water_proxy"] = cloud_acc

    if rain_acc is not None and cloud_acc not in [None, 0]:
        metrics["cloud_to_rain_conversion_proxy"] = float(rain_acc / cloud_acc)
    else:
        metrics["cloud_to_rain_conversion_proxy"] = None

    metrics["rain_onset_time_s"] = rain_onset_time(df)
    metrics["final_rain_water_mixing_ratio"] = _safe_final(df, "rain_water_mixing_ratio")
    metrics["max_rain_water_mixing_ratio"] = _safe_max(df, "rain_water_mixing_ratio")
    metrics["final_effective_radius_um"] = _safe_final(df, "effective_radius_um")
    metrics["final_droplet_number_concentration_cm3"] = _safe_final(
        df,
        "droplet_number_concentration_cm3",
    )
    metrics["final_superdroplet_count"] = _safe_final(df, "superdroplet_count")

    if "seeding_active" in df.columns:
        metrics["n_seeding_active_steps"] = int(df["seeding_active"].fillna(0).sum())

    return metrics


def compute_control_vs_seeding_efficiency(
    control_df: pd.DataFrame,
    seeding_df: pd.DataFrame,
) -> Dict[str, float | int | None]:
    """
    Compute first-pass cloud seeding efficiency metrics from paired simulations.

    Sign convention:
    - delta = seeding - control
    - rain_onset_time_shift_s = seeding_onset - control_onset
      Negative value means rain appeared earlier in the seeding run.
    """
    control = compute_single_run_efficiency(control_df)
    seeding = compute_single_run_efficiency(seeding_df)

    metrics: Dict[str, float | int | None] = {
        "rain_enhancement_final": _safe_delta(
            seeding.get("final_rain_water_mixing_ratio"),
            control.get("final_rain_water_mixing_ratio"),
        ),
        "rain_enhancement_final_percent": _safe_relative_percent(
            seeding.get("final_rain_water_mixing_ratio"),
            control.get("final_rain_water_mixing_ratio"),
        ),
        "rain_enhancement_max": _safe_delta(
            seeding.get("max_rain_water_mixing_ratio"),
            control.get("max_rain_water_mixing_ratio"),
        ),
        "accumulated_rain_enhancement": _safe_delta(
            seeding.get("accumulated_rain_water_proxy"),
            control.get("accumulated_rain_water_proxy"),
        ),
        "accumulated_rain_enhancement_percent": _safe_relative_percent(
            seeding.get("accumulated_rain_water_proxy"),
            control.get("accumulated_rain_water_proxy"),
        ),
        "effective_radius_final_delta_um": _safe_delta(
            seeding.get("final_effective_radius_um"),
            control.get("final_effective_radius_um"),
        ),
        "droplet_number_final_delta_cm3": _safe_delta(
            seeding.get("final_droplet_number_concentration_cm3"),
            control.get("final_droplet_number_concentration_cm3"),
        ),
        "superdroplet_count_final_delta": _safe_delta(
            seeding.get("final_superdroplet_count"),
            control.get("final_superdroplet_count"),
        ),
        "cloud_to_rain_conversion_control": control.get("cloud_to_rain_conversion_proxy"),
        "cloud_to_rain_conversion_seeding": seeding.get("cloud_to_rain_conversion_proxy"),
        "cloud_to_rain_conversion_delta": _safe_delta(
            seeding.get("cloud_to_rain_conversion_proxy"),
            control.get("cloud_to_rain_conversion_proxy"),
        ),
    }

    control_onset = control.get("rain_onset_time_s")
    seeding_onset = seeding.get("rain_onset_time_s")
    metrics["rain_onset_time_control_s"] = control_onset
    metrics["rain_onset_time_seeding_s"] = seeding_onset
    metrics["rain_onset_time_shift_s"] = _safe_delta(seeding_onset, control_onset)

    metrics["seeding_active_steps"] = seeding.get("n_seeding_active_steps")

    metrics["seeding_efficiency_score"] = compute_efficiency_score(metrics)

    return metrics


def compute_efficiency_score(metrics: Dict[str, Any]) -> float | None:
    """
    Compute a first-pass seeding efficiency score.

    This is a heuristic score for dashboard ranking, not a final scientific objective.
    It is intentionally separated so the scoring logic can be revised later.

    Score components:
    - accumulated rain enhancement
    - final rain enhancement
    - cloud-to-rain conversion increase
    - earlier rain onset, if available
    """
    acc = metrics.get("accumulated_rain_enhancement")
    final = metrics.get("rain_enhancement_final")
    conversion = metrics.get("cloud_to_rain_conversion_delta")
    onset_shift = metrics.get("rain_onset_time_shift_s")

    components = []

    components.append(_bounded_positive_score(acc, scale=max(abs(acc or 0.0), 1.0e-12)))
    components.append(_bounded_positive_score(final, scale=max(abs(final or 0.0), 1.0e-12)))
    components.append(_bounded_positive_score(conversion, scale=0.1))

    # Negative shift means earlier onset. Convert earlier onset into positive score.
    if onset_shift is not None:
        components.append(_bounded_positive_score(-onset_shift, scale=300.0))

    if not components:
        return None

    return float(np.mean(components))


def build_efficiency_summary(
    control_df: pd.DataFrame | None = None,
    seeding_df: pd.DataFrame | None = None,
    single_df: pd.DataFrame | None = None,
) -> Dict[str, Any]:
    """Build a typed efficiency summary for either single or paired runs."""
    if control_df is not None and seeding_df is not None:
        return {
            "type": "control_vs_seeding",
            "metrics": compute_control_vs_seeding_efficiency(control_df, seeding_df),
        }

    if single_df is not None:
        return {
            "type": "single",
            "metrics": compute_single_run_efficiency(single_df),
        }

    return {
        "type": "empty",
        "metrics": {},
    }

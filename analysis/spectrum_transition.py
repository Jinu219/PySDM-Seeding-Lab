from __future__ import annotations

"""Spectrum-based cloud-to-rain transition diagnostics."""

from typing import Any, Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TRANSITION_TABLE_NAME = "spectrum_transition"
TRANSITION_ROBUSTNESS_TABLE_NAME = "spectrum_transition_onset_robustness"
TRANSITION_METRIC = "rain_volume_fraction_of_activated"


def spectrum_transition_config(config: Dict[str, Any] | None) -> Dict[str, Any]:
    return dict((config or {}).get("diagnostics", {}).get("spectrum_transition", {}))


def _finite_or_none(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def _crossing_time(
    time_s: np.ndarray,
    values: np.ndarray,
    threshold: float,
) -> float | None:
    """Return the first threshold crossing using linear checkpoint interpolation."""
    order = np.argsort(time_s)
    time_s = np.asarray(time_s, dtype=float)[order]
    values = np.asarray(values, dtype=float)[order]
    finite = np.isfinite(time_s) & np.isfinite(values)
    time_s = time_s[finite]
    values = values[finite]
    if time_s.size == 0:
        return None

    for index, value in enumerate(values):
        if value < threshold:
            continue
        if index == 0:
            return float(time_s[index])
        previous_value = float(values[index - 1])
        previous_time = float(time_s[index - 1])
        current_time = float(time_s[index])
        if previous_value >= threshold or value == previous_value:
            return current_time
        fraction = (threshold - previous_value) / (float(value) - previous_value)
        return float(previous_time + fraction * (current_time - previous_time))
    return None


def build_spectrum_transition_table(
    threshold_comparison: pd.DataFrame,
    config: Dict[str, Any] | None,
) -> pd.DataFrame:
    """Extract the baseline-threshold transition time series."""
    columns = [
        "time_s",
        "rain_volume_fraction_threshold",
        f"{TRANSITION_METRIC}_control",
        f"{TRANSITION_METRIC}_seeding",
        f"{TRANSITION_METRIC}_diff",
        "rain_number_fraction_of_activated_control",
        "rain_number_fraction_of_activated_seeding",
        "rain_number_fraction_of_activated_diff",
        "activated_number_fraction_control",
        "activated_number_fraction_seeding",
        "activated_number_fraction_diff",
    ]
    transition_cfg = spectrum_transition_config(config)
    if not bool(transition_cfg.get("enabled", True)) or threshold_comparison.empty:
        return pd.DataFrame(columns=columns)

    baseline = threshold_comparison[
        np.isclose(threshold_comparison["activation_factor"], 1.0)
        & np.isclose(threshold_comparison["rain_factor"], 1.0)
    ].copy()
    required = [column for column in columns if column != "rain_volume_fraction_threshold"]
    if baseline.empty or not all(column in baseline for column in required):
        return pd.DataFrame(columns=columns)

    threshold = float(transition_cfg.get("rain_volume_fraction_threshold", 0.01))
    baseline["rain_volume_fraction_threshold"] = threshold
    return baseline[columns].sort_values("time_s").reset_index(drop=True)


def build_transition_onset_robustness(
    threshold_comparison: pd.DataFrame,
    config: Dict[str, Any] | None,
) -> pd.DataFrame:
    """Compute spectrum-transition onset for every activation/rain threshold pair."""
    columns = [
        "activation_factor",
        "rain_factor",
        "activation_threshold_um",
        "rain_threshold_um",
        "rain_volume_fraction_threshold",
        "control_transition_onset_s",
        "seeding_transition_onset_s",
        "transition_onset_shift_s",
        "final_rain_volume_fraction_control",
        "final_rain_volume_fraction_seeding",
        "final_rain_volume_fraction_diff",
    ]
    transition_cfg = spectrum_transition_config(config)
    if not bool(transition_cfg.get("enabled", True)) or threshold_comparison.empty:
        return pd.DataFrame(columns=columns)

    threshold = float(transition_cfg.get("rain_volume_fraction_threshold", 0.01))
    rows: list[dict[str, float | None]] = []
    group_columns = [
        "activation_factor",
        "rain_factor",
        "activation_threshold_um",
        "rain_threshold_um",
    ]
    control_column = f"{TRANSITION_METRIC}_control"
    seeding_column = f"{TRANSITION_METRIC}_seeding"
    if not all(column in threshold_comparison for column in [*group_columns, control_column, seeding_column]):
        return pd.DataFrame(columns=columns)

    for group_values, group in threshold_comparison.groupby(group_columns, sort=True):
        group = group.sort_values("time_s")
        times = group["time_s"].to_numpy(dtype=float)
        control = group[control_column].to_numpy(dtype=float)
        seeding = group[seeding_column].to_numpy(dtype=float)
        control_onset = _crossing_time(times, control, threshold)
        seeding_onset = _crossing_time(times, seeding, threshold)
        onset_shift = (
            float(seeding_onset - control_onset)
            if control_onset is not None and seeding_onset is not None
            else None
        )
        rows.append(
            {
                **dict(zip(group_columns, (float(value) for value in group_values))),
                "rain_volume_fraction_threshold": threshold,
                "control_transition_onset_s": control_onset,
                "seeding_transition_onset_s": seeding_onset,
                "transition_onset_shift_s": onset_shift,
                "final_rain_volume_fraction_control": float(control[-1]),
                "final_rain_volume_fraction_seeding": float(seeding[-1]),
                "final_rain_volume_fraction_diff": float(seeding[-1] - control[-1]),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def summarize_spectrum_transition(
    transition_table: pd.DataFrame,
    robustness_table: pd.DataFrame,
) -> Dict[str, Any]:
    """Summarize baseline transition timing and threshold sensitivity."""
    if transition_table.empty:
        return {"available": False, "status": "unavailable"}

    time_s = transition_table["time_s"].to_numpy(dtype=float)
    threshold = float(transition_table["rain_volume_fraction_threshold"].iloc[0])
    control = transition_table[f"{TRANSITION_METRIC}_control"].to_numpy(dtype=float)
    seeding = transition_table[f"{TRANSITION_METRIC}_seeding"].to_numpy(dtype=float)
    control_onset = _crossing_time(time_s, control, threshold)
    seeding_onset = _crossing_time(time_s, seeding, threshold)
    baseline_shift = (
        float(seeding_onset - control_onset)
        if control_onset is not None and seeding_onset is not None
        else None
    )

    finite_shifts = pd.Series(dtype=float)
    if not robustness_table.empty and "transition_onset_shift_s" in robustness_table:
        finite_shifts = pd.to_numeric(
            robustness_table["transition_onset_shift_s"], errors="coerce"
        ).dropna()
    sign_consistent = None
    if len(finite_shifts):
        sign_consistent = bool((finite_shifts <= 0).all() or (finite_shifts >= 0).all())

    return {
        "available": True,
        "status": "resolved" if baseline_shift is not None else "onset_not_resolved",
        "rain_volume_fraction_threshold": threshold,
        "control_transition_onset_s": control_onset,
        "seeding_transition_onset_s": seeding_onset,
        "transition_onset_shift_s": baseline_shift,
        "final_rain_volume_fraction_control": _finite_or_none(control[-1]),
        "final_rain_volume_fraction_seeding": _finite_or_none(seeding[-1]),
        "final_rain_volume_fraction_diff": _finite_or_none(seeding[-1] - control[-1]),
        "max_abs_rain_volume_fraction_diff": (
            float(np.max(np.abs((seeding - control)[np.isfinite(seeding - control)])))
            if np.isfinite(seeding - control).any()
            else None
        ),
        "n_threshold_pairs": int(len(robustness_table)),
        "n_threshold_pairs_with_resolved_shift": int(len(finite_shifts)),
        "threshold_shift_min_s": float(finite_shifts.min()) if len(finite_shifts) else None,
        "threshold_shift_max_s": float(finite_shifts.max()) if len(finite_shifts) else None,
        "threshold_shift_median_s": float(finite_shifts.median()) if len(finite_shifts) else None,
        "threshold_shift_direction_consistent": sign_consistent,
        "onset_method": (
            "First crossing of the configured rain-size liquid-volume fraction among "
            "activated particles, linearly interpolated between stored spectrum checkpoints."
        ),
        "interpretation": (
            "Negative onset shift means the seeding spectrum reached the transition threshold "
            "earlier than control. This is a radius-bin diagnostic, not a particle-history event."
        ),
    }


def plot_spectrum_transition(
    transition_table: pd.DataFrame,
    *,
    title: str = "Spectrum-based cloud-to-rain transition",
):
    """Plot baseline transition fraction and seeding-minus-control response."""
    fig, axes = plt.subplots(2, 1, figsize=(8.0, 6.0), sharex=True)
    if transition_table.empty:
        axes[0].set_title("Spectrum transition unavailable")
        axes[0].text(0.5, 0.5, "Run a control-versus-seeding spectrum comparison.", ha="center")
        axes[1].axis("off")
        fig.tight_layout()
        return fig

    time_s = transition_table["time_s"].to_numpy(dtype=float)
    control_column = f"{TRANSITION_METRIC}_control"
    seeding_column = f"{TRANSITION_METRIC}_seeding"
    diff_column = f"{TRANSITION_METRIC}_diff"
    threshold = float(transition_table["rain_volume_fraction_threshold"].iloc[0])
    axes[0].plot(time_s, transition_table[control_column], marker="o", label="control")
    axes[0].plot(time_s, transition_table[seeding_column], marker="o", label="seeding")
    axes[0].axhline(threshold, color="#b91c1c", linestyle="--", label="transition threshold")
    axes[0].set_ylabel("Rain-size liquid / activated liquid [-]")
    axes[0].set_title(title)
    axes[0].legend(frameon=False)

    axes[1].plot(time_s, transition_table[diff_column], marker="o", color="#7c3aed")
    axes[1].axhline(0.0, color="#334155", linewidth=0.8)
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Seeding - control [-]")
    for axis in axes:
        axis.grid(alpha=0.22)
    fig.tight_layout()
    return fig

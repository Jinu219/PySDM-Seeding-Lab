from __future__ import annotations

"""Plots for checkpoint wet-radius spectra and threshold robustness."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SPECTRUM_VALUE_LABELS = {
    "number_concentration_cm3": "Bin-integrated number concentration [cm$^{-3}$]",
    "volume_fraction_per_dlnr": "$dV_{liquid}/V_{air} / d\\ln(r)$ [-]",
    "bin_liquid_volume_fraction": "Bin-integrated liquid volume fraction [-]",
}

ROBUSTNESS_METRIC_LABELS = {
    "activated_number_fraction": "Activated number fraction [-]",
    "rain_number_fraction_of_activated": "Rain number fraction of activated particles [-]",
    "rain_volume_fraction_of_activated": "Rain liquid-volume fraction of activated particles [-]",
    "rain_number_cm3": "Rain number concentration [cm$^{-3}$]",
    "rain_volume_fraction": "Rain liquid volume fraction [-]",
}


def spectrum_checkpoint_times(*frames: pd.DataFrame) -> list[float]:
    """Return sorted unique checkpoint times from one or more spectrum tables."""
    values: set[float] = set()
    for frame in frames:
        if isinstance(frame, pd.DataFrame) and not frame.empty and "time_s" in frame:
            values.update(float(value) for value in frame["time_s"].dropna().unique())
    return sorted(values)


def threshold_robustness_metrics(frame: pd.DataFrame) -> list[str]:
    """Return supported robustness metrics present in a result table."""
    return [column for column in ROBUSTNESS_METRIC_LABELS if column in frame.columns]


def _checkpoint_slice(frame: pd.DataFrame, checkpoint_time_s: float | None) -> pd.DataFrame:
    if frame.empty or checkpoint_time_s is None or "time_s" not in frame:
        return frame.copy()
    return frame[np.isclose(frame["time_s"].to_numpy(dtype=float), checkpoint_time_s)].copy()


def plot_wet_radius_spectrum(
    spectrum_df: pd.DataFrame,
    *,
    checkpoint_time_s: float | None = None,
    value_column: str = "number_concentration_cm3",
    title: str = "Wet-radius spectrum",
):
    """Plot one or all checkpoint spectra on logarithmic wet-radius axes."""
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    if spectrum_df.empty or value_column not in spectrum_df.columns:
        ax.set_title("Wet-radius spectrum unavailable")
        ax.text(0.5, 0.5, "No spectrum table was stored for this result.", ha="center", va="center")
        fig.tight_layout()
        return fig

    work = _checkpoint_slice(spectrum_df, checkpoint_time_s)
    for time_s, checkpoint in work.groupby("time_s", sort=True):
        x = checkpoint["radius_mid_um"].to_numpy(dtype=float)
        y = checkpoint[value_column].to_numpy(dtype=float)
        finite = np.isfinite(x) & np.isfinite(y) & (x > 0)
        ax.plot(x[finite], y[finite], marker="o", markersize=2.8, linewidth=1.5, label=f"t = {time_s:g} s")

    if "regime" in spectrum_df.columns:
        unactivated = spectrum_df[spectrum_df["regime"] == "unactivated"]
        rain = spectrum_df[spectrum_df["regime"] == "rain"]
    else:
        unactivated = pd.DataFrame()
        rain = pd.DataFrame()
    if not unactivated.empty:
        ax.axvline(float(unactivated["radius_right_um"].max()), color="#64748b", linestyle="--", linewidth=1.0)
    if not rain.empty:
        ax.axvline(float(rain["radius_left_um"].min()), color="#2563eb", linestyle="--", linewidth=1.0)

    plotted_values = work[value_column].to_numpy(dtype=float)
    if np.any(np.isfinite(plotted_values) & (plotted_values > 0)):
        ax.set_yscale("log")
    ax.set_xscale("log")
    ax.set_xlabel("Wet radius [µm]")
    ax.set_ylabel(SPECTRUM_VALUE_LABELS.get(value_column, value_column))
    ax.set_title(title)
    ax.grid(alpha=0.2, which="both")
    if ax.lines:
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def plot_threshold_robustness(
    robustness_df: pd.DataFrame,
    *,
    checkpoint_time_s: float | None = None,
    metric: str = "rain_volume_fraction_of_activated",
    title: str = "Threshold robustness",
):
    """Plot response to the tested rain threshold for each activation threshold."""
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    if robustness_df.empty or metric not in robustness_df.columns:
        ax.set_title("Threshold robustness unavailable")
        ax.text(0.5, 0.5, "No threshold robustness table was stored.", ha="center", va="center")
        fig.tight_layout()
        return fig

    work = _checkpoint_slice(robustness_df, checkpoint_time_s)
    for activation_factor, group in work.groupby("activation_factor", sort=True):
        group = group.sort_values("rain_threshold_um")
        ax.plot(
            group["rain_threshold_um"],
            group[metric],
            marker="o",
            linewidth=1.7,
            label=f"activation × {activation_factor:g}",
        )

    baseline_rain = work.loc[
        np.isclose(work["rain_factor"].to_numpy(dtype=float), 1.0),
        "rain_threshold_um",
    ]
    if not baseline_rain.empty:
        ax.axvline(
            float(baseline_rain.median()),
            color="#334155",
            linestyle="--",
            linewidth=1.0,
            label="baseline rain threshold",
        )
    ax.set_xlabel("Tested rain wet-radius threshold [µm]")
    ax.set_ylabel(ROBUSTNESS_METRIC_LABELS.get(metric, metric))
    ax.set_title(title)
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def plot_wet_radius_spectrum_difference(
    comparison_df: pd.DataFrame,
    *,
    checkpoint_time_s: float | None = None,
    value_column: str = "number_concentration_cm3",
    title: str = "Seeding − control wet-radius spectrum",
):
    """Plot the signed seeding-minus-control spectrum at one checkpoint."""
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    difference_column = f"{value_column}_diff"
    if comparison_df.empty or difference_column not in comparison_df:
        ax.set_title("Wet-radius spectrum difference unavailable")
        ax.text(0.5, 0.5, "Run a new control-versus-seeding experiment.", ha="center", va="center")
        fig.tight_layout()
        return fig

    work = _checkpoint_slice(comparison_df, checkpoint_time_s)
    for time_s, checkpoint in work.groupby("time_s", sort=True):
        x = checkpoint["radius_mid_um"].to_numpy(dtype=float)
        y = checkpoint[difference_column].to_numpy(dtype=float)
        finite = np.isfinite(x) & np.isfinite(y) & (x > 0)
        ax.plot(x[finite], y[finite], marker="o", markersize=3.0, linewidth=1.6, label=f"t = {time_s:g} s")

    values = work[difference_column].to_numpy(dtype=float)
    finite_abs = np.abs(values[np.isfinite(values)])
    if finite_abs.size and float(finite_abs.max()) > 0:
        ax.set_yscale("symlog", linthresh=max(float(finite_abs.max()) * 1.0e-4, 1.0e-18))
    ax.axhline(0.0, color="#334155", linewidth=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("Wet radius [µm]")
    ax.set_ylabel(f"Δ {SPECTRUM_VALUE_LABELS.get(value_column, value_column)}")
    ax.set_title(title)
    ax.grid(alpha=0.2, which="both")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def plot_threshold_robustness_difference(
    comparison_df: pd.DataFrame,
    *,
    checkpoint_time_s: float | None = None,
    metric: str = "rain_volume_fraction_of_activated",
    title: str = "Seeding − control threshold robustness",
):
    """Plot the signed response difference over tested diagnostic thresholds."""
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    difference_column = f"{metric}_diff"
    if comparison_df.empty or difference_column not in comparison_df:
        ax.set_title("Threshold robustness difference unavailable")
        ax.text(0.5, 0.5, "No aligned threshold comparison table was stored.", ha="center", va="center")
        fig.tight_layout()
        return fig

    work = _checkpoint_slice(comparison_df, checkpoint_time_s)
    for activation_factor, group in work.groupby("activation_factor", sort=True):
        group = group.sort_values("rain_threshold_um")
        ax.plot(
            group["rain_threshold_um"],
            group[difference_column],
            marker="o",
            linewidth=1.7,
            label=f"activation × {activation_factor:g}",
        )
    ax.axhline(0.0, color="#334155", linewidth=0.8)
    ax.set_xlabel("Tested rain wet-radius threshold [µm]")
    ax.set_ylabel(f"Δ {ROBUSTNESS_METRIC_LABELS.get(metric, metric)}")
    ax.set_title(title)
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig

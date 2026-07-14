from __future__ import annotations

"""Wet-radius spectrum configuration and threshold-robustness diagnostics."""

from typing import Any, Dict, Iterable

import numpy as np
import pandas as pd

from simulation.schema import diagnostic_radius_thresholds, normalize_config


SPECTRUM_TABLE_NAME = "wet_radius_spectrum"
ROBUSTNESS_TABLE_NAME = "threshold_robustness"


def wet_radius_spectrum_config(config: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return the normalized wet-radius spectrum subsection."""
    cfg = normalize_config(config)
    return dict(cfg.get("diagnostics", {}).get("wet_radius_spectrum", {}))


def resolve_spectrum_checkpoint_times(config: Dict[str, Any] | None) -> list[float]:
    """Resolve requested or automatic checkpoints onto the simulation time grid."""
    cfg = normalize_config(config)
    spectrum_cfg = wet_radius_spectrum_config(cfg)
    env = cfg.get("environment", {})
    seed = cfg.get("seeding", {})

    duration = float(env.get("duration", 1500.0))
    timestep = max(float(env.get("timestep", 15.0)), np.finfo(float).eps)
    requested = spectrum_cfg.get("checkpoint_times", [])
    if not requested:
        requested = [
            0.0,
            float(seed.get("injection_start", 0.0)),
            float(seed.get("injection_end", duration)),
            duration,
        ]

    last_step = max(0, int(np.floor(duration / timestep)))
    resolved_steps = {
        min(last_step, max(0, int(round(float(value) / timestep))))
        for value in requested
    }
    return [float(step * timestep) for step in sorted(resolved_steps)]


def build_spectrum_bin_edges(config: Dict[str, Any] | None) -> np.ndarray:
    """Build log-spaced wet-radius edges and preserve every tested threshold exactly."""
    spectrum_cfg = wet_radius_spectrum_config(config)
    minimum = float(spectrum_cfg.get("min_radius", 0.05e-6))
    maximum = float(spectrum_cfg.get("max_radius", 1000.0e-6))
    n_bins = int(spectrum_cfg.get("n_bins", 32))
    factors = [float(value) for value in spectrum_cfg.get("threshold_factors", [0.8, 1.0, 1.2])]
    activation_radius, rain_radius = diagnostic_radius_thresholds(config)

    base_edges = np.geomspace(minimum, maximum, n_bins + 1)
    threshold_edges = [
        threshold * factor
        for threshold in (activation_radius, rain_radius)
        for factor in factors
        if minimum < threshold * factor < maximum
    ]
    return np.unique(np.asarray([*base_edges, *threshold_edges], dtype=float))


def build_wet_radius_spectrum_table(
    spectra: Dict[str, Any],
    radius_bin_edges_m: Iterable[float],
    config: Dict[str, Any] | None,
) -> pd.DataFrame:
    """Convert checkpoint spectrum arrays into a tidy, analysis-ready table."""
    edges = np.asarray(list(radius_bin_edges_m), dtype=float)
    times = np.asarray(spectra.get("time_s", []), dtype=float)
    number = np.asarray(spectra.get("number_concentration_m3", []), dtype=float)
    volume_density = np.asarray(spectra.get("volume_fraction_per_dlnr", []), dtype=float)
    n_bins = max(0, len(edges) - 1)

    columns = [
        "time_s",
        "bin_index",
        "radius_left_um",
        "radius_right_um",
        "radius_mid_um",
        "number_concentration_m3",
        "number_concentration_cm3",
        "volume_fraction_per_dlnr",
        "bin_liquid_volume_fraction",
        "regime",
    ]
    if times.size == 0 or n_bins == 0:
        return pd.DataFrame(columns=columns)

    number = np.atleast_2d(number)
    volume_density = np.atleast_2d(volume_density)
    expected_shape = (len(times), n_bins)
    if number.shape != expected_shape or volume_density.shape != expected_shape:
        raise ValueError(
            "Wet-radius spectrum arrays do not match checkpoint/bin dimensions: "
            f"times={len(times)}, bins={n_bins}, number={number.shape}, volume={volume_density.shape}."
        )

    left = edges[:-1]
    right = edges[1:]
    midpoint = np.sqrt(left * right)
    dlnr = np.log(right / left)
    activation_radius, rain_radius = diagnostic_radius_thresholds(config)

    regimes = np.full(n_bins, "cloud", dtype=object)
    regimes[
        (right < activation_radius)
        | np.isclose(right, activation_radius, rtol=1.0e-12, atol=0.0)
    ] = "unactivated"
    regimes[
        (left > rain_radius)
        | np.isclose(left, rain_radius, rtol=1.0e-12, atol=0.0)
    ] = "rain"

    frames = []
    for index, time_s in enumerate(times):
        frames.append(
            pd.DataFrame(
                {
                    "time_s": float(time_s),
                    "bin_index": np.arange(n_bins, dtype=int),
                    "radius_left_um": left * 1.0e6,
                    "radius_right_um": right * 1.0e6,
                    "radius_mid_um": midpoint * 1.0e6,
                    "number_concentration_m3": number[index],
                    "number_concentration_cm3": number[index] / 1.0e6,
                    "volume_fraction_per_dlnr": volume_density[index],
                    "bin_liquid_volume_fraction": volume_density[index] * dlnr,
                    "regime": regimes,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)[columns]


def _safe_fraction(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator > 0 else float("nan")


def build_threshold_robustness_table(
    spectrum_df: pd.DataFrame,
    config: Dict[str, Any] | None,
) -> pd.DataFrame:
    """Repartition one spectrum over configured activation/rain threshold factors."""
    columns = [
        "time_s",
        "activation_factor",
        "rain_factor",
        "activation_threshold_um",
        "rain_threshold_um",
        "unactivated_number_cm3",
        "cloud_number_cm3",
        "rain_number_cm3",
        "unactivated_volume_fraction",
        "cloud_volume_fraction",
        "rain_volume_fraction",
        "activated_number_fraction",
        "rain_number_fraction_of_activated",
        "rain_volume_fraction_of_activated",
    ]
    if spectrum_df.empty:
        return pd.DataFrame(columns=columns)

    spectrum_cfg = wet_radius_spectrum_config(config)
    factors = sorted({float(value) for value in spectrum_cfg.get("threshold_factors", [0.8, 1.0, 1.2])})
    activation_radius, rain_radius = diagnostic_radius_thresholds(config)
    rows: list[dict[str, float]] = []

    for time_s, checkpoint in spectrum_df.groupby("time_s", sort=True):
        left_m = checkpoint["radius_left_um"].to_numpy(dtype=float) * 1.0e-6
        right_m = checkpoint["radius_right_um"].to_numpy(dtype=float) * 1.0e-6
        number_cm3 = checkpoint["number_concentration_cm3"].to_numpy(dtype=float)
        volume_fraction = checkpoint["bin_liquid_volume_fraction"].to_numpy(dtype=float)

        for activation_factor in factors:
            activation_test = activation_radius * activation_factor
            for rain_factor in factors:
                rain_test = rain_radius * rain_factor
                if activation_test >= rain_test:
                    continue

                unactivated_mask = (right_m < activation_test) | np.isclose(
                    right_m,
                    activation_test,
                    rtol=1.0e-12,
                    atol=0.0,
                )
                rain_mask = (left_m > rain_test) | np.isclose(
                    left_m,
                    rain_test,
                    rtol=1.0e-12,
                    atol=0.0,
                )
                cloud_mask = ~(unactivated_mask | rain_mask)

                unactivated_number = float(np.nansum(number_cm3[unactivated_mask]))
                cloud_number = float(np.nansum(number_cm3[cloud_mask]))
                rain_number = float(np.nansum(number_cm3[rain_mask]))
                unactivated_volume = float(np.nansum(volume_fraction[unactivated_mask]))
                cloud_volume = float(np.nansum(volume_fraction[cloud_mask]))
                rain_volume = float(np.nansum(volume_fraction[rain_mask]))
                total_number = unactivated_number + cloud_number + rain_number
                activated_number = cloud_number + rain_number
                activated_volume = cloud_volume + rain_volume

                rows.append(
                    {
                        "time_s": float(time_s),
                        "activation_factor": activation_factor,
                        "rain_factor": rain_factor,
                        "activation_threshold_um": activation_test * 1.0e6,
                        "rain_threshold_um": rain_test * 1.0e6,
                        "unactivated_number_cm3": unactivated_number,
                        "cloud_number_cm3": cloud_number,
                        "rain_number_cm3": rain_number,
                        "unactivated_volume_fraction": unactivated_volume,
                        "cloud_volume_fraction": cloud_volume,
                        "rain_volume_fraction": rain_volume,
                        "activated_number_fraction": _safe_fraction(activated_number, total_number),
                        "rain_number_fraction_of_activated": _safe_fraction(rain_number, activated_number),
                        "rain_volume_fraction_of_activated": _safe_fraction(rain_volume, activated_volume),
                    }
                )

    return pd.DataFrame(rows, columns=columns)

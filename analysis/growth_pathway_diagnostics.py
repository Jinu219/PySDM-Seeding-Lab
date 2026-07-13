from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd


GROWTH_PATHWAY_BUILD_ID = "growth-pathway-diagnostics-20260713"

ACTIVATED_RADIUS_THRESHOLD_M = 0.5e-6
RAIN_RADIUS_THRESHOLD_M = 25.0e-6


GROWTH_PATHWAY_VARIABLE_GROUPS: Dict[str, List[str]] = {
    "Thermodynamic pathway": [
        "water_vapour_mixing_ratio",
        "supersaturation_percent",
        "relative_humidity_percent",
        "temperature_K",
    ],
    "Water mass pathway": [
        "cloud_water_mixing_ratio",
        "rain_water_mixing_ratio",
        "all_activated_water_mixing_ratio",
    ],
    "Number concentration pathway": [
        "cloud_droplet_concentration",
        "rain_droplet_concentration",
        "all_activated_concentration",
    ],
    "Size growth pathway": [
        "effective_radius_cloud_um",
        "effective_radius_rain_um",
        "effective_radius_all_um",
    ],
}


GROWTH_PATHWAY_PREFERRED_ORDER: List[str] = [
    "water_vapour_mixing_ratio",
    "supersaturation_percent",
    "relative_humidity_percent",
    "temperature_K",
    "cloud_water_mixing_ratio",
    "rain_water_mixing_ratio",
    "all_activated_water_mixing_ratio",
    "cloud_droplet_concentration",
    "rain_droplet_concentration",
    "all_activated_concentration",
    "effective_radius_cloud_um",
    "effective_radius_rain_um",
    "effective_radius_all_um",
]


def _column(df: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce")
    return pd.Series(default, index=df.index, dtype=float)


def _infer_supersaturation_percent(df: pd.DataFrame) -> pd.Series:
    if "supersaturation_percent" in df.columns:
        return _column(df, "supersaturation_percent")

    if "supersaturation" in df.columns:
        s = _column(df, "supersaturation")
        finite = s.replace([np.inf, -np.inf], np.nan).dropna()
        if len(finite) and finite.abs().quantile(0.95) <= 1.0:
            return s * 100.0
        return s

    if "relative_humidity_percent" in df.columns:
        return _column(df, "relative_humidity_percent") - 100.0

    return pd.Series(np.nan, index=df.index, dtype=float)


def _infer_relative_humidity_percent(df: pd.DataFrame) -> pd.Series:
    if "relative_humidity_percent" in df.columns:
        return _column(df, "relative_humidity_percent")

    supersat = _infer_supersaturation_percent(df)
    return 100.0 + supersat


def _infer_temperature(df: pd.DataFrame, config: Dict[str, Any] | None) -> pd.Series:
    if "temperature_K" in df.columns:
        return _column(df, "temperature_K")

    env = (config or {}).get("environment", {})
    initial_temperature = float(env.get("temperature", 300.0))
    cloud = _column(df, "cloud_water_mixing_ratio")
    rain = _column(df, "rain_water_mixing_ratio")
    liquid = cloud + rain
    scale = float(liquid.max(skipna=True)) if len(liquid) else 0.0

    if scale <= 0:
        return pd.Series(initial_temperature, index=df.index, dtype=float)

    return initial_temperature + 0.2 * liquid / scale


def _infer_water_vapour(df: pd.DataFrame, config: Dict[str, Any] | None) -> pd.Series:
    if "water_vapour_mixing_ratio" in df.columns:
        return _column(df, "water_vapour_mixing_ratio")

    env = (config or {}).get("environment", {})
    qv0 = float(env.get("water_vapour_mixing_ratio", env.get("qv", 0.0222)))

    cloud = _column(df, "cloud_water_mixing_ratio")
    rain = _column(df, "rain_water_mixing_ratio")
    liquid = cloud + rain

    return qv0 - liquid


def add_growth_pathway_diagnostics(
    df: pd.DataFrame,
    config: Dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Add seeding growth-pathway diagnostic columns.

    The pathway is:
    vapour / supersaturation
    -> cloud water and activated particles
    -> rain-size particles
    -> rain water response
    """
    out = df.copy()

    if "supersaturation_percent" not in out.columns:
        out["supersaturation_percent"] = _infer_supersaturation_percent(out)

    if "relative_humidity_percent" not in out.columns:
        out["relative_humidity_percent"] = _infer_relative_humidity_percent(out)

    if "temperature_K" not in out.columns:
        out["temperature_K"] = _infer_temperature(out, config)

    if "water_vapour_mixing_ratio" not in out.columns:
        out["water_vapour_mixing_ratio"] = _infer_water_vapour(out, config)

    cloud_water = _column(out, "cloud_water_mixing_ratio")
    rain_water = _column(out, "rain_water_mixing_ratio")

    if "all_activated_water_mixing_ratio" not in out.columns:
        out["all_activated_water_mixing_ratio"] = cloud_water + rain_water

    if "cloud_droplet_concentration" not in out.columns:
        if "droplet_number_concentration_cm3" in out.columns:
            out["cloud_droplet_concentration"] = _column(out, "droplet_number_concentration_cm3")
        elif "droplet_number_concentration" in out.columns:
            out["cloud_droplet_concentration"] = _column(out, "droplet_number_concentration")
        else:
            out["cloud_droplet_concentration"] = np.nan

    if "rain_droplet_concentration" not in out.columns:
        if "rain_drop_number_concentration" in out.columns:
            out["rain_droplet_concentration"] = _column(out, "rain_drop_number_concentration")
        else:
            out["rain_droplet_concentration"] = np.where(rain_water > 0, 1.0, 0.0)

    if "all_activated_concentration" not in out.columns:
        out["all_activated_concentration"] = (
            _column(out, "cloud_droplet_concentration")
            + _column(out, "rain_droplet_concentration")
        )

    if "effective_radius_all_um" not in out.columns:
        if "effective_radius_um" in out.columns:
            out["effective_radius_all_um"] = _column(out, "effective_radius_um")
        elif "mean_radius_m" in out.columns:
            out["effective_radius_all_um"] = _column(out, "mean_radius_m") * 1.0e6
        else:
            out["effective_radius_all_um"] = np.nan

    if "effective_radius_cloud_um" not in out.columns:
        if "effective_radius_um" in out.columns:
            out["effective_radius_cloud_um"] = _column(out, "effective_radius_um")
        elif "mean_radius_m" in out.columns:
            out["effective_radius_cloud_um"] = _column(out, "mean_radius_m") * 1.0e6
        else:
            out["effective_radius_cloud_um"] = np.nan

    if "effective_radius_rain_um" not in out.columns:
        all_reff = _column(out, "effective_radius_all_um", default=np.nan)
        out["effective_radius_rain_um"] = np.where(rain_water > 0, all_reff, np.nan)

    return out


def diagnostic_health(df: pd.DataFrame) -> Dict[str, Any]:
    """Return finite-fraction health diagnostics for pathway columns."""
    rows: Dict[str, Any] = {}
    for column in GROWTH_PATHWAY_PREFERRED_ORDER:
        if column not in df.columns:
            rows[column] = {
                "exists": False,
                "finite_fraction": 0.0,
                "n_finite": 0,
                "n_total": int(len(df)),
            }
            continue

        values = pd.to_numeric(df[column], errors="coerce")
        finite = np.isfinite(values.to_numpy())
        rows[column] = {
            "exists": True,
            "finite_fraction": float(finite.mean()) if len(finite) else 0.0,
            "n_finite": int(finite.sum()),
            "n_total": int(len(values)),
        }

    return rows


def diagnostic_health_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Return health diagnostics as table rows."""
    health = diagnostic_health(df)
    return [
        {
            "variable": key,
            **value,
        }
        for key, value in health.items()
    ]


def available_growth_pathway_groups(df_columns: List[str]) -> Dict[str, List[str]]:
    """Return diagnostic groups limited to available columns."""
    available = set(df_columns)
    return {
        group: [column for column in columns if column in available]
        for group, columns in GROWTH_PATHWAY_VARIABLE_GROUPS.items()
        if any(column in available for column in columns)
    }


# Backward-compatible aliases for older local code.
EXPER2_BUILD_ID = GROWTH_PATHWAY_BUILD_ID
EXPER2_VARIABLE_GROUPS = GROWTH_PATHWAY_VARIABLE_GROUPS
EXPER2_PREFERRED_ORDER = GROWTH_PATHWAY_PREFERRED_ORDER
add_exper2_diagnostics = add_growth_pathway_diagnostics
available_exper2_groups = available_growth_pathway_groups

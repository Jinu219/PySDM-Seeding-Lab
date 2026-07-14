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


PROVENANCE_NATIVE = "native"
PROVENANCE_DERIVED = "derived"
PROVENANCE_PROXY = "proxy"

PROVENANCE_LABELS_KO: Dict[str, str] = {
    PROVENANCE_NATIVE: "실측 (native)",
    PROVENANCE_DERIVED: "계산값 (derived)",
    PROVENANCE_PROXY: "근사값 (proxy)",
}


def classify_diagnostic_provenance(
    raw_columns: List[str] | set,
    config: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, str]]:
    """
    Classify each Growth Pathway variable as native / derived / proxy.

    - native: the adapter already produced this exact column.
    - derived: computed from other *native* adapter columns using a direct,
      physically exact relationship (e.g. all_activated = cloud + rain, when
      both cloud and rain are themselves native).
    - proxy: not available from the adapter; approximated with a heuristic
      that does not come from PySDM's own physics (e.g. temperature guessed
      from a liquid-water scale, water vapour back-calculated from qv0).

    `raw_columns` must be the adapter's *raw* output columns, captured before
    `add_growth_pathway_diagnostics` is applied, since that function fills in
    proxy columns and would otherwise make everything look native.
    """
    raw = set(raw_columns)
    info: Dict[str, Dict[str, str]] = {}

    def set_info(var: str, provenance: str, basis: str) -> None:
        info[var] = {"provenance": provenance, "basis": basis}

    cloud_native = "cloud_water_mixing_ratio" in raw
    rain_native = "rain_water_mixing_ratio" in raw

    # --- Thermodynamic pathway ---------------------------------------------
    if "water_vapour_mixing_ratio" in raw:
        set_info("water_vapour_mixing_ratio", PROVENANCE_NATIVE, "adapter output column")
    else:
        set_info(
            "water_vapour_mixing_ratio",
            PROVENANCE_PROXY,
            "adapter가 제공하지 않아 qv0 - (cloud_water + rain_water)로 역산 (PySDM 직접 출력 아님)",
        )

    if "supersaturation_percent" in raw:
        set_info("supersaturation_percent", PROVENANCE_NATIVE, "adapter output column")
    elif "supersaturation" in raw:
        set_info(
            "supersaturation_percent",
            PROVENANCE_DERIVED,
            "adapter의 'supersaturation' 컬럼을 %로 단위 변환 (값 자체는 native)",
        )
    elif "relative_humidity_percent" in raw:
        set_info(
            "supersaturation_percent",
            PROVENANCE_DERIVED,
            "adapter의 relative_humidity_percent에서 -100 오프셋으로 계산",
        )
    else:
        set_info(
            "supersaturation_percent",
            PROVENANCE_PROXY,
            "adapter가 supersaturation 관련 값을 전혀 제공하지 않아 NaN으로 남음",
        )

    if "relative_humidity_percent" in raw:
        set_info("relative_humidity_percent", PROVENANCE_NATIVE, "adapter output column")
    else:
        set_info(
            "relative_humidity_percent",
            PROVENANCE_DERIVED if ("supersaturation_percent" in raw or "supersaturation" in raw) else PROVENANCE_PROXY,
            "supersaturation_percent(추정치 포함)로부터 100 + supersaturation으로 계산",
        )

    if "temperature_K" in raw:
        set_info("temperature_K", PROVENANCE_NATIVE, "adapter output column")
    else:
        set_info(
            "temperature_K",
            PROVENANCE_PROXY,
            "adapter가 온도 시계열을 제공하지 않아, 초기 온도에 liquid water 비례 보정을 더한 휴리스틱 (PySDM 열역학 계산 아님)",
        )

    # --- Water mass pathway --------------------------------------------------
    set_info(
        "cloud_water_mixing_ratio",
        PROVENANCE_NATIVE if cloud_native else PROVENANCE_PROXY,
        "adapter output column" if cloud_native else "adapter가 제공하지 않아 0으로 기본값 처리됨 (현재 pysdm_parcel adapter는 이 컬럼을 만들지 않음)",
    )
    set_info(
        "rain_water_mixing_ratio",
        PROVENANCE_NATIVE if rain_native else PROVENANCE_PROXY,
        "adapter output column" if rain_native else "adapter가 제공하지 않아 0으로 기본값 처리됨",
    )
    if cloud_native and rain_native:
        set_info(
            "all_activated_water_mixing_ratio",
            PROVENANCE_DERIVED,
            "cloud_water_mixing_ratio + rain_water_mixing_ratio (둘 다 native이므로 정확한 합산)",
        )
    else:
        set_info(
            "all_activated_water_mixing_ratio",
            PROVENANCE_PROXY,
            "cloud/rain 중 최소 하나가 proxy이므로 합산 결과도 근사값",
        )

    # --- Number concentration pathway ----------------------------------------
    if "droplet_number_concentration_cm3" in raw or "droplet_number_concentration" in raw:
        set_info("cloud_droplet_concentration", PROVENANCE_NATIVE, "adapter output column (단위 변환 포함)")
        cloud_conc_native = True
    else:
        set_info(
            "cloud_droplet_concentration",
            PROVENANCE_PROXY,
            "adapter가 제공하지 않아 NaN으로 남음",
        )
        cloud_conc_native = False

    if "rain_drop_number_concentration" in raw:
        set_info("rain_droplet_concentration", PROVENANCE_NATIVE, "adapter output column")
        rain_conc_native = True
    else:
        set_info(
            "rain_droplet_concentration",
            PROVENANCE_PROXY,
            "adapter가 강우 방울 수농도를 제공하지 않아, rain_water_mixing_ratio>0 여부만으로 0/1 지시값을 대신 사용 (수농도 아님)",
        )
        rain_conc_native = False

    if cloud_conc_native and rain_conc_native:
        set_info(
            "all_activated_concentration",
            PROVENANCE_DERIVED,
            "cloud_droplet_concentration + rain_droplet_concentration (둘 다 native)",
        )
    else:
        set_info(
            "all_activated_concentration",
            PROVENANCE_PROXY,
            "구성 성분 중 최소 하나가 proxy이므로 합산 결과도 근사값",
        )

    # --- Size growth pathway ---------------------------------------------------
    radius_native = "effective_radius_um" in raw or "mean_radius_m" in raw
    set_info(
        "effective_radius_all_um",
        PROVENANCE_NATIVE if radius_native else PROVENANCE_PROXY,
        "adapter output column" if radius_native else "adapter가 제공하지 않아 NaN으로 남음",
    )
    set_info(
        "effective_radius_cloud_um",
        PROVENANCE_DERIVED if radius_native else PROVENANCE_PROXY,
        (
            "adapter의 전체 유효반경을 cloud pathway에도 그대로 대입 (실제로는 cloud만의 유효반경이 아님)"
            if radius_native
            else "adapter가 제공하지 않아 NaN으로 남음"
        ),
    )
    set_info(
        "effective_radius_rain_um",
        PROVENANCE_PROXY,
        "rain_water_mixing_ratio>0인 시점에만 전체 유효반경 값을 그대로 사용하는 근사 (rain 전용 반경 계산이 아님)",
    )

    return info


def diagnostic_provenance_rows(
    raw_columns: List[str] | set,
    config: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Return provenance classification as table rows, in preferred display order."""
    provenance = classify_diagnostic_provenance(raw_columns, config)
    rows: List[Dict[str, Any]] = []
    for column in GROWTH_PATHWAY_PREFERRED_ORDER:
        entry = provenance.get(column, {"provenance": PROVENANCE_PROXY, "basis": "분류되지 않음"})
        rows.append(
            {
                "variable": column,
                "provenance": entry["provenance"],
                "provenance_label": PROVENANCE_LABELS_KO.get(entry["provenance"], entry["provenance"]),
                "basis": entry["basis"],
            }
        )
    return rows


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

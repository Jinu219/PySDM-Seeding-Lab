from __future__ import annotations

"""Extract auditable fixed-column drizzle proxies from ARM ENA KAZR NetCDF."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis.bastalias_observations import detect_persistent_drizzle_onset


ARM_ENA_OBSERVATION_BUILD_ID = "arm-ena-kazr-observation-import-v1-20260721"
ARM_ENA_KAZR_DATASET_DOI = "https://doi.org/10.5439/1213419"
ARM_ENA_METHOD_PAPER_DOI = "https://doi.org/10.5194/amt-13-1485-2020"
ARM_ENA_MAPPING_STATUS = "spatiotemporal_proxy"
ARM_ENA_SAMPLING_CONTEXT = "fixed_eulerian_vertical_column_time_height_sampling"
ARM_ENA_REFLECTIVITY_THRESHOLDS_DBZ = (-20.0, -17.0, -15.0)
REFLECTIVITY_VARIABLE_CANDIDATES = (
    "reflectivity_best_estimate",
    "ReflectivityBestEstimate",
    "reflectivity_copol",
    "reflectivity",
)
HEIGHT_VARIABLE_CANDIDATES = ("height", "range")


def _array(variable: Any) -> np.ndarray:
    return np.asarray(np.ma.filled(variable[:], np.nan), dtype=float)


def _first_variable(dataset: Any, candidates: tuple[str, ...]) -> tuple[str, Any]:
    for name in candidates:
        if name in dataset.variables:
            return name, dataset.variables[name]
    raise ValueError("ARM KAZR NetCDF is missing variables: " + ", ".join(candidates))


def _time_values(dataset: Any) -> tuple[np.ndarray, str, str]:
    if "time" in dataset.variables:
        variable = dataset.variables["time"]
        values = _array(variable)
        return values, str(getattr(variable, "units", "")), "time"
    if "time_offset" in dataset.variables:
        variable = dataset.variables["time_offset"]
        values = _array(variable)
        units = str(getattr(variable, "units", ""))
        if not units and "base_time" in dataset.variables:
            base_time = dataset.variables["base_time"]
            units = str(getattr(base_time, "units", ""))
        return values, units, "time_offset"
    raise ValueError("ARM KAZR NetCDF requires time or time_offset.")


def _height_values_m(variable: Any) -> tuple[np.ndarray, str]:
    values = _array(variable)
    units = str(getattr(variable, "units", "")).strip().lower()
    if units in {"m", "meter", "meters", "metre", "metres"}:
        return values, "m"
    if units in {"km", "kilometer", "kilometers", "kilometre", "kilometres"}:
        return values * 1000.0, "m (converted from km)"
    raise ValueError(
        "ARM KAZR height/range units must be metres or kilometres; "
        f"found {units!r}."
    )


def load_arm_kazr_netcdf(
    path: str | Path,
    *,
    allow_missing_quality: bool = False,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    try:
        from netCDF4 import Dataset
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "ARM KAZR NetCDF import requires requirements-observations.txt."
        ) from exc

    source_path = Path(path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"ARM KAZR NetCDF file not found: {source_path}")
    with Dataset(str(source_path), mode="r") as dataset:
        reflectivity_name, reflectivity_variable = _first_variable(
            dataset, REFLECTIVITY_VARIABLE_CANDIDATES
        )
        height_name, height_variable = _first_variable(
            dataset, HEIGHT_VARIABLE_CANDIDATES
        )
        time_values, time_units, time_name = _time_values(dataset)
        reflectivity = _array(reflectivity_variable)
        height, normalized_height_units = _height_values_m(height_variable)
        reflectivity_units = str(
            getattr(reflectivity_variable, "units", "")
        ).strip()
        if reflectivity_units.lower() not in {"dbz", "dbze"}:
            raise ValueError(
                "ARM KAZR reflectivity units must be dBZ; "
                f"found {reflectivity_units!r}."
            )
        if time_values.ndim != 1 or height.ndim != 1 or reflectivity.ndim != 2:
            raise ValueError(
                "ARM KAZR importer requires 1-D time/height and 2-D reflectivity."
            )
        dimensions = tuple(str(value) for value in reflectivity_variable.dimensions)
        try:
            time_axis = dimensions.index(time_name)
        except ValueError:
            time_axis = 0 if reflectivity.shape[0] == len(time_values) else -1
        if time_axis == -1:
            raise ValueError("Cannot identify the ARM KAZR reflectivity time axis.")
        if time_axis == 1:
            reflectivity = reflectivity.T
        if reflectivity.shape != (len(time_values), len(height)):
            raise ValueError(
                "ARM KAZR reflectivity shape does not match time and height axes."
            )

        quality_name = f"qc_{reflectivity_name}"
        if quality_name in dataset.variables:
            quality = _array(dataset.variables[quality_name])
            if quality.shape == reflectivity.T.shape:
                quality = quality.T
            if quality.shape != reflectivity.shape:
                raise ValueError("ARM KAZR quality field shape does not match reflectivity.")
            quality_valid = quality == 0
            quality_policy = f"{quality_name} == 0"
        elif allow_missing_quality:
            quality_valid = np.isfinite(reflectivity)
            quality_policy = "finite reflectivity only; explicit quality field absent"
            quality_name = ""
        else:
            raise ValueError(
                f"ARM KAZR NetCDF is missing {quality_name}; use an appropriate "
                "quality-controlled product or explicitly allow missing quality."
            )
        metadata = {
            "source_file": source_path.name,
            "datastream": str(getattr(dataset, "datastream", "")),
            "site_id": str(getattr(dataset, "site_id", "")),
            "facility_id": str(getattr(dataset, "facility_id", "")),
            "time_variable": time_name,
            "time_units": time_units,
            "height_variable": height_name,
            "height_units": normalized_height_units,
            "reflectivity_variable": reflectivity_name,
            "reflectivity_units": reflectivity_units,
            "quality_variable": quality_name,
            "quality_policy": quality_policy,
        }
    return {
        "time_s": time_values,
        "height_m": height,
        "reflectivity_dbz": reflectivity,
        "quality_valid": quality_valid,
    }, metadata


def build_arm_kazr_column_timeseries(
    data: dict[str, np.ndarray],
    *,
    reflectivity_threshold_dbz: float,
    minimum_height_m: float,
    maximum_height_m: float,
) -> pd.DataFrame:
    threshold = float(reflectivity_threshold_dbz)
    minimum_height = float(minimum_height_m)
    maximum_height = float(maximum_height_m)
    if not np.isfinite([threshold, minimum_height, maximum_height]).all():
        raise ValueError("ARM KAZR threshold and height limits must be finite.")
    if minimum_height < 0 or maximum_height <= minimum_height:
        raise ValueError("ARM KAZR height limits require 0 <= minimum < maximum.")
    time_values = np.asarray(data["time_s"], dtype=float)
    height = np.asarray(data["height_m"], dtype=float)
    reflectivity = np.asarray(data["reflectivity_dbz"], dtype=float)
    quality_valid = np.asarray(data["quality_valid"], dtype=bool)
    if reflectivity.shape != quality_valid.shape:
        raise ValueError("ARM KAZR reflectivity and quality arrays must have equal shape.")
    selected_height = np.isfinite(height) & (height >= minimum_height) & (
        height <= maximum_height
    )
    if not selected_height.any():
        raise ValueError("No ARM KAZR range gates fall inside the selected height range.")
    selected_reflectivity = reflectivity[:, selected_height]
    selected_quality = quality_valid[:, selected_height] & np.isfinite(
        selected_reflectivity
    )
    drizzle_gates = selected_quality & (selected_reflectivity >= threshold)
    valid_gate_count = selected_quality.sum(axis=1)
    return pd.DataFrame(
        {
            "time_s": time_values,
            "time_issue_flag": np.where(valid_gate_count > 0, 0, 1),
            "drizzle_pixels": drizzle_gates.sum(axis=1),
            "quality_valid_gate_count": valid_gate_count,
        }
    )


def build_arm_ena_threshold_sensitivity(
    data: dict[str, np.ndarray],
    *,
    window_start_s: float,
    window_end_s: float,
    minimum_height_m: float,
    maximum_height_m: float,
    minimum_drizzle_gates: int,
    minimum_persistence_s: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for threshold in ARM_ENA_REFLECTIVITY_THRESHOLDS_DBZ:
        timeseries = build_arm_kazr_column_timeseries(
            data,
            reflectivity_threshold_dbz=threshold,
            minimum_height_m=minimum_height_m,
            maximum_height_m=maximum_height_m,
        )
        try:
            detection = detect_persistent_drizzle_onset(
                timeseries,
                window_start_s=window_start_s,
                window_end_s=window_end_s,
                minimum_drizzle_pixels=minimum_drizzle_gates,
                minimum_persistence_s=minimum_persistence_s,
            )
        except ValueError as exc:
            rows.append(
                {
                    "reflectivity_threshold_dbz": threshold,
                    "detection_status": "unresolved",
                    "onset_time_s": None,
                    "onset_relative_to_window_s": None,
                    "nominal_cadence_s": None,
                    "n_detected_samples": 0,
                    "detail": str(exc),
                }
            )
        else:
            rows.append(
                {
                    "reflectivity_threshold_dbz": threshold,
                    "detection_status": "resolved",
                    "onset_time_s": detection["onset_time_s"],
                    "onset_relative_to_window_s": detection[
                        "onset_relative_to_window_s"
                    ],
                    "nominal_cadence_s": detection["nominal_cadence_s"],
                    "n_detected_samples": detection["n_detected_samples"],
                    "detail": "",
                }
            )
    return pd.DataFrame(rows)


def build_arm_ena_observation_event(
    data: dict[str, np.ndarray],
    metadata: dict[str, Any],
    *,
    event_id: str,
    case: str,
    source_id: str,
    window_start_s: float,
    window_end_s: float,
    observed_uncertainty_s: float,
    model_time_offset_s: float,
    reflectivity_threshold_dbz: float,
    minimum_height_m: float,
    maximum_height_m: float,
    minimum_drizzle_gates: int,
    minimum_persistence_s: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    event_name = str(event_id).strip()
    case_name = str(case).strip().lower()
    source = str(source_id).strip()
    if not event_name or not source:
        raise ValueError("event_id and source_id must be non-blank.")
    if case_name not in {"control", "seeding"}:
        raise ValueError("case must be control or seeding.")
    uncertainty = float(observed_uncertainty_s)
    offset = float(model_time_offset_s)
    if not np.isfinite([uncertainty, offset]).all() or uncertainty < 0:
        raise ValueError("Observed uncertainty and model offset must be finite.")
    timeseries = build_arm_kazr_column_timeseries(
        data,
        reflectivity_threshold_dbz=reflectivity_threshold_dbz,
        minimum_height_m=minimum_height_m,
        maximum_height_m=maximum_height_m,
    )
    detection = detect_persistent_drizzle_onset(
        timeseries,
        window_start_s=window_start_s,
        window_end_s=window_end_s,
        minimum_drizzle_pixels=minimum_drizzle_gates,
        minimum_persistence_s=minimum_persistence_s,
    )
    event_definition = (
        f"at least {int(minimum_drizzle_gates)} quality-valid KAZR gates between "
        f"{float(minimum_height_m):g} and {float(maximum_height_m):g} m with "
        f"reflectivity >= {float(reflectivity_threshold_dbz):g} dBZ for at least "
        f"{float(minimum_persistence_s):g} s"
    )
    mapping_note = (
        "The zenith radar samples a fixed Eulerian vertical column while advected air "
        "parcels change with time. Reflectivity is weighted toward large drops and is "
        "not the model-native rain-liquid fraction. This event remains a temporal "
        "column proxy until an air-parcel trajectory and microphysical mapping are "
        "independently justified."
    )
    time_origin = (
        f"{metadata.get('time_units', '')}; selected_window_start="
        f"{float(window_start_s):g} s"
    )
    event = pd.DataFrame(
        [
            {
                "event_id": event_name,
                "case": case_name,
                "observed_transition_onset_s": detection[
                    "onset_relative_to_window_s"
                ],
                "observed_uncertainty_s": uncertainty,
                "model_time_offset_s": offset,
                "time_origin": time_origin,
                "source_id": source,
                "evidence_class": "observation",
                "observation_method": (
                    "ARM ENA fixed-site Ka-band zenith radar reflectivity threshold"
                ),
                "event_definition": event_definition,
                "sampling_context": ARM_ENA_SAMPLING_CONTEXT,
                "mapping_status": ARM_ENA_MAPPING_STATUS,
                "notes": mapping_note,
            }
        ]
    )
    audit = {
        "build_id": ARM_ENA_OBSERVATION_BUILD_ID,
        "source_id": source,
        "method_source_id": ARM_ENA_METHOD_PAPER_DOI,
        "source_file": metadata.get("source_file", ""),
        "source_metadata": metadata,
        "event_id": event_name,
        "case": case_name,
        "evidence_class": "observation",
        "mapping_status": ARM_ENA_MAPPING_STATUS,
        "sampling_context": ARM_ENA_SAMPLING_CONTEXT,
        "window_start_s": float(window_start_s),
        "window_end_s": float(window_end_s),
        "observed_uncertainty_s": uncertainty,
        "uncertainty_scope": (
            "user-supplied timing only; excludes Eulerian-to-Lagrangian parcel "
            "representativeness and reflectivity-to-liquid-fraction mapping"
        ),
        "model_time_offset_s": offset,
        "reflectivity_threshold_dbz": float(reflectivity_threshold_dbz),
        "minimum_height_m": float(minimum_height_m),
        "maximum_height_m": float(maximum_height_m),
        "minimum_drizzle_gates": int(minimum_drizzle_gates),
        "minimum_persistence_s": float(minimum_persistence_s),
        "event_definition": event_definition,
        "detection": detection,
        "interpretation": mapping_note,
    }
    return event, audit

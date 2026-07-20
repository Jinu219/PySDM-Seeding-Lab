from __future__ import annotations

"""Extract auditable drizzle events from EUREC4A ATR42 BASTALIAS L2 data."""

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd


BASTALIAS_OBSERVATION_BUILD_ID = "bastalias-observation-import-v1-20260720"
BASTALIAS_DATASET_DOI = "https://doi.org/10.25326/316"
BASTALIAS_THRESHOLD_VARIABLES = {
    -15: "nb_drizzle_1",
    -17: "nb_drizzle_2",
    -20: "nb_drizzle_3",
}
BASTALIAS_SAMPLING_CONTEXT = "aircraft_horizontal_lidar_radar_spatial_sampling"
BASTALIAS_MAPPING_STATUS = "spatiotemporal_proxy"


def drizzle_variable_for_threshold(cloud_threshold_dbz: int) -> str:
    """Return the BASTALIAS drizzle-count variable for a documented threshold."""
    threshold = int(cloud_threshold_dbz)
    if threshold not in BASTALIAS_THRESHOLD_VARIABLES:
        supported = ", ".join(str(value) for value in BASTALIAS_THRESHOLD_VARIABLES)
        raise ValueError(f"BASTALIAS cloud threshold must be one of: {supported} dBZ.")
    return BASTALIAS_THRESHOLD_VARIABLES[threshold]


def load_bastalias_netcdf(
    path: Path,
    *,
    cloud_threshold_dbz: int,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Load only the 1-D variables needed for onset detection from a local NetCDF."""
    try:
        from netCDF4 import Dataset
    except ImportError as exc:  # pragma: no cover - exercised by installation path
        raise RuntimeError(
            "BASTALIAS NetCDF import requires requirements-observations.txt."
        ) from exc

    source_path = Path(path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"BASTALIAS NetCDF file not found: {source_path}")
    drizzle_variable = drizzle_variable_for_threshold(cloud_threshold_dbz)
    required_variables = ("time", "time_issue_flag", drizzle_variable)
    with Dataset(str(source_path), mode="r") as dataset:
        missing = [name for name in required_variables if name not in dataset.variables]
        if missing:
            raise ValueError(
                "BASTALIAS NetCDF is missing required variables: " + ", ".join(missing)
            )
        time_variable = dataset.variables["time"]
        frame = pd.DataFrame(
            {
                "time_s": np.asarray(
                    np.ma.filled(time_variable[:], np.nan), dtype=float
                ),
                "time_issue_flag": np.asarray(
                    np.ma.filled(dataset.variables["time_issue_flag"][:], np.nan),
                    dtype=float,
                ),
                "drizzle_pixels": np.asarray(
                    np.ma.filled(dataset.variables[drizzle_variable][:], np.nan),
                    dtype=float,
                ),
            }
        )
        metadata = {
            "source_file": source_path.name,
            "time_units": str(getattr(time_variable, "units", "")),
            "dataset_title": str(getattr(dataset, "title", "")),
            "location": str(getattr(dataset, "location", "")),
            "system": str(getattr(dataset, "system", "")),
            "drizzle_variable": drizzle_variable,
            "cloud_threshold_dbz": int(cloud_threshold_dbz),
        }
    return frame, metadata


def detect_persistent_drizzle_onset(
    timeseries: pd.DataFrame,
    *,
    window_start_s: float,
    window_end_s: float,
    minimum_drizzle_pixels: int,
    minimum_persistence_s: float,
) -> Dict[str, Any]:
    """Find the first quality-valid drizzle run meeting a persistence duration."""
    required = {"time_s", "time_issue_flag", "drizzle_pixels"}
    missing = sorted(required - set(timeseries.columns))
    if missing:
        raise ValueError("BASTALIAS timeseries is missing columns: " + ", ".join(missing))
    start = float(window_start_s)
    end = float(window_end_s)
    minimum_pixels = int(minimum_drizzle_pixels)
    persistence = float(minimum_persistence_s)
    if not np.isfinite([start, end, persistence]).all() or end <= start:
        raise ValueError("BASTALIAS event window must have finite start < end.")
    if minimum_pixels < 1:
        raise ValueError("minimum_drizzle_pixels must be at least 1.")
    if persistence < 0:
        raise ValueError("minimum_persistence_s must be non-negative.")

    frame = timeseries.copy()
    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.loc[
        np.isfinite(frame["time_s"])
        & frame["time_s"].between(start, end, inclusive="both")
    ].sort_values("time_s")
    if frame.empty:
        raise ValueError("No BASTALIAS samples fall inside the selected event window.")
    if frame["time_s"].duplicated().any():
        raise ValueError("BASTALIAS time values must be unique inside the event window.")
    positive_intervals = frame["time_s"].diff().dropna()
    positive_intervals = positive_intervals[positive_intervals > 0]
    if positive_intervals.empty:
        raise ValueError("At least two distinct BASTALIAS samples are required.")
    nominal_cadence = float(positive_intervals.median())
    maximum_contiguous_gap = 1.5 * nominal_cadence
    valid_quality = frame["time_issue_flag"].eq(0)
    detected = valid_quality & frame["drizzle_pixels"].ge(minimum_pixels)

    run_start_index: int | None = None
    previous_time: float | None = None
    for position, (_, row) in enumerate(frame.iterrows()):
        current_time = float(row["time_s"])
        contiguous = (
            previous_time is None
            or current_time - previous_time <= maximum_contiguous_gap
        )
        if bool(detected.iloc[position]) and contiguous:
            if run_start_index is None:
                run_start_index = position
            run_start_time = float(frame.iloc[run_start_index]["time_s"])
            if current_time - run_start_time >= persistence:
                return {
                    "onset_time_s": run_start_time,
                    "onset_relative_to_window_s": run_start_time - start,
                    "run_confirmed_through_s": current_time,
                    "persistence_observed_s": current_time - run_start_time,
                    "nominal_cadence_s": nominal_cadence,
                    "n_window_samples": int(len(frame)),
                    "n_quality_valid_samples": int(valid_quality.sum()),
                    "n_detected_samples": int(detected.sum()),
                }
        elif bool(detected.iloc[position]):
            run_start_index = position
        else:
            run_start_index = None
        previous_time = current_time
    raise ValueError(
        "No quality-valid BASTALIAS drizzle run meets the requested pixel and "
        "persistence thresholds."
    )


def build_bastalias_threshold_sensitivity(
    threshold_timeseries: Dict[int, pd.DataFrame],
    *,
    window_start_s: float,
    window_end_s: float,
    minimum_drizzle_pixels: int,
    minimum_persistence_s: float,
) -> pd.DataFrame:
    """Audit onset detection across all documented BASTALIAS boundaries."""
    rows: list[dict[str, Any]] = []
    for threshold in sorted(BASTALIAS_THRESHOLD_VARIABLES, reverse=True):
        if threshold not in threshold_timeseries:
            raise ValueError(f"Missing BASTALIAS timeseries for {threshold} dBZ.")
        try:
            detection = detect_persistent_drizzle_onset(
                threshold_timeseries[threshold],
                window_start_s=window_start_s,
                window_end_s=window_end_s,
                minimum_drizzle_pixels=minimum_drizzle_pixels,
                minimum_persistence_s=minimum_persistence_s,
            )
        except ValueError as exc:
            rows.append(
                {
                    "cloud_threshold_dbz": threshold,
                    "drizzle_variable": drizzle_variable_for_threshold(threshold),
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
                    "cloud_threshold_dbz": threshold,
                    "drizzle_variable": drizzle_variable_for_threshold(threshold),
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


def build_bastalias_observation_event(
    timeseries: pd.DataFrame,
    *,
    event_id: str,
    case: str,
    source_id: str,
    time_units: str,
    window_start_s: float,
    window_end_s: float,
    observed_uncertainty_s: float,
    model_time_offset_s: float,
    cloud_threshold_dbz: int,
    minimum_drizzle_pixels: int,
    minimum_persistence_s: float,
    source_file: str,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Build one contract row and its explicit BASTALIAS mapping audit."""
    event_name = str(event_id).strip()
    case_name = str(case).strip().lower()
    source = str(source_id).strip()
    units = str(time_units).strip()
    if not event_name or not source or not units:
        raise ValueError("event_id, source_id, and time_units must be non-blank.")
    if case_name not in {"control", "seeding"}:
        raise ValueError("case must be control or seeding.")
    uncertainty = float(observed_uncertainty_s)
    offset = float(model_time_offset_s)
    if not np.isfinite([uncertainty, offset]).all() or uncertainty < 0:
        raise ValueError("Observed uncertainty and model offset must be finite.")

    detection = detect_persistent_drizzle_onset(
        timeseries,
        window_start_s=window_start_s,
        window_end_s=window_end_s,
        minimum_drizzle_pixels=minimum_drizzle_pixels,
        minimum_persistence_s=minimum_persistence_s,
    )
    drizzle_variable = drizzle_variable_for_threshold(cloud_threshold_dbz)
    event_definition = (
        f"{drizzle_variable} >= {int(minimum_drizzle_pixels)} pixels for at least "
        f"{float(minimum_persistence_s):g} s with time_issue_flag == 0"
    )
    time_origin = f"{units}; selected_window_start={float(window_start_s):g} s"
    mapping_note = (
        "BASTALIAS samples hydrometeors horizontally from a moving aircraft. The "
        "detected sequence is a spatiotemporal proxy, not temporal evolution of one "
        "parcel and not a direct calibration target for the model transition floor. "
        "The supplied timing uncertainty excludes spatial representativeness and "
        "parcel-mapping uncertainty."
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
                    "EUREC4A ATR42 BASTALIAS L2 radar-lidar hydrometeor classification"
                ),
                "event_definition": event_definition,
                "sampling_context": BASTALIAS_SAMPLING_CONTEXT,
                "mapping_status": BASTALIAS_MAPPING_STATUS,
                "notes": mapping_note,
            }
        ]
    )
    audit = {
        "build_id": BASTALIAS_OBSERVATION_BUILD_ID,
        "source_id": source,
        "source_file": str(source_file),
        "event_id": event_name,
        "case": case_name,
        "evidence_class": "observation",
        "mapping_status": BASTALIAS_MAPPING_STATUS,
        "sampling_context": BASTALIAS_SAMPLING_CONTEXT,
        "time_units": units,
        "window_start_s": float(window_start_s),
        "window_end_s": float(window_end_s),
        "observed_uncertainty_s": uncertainty,
        "uncertainty_scope": (
            "user_supplied timing only; excludes spatial representativeness and "
            "parcel-mapping uncertainty"
        ),
        "model_time_offset_s": offset,
        "cloud_threshold_dbz": int(cloud_threshold_dbz),
        "drizzle_variable": drizzle_variable,
        "minimum_drizzle_pixels": int(minimum_drizzle_pixels),
        "minimum_persistence_s": float(minimum_persistence_s),
        "event_definition": event_definition,
        "detection": detection,
        "interpretation": mapping_note,
    }
    return event, audit

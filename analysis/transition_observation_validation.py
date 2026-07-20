from __future__ import annotations

"""Align observed drizzle-onset events with model transition candidates."""

from typing import Any, Dict

import numpy as np
import pandas as pd


TRANSITION_OBSERVATION_VALIDATION_BUILD_ID = (
    "transition-observation-validation-v2-20260720"
)
OBSERVATION_EVIDENCE_CLASSES = {"observation", "synthetic"}
OBSERVATION_CASES = {"control", "seeding"}
OBSERVATION_MAPPING_STATUSES = {
    "direct_temporal",
    "spatiotemporal_proxy",
    "unresolved",
    "synthetic_workflow",
}
OBSERVATION_REQUIRED_COLUMNS = (
    "event_id",
    "case",
    "observed_transition_onset_s",
    "observed_uncertainty_s",
    "model_time_offset_s",
    "time_origin",
    "source_id",
    "evidence_class",
    "observation_method",
    "event_definition",
    "sampling_context",
    "mapping_status",
)
MODEL_REQUIRED_COLUMNS = (
    "activation_factor",
    "rain_factor",
    "activation_threshold_um",
    "rain_threshold_um",
    "rain_volume_fraction_threshold",
    "control_transition_onset_s",
    "seeding_transition_onset_s",
)
CANDIDATE_COLUMNS = (
    "activation_factor",
    "rain_factor",
    "activation_threshold_um",
    "rain_threshold_um",
    "rain_volume_fraction_threshold",
)


def observation_contract_template() -> pd.DataFrame:
    """Return a clearly synthetic one-event template for CSV authoring."""
    return pd.DataFrame(
        [
            {
                "event_id": "replace_with_event_id",
                "case": "control",
                "observed_transition_onset_s": 300.0,
                "observed_uncertainty_s": 10.0,
                "model_time_offset_s": 0.0,
                "time_origin": "simulation_start",
                "source_id": "replace_with_doi_url_or_dataset_id",
                "evidence_class": "synthetic",
                "observation_method": "synthetic_fixture",
                "event_definition": "replace_with_explicit_detection_rule",
                "sampling_context": "synthetic_workflow_test",
                "mapping_status": "synthetic_workflow",
                "notes": "Template row; replace before observational use.",
            }
        ]
    )


def normalize_observation_events(observations: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the observation-event contract."""
    missing = [
        column for column in OBSERVATION_REQUIRED_COLUMNS if column not in observations
    ]
    if missing:
        raise ValueError(
            "Observation CSV is missing required columns: " + ", ".join(missing)
        )
    if observations.empty:
        raise ValueError("Observation CSV must contain at least one event row.")

    normalized = observations.copy()
    for column in (
        "event_id",
        "case",
        "time_origin",
        "source_id",
        "evidence_class",
        "observation_method",
        "event_definition",
        "sampling_context",
        "mapping_status",
    ):
        if normalized[column].isna().any():
            raise ValueError(f"Observation column {column} cannot contain blanks.")
        normalized[column] = normalized[column].astype(str).str.strip()
        if normalized[column].eq("").any():
            raise ValueError(f"Observation column {column} cannot contain blanks.")
    normalized["case"] = normalized["case"].str.lower()
    normalized["evidence_class"] = normalized["evidence_class"].str.lower()
    normalized["mapping_status"] = normalized["mapping_status"].str.lower()
    invalid_cases = sorted(set(normalized["case"]) - OBSERVATION_CASES)
    if invalid_cases:
        raise ValueError(
            "Observation case must be control or seeding; found: "
            + ", ".join(invalid_cases)
        )
    invalid_classes = sorted(
        set(normalized["evidence_class"]) - OBSERVATION_EVIDENCE_CLASSES
    )
    if invalid_classes:
        raise ValueError(
            "Observation evidence_class must be observation or synthetic; found: "
            + ", ".join(invalid_classes)
        )
    invalid_mapping_statuses = sorted(
        set(normalized["mapping_status"]) - OBSERVATION_MAPPING_STATUSES
    )
    if invalid_mapping_statuses:
        raise ValueError(
            "Observation mapping_status is invalid; found: "
            + ", ".join(invalid_mapping_statuses)
        )
    synthetic_rows = normalized["evidence_class"].eq("synthetic")
    if not normalized.loc[synthetic_rows, "mapping_status"].eq(
        "synthetic_workflow"
    ).all():
        raise ValueError(
            "Synthetic evidence rows must use mapping_status synthetic_workflow."
        )
    observation_rows = normalized["evidence_class"].eq("observation")
    if normalized.loc[observation_rows, "mapping_status"].eq(
        "synthetic_workflow"
    ).any():
        raise ValueError(
            "Observation evidence rows cannot use mapping_status synthetic_workflow."
        )

    numeric_columns = (
        "observed_transition_onset_s",
        "observed_uncertainty_s",
        "model_time_offset_s",
    )
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if not np.isfinite(normalized[column]).all():
            raise ValueError(f"Observation column {column} must contain finite numbers.")
    if (normalized["observed_transition_onset_s"] < 0).any():
        raise ValueError("observed_transition_onset_s must be non-negative.")
    if (normalized["observed_uncertainty_s"] < 0).any():
        raise ValueError("observed_uncertainty_s must be non-negative.")

    normalized["aligned_observed_onset_s"] = (
        normalized["observed_transition_onset_s"]
        + normalized["model_time_offset_s"]
    )
    if (normalized["aligned_observed_onset_s"] < 0).any():
        raise ValueError(
            "observed_transition_onset_s + model_time_offset_s must be non-negative."
        )
    if normalized.duplicated(subset=["event_id", "case"]).any():
        raise ValueError("Each event_id and case pair must be unique.")
    if "notes" not in normalized:
        normalized["notes"] = ""
    else:
        normalized["notes"] = normalized["notes"].fillna("").astype(str)

    return normalized[
        [
            *OBSERVATION_REQUIRED_COLUMNS,
            "aligned_observed_onset_s",
            "notes",
        ]
    ].reset_index(drop=True)


def build_transition_observation_validation(
    transition_robustness: pd.DataFrame,
    observations: pd.DataFrame,
) -> pd.DataFrame:
    """Compare every observation event with every model threshold candidate."""
    missing = [
        column for column in MODEL_REQUIRED_COLUMNS if column not in transition_robustness
    ]
    if missing:
        raise ValueError(
            "Transition robustness table is missing required columns: "
            + ", ".join(missing)
        )
    if transition_robustness.empty:
        raise ValueError("Transition robustness table must contain at least one candidate.")
    candidates = transition_robustness.copy()
    for column in CANDIDATE_COLUMNS:
        candidates[column] = pd.to_numeric(candidates[column], errors="coerce")
        if not np.isfinite(candidates[column]).all():
            raise ValueError(
                f"Transition candidate column {column} must contain finite numbers."
            )
    for column in ("control_transition_onset_s", "seeding_transition_onset_s"):
        candidates[column] = pd.to_numeric(candidates[column], errors="coerce")
        finite_values = candidates.loc[np.isfinite(candidates[column]), column]
        if (finite_values < 0).any():
            raise ValueError(f"Transition onset column {column} must be non-negative.")
    if candidates.duplicated(subset=list(CANDIDATE_COLUMNS)).any():
        raise ValueError("Each transition threshold candidate definition must be unique.")
    events = normalize_observation_events(observations)
    rows: list[dict[str, Any]] = []
    for event in events.to_dict(orient="records"):
        model_onset_column = f"{event['case']}_transition_onset_s"
        for candidate in candidates.to_dict(orient="records"):
            model_onset = candidate.get(model_onset_column)
            resolved = bool(np.isfinite(model_onset))
            onset_error = (
                float(model_onset - event["aligned_observed_onset_s"])
                if resolved
                else None
            )
            absolute_error = abs(onset_error) if onset_error is not None else None
            uncertainty = float(event["observed_uncertainty_s"])
            rows.append(
                {
                    **event,
                    **{column: candidate.get(column) for column in CANDIDATE_COLUMNS},
                    "model_transition_onset_s": (
                        float(model_onset) if resolved else None
                    ),
                    "onset_error_s": onset_error,
                    "absolute_error_s": absolute_error,
                    "within_observed_uncertainty": (
                        bool(absolute_error <= uncertainty)
                        if absolute_error is not None
                        else None
                    ),
                    "normalized_absolute_error": (
                        float(absolute_error / uncertainty)
                        if absolute_error is not None and uncertainty > 0
                        else None
                    ),
                    "comparison_status": (
                        "resolved" if resolved else "model_onset_unresolved"
                    ),
                }
            )
    return pd.DataFrame(rows)


def score_transition_candidates(validation: pd.DataFrame) -> pd.DataFrame:
    """Aggregate onset error by candidate definition without claiming validation."""
    columns = [
        *CANDIDATE_COLUMNS,
        "n_event_case_rows",
        "n_resolved",
        "n_within_observed_uncertainty",
        "within_observed_uncertainty_fraction",
        "mean_absolute_error_s",
        "median_absolute_error_s",
        "root_mean_square_error_s",
        "max_absolute_error_s",
    ]
    if validation.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    for candidate_values, group in validation.groupby(
        list(CANDIDATE_COLUMNS), sort=True, dropna=False
    ):
        errors = pd.to_numeric(group["onset_error_s"], errors="coerce").dropna()
        absolute_errors = errors.abs()
        within = group["within_observed_uncertainty"].eq(True)
        rows.append(
            {
                **dict(zip(CANDIDATE_COLUMNS, candidate_values)),
                "n_event_case_rows": int(len(group)),
                "n_resolved": int(len(errors)),
                "n_within_observed_uncertainty": int(within.sum()),
                "within_observed_uncertainty_fraction": (
                    float(within.sum() / len(errors)) if len(errors) else None
                ),
                "mean_absolute_error_s": (
                    float(absolute_errors.mean()) if len(errors) else None
                ),
                "median_absolute_error_s": (
                    float(absolute_errors.median()) if len(errors) else None
                ),
                "root_mean_square_error_s": (
                    float(np.sqrt(np.mean(np.square(errors))))
                    if len(errors)
                    else None
                ),
                "max_absolute_error_s": (
                    float(absolute_errors.max()) if len(errors) else None
                ),
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["mean_absolute_error_s", *CANDIDATE_COLUMNS],
        na_position="last",
    ).reset_index(drop=True)


def summarize_transition_observation_validation(
    observations: pd.DataFrame,
    validation: pd.DataFrame,
    candidate_scores: pd.DataFrame,
) -> Dict[str, Any]:
    """Summarize workflow state while preserving the observation/synthetic boundary."""
    events = normalize_observation_events(observations)
    evidence_classes = sorted(str(value) for value in events["evidence_class"].unique())
    mapping_statuses = sorted(str(value) for value in events["mapping_status"].unique())
    if evidence_classes == ["synthetic"]:
        status = "synthetic_workflow_only"
    elif evidence_classes == ["observation"]:
        if mapping_statuses == ["direct_temporal"]:
            status = "observational_comparison_available"
        else:
            status = "observational_mapping_review_required"
    else:
        status = "mixed_observation_and_synthetic_inputs"
    resolved = validation["comparison_status"].eq("resolved")
    best_candidate = None
    if not candidate_scores.empty and candidate_scores["mean_absolute_error_s"].notna().any():
        best_candidate = {
            key: (
                float(candidate_scores.iloc[0][key])
                if key in CANDIDATE_COLUMNS
                or key.endswith("_s")
                or key.endswith("_fraction")
                else int(candidate_scores.iloc[0][key])
            )
            for key in candidate_scores.columns
        }
    return {
        "build_id": TRANSITION_OBSERVATION_VALIDATION_BUILD_ID,
        "available": bool(len(validation)),
        "status": status,
        "evidence_classes": evidence_classes,
        "mapping_statuses": mapping_statuses,
        "n_event_case_rows": int(len(events)),
        "n_direct_temporal_event_case_rows": int(
            events["mapping_status"].eq("direct_temporal").sum()
        ),
        "n_unique_events": int(events["event_id"].nunique()),
        "n_candidate_definitions": int(len(candidate_scores)),
        "n_comparisons": int(len(validation)),
        "n_resolved_comparisons": int(resolved.sum()),
        "n_within_observed_uncertainty": int(
            validation["within_observed_uncertainty"].eq(True).sum()
        ),
        "lowest_mae_candidate": best_candidate,
        "interpretation": (
            "Candidate scores compare model and aligned observed onset times. The lowest-MAE "
            "candidate is descriptive and must not be treated as a universal calibrated "
            "threshold. Synthetic rows validate software workflow only; observational rows "
            "still require source, timing-origin, representativeness, and uncertainty review. "
            "Spatiotemporal proxies cannot validate a parcel-model temporal threshold."
        ),
    }

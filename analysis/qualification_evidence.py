from __future__ import annotations

"""Evidence summary for numerical-qualification tolerance decisions."""

from typing import Any, Dict

import numpy as np
import pandas as pd


QUALIFICATION_EVIDENCE_BUILD_ID = "qualification-evidence-v3-common-seeds-20260715"
RAIN_SIGNAL_REFERENCE_METRICS = (
    "comparison.control.max_rain_water_mixing_ratio",
    "comparison.seeding.max_rain_water_mixing_ratio",
)


def _metric_family(metric: object) -> str:
    name = str(metric)
    if name.startswith(("comparison.control.", "comparison.seeding.")):
        return "absolute_state"
    if name.startswith(("comparison.efficiency.", "comparison.delta_")):
        return "seeding_response"
    return "other"


def _family_evidence(rows: pd.DataFrame, tolerance: float) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {}
    if rows.empty:
        return evidence
    for family, group in rows.groupby("metric_family", sort=True):
        differences = group["relative_difference_percent"]
        supported = bool(len(differences) and (differences <= tolerance).all())
        evidence[str(family)] = {
            "status": "supported_for_profile" if supported else "not_supported_for_profile",
            "n_checks": int(len(group)),
            "n_checks_within_tolerance": int((differences <= tolerance).sum()),
            "median_relative_difference_percent": float(differences.median()),
            "p95_relative_difference_percent": float(np.percentile(differences, 95)),
            "max_relative_difference_percent": float(differences.max()),
            "metrics": sorted(str(value) for value in group["metric"].unique()),
        }
    return evidence


def _common_seed_evidence(
    rows: pd.DataFrame,
    tolerance: float,
) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {}
    if rows.empty or "random_seed" not in rows:
        return evidence
    seeds = pd.to_numeric(rows["random_seed"], errors="coerce")
    for seed in sorted(int(value) for value in seeds.dropna().unique()):
        seed_rows = rows.loc[seeds == seed]
        differences = seed_rows["relative_difference_percent"]
        evidence[str(seed)] = {
            "status": (
                "supported_for_profile"
                if bool(len(differences) and (differences <= tolerance).all())
                else "not_supported_for_profile"
            ),
            "n_checks": int(len(seed_rows)),
            "n_checks_within_tolerance": int((differences <= tolerance).sum()),
            "median_relative_difference_percent": float(differences.median()),
            "max_relative_difference_percent": float(differences.max()),
            "metric_family_evidence": _family_evidence(seed_rows, tolerance),
        }
    return evidence


def build_qualification_evidence(
    convergence_table: pd.DataFrame,
    config: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Summarize next-finest checks without treating near-zero ratios as evidence."""
    convergence_cfg = (
        (config or {}).get("diagnostics", {}).get("numerical_convergence", {})
    )
    tolerance = float(convergence_cfg.get("relative_tolerance_percent", 5.0))
    absolute_floor = float(convergence_cfg.get("relative_reference_floor", 1.0e-12))
    qualification = (config or {}).get("qualification", {})
    common_seed_pairing = bool(
        qualification.get("common_random_seed_pairing", False)
    )
    rain_signal_required = bool(qualification.get("rain_signal_required", False))
    rain_signal_floor = float(qualification.get("rain_signal_floor_kg_kg", 1.0e-8))
    base = {
        "build_id": QUALIFICATION_EVIDENCE_BUILD_ID,
        "configured_tolerance_percent": tolerance,
        "relative_reference_floor": absolute_floor,
        "qualification_profile": qualification.get("profile"),
        "common_random_seed_pairing": common_seed_pairing,
        "configured_common_random_seeds": qualification.get(
            "common_random_seeds", []
        ),
        "rain_signal_required": rain_signal_required,
        "rain_signal_floor_kg_kg": rain_signal_floor,
    }
    if convergence_table.empty:
        return {
            **base,
            "available": False,
            "status": "unavailable",
            "interpretation": "No numerical-convergence table was generated.",
        }

    checks = convergence_table[
        pd.to_numeric(convergence_table["resolution_rank"], errors="coerce") == 1
    ].copy()
    if checks.empty:
        return {
            **base,
            "available": False,
            "status": "insufficient_levels",
            "interpretation": "No next-finest versus finest checks were available.",
        }

    checks["reference_value"] = pd.to_numeric(checks["reference_value"], errors="coerce")
    checks["relative_difference_percent"] = pd.to_numeric(
        checks["relative_difference_percent"], errors="coerce"
    )
    finite = checks[
        np.isfinite(checks["reference_value"])
        & np.isfinite(checks["relative_difference_percent"])
    ].copy()
    finite["near_zero_reference"] = finite["reference_value"].abs() <= absolute_floor
    relative_evidence = finite[~finite["near_zero_reference"]].copy()
    relative_evidence["metric_family"] = relative_evidence["metric"].map(
        _metric_family
    )
    differences = relative_evidence["relative_difference_percent"]
    differences_supported = bool(
        len(differences) and (differences <= tolerance).all()
    )
    reference_rows = convergence_table[
        pd.to_numeric(convergence_table["resolution_rank"], errors="coerce") == 0
    ].copy()
    rain_signal_values: Dict[str, float] = {}
    rain_signal_by_seed: Dict[str, Any] = {}
    reference_seeds = (
        pd.to_numeric(reference_rows.get("random_seed"), errors="coerce")
        if "random_seed" in reference_rows
        else pd.Series(dtype=float)
    )
    observed_seeds = sorted(int(value) for value in reference_seeds.dropna().unique())
    configured_seeds = sorted(
        int(value)
        for value in qualification.get("common_random_seeds", [])
    )
    seed_coverage_complete = bool(
        not common_seed_pairing
        or configured_seeds == observed_seeds
    )
    case_seed_coverage = qualification.get("common_seed_case_coverage", {})
    case_seed_coverage_complete = bool(
        not common_seed_pairing or case_seed_coverage.get("complete", False)
    )
    if common_seed_pairing and observed_seeds:
        for seed in observed_seeds:
            seed_rows = reference_rows.loc[reference_seeds == seed]
            seed_values: Dict[str, float] = {}
            for metric in RAIN_SIGNAL_REFERENCE_METRICS:
                values = pd.to_numeric(
                    seed_rows.loc[seed_rows["metric"] == metric, "reference_value"],
                    errors="coerce",
                )
                values = values[np.isfinite(values)]
                if len(values):
                    seed_values[metric] = float(values.abs().max())
            detected = bool(
                len(seed_values) == len(RAIN_SIGNAL_REFERENCE_METRICS)
                and all(value > rain_signal_floor for value in seed_values.values())
            )
            rain_signal_by_seed[str(seed)] = {
                "detected": detected,
                "reference_values_kg_kg": seed_values,
            }
        rain_signal_detected = bool(
            seed_coverage_complete
            and case_seed_coverage_complete
            and len(rain_signal_by_seed) == len(observed_seeds)
            and all(row["detected"] for row in rain_signal_by_seed.values())
        )
        for metric in RAIN_SIGNAL_REFERENCE_METRICS:
            metric_values = [
                row["reference_values_kg_kg"].get(metric)
                for row in rain_signal_by_seed.values()
            ]
            finite_values = [value for value in metric_values if value is not None]
            if finite_values:
                rain_signal_values[metric] = float(min(finite_values))
    else:
        for metric in RAIN_SIGNAL_REFERENCE_METRICS:
            values = pd.to_numeric(
                reference_rows.loc[
                    reference_rows["metric"] == metric, "reference_value"
                ],
                errors="coerce",
            )
            values = values[np.isfinite(values)]
            if len(values):
                rain_signal_values[metric] = float(values.abs().max())
        rain_signal_detected = bool(
            len(rain_signal_values) == len(RAIN_SIGNAL_REFERENCE_METRICS)
            and all(value > rain_signal_floor for value in rain_signal_values.values())
        )
    status = (
        "incomplete_common_seed_coverage"
        if common_seed_pairing
        and not (seed_coverage_complete and case_seed_coverage_complete)
        else "missing_required_rain_signal"
        if rain_signal_required and not rain_signal_detected
        else "supported_for_profile"
        if differences_supported
        else "not_supported_for_profile"
        if len(differences)
        else "indeterminate_near_zero_references"
    )

    axis_maxima = {}
    if len(relative_evidence):
        axis_maxima = {
            str(axis): float(group["relative_difference_percent"].max())
            for axis, group in relative_evidence.groupby("varied_parameter", sort=True)
        }
    family_evidence = _family_evidence(relative_evidence, tolerance)
    seed_evidence = _common_seed_evidence(relative_evidence, tolerance)

    return {
        **base,
        "available": True,
        "status": status,
        "n_next_finest_checks": int(len(checks)),
        "n_finite_checks": int(len(finite)),
        "n_relative_evidence_checks": int(len(relative_evidence)),
        "n_near_zero_reference_checks": int(finite["near_zero_reference"].sum()),
        "n_checks_within_tolerance": int((differences <= tolerance).sum()),
        "max_relative_difference_percent": (
            float(differences.max()) if len(differences) else None
        ),
        "median_relative_difference_percent": (
            float(differences.median()) if len(differences) else None
        ),
        "p95_relative_difference_percent": (
            float(np.percentile(differences, 95)) if len(differences) else None
        ),
        "axis_max_relative_difference_percent": axis_maxima,
        "metric_family_evidence": family_evidence,
        "n_common_random_seeds": int(len(observed_seeds)),
        "n_common_random_seeds_with_relative_evidence": int(len(seed_evidence)),
        "observed_common_random_seeds": observed_seeds,
        "common_seed_coverage_complete": seed_coverage_complete,
        "common_seed_case_coverage": case_seed_coverage,
        "common_seed_case_coverage_complete": case_seed_coverage_complete,
        "common_seed_evidence": seed_evidence,
        "rain_signal_detected": rain_signal_detected,
        "rain_signal_reference_values_kg_kg": rain_signal_values,
        "rain_signal_by_seed": rain_signal_by_seed,
        "interpretation": (
            "Support is limited to this adapter, configuration, metric set, and resolution grid. "
            "Near-zero reference values are excluded from percentage-based support and require "
            "absolute-difference review. Rain profiles additionally require both control and "
            "seeding reference cases to exceed the configured maximum rain-water signal floor. "
            "Absolute-state convergence does not imply convergence of the smaller seeding-minus-"
            "control response. Common-seed profiles require every paired seed's reference "
            "control and seeding run to exceed the rain-signal floor, and every per-seed "
            "next-finest check to satisfy the configured tolerance."
        ),
    }

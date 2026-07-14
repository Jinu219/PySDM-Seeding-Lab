from __future__ import annotations

"""Evidence summary for numerical-qualification tolerance decisions."""

from typing import Any, Dict

import numpy as np
import pandas as pd


QUALIFICATION_EVIDENCE_BUILD_ID = "qualification-evidence-v1-20260714"


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
    base = {
        "build_id": QUALIFICATION_EVIDENCE_BUILD_ID,
        "configured_tolerance_percent": tolerance,
        "relative_reference_floor": absolute_floor,
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
    differences = relative_evidence["relative_difference_percent"]
    supported = bool(len(differences) and (differences <= tolerance).all())
    status = (
        "supported_for_profile"
        if supported
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
        "interpretation": (
            "Support is limited to this adapter, configuration, metric set, and resolution grid. "
            "Near-zero reference values are excluded from percentage-based support and require "
            "absolute-difference review."
        ),
    }

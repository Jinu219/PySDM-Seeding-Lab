from __future__ import annotations

"""OFAT numerical-convergence diagnostics for timestep and super-droplet sweeps."""

import json
from pathlib import Path
from typing import Any, Dict, Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


NUMERICAL_PARAMETERS = {
    "param.environment.timestep": "min",
    "param.seeding.number_superdroplets": "max",
    "param.background_aerosol.number_superdroplets": "max",
}

DEFAULT_CONVERGENCE_METRICS = (
    "comparison.efficiency.effective_radius_final_delta_um",
    "comparison.efficiency.droplet_number_final_delta_cm3",
    "comparison.delta_final_all_activated_water_mixing_ratio",
    "comparison.delta_final_supersaturation_percent",
    "comparison.efficiency.accumulated_rain_enhancement",
    "comparison.efficiency.rain_enhancement_final",
    "comparison.efficiency.cloud_to_rain_conversion_delta",
    "comparison.efficiency.seeding_efficiency_score",
    "comparison.control.final_rain_water_mixing_ratio",
    "comparison.seeding.final_rain_water_mixing_ratio",
    "comparison.control.max_rain_water_mixing_ratio",
    "comparison.seeding.max_rain_water_mixing_ratio",
    "metrics.final_rain_water_mixing_ratio",
    "metrics.max_rain_water_mixing_ratio",
)
COMMON_SEED_PARAMETER_COLUMN = "param.experiment.random_seed"
MEMBER_CONVERGENCE_METRIC_PREFIX = "convergence."


def _condition_groups(
    sweep_df: pd.DataFrame,
    condition_columns: list[str],
) -> Iterable[tuple[str, pd.DataFrame]]:
    if not condition_columns:
        yield "all", sweep_df
        return
    for condition_values, group in sweep_df.groupby(condition_columns, dropna=False, sort=False):
        if not isinstance(condition_values, tuple):
            condition_values = (condition_values,)
        payload = {
            column: value
            for column, value in zip(condition_columns, condition_values)
        }
        yield json.dumps(payload, ensure_ascii=False, default=str), group


def build_numerical_convergence_table(
    sweep_df: pd.DataFrame,
    config: Dict[str, Any] | None,
) -> pd.DataFrame:
    """Compare OFAT resolution levels against the finest available reference case."""
    columns = [
        "condition",
        "metric",
        "varied_parameter",
        "parameter_value",
        "resolution_rank",
        "reference_parameter_value",
        "response_value",
        "reference_value",
        "absolute_difference",
        "relative_difference_percent",
        "tolerance_percent",
        "converged",
        "is_reference",
        "random_seed",
        "case_name",
        "reference_case_name",
    ]
    if sweep_df.empty:
        return pd.DataFrame(columns=columns)

    numerical_columns = [column for column in NUMERICAL_PARAMETERS if column in sweep_df]
    if not numerical_columns:
        return pd.DataFrame(columns=columns)

    cfg = config or {}
    convergence_cfg = cfg.get("diagnostics", {}).get("numerical_convergence", {})
    if not bool(convergence_cfg.get("enabled", True)):
        return pd.DataFrame(columns=columns)
    tolerance = float(convergence_cfg.get("relative_tolerance_percent", 5.0))
    configured_metrics = convergence_cfg.get("metrics", [])
    metric_candidates = configured_metrics or DEFAULT_CONVERGENCE_METRICS
    metrics = [
        metric
        for metric in metric_candidates
        if metric in sweep_df and pd.api.types.is_numeric_dtype(sweep_df[metric])
    ]
    if not metrics:
        return pd.DataFrame(columns=columns)

    all_parameter_columns = [column for column in sweep_df if column.startswith("param.")]
    condition_columns = [column for column in all_parameter_columns if column not in numerical_columns]
    rows: list[dict[str, Any]] = []

    for condition, condition_df in _condition_groups(sweep_df, condition_columns):
        random_seed = None
        if COMMON_SEED_PARAMETER_COLUMN in condition_df:
            seed_values = pd.to_numeric(
                condition_df[COMMON_SEED_PARAMETER_COLUMN], errors="coerce"
            ).dropna()
            if len(seed_values):
                random_seed = int(seed_values.iloc[0])
        targets: Dict[str, float] = {}
        for parameter in numerical_columns:
            values = pd.to_numeric(condition_df[parameter], errors="coerce").dropna()
            if values.empty:
                continue
            targets[parameter] = float(values.min() if NUMERICAL_PARAMETERS[parameter] == "min" else values.max())
        if len(targets) != len(numerical_columns):
            continue

        reference_mask = np.ones(len(condition_df), dtype=bool)
        for parameter, target in targets.items():
            reference_mask &= np.isclose(
                pd.to_numeric(condition_df[parameter], errors="coerce").to_numpy(dtype=float),
                target,
            )
        references = condition_df.loc[reference_mask]
        if references.empty:
            continue
        reference = references.iloc[0]

        for metric in metrics:
            reference_value = float(reference[metric]) if pd.notna(reference[metric]) else float("nan")
            if not np.isfinite(reference_value):
                continue
            for varied_parameter in numerical_columns:
                ofat_mask = np.ones(len(condition_df), dtype=bool)
                for fixed_parameter, target in targets.items():
                    if fixed_parameter == varied_parameter:
                        continue
                    ofat_mask &= np.isclose(
                        pd.to_numeric(condition_df[fixed_parameter], errors="coerce").to_numpy(dtype=float),
                        target,
                    )
                ofat = condition_df.loc[ofat_mask].copy()
                ofat["_parameter_value"] = pd.to_numeric(ofat[varied_parameter], errors="coerce")
                ofat = ofat.dropna(subset=["_parameter_value", metric])
                ascending = NUMERICAL_PARAMETERS[varied_parameter] == "min"
                ofat = ofat.sort_values("_parameter_value", ascending=ascending)
                for resolution_rank, (_, row) in enumerate(ofat.iterrows()):
                    response = float(row[metric])
                    absolute = abs(response - reference_value)
                    relative = (
                        0.0
                        if absolute == 0.0
                        else 100.0 * absolute / max(abs(reference_value), 1.0e-12)
                    )
                    rows.append(
                        {
                            "condition": condition,
                            "metric": metric,
                            "varied_parameter": varied_parameter,
                            "parameter_value": float(row["_parameter_value"]),
                            "resolution_rank": int(resolution_rank),
                            "reference_parameter_value": targets[varied_parameter],
                            "response_value": response,
                            "reference_value": reference_value,
                            "absolute_difference": absolute,
                            "relative_difference_percent": relative,
                            "tolerance_percent": tolerance,
                            "converged": bool(relative <= tolerance),
                            "is_reference": bool(resolution_rank == 0),
                            "random_seed": random_seed,
                            "case_name": str(row.get("case_name", "")),
                            "reference_case_name": str(reference.get("case_name", "")),
                        }
                    )

    return pd.DataFrame(rows, columns=columns)


def build_common_seed_convergence_input(
    sweep_df: pd.DataFrame,
    sweep_root: Path,
) -> pd.DataFrame:
    """Expand ensemble case summaries into one scalar row per common seed.

    Every sweep case must use the same ensemble seed sequence. The resulting
    ``param.experiment.random_seed`` column becomes a convergence condition, so
    only matched seeds are compared across numerical-resolution cases.
    """
    rows: list[dict[str, Any]] = []
    if sweep_df.empty:
        return pd.DataFrame()
    sweep_root = Path(sweep_root)
    parameter_columns = [
        column for column in sweep_df.columns if column.startswith("param.")
    ]
    for _, case in sweep_df.iterrows():
        relative_result_dir = str(case.get("result_dir", ""))
        member_path = sweep_root / relative_result_dir / "member_summary.csv"
        if not relative_result_dir or not member_path.exists():
            continue
        members = pd.read_csv(member_path)
        if "success" in members:
            successful = members["success"].astype(str).str.lower().isin(
                {"true", "1", "1.0"}
            )
            members = members.loc[successful]
        for _, member in members.iterrows():
            seed = pd.to_numeric(
                pd.Series([member.get("random_seed")]), errors="coerce"
            ).iloc[0]
            if not np.isfinite(seed):
                continue
            record: dict[str, Any] = {
                "sweep_case_name": str(case.get("case_name", "")),
                "case_name": f"{case.get('case_name', '')}__seed_{int(seed)}",
                COMMON_SEED_PARAMETER_COLUMN: int(seed),
            }
            for column in parameter_columns:
                record[column] = case.get(column)
            for metric in DEFAULT_CONVERGENCE_METRICS:
                member_column = f"{MEMBER_CONVERGENCE_METRIC_PREFIX}{metric}"
                if member_column in members.columns:
                    record[metric] = member.get(member_column)
            rows.append(record)
    return pd.DataFrame(rows)


def summarize_common_seed_case_coverage(
    paired_seed_metrics: pd.DataFrame,
    config: Dict[str, Any] | None,
    *,
    n_cases: int,
) -> Dict[str, Any]:
    """Report whether every expected seed exists in every resolution case."""
    qualification = (config or {}).get("qualification", {})
    expected_seeds = sorted(
        int(value) for value in qualification.get("common_random_seeds", [])
    )
    expected_pairs = int(n_cases * len(expected_seeds))
    if paired_seed_metrics.empty:
        observed_pairs = 0
        observed_seeds: list[int] = []
    else:
        observed_seeds = sorted(
            int(value)
            for value in pd.to_numeric(
                paired_seed_metrics.get(COMMON_SEED_PARAMETER_COLUMN), errors="coerce"
            ).dropna().unique()
        )
        pair_columns = [
            column
            for column in ("sweep_case_name", COMMON_SEED_PARAMETER_COLUMN)
            if column in paired_seed_metrics
        ]
        observed_pairs = int(
            len(paired_seed_metrics[pair_columns].drop_duplicates())
            if len(pair_columns) == 2
            else len(paired_seed_metrics)
        )
    return {
        "expected_case_seed_pairs": expected_pairs,
        "observed_case_seed_pairs": observed_pairs,
        "observed_common_random_seeds": observed_seeds,
        "complete": bool(
            expected_pairs > 0
            and observed_pairs == expected_pairs
            and observed_seeds == expected_seeds
        ),
    }


def summarize_numerical_convergence(table: pd.DataFrame) -> Dict[str, Any]:
    """Classify the next-finest resolution level for every metric/axis/condition."""
    if table.empty:
        return {"available": False, "status": "unavailable"}
    next_finest = table[table["resolution_rank"] == 1].copy()
    if next_finest.empty:
        return {
            "available": True,
            "status": "insufficient_levels",
            "n_curves": int(table.groupby(["condition", "metric", "varied_parameter"]).ngroups),
        }
    passed = next_finest["converged"].astype(bool)
    return {
        "available": True,
        "status": "pass" if bool(passed.all()) else "warning",
        "n_next_finest_checks": int(len(next_finest)),
        "n_converged": int(passed.sum()),
        "n_not_converged": int((~passed).sum()),
        "max_next_finest_relative_difference_percent": float(
            next_finest["relative_difference_percent"].max()
        ),
        "tolerance_percent": float(next_finest["tolerance_percent"].iloc[0]),
        "rule": (
            "Each numerical axis is varied one at a time while all other numerical axes remain "
            "at the finest available resolution. Status checks resolution_rank=1 against rank=0."
        ),
    }


def convergence_metrics(table: pd.DataFrame) -> list[str]:
    if table.empty or "metric" not in table:
        return []
    return sorted(str(value) for value in table["metric"].dropna().unique())


def plot_numerical_convergence(
    table: pd.DataFrame,
    *,
    metric: str,
):
    """Plot relative error against each numerical-resolution axis."""
    work = table[table["metric"] == metric] if not table.empty else pd.DataFrame()
    parameters = list(work["varied_parameter"].dropna().unique()) if len(work) else []
    n_axes = max(1, len(parameters))
    fig, axes = plt.subplots(1, n_axes, figsize=(4.2 * n_axes, 4.2), squeeze=False)
    if not parameters:
        axes[0, 0].set_title("Numerical convergence unavailable")
        axes[0, 0].text(0.5, 0.5, "Run a timestep/super-droplet sweep.", ha="center", va="center")
        fig.tight_layout()
        return fig

    for axis, parameter in zip(axes[0], parameters):
        parameter_df = work[work["varied_parameter"] == parameter]
        for condition, group in parameter_df.groupby("condition", sort=False):
            group = group.sort_values("parameter_value")
            axis.plot(
                group["parameter_value"],
                group["relative_difference_percent"],
                marker="o",
                label=str(condition)[:42],
            )
        tolerance = float(parameter_df["tolerance_percent"].iloc[0])
        axis.axhline(tolerance, color="#b91c1c", linestyle="--", linewidth=1.0, label="tolerance")
        axis.set_xlabel(parameter.replace("param.", ""))
        axis.set_ylabel("Relative difference from finest [%]")
        axis.set_title(parameter.replace("param.", ""))
        axis.grid(alpha=0.22)
        if parameter_df["condition"].nunique() > 1:
            axis.legend(frameon=False, fontsize=7)
    fig.suptitle(metric, fontsize=11)
    fig.tight_layout()
    return fig

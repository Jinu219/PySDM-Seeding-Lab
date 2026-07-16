from __future__ import annotations

import copy
import itertools
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from simulation.config import set_nested
from simulation.schema import normalize_config


ENSEMBLE_RANKING_FALLBACKS = {
    "comparison.efficiency.seeding_efficiency_score": (
        "ensemble.member_metrics.seeding_efficiency_score.mean"
    ),
    "comparison.efficiency.accumulated_rain_enhancement": (
        "ensemble.member_metrics.accumulated_rain_enhancement.mean"
    ),
    "comparison.efficiency.rain_enhancement_final": (
        "ensemble.member_metrics.rain_enhancement_final.mean"
    ),
    "comparison.efficiency.rain_onset_time_shift_s": (
        "ensemble.member_metrics.rain_onset_time_shift_s.mean"
    ),
    "comparison.efficiency.cloud_to_rain_conversion_delta": (
        "ensemble.member_metrics.cloud_to_rain_conversion_delta.mean"
    ),
}


@dataclass(frozen=True)
class SweepCase:
    """One generated parameter-sweep case."""

    case_index: int
    case_name: str
    parameter_values: Dict[str, Any]
    config: Dict[str, Any]


def _safe_case_token(value: Any) -> str:
    text = str(value)
    text = text.replace(".", "p").replace("-", "m").replace("+", "")
    return "".join(ch if ch.isalnum() or ch in ["_", "p", "m"] else "_" for ch in text)


def _format_case_name(case_index: int, parameter_values: Dict[str, Any]) -> str:
    parts = [f"case_{case_index:03d}"]
    short_keys = [key.split(".")[-1] for key in parameter_values]
    for key, value in parameter_values.items():
        short_key = key.split(".")[-1]
        if short_keys.count(short_key) > 1:
            short_key = key.replace(".", "_")
        parts.append(f"{short_key}_{_safe_case_token(value)}")
    return "__".join(parts)


def active_sweep_parameters(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return sweep parameters with non-empty values."""
    cfg = normalize_config(config)
    sweep = cfg.get("sweep", {})
    params = sweep.get("parameters", [])

    active = []
    for param in params:
        name = param.get("name")
        values = param.get("values", [])
        if name and isinstance(values, list) and len(values) > 0:
            item = {"name": name, "values": values}
            if "reference" in param:
                item["reference"] = param["reference"]
            active.append(item)

    return active


def count_sweep_cases(config: Dict[str, Any]) -> int:
    """Count the number of generated cases."""
    cfg = normalize_config(config)
    params = active_sweep_parameters(config)
    if not params:
        return 0

    design = str(cfg.get("sweep", {}).get("design", "cartesian"))
    if design == "one_factor_at_reference":
        return int(
            1
            + sum(
                max(0, len(dict.fromkeys(param["values"])) - 1)
                for param in params
            )
        )

    count = 1
    for param in params:
        count *= len(param["values"])
    return int(count)


def _reference_value(param: Dict[str, Any]) -> Any:
    values = list(param["values"])
    selector = param.get("reference")
    if selector == "min":
        return min(values)
    if selector == "max":
        return max(values)
    if selector in values:
        return selector
    raise ValueError(
        f"Sweep parameter {param['name']!r} must define reference='min', "
        "reference='max', or an explicit value present in values for "
        "one_factor_at_reference design."
    )


def _one_factor_at_reference_cases(
    params: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return one reference case plus each non-reference value varied alone."""
    reference = {param["name"]: _reference_value(param) for param in params}
    cases = [reference]
    for param in params:
        name = param["name"]
        reference_value = reference[name]
        unique_values = list(dict.fromkeys(param["values"]))
        for value in unique_values:
            if value == reference_value:
                continue
            case = dict(reference)
            case[name] = value
            cases.append(case)
    return cases


def generate_sweep_cases(config: Dict[str, Any]) -> List[SweepCase]:
    """
    Generate all parameter combinations.

    The outer config must have `experiment.mode = parameter_sweep`.
    Each generated case uses `sweep.run_mode`, usually `control_vs_seeding`.
    """
    cfg = normalize_config(config)
    sweep = cfg.get("sweep", {})
    params = active_sweep_parameters(cfg)
    max_runs = int(sweep.get("max_runs", 100))
    run_mode = str(sweep.get("run_mode", "control_vs_seeding"))

    total = count_sweep_cases(cfg)
    if total == 0:
        raise ValueError("No active sweep parameters were configured.")

    if total > max_runs:
        raise ValueError(
            f"Sweep would generate {total} runs, which exceeds sweep.max_runs={max_runs}."
        )

    names = [param["name"] for param in params]
    design = str(sweep.get("design", "cartesian"))
    if design == "cartesian":
        parameter_sets = [
            dict(zip(names, values))
            for values in itertools.product(*[param["values"] for param in params])
        ]
    elif design == "one_factor_at_reference":
        parameter_sets = _one_factor_at_reference_cases(params)
    else:
        raise ValueError(
            f"Unsupported sweep design {design!r}; use 'cartesian' or "
            "'one_factor_at_reference'."
        )

    cases: List[SweepCase] = []

    for idx, parameter_values in enumerate(parameter_sets, start=1):

        case_cfg = copy.deepcopy(cfg)
        case_cfg.setdefault("experiment", {})["mode"] = run_mode

        for name, value in parameter_values.items():
            set_nested(case_cfg, name, value)

        # injection_duration is a sweep convenience rather than a direct
        # adapter field. Resolve it after all parameters are applied so a joint
        # injection_start × injection_duration sweep produces the correct end
        # time for every Cartesian-product case.
        if "seeding.injection_duration" in parameter_values:
            seeding_cfg = case_cfg.setdefault("seeding", {})
            injection_start = int(seeding_cfg.get("injection_start", 0))
            injection_duration = int(parameter_values["seeding.injection_duration"])
            seeding_cfg["injection_end"] = injection_start + injection_duration

        case_name = _format_case_name(idx, parameter_values)

        case_cfg.setdefault("simulation", {})["case_name"] = case_name
        case_cfg.setdefault("experiment", {})["name"] = str(cfg.get("experiment", {}).get("name", "sweep"))

        cases.append(
            SweepCase(
                case_index=idx,
                case_name=case_name,
                parameter_values=parameter_values,
                config=case_cfg,
            )
        )

    return cases


def flatten_nested_dict(payload: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten a nested dictionary using dotted keys."""
    flat: Dict[str, Any] = {}

    for key, value in payload.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(flatten_nested_dict(value, dotted))
        else:
            flat[dotted] = value

    return flat


def get_nested_value(payload: Dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    """Read a dotted-key value from a nested dictionary."""
    current: Any = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def build_sweep_row(
    *,
    case: SweepCase,
    result_dir: str,
    summary: Dict[str, Any],
    ranking_metric: str,
) -> Dict[str, Any]:
    """Build a table row for sweep_summary.csv."""
    flat_summary = flatten_nested_dict(summary)
    ranking_value = flat_summary.get(ranking_metric)
    ranking_source = ranking_metric
    if ranking_value is None and ranking_metric in ENSEMBLE_RANKING_FALLBACKS:
        ranking_source = ENSEMBLE_RANKING_FALLBACKS[ranking_metric]
        ranking_value = flat_summary.get(ranking_source)

    row: Dict[str, Any] = {
        "case_index": case.case_index,
        "case_name": case.case_name,
        "result_dir": result_dir,
        "parameter_values_json": json.dumps(case.parameter_values, ensure_ascii=False),
        "ranking_metric": ranking_metric,
        "ranking_source": ranking_source,
        "ranking_value": ranking_value,
    }

    for key, value in case.parameter_values.items():
        row[f"param.{key}"] = value

    preferred_metrics = [
        "ensemble.metrics.rain_water_mixing_ratio_diff_final_mean",
        "ensemble.metrics.rain_water_mixing_ratio_diff_max_mean",
        "ensemble.metrics.rain_water_mixing_ratio_diff_integral_mean",
        "ensemble.n_success",
        "ensemble.n_failed",
        "ensemble.member_metrics.seeding_efficiency_score.mean",
        "ensemble.member_metrics.seeding_efficiency_score.std",
        "ensemble.member_metrics.accumulated_rain_enhancement.mean",
        "ensemble.member_metrics.rain_enhancement_final.mean",
        "ensemble.member_metrics.rain_onset_time_shift_s.mean",
        "ensemble.member_metrics.cloud_to_rain_conversion_delta.mean",
        "comparison.efficiency.seeding_efficiency_score",
        "comparison.efficiency.accumulated_rain_enhancement",
        "comparison.efficiency.accumulated_rain_enhancement_percent",
        "comparison.efficiency.rain_enhancement_final",
        "comparison.efficiency.rain_enhancement_final_percent",
        "comparison.efficiency.rain_onset_time_shift_s",
        "comparison.efficiency.cloud_to_rain_conversion_delta",
        "comparison.efficiency.effective_radius_final_delta_um",
        "comparison.efficiency.droplet_number_final_delta_cm3",
        "comparison.control.final_rain_water_mixing_ratio",
        "comparison.seeding.final_rain_water_mixing_ratio",
        "comparison.control.max_rain_water_mixing_ratio",
        "comparison.seeding.max_rain_water_mixing_ratio",
        "comparison.delta_final_all_activated_water_mixing_ratio",
        "comparison.delta_final_supersaturation_percent",
        "comparison.research_quality.water_budget.control.max_abs_closed_window_relative_drift_percent",
        "comparison.research_quality.water_budget.seeding.max_abs_closed_window_relative_drift_percent",
        "comparison.research_quality.wet_radius_spectrum.final_number_l1_difference_cm3",
        "comparison.research_quality.wet_radius_spectrum.final_liquid_volume_l1_difference",
        "comparison.research_quality.spectrum_transition.transition_onset_shift_s",
        "comparison.research_quality.spectrum_transition.final_rain_volume_fraction_diff",
        "comparison.research_quality.spectrum_transition.threshold_shift_direction_consistent",
        "metrics.accumulated_rain_water_proxy",
        "metrics.cloud_to_rain_conversion_proxy",
        "metrics.final_rain_water_mixing_ratio",
        "metrics.max_rain_water_mixing_ratio",
    ]

    for metric in preferred_metrics:
        row[metric] = flat_summary.get(metric)

    return row

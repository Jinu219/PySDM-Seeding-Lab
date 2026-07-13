from __future__ import annotations

import copy
import itertools
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from simulation.config import set_nested
from simulation.schema import normalize_config


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
    for key, value in parameter_values.items():
        short_key = key.split(".")[-1]
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
            active.append({"name": name, "values": values})

    return active


def count_sweep_cases(config: Dict[str, Any]) -> int:
    """Count the number of generated cases."""
    params = active_sweep_parameters(config)
    if not params:
        return 0

    count = 1
    for param in params:
        count *= len(param["values"])
    return int(count)


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
    values_product = itertools.product(*[param["values"] for param in params])

    cases: List[SweepCase] = []

    for idx, values in enumerate(values_product, start=1):
        parameter_values = dict(zip(names, values))

        case_cfg = copy.deepcopy(cfg)
        case_cfg.setdefault("experiment", {})["mode"] = run_mode

        for name, value in parameter_values.items():
            set_nested(case_cfg, name, value)

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
    row: Dict[str, Any] = {
        "case_index": case.case_index,
        "case_name": case.case_name,
        "result_dir": result_dir,
        "parameter_values_json": json.dumps(case.parameter_values, ensure_ascii=False),
        "ranking_metric": ranking_metric,
        "ranking_value": flat_summary.get(ranking_metric),
    }

    for key, value in case.parameter_values.items():
        row[f"param.{key}"] = value

    preferred_metrics = [
        "ensemble.metrics.rain_water_mixing_ratio_diff_final_mean",
        "ensemble.metrics.rain_water_mixing_ratio_diff_max_mean",
        "ensemble.metrics.rain_water_mixing_ratio_diff_integral_mean",
        "ensemble.n_success",
        "ensemble.n_failed",
        "comparison.efficiency.seeding_efficiency_score",
        "comparison.efficiency.accumulated_rain_enhancement",
        "comparison.efficiency.accumulated_rain_enhancement_percent",
        "comparison.efficiency.rain_enhancement_final",
        "comparison.efficiency.rain_enhancement_final_percent",
        "comparison.efficiency.rain_onset_time_shift_s",
        "comparison.efficiency.cloud_to_rain_conversion_delta",
        "metrics.accumulated_rain_water_proxy",
        "metrics.cloud_to_rain_conversion_proxy",
        "metrics.final_rain_water_mixing_ratio",
        "metrics.max_rain_water_mixing_ratio",
    ]

    for metric in preferred_metrics:
        row[metric] = flat_summary.get(metric)

    return row

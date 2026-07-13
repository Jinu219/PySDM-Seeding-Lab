from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from operator import mul
from typing import Any, Dict, List


@dataclass(frozen=True)
class RunPlan:
    mode: str
    case_count: int
    ensemble_members: int
    control_factor: int
    total_model_runs: int
    adapter: str
    run_label: str
    description: str


def _sweep_case_count(config: Dict[str, Any]) -> int:
    sweep = config.get("sweep", {})
    params = sweep.get("parameters", []) or []

    if not params:
        return 1

    lengths: List[int] = []
    for param in params:
        values = param.get("values", [])
        lengths.append(max(len(values), 1))

    total = reduce(mul, lengths, 1)
    max_runs = int(sweep.get("max_runs", total))
    return min(total, max_runs)


def estimate_run_plan(config: Dict[str, Any]) -> RunPlan:
    """Estimate how many model runs will be executed."""
    experiment = config.get("experiment", {})
    simulation = config.get("simulation", {})
    sweep = config.get("sweep", {})
    ensemble = config.get("ensemble", {})

    mode = str(experiment.get("mode", "single"))
    adapter = str(simulation.get("adapter", "unknown"))
    run_label = str(experiment.get("scenario_slug", experiment.get("name", "experiment")))

    if mode == "parameter_sweep":
        case_count = _sweep_case_count(config)
        run_mode = str(sweep.get("run_mode", "control_vs_seeding"))
    else:
        case_count = 1
        run_mode = mode

    control_factor = 2 if run_mode == "control_vs_seeding" else 1

    ensemble_enabled = bool(ensemble.get("enabled", False))
    ensemble_members = int(ensemble.get("n_members", 1)) if ensemble_enabled else 1
    ensemble_members = max(ensemble_members, 1)

    total_model_runs = case_count * ensemble_members * control_factor

    if mode == "parameter_sweep":
        description = (
            f"{case_count} sweep cases × {ensemble_members} ensemble members × "
            f"{control_factor} control/seeding runs"
        )
    elif ensemble_enabled:
        description = f"{ensemble_members} ensemble members × {control_factor} control/seeding runs"
    else:
        description = f"{control_factor} model run(s)"

    return RunPlan(
        mode=mode,
        case_count=case_count,
        ensemble_members=ensemble_members,
        control_factor=control_factor,
        total_model_runs=total_model_runs,
        adapter=adapter,
        run_label=run_label,
        description=description,
    )


def run_plan_rows(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a compact table for run plan display."""
    plan = estimate_run_plan(config)
    return [
        {"item": "Scenario / experiment", "value": plan.run_label},
        {"item": "Mode", "value": plan.mode},
        {"item": "Adapter", "value": plan.adapter},
        {"item": "Sweep cases", "value": plan.case_count},
        {"item": "Ensemble members", "value": plan.ensemble_members},
        {"item": "Control/seeding factor", "value": plan.control_factor},
        {"item": "Estimated model runs", "value": plan.total_model_runs},
        {"item": "Plan", "value": plan.description},
    ]

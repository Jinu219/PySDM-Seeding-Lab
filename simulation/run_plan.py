from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from simulation.run_timing import estimate_seconds_per_run, format_seconds
from simulation.sweep import count_sweep_cases

# Above this many total model runs, an unmeasured (no history yet) runtime
# estimate is treated as too uncertain to trust at face value, and the UI
# should warn the user rather than show a falsely precise number.
LARGE_RUN_WARNING_THRESHOLD = 50


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
    estimated_seconds_per_run: float
    estimated_total_seconds: float
    estimated_total_duration: str
    runtime_basis: str
    runtime_is_measured: bool
    runtime_warning: Optional[str] = None


def _sweep_case_count(config: Dict[str, Any]) -> int:
    sweep = config.get("sweep", {})
    total = count_sweep_cases(config)
    if total == 0:
        return 1
    max_runs = int(sweep.get("max_runs", total))
    return min(total, max_runs)


def estimate_run_plan(config: Dict[str, Any], results_dir: Path | str = "results") -> RunPlan:
    """
    Estimate how many model runs will be executed, and how long that is
    likely to take based on locally recorded run-duration history.
    """
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

    timing = estimate_seconds_per_run(Path(results_dir), adapter)
    estimated_total_seconds = timing.seconds_per_run * total_model_runs

    runtime_warning = None
    if total_model_runs >= LARGE_RUN_WARNING_THRESHOLD and not timing.is_measured:
        runtime_warning = (
            f"{total_model_runs}회 실행 예정이지만 '{adapter}' adapter의 실측 이력이 없어 "
            "런타임 추정치의 신뢰도가 낮습니다. 먼저 소규모(예: 2~3 case)로 한 번 실행해 "
            "이력을 쌓은 뒤 전체 sweep/ensemble을 돌리는 것을 권장합니다."
        )
    elif total_model_runs >= LARGE_RUN_WARNING_THRESHOLD and estimated_total_seconds >= 1800:
        runtime_warning = (
            f"예상 소요 시간이 {format_seconds(estimated_total_seconds)}으로 깁니다. "
            "sweep case 수나 ensemble member 수를 줄여 먼저 테스트하는 것을 권장합니다."
        )

    return RunPlan(
        mode=mode,
        case_count=case_count,
        ensemble_members=ensemble_members,
        control_factor=control_factor,
        total_model_runs=total_model_runs,
        adapter=adapter,
        run_label=run_label,
        description=description,
        estimated_seconds_per_run=timing.seconds_per_run,
        estimated_total_seconds=estimated_total_seconds,
        estimated_total_duration=format_seconds(estimated_total_seconds),
        runtime_basis=timing.basis,
        runtime_is_measured=timing.is_measured,
        runtime_warning=runtime_warning,
    )


def run_plan_rows(config: Dict[str, Any], results_dir: Path | str = "results") -> List[Dict[str, Any]]:
    """Return a compact table for run plan display."""
    plan = estimate_run_plan(config, results_dir=results_dir)
    return [
        {"item": "Scenario / experiment", "value": plan.run_label},
        {"item": "Mode", "value": plan.mode},
        {"item": "Adapter", "value": plan.adapter},
        {"item": "Sweep cases", "value": plan.case_count},
        {"item": "Ensemble members", "value": plan.ensemble_members},
        {"item": "Control/seeding factor", "value": plan.control_factor},
        {"item": "Estimated model runs", "value": plan.total_model_runs},
        {"item": "Estimated time per run", "value": format_seconds(plan.estimated_seconds_per_run)},
        {"item": "Estimated total runtime", "value": plan.estimated_total_duration},
        {"item": "Runtime estimate basis", "value": plan.runtime_basis},
        {"item": "Plan", "value": plan.description},
    ]

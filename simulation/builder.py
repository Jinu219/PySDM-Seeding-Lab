from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict

from simulation.schema import normalize_config
from simulation.types import SimulationRunSpec


def build_simulation_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert normalized YAML config into adapter-facing settings.

    This is the translation layer between user-facing configuration and
    simulation-specific implementation details.
    """
    cfg = normalize_config(config)

    return {
        "environment": deepcopy(cfg.get("environment", {})),
        "background_aerosol": deepcopy(cfg.get("background_aerosol", {})),
        "seeding": deepcopy(cfg.get("seeding", {})),
        "dynamics": deepcopy(cfg.get("dynamics", {})),
        "microphysics": deepcopy(cfg.get("microphysics", {})),
        "diagnostics": deepcopy(cfg.get("diagnostics", {})),
        "simulation": deepcopy(cfg.get("simulation", {})),
    }


def build_run_spec(config: Dict[str, Any]) -> SimulationRunSpec:
    """
    Build a standardized run specification.

    The runner should build this object once and pass it into the selected adapter.
    """
    cfg = normalize_config(config)
    experiment = cfg.get("experiment", {})
    simulation = cfg.get("simulation", {})

    experiment_name = str(experiment.get("name", "experiment"))
    experiment_mode = str(experiment.get("mode", "single"))
    adapter_name = str(simulation.get("adapter", "placeholder_warm_cloud"))
    case_name = str(simulation.get("case_name", "base"))

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
    run_id = f"{timestamp}_{experiment_name}_{case_name}"

    metadata = {
        "run_id": run_id,
        "created_at": now.isoformat(timespec="seconds"),
        "experiment_name": experiment_name,
        "experiment_mode": experiment_mode,
        "adapter_name": adapter_name,
        "case_name": case_name,
        "schema_version": cfg.get("schema_version"),
    }

    return SimulationRunSpec(
        run_id=run_id,
        experiment_name=experiment_name,
        experiment_mode=experiment_mode,
        adapter_name=adapter_name,
        case_name=case_name,
        config=cfg,
        settings=build_simulation_settings(cfg),
        metadata=metadata,
    )

from pathlib import Path
from datetime import datetime
from typing import Any, Dict

from simulation.builder import build_simulation_settings
from simulation.pysdm_adapter import run_pysdm_simulation


def run_experiment(config: Dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    experiment = config.get("experiment", {})
    name = experiment.get("name", "experiment")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    settings = build_simulation_settings(config)
    df = run_pysdm_simulation(settings)

    output_path = output_dir / f"{timestamp}_{name}.csv"
    df.to_csv(output_path, index=False)

    return output_path

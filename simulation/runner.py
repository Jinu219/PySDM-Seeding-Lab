from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from simulation.builder import build_run_spec
from simulation.pysdm_adapter import run_adapter


def run_experiment(config: Dict[str, Any], output_dir: Path) -> Path:
    """
    Run a single experiment and save the time-series CSV.

    Current Step 4 behavior:
    - Build normalized SimulationRunSpec
    - Select and run adapter
    - Save time-series result as CSV

    Step 6 will replace this with a richer result directory containing:
    - config.yaml
    - timeseries.csv
    - summary.json
    - metadata.json
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    spec = build_run_spec(config)
    result = run_adapter(spec)

    output_path = output_dir / f"{spec.run_id}.csv"
    result.timeseries.to_csv(output_path, index=False)

    return output_path

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# Allow this file to be executed directly:
#   python scripts/run_config.py --adapter placeholder_warm_cloud
#
# When Python runs a file inside scripts/, sys.path[0] becomes the scripts/
# directory rather than the project root. Therefore the top-level package
# `simulation` is not importable unless the project root is added manually.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from simulation.config import load_config
from simulation.runner import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a PySDM Seeding Lab config from CLI.")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--adapter", default=None, choices=["placeholder_warm_cloud", "pysdm_parcel"])
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path

    cfg = load_config(config_path)

    if args.adapter is not None:
        cfg.setdefault("simulation", {})["adapter"] = args.adapter

    output_dir = Path(args.output_dir or cfg.get("output", {}).get("base_dir", "results"))
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    result_path = run_experiment(cfg, output_dir=output_dir)
    print(result_path)


if __name__ == "__main__":
    main()

from __future__ import annotations

"""Child entry point for one isolated worker-scaling trial."""

import argparse
import json
from pathlib import Path

import yaml

from simulation.runner import run_experiment


def _write_status(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one worker-scaling trial.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--status-file", required=True)
    args = parser.parse_args()

    status_path = Path(args.status_file).resolve()
    try:
        config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
        result_dir = run_experiment(config, Path(args.output_dir).resolve())
        _write_status(
            status_path,
            {
                "success": True,
                "result_dir": str(result_dir.resolve()),
            },
        )
        return 0
    except Exception as exc:
        _write_status(
            status_path,
            {
                "success": False,
                "error": repr(exc),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "result_dir": str(Path(getattr(exc, "result_dir", "")).resolve())
                if getattr(exc, "result_dir", None)
                else "",
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

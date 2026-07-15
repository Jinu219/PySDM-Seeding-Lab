from __future__ import annotations

import argparse
from pathlib import Path

from simulation.server_jobs import run_background_job


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one detached PySDM Seeding Lab experiment job."
    )
    parser.add_argument("--job-dir", type=Path, required=True)
    args = parser.parse_args()
    return run_background_job(args.job_dir)


if __name__ == "__main__":
    raise SystemExit(main())

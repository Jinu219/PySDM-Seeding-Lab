from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from simulation.runner import run_parameter_sweep
from simulation.schema import default_config
from simulation.server_jobs import (
    _atomic_write_json,
    job_table_rows,
    read_background_job,
    submit_background_job,
)
from simulation.validation import validate_config_detailed


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fast_config() -> dict:
    cfg = default_config()
    cfg["experiment"]["name"] = "server_execution_test"
    cfg["simulation"]["adapter"] = "placeholder_warm_cloud"
    cfg["environment"].update({"duration": 20, "timestep": 10})
    cfg["seeding"].update({"injection_start": 10, "injection_end": 20})
    cfg["ensemble"]["enabled"] = False
    return cfg


class ServerExecutionTests(unittest.TestCase):
    def test_atomic_status_write_retries_transient_permission_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            status_path = Path(tmp_dir) / "status.json"
            real_replace = os.replace
            attempts = 0

            def transient_replace(source, destination):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError("transient status file lock")
                real_replace(source, destination)

            with patch(
                "simulation.server_jobs.os.replace",
                side_effect=transient_replace,
            ), patch("simulation.server_jobs.time.sleep") as sleep:
                _atomic_write_json(status_path, {"state": "running"})

            self.assertEqual(attempts, 3)
            self.assertEqual(
                json.loads(status_path.read_text(encoding="utf-8")),
                {"state": "running"},
            )
            self.assertEqual(sleep.call_count, 2)

    def test_worker_count_validation(self):
        cfg = _fast_config()
        cfg["execution"]["max_workers"] = 0

        issues = validate_config_detailed(cfg)

        self.assertTrue(
            any(
                issue.field == "execution.max_workers"
                and issue.severity == "error"
                for issue in issues
            )
        )

    def test_parallel_sweep_preserves_order_and_worker_metadata(self):
        cfg = _fast_config()
        cfg["experiment"]["mode"] = "parameter_sweep"
        cfg["sweep"].update(
            {
                "run_mode": "control_vs_seeding",
                "parameters": [
                    {"name": "seeding.kappa", "values": [0.4, 0.8, 1.2]},
                ],
            }
        )
        cfg["execution"]["max_workers"] = 2

        with tempfile.TemporaryDirectory() as tmp_dir:
            result_dir = run_parameter_sweep(cfg, Path(tmp_dir))
            sweep = pd.read_csv(result_dir / "sweep_summary.csv")
            summary = json.loads(
                (result_dir / "summary.json").read_text(encoding="utf-8")
            )

        self.assertEqual(len(sweep), 3)
        self.assertTrue(sweep["case_success"].all())
        self.assertEqual(summary["execution"]["configured_case_workers"], 2)
        self.assertEqual(summary["execution"]["effective_case_workers"], 2)

    def test_detached_job_survives_submitter_and_persists_result(self):
        cfg = _fast_config()
        cfg["experiment"]["mode"] = "single"

        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg["output"]["base_dir"] = str(Path(tmp_dir) / "results")
            record = submit_background_job(cfg, project_root=PROJECT_ROOT)
            job_dir = Path(record["config_path"]).parent
            deadline = time.monotonic() + 30.0
            try:
                while time.monotonic() < deadline:
                    record = read_background_job(job_dir)
                    if record.get("state") in {"succeeded", "failed"}:
                        break
                    time.sleep(0.1)

                self.assertEqual(record.get("state"), "succeeded", record)
                self.assertTrue(Path(str(record.get("result_dir"))).is_dir())
                self.assertEqual(record.get("completed_model_runs"), 1)
                rows = job_table_rows([record])
                self.assertEqual(rows[0]["progress_percent"], 100.0)
            finally:
                shutil.rmtree(job_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

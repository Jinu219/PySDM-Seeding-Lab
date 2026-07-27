from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from simulation.runner import run_parameter_sweep
from simulation.schema import default_config
from simulation.server_jobs import (
    BackgroundJobControlError,
    _atomic_write_json,
    control_background_job,
    estimate_job_remaining,
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
    def test_server_restart_returns_from_stop_before_starting(self):
        script = (PROJECT_ROOT / "scripts" / "server_web.sh").read_text(
            encoding="utf-8"
        )
        stop_body = script.split("stop_server() {", 1)[1].split(
            "status_server() {", 1
        )[0]

        self.assertNotIn("exit 0", stop_body)
        self.assertIn("return 0", stop_body)
        self.assertIn("restart) stop_server; start_server ;;", script)

    def test_server_launcher_prefers_user_systemd_over_nohup(self):
        script = (PROJECT_ROOT / "scripts" / "server_web.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("systemctl --user start", script)
        self.assertIn("Restart=on-failure", script)
        self.assertIn("run-process) run_server_process ;;", script)
        self.assertLess(
            script.index("if user_systemd_available; then"),
            script.index("falling back to nohup"),
        )

    def test_deployment_persistence_health_check_bypasses_proxy(self):
        script = (PROJECT_ROOT / "scripts" / "deploy_server.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("curl --noproxy \\* --fail", script)
        self.assertIn("ssh '$Target'", script)

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

    def test_read_job_reports_externally_paused_linux_process(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            job_dir = Path(tmp_dir)
            (job_dir / "status.json").write_text(
                json.dumps(
                    {
                        "state": "running",
                        "pid": 1234,
                        "message": "Calculating",
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "simulation.server_jobs._linux_process_state",
                return_value="T",
            ):
                record = read_background_job(job_dir)

        self.assertEqual(record["state"], "paused")
        self.assertIn("paused", record["message"])

    def test_control_job_pauses_isolated_process_group(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            job_dir = Path(tmp_dir)
            (job_dir / "status.json").write_text(
                json.dumps({"state": "running", "pid": 1234}),
                encoding="utf-8",
            )
            with patch(
                "simulation.server_jobs._job_process_group",
                return_value=(1234, 1234),
            ), patch(
                "simulation.server_jobs._signal_process_group"
            ) as signal_group:
                record = control_background_job(job_dir, "pause")

        signal_group.assert_called_once()
        self.assertEqual(record["state"], "paused")
        self.assertEqual(record["stage"], "paused")

    def test_control_job_rejects_resume_for_running_job(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            job_dir = Path(tmp_dir)
            (job_dir / "status.json").write_text(
                json.dumps({"state": "running", "pid": 1234}),
                encoding="utf-8",
            )
            with patch(
                "simulation.server_jobs._job_process_group",
                return_value=(1234, 1234),
            ):
                with self.assertRaises(BackgroundJobControlError):
                    control_background_job(job_dir, "resume")

    def test_cancel_continues_paused_group_after_termination_signal(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            job_dir = Path(tmp_dir)
            (job_dir / "status.json").write_text(
                json.dumps({"state": "paused", "pid": 1234}),
                encoding="utf-8",
            )
            with patch(
                "simulation.server_jobs._job_process_group",
                return_value=(1234, 1234),
            ), patch(
                "simulation.server_jobs._signal_process_group"
            ) as signal_group:
                record = control_background_job(job_dir, "cancel")

        self.assertEqual(signal_group.call_count, 2)
        self.assertEqual(record["state"], "cancelled")

    def test_job_eta_uses_recent_aggregate_throughput(self):
        estimate = estimate_job_remaining(
            {
                "state": "running",
                "total_model_runs": 100,
                "completed_model_runs": 50,
                "started_at": "2026-07-27T12:00:00",
                "progress_samples": [
                    {"at": "2026-07-27T12:10:00", "completed": 20},
                    {"at": "2026-07-27T12:15:00", "completed": 50},
                ],
            },
            now=datetime.fromisoformat("2026-07-27T12:15:00"),
        )

        self.assertEqual(estimate["seconds"], 500.0)
        self.assertEqual(estimate["label"], "\u2248 8m 20s")
        self.assertIn("recent throughput", estimate["basis"])

    def test_job_eta_excludes_recorded_pause_interval(self):
        estimate = estimate_job_remaining(
            {
                "state": "running",
                "total_model_runs": 100,
                "completed_model_runs": 50,
                "started_at": "2026-07-27T12:00:00",
                "paused_at": "2026-07-27T12:04:00",
                "resumed_at": "2026-07-27T12:14:00",
            },
            now=datetime.fromisoformat("2026-07-27T12:20:00"),
        )

        self.assertEqual(estimate["seconds"], 600.0)
        self.assertEqual(estimate["label"], "≈ 10m 0s")

    def test_job_eta_reports_paused_state_without_countdown(self):
        estimate = estimate_job_remaining(
            {
                "state": "paused",
                "total_model_runs": 100,
                "completed_model_runs": 50,
            }
        )

        self.assertEqual(estimate["label"], "Paused")
        self.assertIsNone(estimate["seconds"])

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

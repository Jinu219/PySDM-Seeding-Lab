from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.run_worker_scaling_benchmark import run_trial
from simulation.schema import default_config
from simulation.worker_scaling import (
    GIB,
    build_benchmark_plan,
    load_benchmark_config,
    matched_workload_fingerprint,
    prepare_trial_config,
    render_markdown,
    summarize_trials,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fast_sweep_config() -> dict:
    cfg = default_config()
    cfg["experiment"].update(
        {
            "name": "worker_scaling_test",
            "mode": "parameter_sweep",
        }
    )
    cfg["simulation"]["adapter"] = "placeholder_warm_cloud"
    cfg["environment"].update({"duration": 20, "timestep": 10})
    cfg["seeding"].update({"injection_start": 10, "injection_end": 20})
    cfg["ensemble"]["enabled"] = False
    cfg["sweep"].update(
        {
            "run_mode": "control_vs_seeding",
            "max_runs": 2,
            "parameters": [
                {"name": "seeding.kappa", "values": [0.4, 0.8]},
            ],
        }
    )
    return cfg


class WorkerScalingTests(unittest.TestCase):
    def test_scenario_wrapper_and_plain_config_load_identically(self):
        cfg = _fast_sweep_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            plain = root / "plain.yaml"
            scenario = root / "scenario.yaml"
            plain.write_text(
                yaml.safe_dump(cfg, sort_keys=False),
                encoding="utf-8",
            )
            scenario.write_text(
                yaml.safe_dump(
                    {
                        "metadata": {"name": "test", "slug": "test"},
                        "config": cfg,
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            plain_cfg = load_benchmark_config(plain)
            scenario_cfg = load_benchmark_config(scenario)

        self.assertEqual(plain_cfg, scenario_cfg)

    def test_plan_caps_effective_workers_and_checks_memory(self):
        cfg = _fast_sweep_config()
        plan = build_benchmark_plan(
            cfg,
            [1, 4, 8],
            source_path=Path("scenario.yaml"),
            project_root=PROJECT_ROOT,
            estimated_gib_per_worker=1.0,
            reserve_gib=1.0,
            available_memory_bytes=4 * GIB,
        )

        self.assertEqual([row["effective_workers"] for row in plan["trials"]], [1, 2, 2])
        self.assertEqual(
            [row["memory_preflight_passed"] for row in plan["trials"]],
            [True, True, True],
        )
        self.assertEqual(plan["total_model_runs"], 4)

    def test_workload_fingerprint_ignores_only_worker_count(self):
        cfg = _fast_sweep_config()
        serial = prepare_trial_config(cfg, 1)
        parallel = prepare_trial_config(cfg, 8)
        changed = prepare_trial_config(cfg, 8)
        changed["environment"]["duration"] += 10

        self.assertEqual(
            matched_workload_fingerprint(serial),
            matched_workload_fingerprint(parallel),
        )
        self.assertNotEqual(
            matched_workload_fingerprint(serial),
            matched_workload_fingerprint(changed),
        )

    def test_summary_computes_speedup_and_bounded_candidate(self):
        cfg = _fast_sweep_config()
        plan = build_benchmark_plan(
            cfg,
            [1, 2],
            source_path=Path("scenario.yaml"),
            project_root=PROJECT_ROOT,
            available_memory_bytes=16 * GIB,
        )
        evidence = summarize_trials(
            plan,
            {
                "hostname": "test-host",
                "git_commit": "abc",
                "git_dirty": False,
                "python_version": "3.test",
            },
            [
                {
                    "configured_workers": 1,
                    "effective_workers": 1,
                    "matched_workload_sha256": plan["matched_workload_sha256"],
                    "machine_hostname": "test-host",
                    "git_commit": "abc",
                    "python_version": "3.test",
                    "qualification_status": "success",
                    "elapsed_seconds": 100.0,
                    "process_tree_peak_rss_bytes": 2 * GIB,
                    "failed_cases": 0,
                },
                {
                    "configured_workers": 2,
                    "effective_workers": 2,
                    "matched_workload_sha256": plan["matched_workload_sha256"],
                    "machine_hostname": "test-host",
                    "git_commit": "abc",
                    "python_version": "3.test",
                    "qualification_status": "success",
                    "elapsed_seconds": 60.0,
                    "process_tree_peak_rss_bytes": 3 * GIB,
                    "failed_cases": 0,
                },
            ],
        )

        self.assertAlmostEqual(evidence["trials"][1]["speedup_vs_serial"], 5 / 3)
        self.assertAlmostEqual(
            evidence["trials"][1]["parallel_efficiency_vs_serial"],
            5 / 6,
        )
        self.assertEqual(
            evidence["qualification"]["measured_candidate_workers"],
            2,
        )
        self.assertIn("this machine and workload only", render_markdown(evidence))

    def test_isolated_placeholder_trial_writes_success_evidence(self):
        cfg = _fast_sweep_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            trial_dir = Path(tmp_dir) / "workers_1"
            evidence = run_trial(
                cfg,
                configured_workers=1,
                effective_workers=1,
                trial_dir=trial_dir,
                sample_interval_seconds=0.02,
                matched_workload_sha256="test-workload",
                environment={
                    "hostname": "test-host",
                    "git_commit": "abc",
                    "python_version": "3.test",
                },
            )
            stored = json.loads(
                (trial_dir / "trial.json").read_text(encoding="utf-8")
            )

        self.assertEqual(evidence["qualification_status"], "success")
        self.assertEqual(stored["successful_cases"], 2)
        self.assertEqual(stored["failed_cases"], 0)
        self.assertEqual(stored["matched_workload_sha256"], "test-workload")
        self.assertGreater(stored["rss_samples"], 0)
        self.assertGreater(stored["process_tree_peak_rss_bytes"], 0)


if __name__ == "__main__":
    unittest.main()

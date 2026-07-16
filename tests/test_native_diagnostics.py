from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from analysis.case_diagnostic_comparison import (
    build_threshold_robustness_comparison,
    build_water_budget_comparison,
    build_wet_radius_spectrum_comparison,
)
from analysis.growth_pathway_diagnostics import diagnostic_provenance_rows
from analysis.ensemble_statistics import (
    benchmark_ensemble_statistics_from_paths,
    build_ensemble_statistics,
    build_ensemble_statistics_from_paths,
)
from analysis.resource_monitor import (
    ProcessRSSCheckpointProfiler,
    compare_ensemble_execution_backends,
    compare_ensemble_memory_benchmarks,
)
from analysis.numerical_convergence import (
    MEMBER_CONVERGENCE_METRIC_PREFIX,
    build_common_seed_convergence_input,
    build_numerical_convergence_table,
    summarize_common_seed_case_coverage,
    summarize_numerical_convergence,
)
from analysis.qualification_evidence import build_qualification_evidence
from analysis.result_manifest import inspect_result_compatibility
from analysis.reporting import REPORT_BUILD_ID, build_pdf_report
from analysis.dashboard import sweep_execution_status_table
from analysis.spectrum_transition import (
    build_spectrum_transition_table,
    build_transition_onset_robustness,
    summarize_spectrum_transition,
)
from analysis.water_budget import build_water_budget_table, summarize_water_budget
from simulation.builder import build_run_spec
from simulation.experiment_manager import apply_scenario_identity, read_scenario
from simulation.pysdm_parcel_adapter import (
    _output_to_dataframe,
    run_pysdm_parcel_simulation,
)
from simulation.path_policy import (
    ResultPathBudgetError,
    SWEEP_RESULT_DESCENDANT_RESERVE,
    WINDOWS_PORTABLE_PATH_LIMIT,
    filesystem_token,
    path_character_count,
    resolve_result_directory,
)
from simulation.runner import (
    ExperimentExecutionError,
    run_ensemble_experiment,
    run_experiment,
    run_parameter_sweep,
)
from simulation.run_plan import estimate_run_plan
from simulation.schema import default_config
from simulation.sweep import generate_sweep_cases
from simulation.validation import validate_config_detailed
from simulation.wet_radius_spectrum import (
    build_spectrum_bin_edges,
    build_threshold_robustness_table,
    build_wet_radius_spectrum_table,
    resolve_spectrum_checkpoint_times,
)
from scripts.run_numerical_qualification import (
    build_qualification_config,
    qualification_plan,
)
from scripts.run_ensemble_benchmark import build_benchmark_config


PYSDM_AVAILABLE = (
    importlib.util.find_spec("PySDM") is not None
    and importlib.util.find_spec("PySDM_examples") is not None
)


def _small_native_config() -> dict:
    cfg = default_config()
    cfg["experiment"]["mode"] = "single"
    cfg["simulation"]["adapter"] = "pysdm_parcel"
    cfg["environment"]["duration"] = 30
    cfg["environment"]["timestep"] = 15
    cfg["background_aerosol"]["number_superdroplets"] = 20
    cfg["seeding"]["number_superdroplets"] = 5
    cfg["seeding"]["injection_start"] = 15
    cfg["seeding"]["injection_end"] = 30
    return cfg


class NativeDiagnosticMappingTests(unittest.TestCase):
    def test_marine_showcase_scenario_is_runnable(self):
        scenario_path = (
            Path(__file__).resolve().parents[1]
            / "experiments"
            / "scenarios"
            / "marine_showcase_ofat_v1.yaml"
        )
        payload = read_scenario(scenario_path)
        cfg = apply_scenario_identity(payload["config"], scenario_path)
        cases = generate_sweep_cases(cfg)
        plan = estimate_run_plan(cfg)
        errors = [
            issue
            for issue in validate_config_detailed(cfg)
            if issue.severity == "error"
        ]
        case_errors = [
            issue
            for case in cases
            for issue in validate_config_detailed(case.config)
            if issue.severity == "error"
        ]

        self.assertFalse(errors)
        self.assertFalse(case_errors)
        self.assertEqual(len(cases), 10)
        self.assertEqual(plan.total_model_runs, 60)
        self.assertEqual(cfg["simulation"]["adapter"], "pysdm_parcel")
        self.assertEqual(cfg["ensemble"]["execution_backend"], "in_process")
        self.assertEqual(
            sorted(
                {
                    (
                        case.config["seeding"]["injection_start"],
                        case.config["seeding"]["injection_end"],
                    )
                    for case in cases
                }
            ),
            [(600, 900), (900, 1200), (1200, 1500)],
        )

    def test_run_plan_uses_ofat_case_count(self):
        cfg = default_config()
        cfg["experiment"]["mode"] = "parameter_sweep"
        cfg["sweep"].update(
            {
                "design": "one_factor_at_reference",
                "parameters": [
                    {
                        "name": "seeding.kappa",
                        "values": [0.4, 0.8, 1.2],
                        "reference": 0.8,
                    },
                    {
                        "name": "microphysics.collision",
                        "values": [False, True],
                        "reference": True,
                    },
                ],
            }
        )
        cfg["ensemble"].update({"enabled": True, "n_members": 3})

        plan = estimate_run_plan(cfg)

        self.assertEqual(plan.case_count, 4)
        self.assertEqual(plan.total_model_runs, 24)

    def test_nested_sweep_ensemble_uses_compact_paths(self):
        cfg = default_config()
        cfg["experiment"]["name"] = "long experiment name " * 5
        cfg["experiment"]["mode"] = "parameter_sweep"
        cfg["simulation"]["adapter"] = "placeholder_warm_cloud"
        cfg["environment"]["duration"] = 20
        cfg["environment"]["timestep"] = 10
        cfg["seeding"]["injection_start"] = 10
        cfg["seeding"]["injection_end"] = 20
        cfg["sweep"]["run_mode"] = "control_vs_seeding"
        cfg["sweep"]["parameters"] = [
            {"name": "seeding.dry_radius", "values": [1.0e-6]},
        ]
        cfg.setdefault("ensemble", {})["enabled"] = True
        cfg["ensemble"]["n_members"] = 2

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / ("deep_parent_" + "x" * 45)
            result_dir = run_experiment(cfg, output_dir)
            sweep = pd.read_csv(result_dir / "sweep_summary.csv")
            compact_case = result_dir / "cases" / "case_001"
            member_comparison = (
                compact_case / "members" / "member_001" / "comparison"
            )
            comparison_exists = (member_comparison / "comparison.csv").exists()
            all_path_lengths = [path_character_count(path) for path in result_dir.rglob("*")]

        self.assertEqual(sweep["case_status"].tolist(), ["success"])
        self.assertEqual(sweep["ensemble.n_success"].tolist(), [2])
        self.assertTrue(sweep["ranking_value"].notna().all())
        self.assertEqual(
            sweep["ranking_source"].iloc[0],
            "ensemble.member_metrics.seeding_efficiency_score.mean",
        )
        self.assertTrue(comparison_exists)
        self.assertLessEqual(max(all_path_lengths), WINDOWS_PORTABLE_PATH_LIMIT)
        self.assertLessEqual(len(filesystem_token("x" * 200)), 48)
        self.assertEqual(filesystem_token("CON.txt"), "_CON.txt")

    def test_result_path_budget_hashes_long_name_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / ("portable_parent_" + "x" * 35)
            result_dir = resolve_result_directory(
                output_dir,
                "very_long_scenario_name_" * 20,
                descendant_reserve=SWEEP_RESULT_DESCENDANT_RESERVE,
            )

        self.assertRegex(result_dir.name, r"_[0-9a-f]{8}$")
        self.assertLessEqual(
            path_character_count(result_dir) + SWEEP_RESULT_DESCENDANT_RESERVE,
            WINDOWS_PORTABLE_PATH_LIMIT,
        )

    def test_result_path_budget_rejects_output_root_that_is_already_too_deep(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / ("x" * 70) / ("y" * 70)
            with self.assertRaisesRegex(
                ResultPathBudgetError,
                "Choose a shorter output root",
            ):
                resolve_result_directory(
                    output_dir,
                    "scenario",
                    descendant_reserve=SWEEP_RESULT_DESCENDANT_RESERVE,
                )

    def test_all_failed_ensemble_writes_health_then_raises(self):
        cfg = default_config()
        cfg["experiment"]["mode"] = "control_vs_seeding"
        cfg.setdefault("ensemble", {})["enabled"] = True
        cfg["ensemble"]["n_members"] = 2

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "simulation.runner.run_control_vs_seeding",
                side_effect=FileNotFoundError(206, "path too long"),
            ):
                with self.assertRaises(ExperimentExecutionError) as raised:
                    run_ensemble_experiment(cfg, Path(tmp_dir))
            result_dir = raised.exception.result_dir
            summary = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
            members = pd.read_csv(result_dir / "member_summary.csv")

        self.assertEqual(summary["execution"]["status"], "failed")
        self.assertEqual(summary["execution"]["failed_members"], 2)
        self.assertEqual(set(members["error_type"]), {"FileNotFoundError"})
        self.assertTrue((members["success"] == False).all())  # noqa: E712

    def test_failed_sweep_case_is_preserved_and_propagated(self):
        cfg = default_config()
        cfg["experiment"]["mode"] = "parameter_sweep"
        cfg["sweep"]["parameters"] = [
            {"name": "seeding.kappa", "values": [0.8]},
        ]

        def fail_case(config, output_dir, progress_callback=None, *, result_dir_name=None):
            result_dir = Path(output_dir) / str(result_dir_name)
            result_dir.mkdir(parents=True, exist_ok=True)
            raise ExperimentExecutionError("synthetic nested failure", result_dir=result_dir)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("simulation.runner.run_experiment", side_effect=fail_case):
                with self.assertRaises(ExperimentExecutionError) as raised:
                    run_parameter_sweep(cfg, Path(tmp_dir))
            result_dir = raised.exception.result_dir
            sweep = pd.read_csv(result_dir / "sweep_summary.csv")
            summary = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(sweep["case_status"].tolist(), ["failed"])
        self.assertIn("synthetic nested failure", sweep["case_error"].iloc[0])
        self.assertEqual(summary["execution"]["status"], "failed")
        self.assertEqual(summary["execution"]["failed_cases"], 1)

    def test_sweep_health_infers_legacy_all_member_failure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            case_dir = root / "cases" / "legacy_case"
            case_dir.mkdir(parents=True)
            (case_dir / "ensemble_statistics.csv").write_text("\n", encoding="utf-8")
            pd.DataFrame(
                [
                    {
                        "success": False,
                        "error": "FileNotFoundError: path too long",
                    }
                ]
            ).to_csv(case_dir / "member_summary.csv", index=False)
            sweep = pd.DataFrame(
                [
                    {
                        "case_index": 1,
                        "case_name": "legacy_case",
                        "result_dir": "cases/legacy_case",
                        "ensemble.n_success": 0,
                        "ensemble.n_failed": 1,
                    }
                ]
            )
            health = sweep_execution_status_table(root, sweep)

        self.assertEqual(health["execution_status"].tolist(), ["failed"])
        self.assertEqual(health["member_failed"].tolist(), [1])
        self.assertIn("path too long", health["error"].iloc[0])

    def test_native_product_mapping_has_no_growth_pathway_proxy(self):
        cfg = _small_native_config()
        spec = build_run_spec(cfg)
        product_names = (
            "temperature_K",
            "pressure_Pa",
            "water_vapour_mixing_ratio",
            "relative_humidity",
            "unactivated_water_mixing_ratio",
            "cloud_water_mixing_ratio",
            "rain_water_mixing_ratio",
            "total_liquid_water_mixing_ratio",
            "cloud_droplet_concentration",
            "rain_droplet_concentration",
            "effective_radius_cloud_um",
            "effective_radius_rain_um",
            "effective_radius_all_um",
            "superdroplet_count",
        )
        products = {"time": np.array([0.0, 15.0, 30.0])}
        for index, name in enumerate(product_names, start=1):
            products[name] = np.full(3, index * 0.01)

        df = _output_to_dataframe({"products": products}, spec)
        provenance = diagnostic_provenance_rows(list(df.columns), cfg)

        self.assertIn("relative_humidity_percent", df.columns)
        self.assertIn("supersaturation_percent", df.columns)
        self.assertIn("droplet_number_concentration_cm3", df.columns)
        self.assertIn("effective_radius_um", df.columns)
        self.assertFalse(any(row["provenance"] == "proxy" for row in provenance))

    def test_invalid_diagnostic_threshold_order_is_blocking(self):
        cfg = default_config()
        cfg["diagnostics"]["activation_radius_threshold"] = 30.0e-6
        cfg["diagnostics"]["rain_radius_threshold"] = 25.0e-6
        issues = validate_config_detailed(cfg)
        fields = {
            issue.field
            for issue in issues
            if issue.severity == "error"
        }
        self.assertIn("diagnostics.rain_radius_threshold", fields)

    def test_spectrum_edges_checkpoints_and_threshold_repartition(self):
        cfg = _small_native_config()
        edges = build_spectrum_bin_edges(cfg)
        checkpoints = resolve_spectrum_checkpoint_times(cfg)

        self.assertEqual(checkpoints, [0.0, 15.0, 30.0])
        for threshold in (0.5e-6, 25.0e-6):
            for factor in (0.8, 1.0, 1.2):
                self.assertTrue(np.any(np.isclose(edges, threshold * factor)))

        n_bins = len(edges) - 1
        spectra = {
            "time_s": np.asarray(checkpoints),
            "number_concentration_m3": np.ones((len(checkpoints), n_bins)) * 1.0e6,
            "volume_fraction_per_dlnr": np.ones((len(checkpoints), n_bins)) * 1.0e-9,
        }
        spectrum_df = build_wet_radius_spectrum_table(spectra, edges, cfg)
        robustness_df = build_threshold_robustness_table(spectrum_df, cfg)

        self.assertEqual(len(spectrum_df), len(checkpoints) * n_bins)
        self.assertEqual(len(robustness_df), len(checkpoints) * 9)
        partitioned = (
            robustness_df["unactivated_number_cm3"]
            + robustness_df["cloud_number_cm3"]
            + robustness_df["rain_number_cm3"]
        )
        self.assertTrue(np.allclose(partitioned, float(n_bins)))

    def test_invalid_spectrum_configuration_is_blocking(self):
        cfg = default_config()
        cfg["diagnostics"]["wet_radius_spectrum"]["threshold_factors"] = [0.8, 1.2]
        cfg["diagnostics"]["wet_radius_spectrum"]["min_radius"] = 1.0e-6
        issues = validate_config_detailed(cfg)
        fields = {
            issue.field
            for issue in issues
            if issue.severity == "error"
        }
        self.assertIn("diagnostics.wet_radius_spectrum.threshold_factors", fields)

    def test_water_budget_excludes_injection_source_window(self):
        cfg = _small_native_config()
        cfg["seeding"]["injection_start"] = 10
        cfg["seeding"]["injection_end"] = 20
        df = pd.DataFrame(
            {
                "time_s": [0.0, 10.0, 20.0, 30.0, 40.0],
                "water_vapour_mixing_ratio": [0.02, 0.02, 0.02, 0.02, 0.02],
                "unactivated_water_mixing_ratio": [0.001, 0.0015, 0.002, 0.002, 0.002],
                "cloud_water_mixing_ratio": [0.0, 0.0, 0.0, 0.0, 0.0],
                "rain_water_mixing_ratio": [0.0, 0.0, 0.0, 0.0, 0.0],
                "total_liquid_water_mixing_ratio": [0.001, 0.0015, 0.002, 0.002, 0.002],
            }
        )
        budget = build_water_budget_table(df, cfg)
        summary = summarize_water_budget(budget, cfg)

        source_rows = budget[budget["phase"] == "injection_source_open"]
        self.assertTrue(source_rows["closed_window_drift"].isna().all())
        self.assertEqual(summary["status"], "pass")
        self.assertEqual(summary["max_abs_liquid_partition_residual"], 0.0)
        self.assertAlmostEqual(summary["source_window_total_water_change"], 0.001)

    def test_streaming_ensemble_statistics_match_in_memory_result(self):
        members = [
            pd.DataFrame(
                {
                    "time_s": [0.0, 10.0, 20.0],
                    "rain": [0.0, 1.0 + offset, 2.0 + offset],
                    "cloud": [3.0 + offset, 2.0, 1.0],
                }
            )
            for offset in (0.0, 0.5, 1.0)
        ]
        expected = build_ensemble_statistics(members)

        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = []
            for index, member in enumerate(members):
                path = Path(tmp_dir) / f"member_{index}.csv"
                member.to_csv(path, index=False)
                paths.append(path)
            actual = build_ensemble_statistics_from_paths(paths)
            benchmarked, benchmark = benchmark_ensemble_statistics_from_paths(paths)

        pd.testing.assert_frame_equal(actual, expected)
        pd.testing.assert_frame_equal(benchmarked, expected)
        self.assertEqual(benchmark["n_member_files"], 3)
        self.assertEqual(benchmark["aggregated_variables"], 2)
        self.assertEqual(benchmark["csv_read_passes_per_member"], 3)
        self.assertGreater(benchmark["total_input_bytes"], 0)
        self.assertGreaterEqual(
            benchmark["estimated_csv_bytes_scanned"],
            benchmark["total_input_bytes"],
        )
        self.assertGreaterEqual(benchmark["column_streaming_seconds"], 0.0)
        self.assertGreaterEqual(benchmark["python_peak_traced_bytes"], 0)
        process_rss = benchmark["process_rss"]
        self.assertTrue(process_rss["available"])
        self.assertGreaterEqual(process_rss["n_samples"], 2)
        self.assertGreaterEqual(process_rss["peak_rss_bytes"], process_rss["rss_before_bytes"])

    def test_placeholder_ensemble_uses_streaming_aggregation(self):
        cfg = default_config()
        cfg["simulation"]["adapter"] = "placeholder_warm_cloud"
        cfg["environment"]["duration"] = 30
        cfg["environment"]["timestep"] = 10
        cfg.setdefault("ensemble", {})["enabled"] = True
        cfg["ensemble"]["n_members"] = 3

        with tempfile.TemporaryDirectory() as tmp_dir:
            result_dir = run_experiment(cfg, Path(tmp_dir))
            statistics = pd.read_csv(result_dir / "ensemble_statistics.csv")
            metadata = json.loads(
                (result_dir / "metadata.json").read_text(encoding="utf-8")
            )
            summary = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
            compatibility = inspect_result_compatibility(result_dir)
            aggregation = json.loads(
                (result_dir / "ensemble_aggregation_diagnostics.json").read_text(
                    encoding="utf-8"
                )
            )
            html_report = (result_dir / "report.html").read_text(encoding="utf-8")
            pdf_report = (result_dir / "report.pdf").read_bytes()

        self.assertFalse(statistics.empty)
        self.assertEqual(
            metadata["ensemble_aggregation_method"],
            "column_streaming_from_member_csv",
        )
        self.assertEqual(
            summary["ensemble"]["aggregation_method"],
            "column_streaming_from_member_csv",
        )
        self.assertEqual(compatibility["status"], "current")
        self.assertEqual(aggregation["n_member_files"], 3)
        self.assertIn("<!doctype html>", html_report.lower())
        self.assertTrue(pdf_report.startswith(b"%PDF"))
        self.assertTrue(aggregation["process_rss"]["available"])

    def test_subprocess_ensemble_preserves_member_audit_and_resource_data(self):
        cfg = default_config()
        cfg["experiment"]["mode"] = "single"
        cfg["simulation"]["adapter"] = "placeholder_warm_cloud"
        cfg["environment"]["duration"] = 20
        cfg["environment"]["timestep"] = 10
        cfg.setdefault("ensemble", {}).update(
            {
                "enabled": True,
                "n_members": 2,
                "execution_backend": "subprocess",
            }
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            result_dir = run_experiment(cfg, Path(tmp_dir))
            member_summary = pd.read_csv(result_dir / "member_summary.csv")
            summary = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
            member_dirs = sorted((result_dir / "members").glob("member_*"))
            audit_files_exist = all(
                (member_dir / filename).exists()
                for member_dir in member_dirs
                for filename in (
                    "isolated_member_config.yaml",
                    "isolated_member_stdout.log",
                    "isolated_member_stderr.log",
                    "isolated_member_status.json",
                )
            )

        self.assertEqual(len(member_summary), 2)
        self.assertTrue(member_summary["success"].all())
        self.assertEqual(set(member_summary["execution_backend"]), {"subprocess"})
        self.assertTrue((member_summary["member_process_return_code"] == 0).all())
        self.assertTrue(audit_files_exist)
        resources = summary["ensemble"]["member_process_resources"]
        self.assertTrue(resources["member_process_isolation"])
        self.assertEqual(resources["successful_child_processes"], 2)
        self.assertGreater(resources["max_child_process_tree_rss_bytes"], 0)

    def test_invalid_ensemble_execution_backend_is_blocking(self):
        cfg = default_config()
        cfg["ensemble"]["execution_backend"] = "thread"
        fields = {
            issue.field
            for issue in validate_config_detailed(cfg)
            if issue.severity == "error"
        }
        self.assertIn("ensemble.execution_backend", fields)

    def test_subprocess_member_failure_preserves_child_error(self):
        cfg = default_config()
        cfg["experiment"]["mode"] = "single"
        cfg["simulation"]["adapter"] = "missing_test_adapter"
        cfg.setdefault("ensemble", {}).update(
            {
                "enabled": True,
                "n_members": 1,
                "execution_backend": "subprocess",
            }
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ExperimentExecutionError) as raised:
                run_ensemble_experiment(cfg, Path(tmp_dir))
            result_dir = raised.exception.result_dir
            member_summary = pd.read_csv(result_dir / "member_summary.csv")
            status_path = (
                result_dir
                / "members"
                / "member_001"
                / "isolated_member_status.json"
            )
            child_status = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertEqual(member_summary.loc[0, "execution_backend"], "subprocess")
        self.assertNotEqual(member_summary.loc[0, "member_process_return_code"], 0)
        self.assertFalse(child_status["success"])
        self.assertIn("adapter", child_status["error_message"].lower())

    def test_pdf_report_and_qualification_plan_contracts(self):
        cfg = default_config()
        metadata = {
            "run_id": "pdf-test",
            "experiment_name": "Unicode warm cloud 실험",
            "result_type": "single",
            "result_files": {"summary": "summary.json", "report_pdf": "report.pdf"},
        }
        report = build_pdf_report(
            summary={"metrics": {"final_rain_water_mixing_ratio": 1.0e-5}},
            metadata=metadata,
            validation_rows=[{"severity": "warning"}],
            config=cfg,
        )
        self.assertTrue(report.startswith(b"%PDF"))
        self.assertGreater(len(report), 2_000)
        self.assertIn("research-report-v5", REPORT_BUILD_ID)

        pilot = build_qualification_config(
            cfg,
            profile="pilot",
            adapter="placeholder_warm_cloud",
        )
        plan = qualification_plan(pilot, profile="pilot")
        self.assertEqual(plan["case_count"], 4)
        self.assertEqual(plan["model_execution_count"], 8)
        self.assertEqual(plan["sweep_design"], "one_factor_at_reference")
        self.assertEqual(pilot["environment"]["duration"], 60)
        self.assertEqual(pilot["seeding"]["injection_start"], 20)
        self.assertTrue(pilot["diagnostics"]["numerical_convergence"]["enabled"])
        self.assertFalse(pilot["ensemble"]["enabled"])
        self.assertFalse(plan["ensemble_enabled"])
        pilot_cases = generate_sweep_cases(pilot)
        reference = pilot_cases[0].parameter_values
        self.assertEqual(len(pilot_cases), 4)
        self.assertTrue(
            all(
                sum(values[key] != reference[key] for key in reference) <= 1
                for values in [case.parameter_values for case in pilot_cases]
            )
        )

        rain_standard = build_qualification_config(
            cfg,
            profile="rain_standard",
            adapter="pysdm_parcel",
        )
        rain_plan = qualification_plan(rain_standard, profile="rain_standard")
        self.assertTrue(rain_standard["microphysics"]["collision"])
        self.assertEqual(rain_plan["case_count"], 7)
        self.assertEqual(rain_plan["model_execution_count"], 14)
        self.assertTrue(rain_plan["rain_signal_required"])

        response_pilot = build_qualification_config(
            cfg,
            profile="rain_response_pilot",
            adapter="pysdm_parcel",
        )
        response_plan = qualification_plan(
            response_pilot,
            profile="rain_response_pilot",
        )
        self.assertTrue(response_pilot["ensemble"]["enabled"])
        self.assertEqual(response_pilot["ensemble"]["n_members"], 3)
        self.assertEqual(response_plan["case_count"], 4)
        self.assertEqual(response_plan["model_execution_count"], 24)
        self.assertTrue(response_plan["common_random_seed_pairing"])
        self.assertEqual(len(response_plan["common_random_seeds"]), 3)
        self.assertEqual(
            max(response_pilot["sweep"]["parameters"][1]["values"]),
            800,
        )

        targeted = build_qualification_config(
            cfg,
            profile="rain_response_targeted",
            adapter="pysdm_parcel",
        )
        targeted_plan = qualification_plan(
            targeted,
            profile="rain_response_targeted",
        )
        targeted_cases = generate_sweep_cases(targeted)
        self.assertEqual(targeted_plan["case_count"], 4)
        self.assertEqual(targeted_plan["case_seed_pair_count"], 20)
        self.assertEqual(targeted_plan["model_execution_count"], 40)
        self.assertEqual(targeted_plan["n_common_random_seeds"], 5)
        self.assertEqual(len(set(targeted_plan["common_random_seeds"])), 5)
        self.assertTrue(targeted_plan["execution_confirmation_required"])
        self.assertIn("may underestimate", targeted_plan["runtime_estimate_warning"])
        self.assertEqual(
            targeted_plan["execution_confirmation_flag"],
            "--confirm-targeted-run",
        )
        self.assertEqual(targeted["execution"]["max_workers"], 1)
        self.assertEqual(
            targeted_cases[0].parameter_values,
            {
                "environment.timestep": 2.5,
                "seeding.number_superdroplets": 1600,
                "background_aerosol.number_superdroplets": 1600,
            },
        )
        self.assertTrue(
            all(
                len(case.parameter_values) == 3
                for case in targeted_cases
            )
        )

        benchmark = build_benchmark_config(cfg, profile="large")
        self.assertEqual(benchmark["simulation"]["adapter"], "pysdm_parcel")
        self.assertEqual(benchmark["ensemble"]["n_members"], 24)
        self.assertEqual(benchmark["environment"]["duration"], 600)
        benchmark_gc = build_benchmark_config(
            cfg,
            profile="pilot",
            collect_garbage_between_members=True,
        )
        self.assertTrue(
            benchmark_gc["ensemble"]["collect_garbage_between_members"]
        )
        benchmark_subprocess = build_benchmark_config(
            cfg,
            profile="pilot",
            member_execution_backend="subprocess",
        )
        self.assertEqual(
            benchmark_subprocess["ensemble"]["execution_backend"],
            "subprocess",
        )
        profiler = ProcessRSSCheckpointProfiler()
        profiler("ensemble_member_complete_pre_gc", 1, 2, "before gc")
        profiler("ensemble_member_complete", 1, 2, "after gc")
        profiler("ensemble_member_complete_pre_gc", 2, 2, "before gc")
        profiler("ensemble_member_complete", 2, 2, "after gc")
        profile_summary = profiler.summary()
        self.assertEqual(profile_summary["n_member_boundaries"], 2)
        self.assertEqual(len(profile_summary["gc_reclaimed_rss_bytes"]), 2)

        baseline_evidence = {
            "profile": "standard",
            "workload": {"n_members": 12},
            "collect_garbage_between_members": False,
            "full_run_elapsed_seconds": 100.0,
            "full_process_rss": {"peak_rss_increase_bytes": 1_000},
            "memory_checkpoint_summary": {
                "member_boundary_rss_increase_bytes": 500,
                "member_boundary_rss_slope_bytes_per_member": 50.0,
            },
        }
        gc_evidence = {
            "profile": "standard",
            "workload": {"n_members": 12},
            "collect_garbage_between_members": True,
            "full_run_elapsed_seconds": 105.0,
            "full_process_rss": {"peak_rss_increase_bytes": 1_010},
            "memory_checkpoint_summary": {
                "member_boundary_rss_increase_bytes": 510,
                "member_boundary_rss_slope_bytes_per_member": 51.0,
                "gc_reclaimed_rss_total_bytes": 200,
            },
        }
        memory_comparison = compare_ensemble_memory_benchmarks(
            baseline_evidence,
            gc_evidence,
        )
        self.assertTrue(memory_comparison["matched_workload"])
        self.assertEqual(
            memory_comparison["conclusion"],
            "no_observed_peak_and_retained_rss_reduction",
        )
        self.assertFalse(
            memory_comparison["recommend_collect_garbage_between_members_default"]
        )
        self.assertAlmostEqual(
            memory_comparison["observed_differences"]["wall_time_overhead_percent"],
            5.0,
        )

        backend_baseline = {
            **baseline_evidence,
            "member_execution_backend": "in_process",
            "full_process_rss": {
                "process_tree": {"peak_rss_increase_bytes": 1_000},
            },
        }
        backend_isolated = {
            **baseline_evidence,
            "member_execution_backend": "subprocess",
            "full_run_elapsed_seconds": 130.0,
            "full_process_rss": {
                "process_tree": {"peak_rss_increase_bytes": 950},
            },
            "memory_checkpoint_summary": {
                "member_boundary_rss_increase_bytes": 50,
            },
            "member_process_resources": {
                "max_child_process_tree_rss_bytes": 800,
            },
        }
        backend_comparison = compare_ensemble_execution_backends(
            backend_baseline,
            backend_isolated,
        )
        self.assertEqual(
            backend_comparison["conclusion"],
            "observed_parent_retained_rss_release",
        )
        self.assertTrue(
            backend_comparison[
                "recommend_subprocess_for_memory_bounded_ensembles"
            ]
        )
        self.assertFalse(backend_comparison["recommend_subprocess_as_default"])

        pilot_with_duration = build_qualification_config(
            cfg,
            profile="pilot",
            duration_seconds=120,
        )
        self.assertEqual(pilot_with_duration["seeding"]["injection_start"], 20)
        first_spec = build_run_spec(cfg)
        second_spec = build_run_spec(cfg)
        self.assertNotEqual(first_spec.run_id, second_spec.run_id)
        self.assertIn("T", first_spec.metadata["created_at"])

    def test_rain_qualification_evidence_requires_physical_rain_signal(self):
        rows = []
        for metric, reference in (
            ("comparison.control.max_rain_water_mixing_ratio", 3.0e-3),
            ("comparison.seeding.max_rain_water_mixing_ratio", 2.8e-3),
        ):
            rows.extend(
                [
                    {
                        "metric": metric,
                        "varied_parameter": "param.environment.timestep",
                        "resolution_rank": 0,
                        "reference_value": reference,
                        "relative_difference_percent": 0.0,
                    },
                    {
                        "metric": metric,
                        "varied_parameter": "param.environment.timestep",
                        "resolution_rank": 1,
                        "reference_value": reference,
                        "relative_difference_percent": 1.0,
                    },
                ]
            )
        cfg = default_config()
        cfg["qualification"] = {
            "profile": "rain_standard",
            "rain_signal_required": True,
            "rain_signal_floor_kg_kg": 1.0e-8,
        }
        evidence = build_qualification_evidence(pd.DataFrame(rows), cfg)
        self.assertEqual(evidence["status"], "supported_for_profile")
        self.assertTrue(evidence["rain_signal_detected"])
        self.assertEqual(
            evidence["metric_family_evidence"]["absolute_state"]["status"],
            "supported_for_profile",
        )

        missing = pd.DataFrame(rows)
        missing["reference_value"] = 0.0
        evidence = build_qualification_evidence(missing, cfg)
        self.assertEqual(evidence["status"], "missing_required_rain_signal")
        self.assertFalse(evidence["rain_signal_detected"])

    def test_common_seed_convergence_pairs_identical_seeds(self):
        metric = "comparison.control.max_rain_water_mixing_ratio"
        cases = [
            ("case_001", 5, 800, 800, {101: 1.0, 202: 2.0}),
            ("case_002", 10, 800, 800, {101: 1.02, 202: 2.04}),
            ("case_003", 5, 400, 800, {101: 1.03, 202: 2.06}),
            ("case_004", 5, 800, 400, {101: 1.04, 202: 2.08}),
        ]
        sweep_rows = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            for case_name, timestep, seed_nsd, background_nsd, values in cases:
                case_dir = root / "cases" / case_name
                case_dir.mkdir(parents=True)
                pd.DataFrame(
                    [
                        {
                            "random_seed": seed,
                            "success": True,
                            f"{MEMBER_CONVERGENCE_METRIC_PREFIX}{metric}": value,
                        }
                        for seed, value in values.items()
                    ]
                ).to_csv(case_dir / "member_summary.csv", index=False)
                sweep_rows.append(
                    {
                        "case_name": case_name,
                        "result_dir": f"cases/{case_name}",
                        "param.environment.timestep": timestep,
                        "param.seeding.number_superdroplets": seed_nsd,
                        "param.background_aerosol.number_superdroplets": background_nsd,
                    }
                )
            paired = build_common_seed_convergence_input(
                pd.DataFrame(sweep_rows), root
            )

        cfg = default_config()
        cfg["diagnostics"]["numerical_convergence"]["metrics"] = [metric]
        cfg["qualification"] = {
            "common_random_seeds": [101, 202],
        }
        coverage = summarize_common_seed_case_coverage(
            paired,
            cfg,
            n_cases=4,
        )
        table = build_numerical_convergence_table(paired, cfg)
        next_finest = table[table["resolution_rank"] == 1]

        self.assertEqual(len(paired), 8)
        self.assertEqual(set(paired["param.experiment.random_seed"]), {101, 202})
        self.assertEqual(len(next_finest), 6)
        self.assertTrue(coverage["complete"])
        self.assertEqual(coverage["observed_case_seed_pairs"], 8)
        self.assertEqual(set(next_finest["random_seed"]), {101, 202})
        self.assertTrue((next_finest["relative_difference_percent"] <= 5.0).all())

    def test_common_seed_evidence_requires_complete_seed_rain_coverage(self):
        rows = []
        for seed in (101, 202):
            for metric in (
                "comparison.control.max_rain_water_mixing_ratio",
                "comparison.seeding.max_rain_water_mixing_ratio",
            ):
                reference = 2.0e-3
                if seed == 202 and metric.startswith("comparison.control"):
                    reference = 0.0
                rows.extend(
                    [
                        {
                            "metric": metric,
                            "varied_parameter": "param.environment.timestep",
                            "resolution_rank": 0,
                            "reference_value": reference,
                            "relative_difference_percent": 0.0,
                            "random_seed": seed,
                        },
                        {
                            "metric": metric,
                            "varied_parameter": "param.environment.timestep",
                            "resolution_rank": 1,
                            "reference_value": reference,
                            "relative_difference_percent": 1.0,
                            "random_seed": seed,
                        },
                    ]
                )
        cfg = default_config()
        cfg["qualification"] = {
            "profile": "rain_response_pilot",
            "rain_signal_required": True,
            "rain_signal_floor_kg_kg": 1.0e-8,
            "common_random_seed_pairing": True,
            "common_random_seeds": [101, 202],
            "common_seed_case_coverage": {
                "expected_case_seed_pairs": 8,
                "observed_case_seed_pairs": 8,
                "complete": True,
            },
        }
        evidence = build_qualification_evidence(pd.DataFrame(rows), cfg)
        self.assertTrue(evidence["common_seed_coverage_complete"])
        self.assertEqual(evidence["n_common_random_seeds"], 2)
        self.assertEqual(evidence["status"], "missing_required_rain_signal")
        self.assertFalse(evidence["rain_signal_by_seed"]["202"]["detected"])

        incomplete = pd.DataFrame(rows)
        incomplete = incomplete[incomplete["random_seed"] == 101]
        evidence = build_qualification_evidence(incomplete, cfg)
        self.assertEqual(evidence["status"], "incomplete_common_seed_coverage")
        self.assertFalse(evidence["common_seed_coverage_complete"])

    def test_spectrum_transition_onset_is_interpolated_and_audited(self):
        cfg = default_config()
        cfg["diagnostics"]["spectrum_transition"]["rain_volume_fraction_threshold"] = 0.01
        rows = []
        for time_s, control, seeding in (
            (0.0, 0.0, 0.0),
            (10.0, 0.005, 0.02),
            (20.0, 0.02, 0.04),
        ):
            rows.append(
                {
                    "time_s": time_s,
                    "activation_factor": 1.0,
                    "rain_factor": 1.0,
                    "activation_threshold_um": 0.5,
                    "rain_threshold_um": 25.0,
                    "rain_volume_fraction_of_activated_control": control,
                    "rain_volume_fraction_of_activated_seeding": seeding,
                    "rain_volume_fraction_of_activated_diff": seeding - control,
                    "rain_number_fraction_of_activated_control": control / 2,
                    "rain_number_fraction_of_activated_seeding": seeding / 2,
                    "rain_number_fraction_of_activated_diff": (seeding - control) / 2,
                    "activated_number_fraction_control": 0.8,
                    "activated_number_fraction_seeding": 0.8,
                    "activated_number_fraction_diff": 0.0,
                }
            )
        comparison = pd.DataFrame(rows)
        transition = build_spectrum_transition_table(comparison, cfg)
        robustness = build_transition_onset_robustness(comparison, cfg)
        summary = summarize_spectrum_transition(transition, robustness)

        self.assertAlmostEqual(summary["control_transition_onset_s"], 13.3333333333)
        self.assertAlmostEqual(summary["seeding_transition_onset_s"], 5.0)
        self.assertAlmostEqual(summary["transition_onset_shift_s"], -8.3333333333)
        self.assertTrue(summary["threshold_shift_direction_consistent"])
        self.assertEqual(summary["n_transition_fraction_thresholds"], 3)
        self.assertEqual(summary["maximum_checkpoint_interval_s"], 10.0)
        self.assertEqual(len(robustness), 3)
        self.assertEqual(summary["status"], "resolved")

    def test_diagnostic_comparison_tables_are_aligned(self):
        cfg = _small_native_config()
        edges = build_spectrum_bin_edges(cfg)
        n_bins = len(edges) - 1
        spectra = {
            "time_s": np.asarray([0.0, 30.0]),
            "number_concentration_m3": np.ones((2, n_bins)) * 1.0e6,
            "volume_fraction_per_dlnr": np.ones((2, n_bins)) * 1.0e-9,
        }
        control_spectrum = build_wet_radius_spectrum_table(spectra, edges, cfg)
        seeding_spectrum = control_spectrum.copy()
        seeding_spectrum["number_concentration_cm3"] += 2.0
        spectrum_comparison = build_wet_radius_spectrum_comparison(
            control_spectrum,
            seeding_spectrum,
        )
        self.assertTrue(
            np.allclose(spectrum_comparison["number_concentration_cm3_diff"], 2.0)
        )

        control_robustness = build_threshold_robustness_table(control_spectrum, cfg)
        seeding_robustness = control_robustness.copy()
        seeding_robustness["rain_number_cm3"] += 1.0
        robustness_comparison = build_threshold_robustness_comparison(
            control_robustness,
            seeding_robustness,
        )
        self.assertTrue(np.allclose(robustness_comparison["rain_number_cm3_diff"], 1.0))

        water_control = pd.DataFrame(
            {"time_s": [0.0, 1.0], "total_water_mixing_ratio": [0.02, 0.02]}
        )
        water_seeding = pd.DataFrame(
            {"time_s": [0.0, 1.0], "total_water_mixing_ratio": [0.02, 0.021]}
        )
        water_comparison = build_water_budget_comparison(water_control, water_seeding)
        self.assertAlmostEqual(
            float(water_comparison["total_water_mixing_ratio_diff"].iloc[-1]),
            0.001,
        )

    def test_numerical_convergence_uses_finest_ofat_reference(self):
        cfg = default_config()
        metric = "comparison.efficiency.rain_enhancement_final"
        cfg["diagnostics"]["numerical_convergence"]["metrics"] = [metric]
        cfg["diagnostics"]["numerical_convergence"]["relative_tolerance_percent"] = 5.0
        rows = []
        case_index = 0
        for timestep in (5, 10):
            for seed_nsd in (100, 200):
                for background_nsd in (100, 200):
                    case_index += 1
                    response = (
                        100.0
                        + (2.0 if timestep == 10 else 0.0)
                        + (2.0 if seed_nsd == 100 else 0.0)
                        + (2.0 if background_nsd == 100 else 0.0)
                    )
                    rows.append(
                        {
                            "case_name": f"case_{case_index}",
                            "param.environment.timestep": timestep,
                            "param.seeding.number_superdroplets": seed_nsd,
                            "param.background_aerosol.number_superdroplets": background_nsd,
                            metric: response,
                        }
                    )
        convergence = build_numerical_convergence_table(pd.DataFrame(rows), cfg)
        summary = summarize_numerical_convergence(convergence)

        self.assertEqual(len(convergence), 6)
        self.assertEqual(summary["status"], "pass")
        self.assertEqual(summary["n_next_finest_checks"], 3)

    def test_invalid_research_quality_gates_are_blocking(self):
        cfg = default_config()
        cfg["diagnostics"]["water_budget"]["warning_relative_drift_percent"] = 1.0
        cfg["diagnostics"]["water_budget"]["failure_relative_drift_percent"] = 0.1
        cfg["diagnostics"]["numerical_convergence"]["relative_tolerance_percent"] = 0.0
        cfg["diagnostics"]["spectrum_transition"]["rain_volume_fraction_threshold"] = 1.0
        cfg["sweep"]["design"] = "one_factor_at_reference"
        cfg["ensemble"]["collect_garbage_between_members"] = "yes"
        cfg["qualification"] = {"common_random_seed_pairing": True}
        error_fields = {
            issue.field
            for issue in validate_config_detailed(cfg)
            if issue.severity == "error"
        }
        self.assertIn(
            "diagnostics.water_budget.failure_relative_drift_percent",
            error_fields,
        )
        self.assertIn(
            "diagnostics.numerical_convergence.relative_tolerance_percent",
            error_fields,
        )
        self.assertIn(
            "diagnostics.spectrum_transition.rain_volume_fraction_threshold",
            error_fields,
        )
        self.assertIn("sweep.parameters.0.reference", error_fields)
        self.assertIn("ensemble.collect_garbage_between_members", error_fields)
        self.assertIn("qualification.common_random_seed_pairing", error_fields)

    def test_placeholder_numerical_sweep_writes_convergence_audit(self):
        cfg = default_config()
        cfg["experiment"]["mode"] = "parameter_sweep"
        cfg["simulation"]["adapter"] = "placeholder_warm_cloud"
        cfg["sweep"]["run_mode"] = "control_vs_seeding"
        cfg["sweep"]["max_runs"] = 8
        cfg["sweep"]["parameters"] = [
            {"name": "environment.timestep", "values": [5, 10]},
            {"name": "seeding.number_superdroplets", "values": [100, 200]},
            {"name": "background_aerosol.number_superdroplets", "values": [100, 200]},
        ]
        cfg["qualification"] = {"build_id": "qualification-test", "profile": "pilot"}
        with tempfile.TemporaryDirectory() as tmp_dir:
            sweep_dir = run_experiment(cfg, Path(tmp_dir))
            convergence_path = sweep_dir / "numerical_convergence.csv"
            summary = json.loads((sweep_dir / "summary.json").read_text(encoding="utf-8"))
            convergence = pd.read_csv(convergence_path)
            report = (sweep_dir / "report.md").read_text(encoding="utf-8")
            html_report = (sweep_dir / "report.html").read_text(encoding="utf-8")
            pdf_report = (sweep_dir / "report.pdf").read_bytes()
            manifest = json.loads(
                (sweep_dir / "result_manifest.json").read_text(encoding="utf-8")
            )
            compatibility = inspect_result_compatibility(sweep_dir)
            case_directories = list((sweep_dir / "cases").iterdir())
            stored_plan = json.loads(
                (sweep_dir / "qualification_plan.json").read_text(encoding="utf-8")
            )
            stored_evidence = json.loads(
                (sweep_dir / "qualification_evidence.json").read_text(encoding="utf-8")
            )

        self.assertFalse(convergence.empty)
        self.assertTrue(summary["numerical_convergence"]["available"])
        self.assertIn("Research quality gates", report)
        self.assertIn("numerical_convergence.status", report)
        self.assertIn("<!doctype html>", html_report.lower())
        self.assertTrue(pdf_report.startswith(b"%PDF"))
        self.assertEqual(manifest["result_schema_version"], 2)
        self.assertEqual(manifest["primary_data"], "sweep_summary.csv")
        self.assertEqual(compatibility["status"], "current")
        self.assertTrue(compatibility["readable"])
        self.assertEqual(len(case_directories), 8)
        self.assertEqual(stored_plan["build_id"], "qualification-test")
        self.assertTrue(stored_evidence["available"])
        self.assertIn(stored_evidence["status"], {"supported_for_profile", "not_supported_for_profile"})
        self.assertEqual(
            manifest["files"]["qualification_plan"],
            "qualification_plan.json",
        )

    def test_placeholder_common_seed_sweep_writes_paired_audit(self):
        cfg = default_config()
        cfg["experiment"]["mode"] = "parameter_sweep"
        cfg["experiment"]["name"] = "paired_seed_regression"
        cfg["simulation"]["adapter"] = "placeholder_warm_cloud"
        cfg["environment"]["duration"] = 20
        cfg["environment"]["timestep"] = 5
        cfg["seeding"]["injection_start"] = 10
        cfg["seeding"]["injection_end"] = 20
        cfg["ensemble"].update(
            {
                "enabled": True,
                "n_members": 2,
                "seed_start": 101,
                "seed_step": 101,
            }
        )
        cfg["sweep"] = {
            "design": "one_factor_at_reference",
            "run_mode": "control_vs_seeding",
            "max_runs": 10,
            "ranking_metric": "comparison.efficiency.seeding_efficiency_score",
            "parameters": [
                {
                    "name": "environment.timestep",
                    "values": [5, 10],
                    "reference": "min",
                },
                {
                    "name": "seeding.number_superdroplets",
                    "values": [10, 20],
                    "reference": "max",
                },
                {
                    "name": "background_aerosol.number_superdroplets",
                    "values": [20, 40],
                    "reference": "max",
                },
            ],
        }
        cfg["qualification"] = {
            "build_id": "paired-seed-regression",
            "profile": "software_test",
            "common_random_seed_pairing": True,
            "common_random_seeds": [101, 202],
            "rain_signal_required": False,
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            result_dir = run_experiment(cfg, Path(tmp_dir))
            paired = pd.read_csv(result_dir / "paired_seed_metrics.csv")
            convergence = pd.read_csv(result_dir / "numerical_convergence.csv")
            evidence = json.loads(
                (result_dir / "qualification_evidence.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest = json.loads(
                (result_dir / "result_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(len(paired), 8)
        self.assertEqual(set(paired["param.experiment.random_seed"]), {101, 202})
        self.assertEqual(set(convergence["random_seed"]), {101, 202})
        self.assertTrue(evidence["common_seed_case_coverage_complete"])
        self.assertEqual(
            evidence["common_seed_case_coverage"]["observed_case_seed_pairs"],
            8,
        )
        self.assertEqual(manifest["files"]["paired_seed_metrics"], "paired_seed_metrics.csv")

    def test_legacy_result_without_manifest_is_inferred(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            legacy_dir = Path(tmp_dir)
            pd.DataFrame({"time_s": [0.0], "value": [1.0]}).to_csv(
                legacy_dir / "timeseries.csv",
                index=False,
            )
            compatibility = inspect_result_compatibility(legacy_dir)

        self.assertEqual(compatibility["status"], "legacy_without_manifest")
        self.assertEqual(compatibility["result_type"], "single")
        self.assertEqual(compatibility["primary_data"], "timeseries.csv")
        self.assertTrue(compatibility["readable"])

    def test_actual_legacy_sweep_fixture_remains_readable(self):
        fixture = Path(__file__).parent / "fixtures" / "results" / "legacy_actual_sweep"
        compatibility = inspect_result_compatibility(fixture)
        sweep = pd.read_csv(fixture / "sweep_summary.csv")

        self.assertEqual(compatibility["status"], "legacy_without_manifest")
        self.assertEqual(compatibility["result_type"], "parameter_sweep")
        self.assertTrue(compatibility["readable"])
        self.assertEqual(len(sweep), 3)
        self.assertEqual(int(sweep["ensemble.n_success"].sum()), 15)

    def test_schema_v1_manifest_aliases_are_migrated_in_memory(self):
        fixture = (
            Path(__file__).parent
            / "fixtures"
            / "results"
            / "schema_v1_alias_manifest"
        )
        compatibility = inspect_result_compatibility(fixture)

        self.assertEqual(compatibility["status"], "supported_older_schema")
        self.assertTrue(compatibility["readable"])
        self.assertEqual(compatibility["result_type"], "single")
        self.assertEqual(compatibility["primary_data"], "timeseries.csv")
        self.assertIn("v1:type->result_type", compatibility["migrations_applied"])
        self.assertEqual(compatibility["stored_manifest"]["type"], "single")

    def test_manifest_blocks_incompatible_or_incomplete_results(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            result_dir = Path(tmp_dir)
            (result_dir / "timeseries.csv").write_text("time_s\n0\n", encoding="utf-8")
            manifest_path = result_dir / "result_manifest.json"

            base_manifest = {
                "result_schema_version": 2,
                "minimum_reader_version": 99,
                "result_type": "single",
                "primary_data": "timeseries.csv",
                "run_id": "compatibility-test",
                "files": {"timeseries": "timeseries.csv"},
            }
            manifest_path.write_text(json.dumps(base_manifest), encoding="utf-8")
            requires_newer = inspect_result_compatibility(result_dir)

            base_manifest["minimum_reader_version"] = 1
            base_manifest["result_schema_version"] = 99
            manifest_path.write_text(json.dumps(base_manifest), encoding="utf-8")
            future = inspect_result_compatibility(result_dir)

            base_manifest["result_schema_version"] = 2
            base_manifest["primary_data"] = "missing.csv"
            manifest_path.write_text(json.dumps(base_manifest), encoding="utf-8")
            missing = inspect_result_compatibility(result_dir)

        self.assertEqual(requires_newer["status"], "requires_newer_reader")
        self.assertFalse(requires_newer["readable"])
        self.assertEqual(future["status"], "future_schema")
        self.assertFalse(future["readable"])
        self.assertEqual(missing["status"], "missing_primary_data")
        self.assertFalse(missing["readable"])


@unittest.skipUnless(PYSDM_AVAILABLE, "PySDM optional dependencies are not installed")
class NativePySDMIntegrationTests(unittest.TestCase):
    def test_real_pysdm_native_products_and_liquid_partition(self):
        cfg = _small_native_config()
        result = run_pysdm_parcel_simulation(build_run_spec(cfg))
        df = result.require_timeseries()

        expected_native = {
            "temperature_K",
            "pressure_Pa",
            "water_vapour_mixing_ratio",
            "relative_humidity_percent",
            "cloud_water_mixing_ratio",
            "rain_water_mixing_ratio",
            "cloud_droplet_concentration",
            "rain_droplet_concentration",
            "effective_radius_cloud_um",
            "effective_radius_rain_um",
            "effective_radius_all_um",
        }
        self.assertTrue(expected_native.issubset(df.columns))
        self.assertTrue(np.isfinite(df["temperature_K"]).all())
        self.assertTrue(np.isfinite(df["water_vapour_mixing_ratio"]).all())
        self.assertEqual(result.summary["liquid_water_partition_max_abs_error"], 0.0)

        provenance = diagnostic_provenance_rows(list(df.columns), cfg)
        self.assertFalse(any(row["provenance"] == "proxy" for row in provenance))
        self.assertEqual(
            result.metadata["diagnostic_radius_thresholds"]["range_convention"],
            "lower inclusive, upper exclusive",
        )
        self.assertIn("wet_radius_spectrum", result.tables)
        self.assertIn("threshold_robustness", result.tables)
        self.assertFalse(result.tables["wet_radius_spectrum"].empty)
        self.assertEqual(
            sorted(result.tables["wet_radius_spectrum"]["time_s"].unique().tolist()),
            [0.0, 15.0, 30.0],
        )

    def test_runner_writes_native_quality_and_comparison_files(self):
        cfg = _small_native_config()
        cfg["experiment"]["mode"] = "control_vs_seeding"
        with tempfile.TemporaryDirectory() as tmp_dir:
            result_dir = run_experiment(cfg, Path(tmp_dir))
            provenance = json.loads(
                (result_dir / "control" / "diagnostic_provenance.json").read_text(
                    encoding="utf-8"
                )
            )
            metadata = json.loads(
                (result_dir / "control" / "metadata.json").read_text(encoding="utf-8")
            )
            spectrum_exists = (result_dir / "control" / "wet_radius_spectrum.csv").exists()
            robustness_exists = (result_dir / "control" / "threshold_robustness.csv").exists()
            water_budget_exists = (result_dir / "control" / "water_budget.csv").exists()
            stored_summary = json.loads(
                (result_dir / "control" / "summary.json").read_text(encoding="utf-8")
            )
            comparison_files = {
                filename: (result_dir / filename).exists()
                for filename in (
                    "wet_radius_spectrum_comparison.csv",
                    "threshold_robustness_comparison.csv",
                    "water_budget_comparison.csv",
                )
            }
            comparison_summary = json.loads(
                (result_dir / "summary.json").read_text(encoding="utf-8")
            )
            comparison_report = (result_dir / "report.md").read_text(encoding="utf-8")
            comparison_html_report = (result_dir / "report.html").read_text(encoding="utf-8")
            transition_exists = (result_dir / "spectrum_transition.csv").exists()
            transition_robustness_exists = (
                result_dir / "spectrum_transition_onset_robustness.csv"
            ).exists()
            comparison_compatibility = inspect_result_compatibility(result_dir)

        self.assertFalse(any(row["provenance"] == "proxy" for row in provenance))
        self.assertEqual(
            metadata["native_product_build_id"],
            "native-parcel-spectrum-products-20260714",
        )
        self.assertEqual(
            metadata["diagnostic_radius_thresholds"]["rain_radius_um"],
            25.0,
        )
        self.assertEqual(metadata["wet_radius_spectrum"]["checkpoint_times_s"], [0.0, 15.0, 30.0])
        self.assertTrue(spectrum_exists)
        self.assertTrue(robustness_exists)
        self.assertTrue(water_budget_exists)
        self.assertTrue(stored_summary["adapter_summary"]["water_budget"]["available"])
        self.assertTrue(all(comparison_files.values()))
        self.assertTrue(
            comparison_summary["comparison"]["research_quality"]["wet_radius_spectrum"][
                "available"
            ]
        )
        self.assertIn("water_budget", comparison_report)
        self.assertIn("Research quality gates", comparison_html_report)
        self.assertTrue(transition_exists)
        self.assertTrue(transition_robustness_exists)
        self.assertTrue(
            comparison_summary["comparison"]["research_quality"]["spectrum_transition"][
                "available"
            ]
        )
        self.assertEqual(comparison_compatibility["status"], "current")
        self.assertEqual(comparison_compatibility["result_type"], "comparison")
        self.assertTrue(comparison_compatibility["readable"])


if __name__ == "__main__":
    unittest.main()

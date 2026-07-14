from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.case_diagnostic_comparison import (
    build_threshold_robustness_comparison,
    build_water_budget_comparison,
    build_wet_radius_spectrum_comparison,
)
from analysis.growth_pathway_diagnostics import diagnostic_provenance_rows
from analysis.ensemble_statistics import (
    build_ensemble_statistics,
    build_ensemble_statistics_from_paths,
)
from analysis.numerical_convergence import (
    build_numerical_convergence_table,
    summarize_numerical_convergence,
)
from analysis.result_manifest import inspect_result_compatibility
from analysis.water_budget import build_water_budget_table, summarize_water_budget
from simulation.builder import build_run_spec
from simulation.pysdm_parcel_adapter import (
    _output_to_dataframe,
    run_pysdm_parcel_simulation,
)
from simulation.runner import run_experiment
from simulation.schema import default_config
from simulation.validation import validate_config_detailed
from simulation.wet_radius_spectrum import (
    build_spectrum_bin_edges,
    build_threshold_robustness_table,
    build_wet_radius_spectrum_table,
    resolve_spectrum_checkpoint_times,
)


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

        pd.testing.assert_frame_equal(actual, expected)

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
        with tempfile.TemporaryDirectory() as tmp_dir:
            sweep_dir = run_experiment(cfg, Path(tmp_dir))
            convergence_path = sweep_dir / "numerical_convergence.csv"
            summary = json.loads((sweep_dir / "summary.json").read_text(encoding="utf-8"))
            convergence = pd.read_csv(convergence_path)
            report = (sweep_dir / "report.md").read_text(encoding="utf-8")
            manifest = json.loads(
                (sweep_dir / "result_manifest.json").read_text(encoding="utf-8")
            )
            compatibility = inspect_result_compatibility(sweep_dir)

        self.assertFalse(convergence.empty)
        self.assertTrue(summary["numerical_convergence"]["available"])
        self.assertIn("Research quality gates", report)
        self.assertIn("numerical_convergence.status", report)
        self.assertEqual(manifest["result_schema_version"], 2)
        self.assertEqual(manifest["primary_data"], "sweep_summary.csv")
        self.assertEqual(compatibility["status"], "current")
        self.assertTrue(compatibility["readable"])

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
        self.assertEqual(comparison_compatibility["status"], "current")
        self.assertEqual(comparison_compatibility["result_type"], "comparison")
        self.assertTrue(comparison_compatibility["readable"])


if __name__ == "__main__":
    unittest.main()

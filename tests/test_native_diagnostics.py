from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from analysis.growth_pathway_diagnostics import diagnostic_provenance_rows
from simulation.builder import build_run_spec
from simulation.pysdm_parcel_adapter import (
    _output_to_dataframe,
    run_pysdm_parcel_simulation,
)
from simulation.runner import run_single_experiment
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

    def test_runner_writes_native_provenance_and_threshold_metadata(self):
        cfg = _small_native_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            result_dir = run_single_experiment(cfg, Path(tmp_dir))
            provenance = json.loads(
                (result_dir / "diagnostic_provenance.json").read_text(encoding="utf-8")
            )
            metadata = json.loads(
                (result_dir / "metadata.json").read_text(encoding="utf-8")
            )
            spectrum_exists = (result_dir / "wet_radius_spectrum.csv").exists()
            robustness_exists = (result_dir / "threshold_robustness.csv").exists()

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


if __name__ == "__main__":
    unittest.main()

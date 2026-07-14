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

        self.assertFalse(any(row["provenance"] == "proxy" for row in provenance))
        self.assertEqual(metadata["native_product_build_id"], "native-parcel-products-20260714")
        self.assertEqual(
            metadata["diagnostic_radius_thresholds"]["rain_radius_um"],
            25.0,
        )


if __name__ == "__main__":
    unittest.main()

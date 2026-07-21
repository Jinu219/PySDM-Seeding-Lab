from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from netCDF4 import Dataset

from analysis.bastalias_observations import (
    BASTALIAS_DATASET_DOI,
    build_bastalias_observation_event,
    build_bastalias_threshold_sensitivity,
    detect_persistent_drizzle_onset,
    drizzle_variable_for_threshold,
    load_bastalias_netcdf,
)
from analysis.transition_observation_validation import normalize_observation_events
from scripts.extract_bastalias_drizzle_event import run_extraction


def _write_bastalias_fixture(path: Path) -> None:
    with Dataset(str(path), mode="w", format="NETCDF4") as dataset:
        dataset.createDimension("time", 6)
        time = dataset.createVariable("time", "f4", ("time",))
        time.units = "Seconds since 2020-2-5 00:00:00.0"
        time[:] = [100.0, 101.5, 103.0, 104.5, 106.0, 107.5]
        quality = dataset.createVariable("time_issue_flag", "i1", ("time",))
        quality[:] = [0, 0, 0, 0, 0, 0]
        drizzle_1 = dataset.createVariable("nb_drizzle_1", "f4", ("time",))
        drizzle_2 = dataset.createVariable("nb_drizzle_2", "f4", ("time",))
        drizzle_3 = dataset.createVariable("nb_drizzle_3", "f4", ("time",))
        drizzle_1[:] = [0, 0, 0, 0, 0, 0]
        drizzle_2[:] = [0, 0, 0, 0, 0, 0]
        drizzle_3[:] = [0, 2, 3, 2, 0, 1]
        dataset.title = "Airborne Basta L2 with Alias data"
        dataset.location = "BASTA ATR42, BARBADOS"
        dataset.system = "BASTA radar and Alias lidar"


class BastaliasObservationTests(unittest.TestCase):
    def test_netcdf_loader_and_persistent_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "bastalias_fixture.nc"
            _write_bastalias_fixture(source_path)
            frame, metadata = load_bastalias_netcdf(
                source_path,
                cloud_threshold_dbz=-20,
            )

        detection = detect_persistent_drizzle_onset(
            frame,
            window_start_s=100.0,
            window_end_s=107.5,
            minimum_drizzle_pixels=2,
            minimum_persistence_s=3.0,
        )
        self.assertEqual(metadata["drizzle_variable"], "nb_drizzle_3")
        self.assertAlmostEqual(detection["onset_time_s"], 101.5)
        self.assertAlmostEqual(detection["onset_relative_to_window_s"], 1.5)
        self.assertAlmostEqual(detection["nominal_cadence_s"], 1.5)

    def test_event_is_forced_to_spatiotemporal_proxy(self) -> None:
        frame = pd.DataFrame(
            {
                "time_s": [10.0, 11.5, 13.0, 14.5],
                "time_issue_flag": [0, 0, 0, 0],
                "drizzle_pixels": [0, 1, 1, 1],
            }
        )
        event, audit = build_bastalias_observation_event(
            frame,
            event_id="EUREC4A_F11_window_001",
            case="control",
            source_id=BASTALIAS_DATASET_DOI,
            time_units="Seconds since 2020-2-5 00:00:00.0",
            window_start_s=10.0,
            window_end_s=14.5,
            observed_uncertainty_s=2.0,
            model_time_offset_s=5.0,
            cloud_threshold_dbz=-20,
            minimum_drizzle_pixels=1,
            minimum_persistence_s=3.0,
            source_file="F11.nc",
        )
        normalized = normalize_observation_events(event)
        self.assertEqual(normalized.iloc[0]["mapping_status"], "spatiotemporal_proxy")
        self.assertAlmostEqual(normalized.iloc[0]["observed_transition_onset_s"], 1.5)
        self.assertAlmostEqual(normalized.iloc[0]["aligned_observed_onset_s"], 6.5)
        self.assertIn("moving aircraft", normalized.iloc[0]["notes"])
        self.assertEqual(audit["mapping_status"], "spatiotemporal_proxy")

    def test_threshold_sensitivity_keeps_unresolved_definitions(self) -> None:
        base = pd.DataFrame(
            {
                "time_s": [0.0, 1.5, 3.0, 4.5],
                "time_issue_flag": [0, 0, 0, 0],
                "drizzle_pixels": [0, 1, 1, 1],
            }
        )
        empty = base.assign(drizzle_pixels=0)
        sensitivity = build_bastalias_threshold_sensitivity(
            {-15: empty, -17: empty, -20: base},
            window_start_s=0.0,
            window_end_s=4.5,
            minimum_drizzle_pixels=1,
            minimum_persistence_s=3.0,
        )
        indexed = sensitivity.set_index("cloud_threshold_dbz")
        self.assertEqual(len(sensitivity), 3)
        self.assertEqual(indexed.loc[-20, "detection_status"], "resolved")
        self.assertEqual(indexed.loc[-15, "detection_status"], "unresolved")

    def test_quality_flag_breaks_persistence_and_invalid_threshold_is_rejected(self) -> None:
        frame = pd.DataFrame(
            {
                "time_s": [0.0, 1.5, 3.0, 4.5],
                "time_issue_flag": [0, 0, 1, 0],
                "drizzle_pixels": [0, 1, 1, 1],
            }
        )
        with self.assertRaisesRegex(ValueError, "No quality-valid"):
            detect_persistent_drizzle_onset(
                frame,
                window_start_s=0.0,
                window_end_s=4.5,
                minimum_drizzle_pixels=1,
                minimum_persistence_s=3.0,
            )
        with self.assertRaisesRegex(ValueError, "must be one of"):
            drizzle_variable_for_threshold(-10)

    def test_cli_package_preserves_source_hash_and_mapping_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_path = root / "bastalias_fixture.nc"
            _write_bastalias_fixture(source_path)
            output_dir = root / "observation_package"
            created = run_extraction(
                netcdf_path=source_path,
                output_dir=output_dir,
                event_id="EUREC4A_F11_window_001",
                case="control",
                window_start_s=100.0,
                window_end_s=107.5,
                observed_uncertainty_s=2.0,
                model_time_offset_s=0.0,
                cloud_threshold_dbz=-20,
                minimum_drizzle_pixels=2,
                minimum_persistence_s=3.0,
            )
            self.assertEqual(
                {path.name for path in created.iterdir()},
                {
                    "observation_events.csv",
                    "mapping_audit.json",
                    "bastalias_observation_manifest.json",
                    "bastalias_threshold_sensitivity.csv",
                },
            )
            manifest = json.loads(
                (created / "bastalias_observation_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            audit = json.loads(
                (created / "mapping_audit.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["mapping_status"], "spatiotemporal_proxy")
            self.assertEqual(len(manifest["source_sha256"]), 64)
            self.assertEqual(audit["drizzle_variable"], "nb_drizzle_3")
            sensitivity = pd.read_csv(
                created / "bastalias_threshold_sensitivity.csv"
            )
            self.assertEqual(len(sensitivity), 3)


if __name__ == "__main__":
    unittest.main()

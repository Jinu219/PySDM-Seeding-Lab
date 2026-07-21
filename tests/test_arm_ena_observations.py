from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path

import pandas as pd
from netCDF4 import Dataset

from analysis.arm_ena_observations import (
    ARM_ENA_KAZR_DATASET_DOI,
    build_arm_ena_observation_event,
    build_arm_ena_threshold_sensitivity,
    load_arm_kazr_netcdf,
)
from analysis.arm_live import (
    build_arm_query_url,
    download_arm_files,
    query_arm_file_names,
    redact_arm_url,
)
from analysis.transition_observation_validation import normalize_observation_events
from scripts.extract_arm_ena_drizzle_event import run_extraction


def _write_arm_fixture(
    path: Path,
    *,
    include_quality: bool = True,
    height_units: str = "m",
) -> None:
    with Dataset(str(path), mode="w", format="NETCDF4") as dataset:
        dataset.createDimension("time", 6)
        dataset.createDimension("range", 3)
        time = dataset.createVariable("time", "f8", ("time",))
        time.units = "seconds since 2016-11-21 00:00:00 UTC"
        time[:] = [0, 4, 8, 12, 16, 20]
        height = dataset.createVariable("range", "f4", ("range",))
        height.units = height_units
        height[:] = [0.1, 0.5, 1.0] if height_units == "km" else [100, 500, 1000]
        reflectivity = dataset.createVariable(
            "reflectivity_best_estimate", "f4", ("time", "range")
        )
        reflectivity.units = "dBZ"
        reflectivity[:] = [
            [-40, -40, -40],
            [-40, -19, -40],
            [-40, -18, -40],
            [-40, -16, -40],
            [-40, -14, -40],
            [-40, -14, -40],
        ]
        if include_quality:
            quality = dataset.createVariable(
                "qc_reflectivity_best_estimate", "i4", ("time", "range")
            )
            quality[:] = 0
        dataset.datastream = "enakazrarsclC1.c1"
        dataset.site_id = "ena"
        dataset.facility_id = "C1"


class _Response:
    def __init__(self, payload: bytes):
        self._handle = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._handle.close()

    def read(self, size: int = -1) -> bytes:
        return self._handle.read(size)


class ArmEnaObservationTests(unittest.TestCase):
    def test_loader_and_threshold_sensitivity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "arm_fixture.cdf"
            _write_arm_fixture(source)
            data, metadata = load_arm_kazr_netcdf(source)

        sensitivity = build_arm_ena_threshold_sensitivity(
            data,
            window_start_s=0,
            window_end_s=20,
            minimum_height_m=100,
            maximum_height_m=1000,
            minimum_drizzle_gates=1,
            minimum_persistence_s=8,
        ).set_index("reflectivity_threshold_dbz")
        self.assertEqual(metadata["datastream"], "enakazrarsclC1.c1")
        self.assertEqual(metadata["quality_policy"], "qc_reflectivity_best_estimate == 0")
        self.assertEqual(sensitivity.loc[-20, "detection_status"], "resolved")
        self.assertAlmostEqual(sensitivity.loc[-20, "onset_time_s"], 4.0)
        self.assertAlmostEqual(sensitivity.loc[-17, "onset_time_s"], 12.0)
        self.assertEqual(sensitivity.loc[-15, "detection_status"], "unresolved")

    def test_event_is_forced_to_fixed_column_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "arm_fixture.cdf"
            _write_arm_fixture(source)
            data, metadata = load_arm_kazr_netcdf(source)
        event, audit = build_arm_ena_observation_event(
            data,
            metadata,
            event_id="ENA_20161121_window_001",
            case="control",
            source_id=ARM_ENA_KAZR_DATASET_DOI,
            window_start_s=0,
            window_end_s=20,
            observed_uncertainty_s=4,
            model_time_offset_s=0,
            reflectivity_threshold_dbz=-20,
            minimum_height_m=100,
            maximum_height_m=1000,
            minimum_drizzle_gates=1,
            minimum_persistence_s=8,
        )
        normalized = normalize_observation_events(event)
        self.assertEqual(normalized.iloc[0]["mapping_status"], "spatiotemporal_proxy")
        self.assertAlmostEqual(normalized.iloc[0]["observed_transition_onset_s"], 4.0)
        self.assertIn("fixed Eulerian", normalized.iloc[0]["notes"])
        self.assertEqual(audit["mapping_status"], "spatiotemporal_proxy")

    def test_missing_quality_requires_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "arm_no_qc.cdf"
            _write_arm_fixture(source, include_quality=False)
            with self.assertRaisesRegex(ValueError, "missing qc_reflectivity"):
                load_arm_kazr_netcdf(source)
            _, metadata = load_arm_kazr_netcdf(
                source,
                allow_missing_quality=True,
            )
        self.assertIn("explicit quality field absent", metadata["quality_policy"])

    def test_height_kilometres_are_normalized_to_metres(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "arm_km.cdf"
            _write_arm_fixture(source, height_units="km")
            data, metadata = load_arm_kazr_netcdf(source)
        self.assertEqual(metadata["height_units"], "m (converted from km)")
        for actual, expected in zip(data["height_m"], [100.0, 500.0, 1000.0]):
            self.assertAlmostEqual(actual, expected, places=4)

    def test_extraction_package_records_hash_and_proxy_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "arm_fixture.cdf"
            output = root / "package"
            _write_arm_fixture(source)
            created = run_extraction(
                netcdf_path=source,
                output_dir=output,
                event_id="ENA_20161121_window_001",
                case="control",
                window_start_s=0,
                window_end_s=20,
                observed_uncertainty_s=4,
                model_time_offset_s=0,
                reflectivity_threshold_dbz=-20,
                minimum_height_m=100,
                maximum_height_m=1000,
                minimum_drizzle_gates=1,
                minimum_persistence_s=8,
            )
            manifest = json.loads(
                (created / "arm_ena_observation_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            event = pd.read_csv(created / "observation_events.csv")
            sensitivity = pd.read_csv(
                created / "arm_ena_threshold_sensitivity.csv"
            )
        self.assertEqual(manifest["mapping_status"], "spatiotemporal_proxy")
        self.assertEqual(len(manifest["source_sha256"]), 64)
        self.assertEqual(event.iloc[0]["mapping_status"], "spatiotemporal_proxy")
        self.assertEqual(len(sensitivity), 3)


class ArmLiveClientTests(unittest.TestCase):
    def test_query_parses_files_and_redacts_credentials(self) -> None:
        seen_urls: list[str] = []

        def opener(url: str, timeout: int):
            seen_urls.append(url)
            payload = {
                "status": "success",
                "files": [
                    "enakazrarsclC1.c1.20161121.000000.cdf",
                    {
                        "url": "https://adc.arm.gov/armlive/saveData?file="
                        "enakazrarsclC1.c1.20161121.120000.cdf"
                    },
                ],
            }
            return _Response(json.dumps(payload).encode("utf-8"))

        files = query_arm_file_names(
            user_id="researcher",
            access_token="secret-token",
            datastream="enakazrarsclC1.c1",
            start="2016-11-21",
            end="2016-11-22",
            opener=opener,
        )
        self.assertEqual(len(files), 2)
        self.assertIn("secret-token", urllib.parse.unquote(seen_urls[0]))
        self.assertNotIn("secret-token", redact_arm_url(seen_urls[0]))

    def test_query_error_message_never_contains_token(self) -> None:
        def opener(url: str, timeout: int):
            raise OSError(f"failed URL {url}")

        with self.assertRaises(RuntimeError) as context:
            query_arm_file_names(
                user_id="researcher",
                access_token="secret-token",
                datastream="enakazrarsclC1.c1",
                start="2016-11-21",
                end="2016-11-22",
                opener=opener,
            )
        self.assertNotIn("secret-token", str(context.exception))
        self.assertIn("REDACTED", str(context.exception))

    def test_download_is_atomic_and_hash_recorded(self) -> None:
        content = b"synthetic ARM NetCDF bytes"

        def opener(url: str, timeout: int):
            return _Response(content)

        with tempfile.TemporaryDirectory() as temporary_directory:
            records = download_arm_files(
                ["enakazrarsclC1.c1.20161121.000000.cdf"],
                user_id="researcher",
                access_token="secret-token",
                output_dir=temporary_directory,
                opener=opener,
            )
            output = (
                Path(temporary_directory)
                / "enakazrarsclC1.c1.20161121.000000.cdf"
            )
            partial = output.with_name(output.name + ".part")
            self.assertEqual(output.read_bytes(), content)
            self.assertFalse(partial.exists())
        self.assertEqual(records[0]["sha256"], hashlib.sha256(content).hexdigest())

    def test_query_url_rejects_unsafe_datastream(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported characters"):
            build_arm_query_url(
                user_id="researcher",
                access_token="secret-token",
                datastream="../unsafe",
                start="2016-11-21",
                end="2016-11-22",
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from analysis.columnar_cache import (
    CACHE_ENVIRONMENT_VARIABLE,
    columnar_cache_available,
    columnar_cache_paths,
    read_csv_with_columnar_cache,
)
from analysis.dashboard import safe_read_csv
from scripts.benchmark_columnar_cache import benchmark_columnar_cache


@unittest.skipUnless(columnar_cache_available(), "pyarrow is not installed")
class ColumnarCacheTests(unittest.TestCase):
    def test_cache_hit_is_numerically_identical_to_csv(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "timeseries.csv"
            pd.DataFrame(
                {
                    "time_s": [0.0, 5.0, 10.0],
                    "rain_water": [0.0, np.nan, 1.25e-5],
                    "count": [1, 2, 3],
                    "collision": [False, True, True],
                    "label": ["control", "seeded", "seeded"],
                }
            ).to_csv(source, index=False)
            expected = pd.read_csv(source)

            cache_miss_result = safe_read_csv(source)
            cache_hit_result = read_csv_with_columnar_cache(source)
            paths = columnar_cache_paths(source)
            metadata = json.loads(paths.metadata.read_text(encoding="utf-8"))

        assert_frame_equal(cache_miss_result, expected, check_exact=True)
        assert_frame_equal(cache_hit_result, expected, check_exact=True)
        self.assertEqual(metadata["row_count"], 3)
        self.assertEqual(metadata["columns"], list(expected.columns))

    def test_source_change_invalidates_stale_cache(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "comparison.csv"
            pd.DataFrame({"time_s": [0.0], "value": [1.0]}).to_csv(source, index=False)
            first = read_csv_with_columnar_cache(source)

            pd.DataFrame(
                {"time_s": [0.0, 5.0], "value": [2.0, 3.0]}
            ).to_csv(source, index=False)
            expected = pd.read_csv(source)
            refreshed = read_csv_with_columnar_cache(source)

        self.assertEqual(first["value"].tolist(), [1.0])
        assert_frame_equal(refreshed, expected, check_exact=True)

    def test_corrupt_cache_falls_back_to_csv_and_rebuilds(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "sweep_summary.csv"
            pd.DataFrame({"case": [1, 2], "score": [0.1, 0.2]}).to_csv(
                source, index=False
            )
            expected = read_csv_with_columnar_cache(source)
            paths = columnar_cache_paths(source)
            paths.parquet.write_bytes(b"not-a-parquet-file")

            recovered = read_csv_with_columnar_cache(source)
            second_hit = read_csv_with_columnar_cache(source)

        assert_frame_equal(recovered, expected, check_exact=True)
        assert_frame_equal(second_hit, expected, check_exact=True)

    def test_environment_switch_disables_cache_writes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "timeseries.csv"
            pd.DataFrame({"time_s": [0.0], "value": [1.0]}).to_csv(
                source, index=False
            )
            with patch.dict(os.environ, {CACHE_ENVIRONMENT_VARIABLE: "0"}):
                loaded = read_csv_with_columnar_cache(source)
            paths = columnar_cache_paths(source)
            cache_directory_exists = paths.directory.exists()

        self.assertEqual(loaded["value"].tolist(), [1.0])
        self.assertFalse(cache_directory_exists)

    def test_benchmark_requires_exact_dataframe_equality(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "large_timeseries.csv"
            values = np.arange(20_000, dtype=float)
            pd.DataFrame(
                {
                    "time_s": values,
                    "value": np.sin(values / 100.0),
                    "group": np.where(values % 2 == 0, "a", "b"),
                }
            ).to_csv(source, index=False)

            result = benchmark_columnar_cache(source, repeats=2)

        self.assertEqual(result["rows"], 20_000)
        self.assertEqual(result["columns"], 3)
        self.assertEqual(
            result["numerical_equality"],
            "pandas.assert_frame_equal(check_exact=True)",
        )
        self.assertGreater(result["warm_speedup_vs_csv"], 0.0)


if __name__ == "__main__":
    unittest.main()

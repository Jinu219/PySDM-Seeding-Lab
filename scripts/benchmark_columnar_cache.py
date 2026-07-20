from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from analysis.columnar_cache import (
    COLUMNAR_CACHE_BUILD_ID,
    columnar_cache_available,
    columnar_cache_paths,
    read_csv_with_columnar_cache,
)


def _elapsed(callable_):
    started = time.perf_counter()
    value = callable_()
    return value, time.perf_counter() - started


def benchmark_columnar_cache(csv_path: Path, *, repeats: int = 3) -> dict:
    """Compare raw CSV reads with cold-build and warm Parquet-cache reads."""
    source = Path(csv_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if not columnar_cache_available():
        raise RuntimeError("pyarrow is required for the columnar-cache benchmark.")

    repeats = max(int(repeats), 1)
    raw_times = []
    raw_reference = None
    for _ in range(repeats):
        dataframe, elapsed = _elapsed(lambda: pd.read_csv(source))
        raw_times.append(elapsed)
        if raw_reference is None:
            raw_reference = dataframe

    paths = columnar_cache_paths(source)
    paths.parquet.unlink(missing_ok=True)
    paths.metadata.unlink(missing_ok=True)
    cold_result, cold_seconds = _elapsed(
        lambda: read_csv_with_columnar_cache(source)
    )
    assert_frame_equal(cold_result, raw_reference, check_exact=True)

    warm_times = []
    for _ in range(repeats):
        cached, elapsed = _elapsed(lambda: read_csv_with_columnar_cache(source))
        assert_frame_equal(cached, raw_reference, check_exact=True)
        warm_times.append(elapsed)

    raw_median = float(statistics.median(raw_times))
    warm_median = float(statistics.median(warm_times))
    return {
        "build_id": COLUMNAR_CACHE_BUILD_ID,
        "source_csv": str(source),
        "source_size_bytes": int(source.stat().st_size),
        "rows": int(len(raw_reference)),
        "columns": int(len(raw_reference.columns)),
        "repeats": repeats,
        "raw_csv_seconds": raw_times,
        "raw_csv_median_seconds": raw_median,
        "cold_cache_build_seconds": float(cold_seconds),
        "warm_cache_seconds": warm_times,
        "warm_cache_median_seconds": warm_median,
        "warm_speedup_vs_csv": (
            raw_median / warm_median if warm_median > 0 else None
        ),
        "numerical_equality": "pandas.assert_frame_equal(check_exact=True)",
        "cache_parquet": str(paths.parquet),
        "cache_metadata": str(paths.metadata),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark CSV reads against the internal Parquet columnar cache."
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = benchmark_columnar_cache(args.csv_path, repeats=args.repeats)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

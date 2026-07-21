# Internal Columnar Result Cache

Last updated: 2026-07-20

## Contract

CSV remains the portable source of truth for every result. The Results Dashboard
may create an Arrow IPC copy under a hidden `.columnar_cache/` directory after it
successfully parses an eligible CSV. This file is a disposable local performance
artifact:

- it is not included in the result manifest;
- it is not used when `pyarrow` is unavailable;
- it can be deleted without losing scientific data;
- cache read/write failures fall back to the source CSV;
- CSV downloads, reports, migrations, and provenance continue to use the original
  data contract.

Automatic caching defaults to DataFrames with at least 25,000 cells
(`rows * columns`). This avoids creating cache files for small tables whose
one-time write cost is unlikely to be recovered. Override the threshold or disable
the cache entirely with:

```text
PYSDM_COLUMNAR_CACHE_MIN_CELLS=25000
PYSDM_COLUMNAR_CACHE=0
```

The benchmark command forces cache creation regardless of this threshold so a
candidate file can be evaluated before changing the default.

## Invalidation and recovery

Each cache metadata file stores the source CSV byte size and nanosecond modification
time, cache schema/build ID, row/cell counts, columns, pandas version, and Arrow
format. A cache is used only when its fingerprint matches the current CSV and its
recorded cell count meets the active threshold.

CSV parsing checks the fingerprint before and after the read. A cache is written
only when the source remained stable. Arrow and metadata updates use unique
temporary files and atomic replacement so concurrent dashboard sessions do not
expose partial files.

If Arrow data or its metadata is corrupt or incompatible, the dashboard reads CSV
and rebuilds the cache. A successful schema-v2 Arrow write also deletes disposable
schema-v1 Parquet artifacts for that source.

The size-plus-modification-time fingerprint is designed for immutable result files.
An external tool that rewrites a CSV with the exact same size while deliberately
preserving its timestamp should also delete `.columnar_cache/`.

## Numerical-equality regression

Tests cover numeric, integer, Boolean, string, and missing-value columns. Cold CSV,
warm Arrow, stale-cache refresh, corrupt data/metadata recovery, the size threshold,
and the environment opt-out are checked with:

```python
pandas.testing.assert_frame_equal(..., check_exact=True)
```

## Reproducible benchmark

Benchmark any result CSV without rerunning PySDM:

```powershell
& .\.conda\python.exe scripts\benchmark_columnar_cache.py `
  results\RESULT_DIR\timeseries.csv `
  --repeats 20 `
  --output artifacts\columnar_cache_benchmark.json
```

The benchmark reports raw CSV timings, cold cache-build time, warm cache timings,
speedup, estimated break-even read count, storage ratio, file dimensions, and the
exact-equality assertion. It deletes and rebuilds only the disposable cache for the
selected CSV; the source CSV is never modified.

The retained real-result benchmark used a 101-row by 505-column ensemble table.
Warm Arrow reads were 2.01 times faster than CSV, with an estimated break-even at
about seven total reads. Arrow used 1.247 times the CSV storage. The exploratory
Parquet version was rejected because it was slower than CSV on the same source.
See [`evidence/COLUMNAR_CACHE_BENCHMARK_20260720.md`](evidence/COLUMNAR_CACHE_BENCHMARK_20260720.md).

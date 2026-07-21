# Columnar Cache Benchmark Evidence

Date: 2026-07-20

## Question

Can the Results Dashboard accelerate repeated reads of an existing real result
without changing the scientific CSV contract or numerical values?

## Source and method

- Source: `results/20260713_163728_edited12_parameter_sweep/cases/20260713_163741_edited12_control_vs_seeding_ensemble/ensemble_statistics.csv`
- Shape: 101 rows by 505 columns (51,005 cells)
- CSV size: 564,731 bytes
- Repetitions: 20 raw reads and 20 warm-cache reads per format screening
- Equality gate: `pandas.assert_frame_equal(check_exact=True)`
- Scope: local Windows filesystem; the existing CSV was read but never modified;
  PySDM was not rerun

Timings are medians. The Parquet screening and Arrow IPC confirmation were separate
sequential local runs, so OS filesystem caching can affect absolute values. The
comparison supports this repository's format choice; it is not a universal storage
benchmark.

## Format screening

| Format | Raw CSV | Cold build/read | Warm cache | Warm / CSV | Decision |
|---|---:|---:|---:|---:|---|
| Parquet prototype | 24.981 ms | 370.801 ms | 33.058 ms | 0.756x | Rejected |
| Arrow IPC v2 | 16.271 ms | 61.597 ms | 8.076 ms | 2.015x | Selected |

The Parquet prototype made warm reads approximately 32.3% slower than its raw CSV
baseline. Arrow IPC reduced warm-read latency by approximately 50.4%. Its cold
creation cost is recovered after an estimated 6.53 total reads, rounded up to seven
for operational planning.

## Storage and policy

- Arrow cache size: 704,066 bytes
- Arrow-to-CSV size ratio: 1.2467
- Default automatic threshold: 25,000 DataFrame cells
- CSV remains the manifest, report, migration, download, and provenance source
- Arrow files and metadata remain hidden, ignored, disposable, and rebuildable

The Arrow file is larger because this IPC choice optimizes repeated local dashboard
reads rather than archival compression. Small tables remain on CSV by default; the
benchmark CLI can force a cache when evaluating a new workload.

## Reproduction

```powershell
& .\.conda\python.exe scripts\benchmark_columnar_cache.py `
  "results\20260713_163728_edited12_parameter_sweep\cases\20260713_163741_edited12_control_vs_seeding_ensemble\ensemble_statistics.csv" `
  --repeats 20 `
  --output docs\evidence\COLUMNAR_CACHE_BENCHMARK_20260720.json
```

The machine-readable evidence is retained in
[`COLUMNAR_CACHE_BENCHMARK_20260720.json`](COLUMNAR_CACHE_BENCHMARK_20260720.json).

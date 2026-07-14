# Large PySDM ensemble benchmark — 2026-07-14

## Workload

- Result: `20260714_202922_213202_ensemble_benchmark_large_single_ensemble`
- Adapter: `pysdm_parcel`
- Base configuration: `configs/marine.yaml`
- Profile: `large`
- Members: 24 successful / 24 requested
- Simulation duration: 600 s
- Timestep: 10 s
- Background super-droplets: 400
- Seeding super-droplets: 400
- Mode: single-member PySDM condensation/seeding ensemble
- Collision: OFF, inherited from the marine base configuration

The raw result is ignored by Git under `artifacts/ensemble_benchmark/`. Its
`ensemble_benchmark.json` is the machine-readable evidence source.

## End-to-end process result

| Measurement | Result |
|---|---:|
| Full run wall time | 743.878 s |
| RSS before | 111.34 MiB |
| Peak whole-process RSS | 1,110.98 MiB |
| Peak RSS increase | 999.64 MiB |
| RSS after | 1,064.70 MiB |
| RSS samples | 11,386 at 0.05 s target interval |

The process retained most of the added RSS after all members completed. This
benchmark does not identify whether the retained memory belongs to JIT caches,
PySDM/backend objects, Matplotlib/ReportLab resources, or another owner. It does
show that end-to-end repeated model execution, not the streaming statistics array,
is the dominant memory target for the next profiling pass.

## Streaming CSV aggregation result

| Measurement | Result |
|---|---:|
| Member CSV source bytes | 464,874 B (0.443 MiB) |
| Member files | 24 |
| Timesteps × output columns | 61 × 148 |
| Aggregated variables | 21 |
| CSV passes per member | 22 |
| Schema discovery | 0.152 s |
| Column streaming | 3.614 s |
| Total aggregation | 3.772 s |
| Estimated CSV bytes scanned | 10,227,228 B (9.753 MiB) |
| Estimated scan throughput | 2.586 MiB/s |
| tracemalloc peak | 583,718 B (0.557 MiB) |
| Aggregation-window RSS increase | 282,624 B (0.270 MiB) |

CSV is reparsed once for schema discovery and once per common variable. Memory use
is well bounded, but the measured throughput is low because text CSV parsing is
repeated 22 times per member. The next performance experiment should compare a
columnar member format such as Parquet against CSV while retaining CSV as the
portable publication/export artifact.

## Decision

Keep the column-streaming aggregator as the safe default: its measured incremental
RSS is negligible relative to the full process. Prioritize two follow-ups:

1. profile retained memory across members and explicitly close/release figure,
   report, PySDM, and backend objects where possible;
2. prototype a columnar internal cache to reduce repeated CSV parse time, with an
   equality regression against the canonical CSV-derived statistics.

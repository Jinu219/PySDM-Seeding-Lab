# Ensemble retained-memory ownership A/B — 2026-07-15

## Question and matched workload

The earlier 24-member benchmark showed that streaming CSV aggregation was not the
main RSS cost, but it could not distinguish Python garbage from backend/JIT memory.
Two real-PySDM runs therefore used the same `standard` workload and seeds:

- Adapter/base: `pysdm_parcel`, `configs/marine.yaml`
- Members: 12
- Duration/timestep: 300 s / 10 s
- Background/seeding super-droplets: 200 / 200
- Mode: single-run ensemble, collision OFF
- Baseline: normal interpreter garbage-collection policy
- A/B candidate: `gc.collect()` after every member

Raw results are local under `artifacts/ensemble_benchmark/`. The compact comparison
is committed as
[`ENSEMBLE_MEMORY_OWNERSHIP_20260715.json`](ENSEMBLE_MEMORY_OWNERSHIP_20260715.json).

## Results

| Measurement | Baseline | Explicit GC | Observed GC change |
|---|---:|---:|---:|
| Full wall time | 475.329 s | 493.260 s | +3.772% |
| Peak RSS increase | 878.137 MiB | 880.859 MiB | 0.310% worse |
| First-to-last member RSS increase | 252.883 MiB | 256.715 MiB | 1.515% worse |
| Member-boundary RSS slope | 23.461 MiB/member | 24.472 MiB/member | 4.291% worse |
| Aggregation-window RSS increase | 0.258 MiB | 0.262 MiB | negligible |
| Sum of per-member GC RSS drops | not requested | 198.676 MiB | event-level only |
| Maximum open Matplotlib figures | 0 | 0 | no figure accumulation |

The explicit-GC run finished with 541,305 GC-tracked objects versus 602,789 in the
baseline. It therefore did reclaim Python objects, and individual collection events
temporarily reduced RSS. However, that address space was reused or retained later:
neither peak RSS nor the member-to-member retained-RSS trend improved.

The 198.676 MiB value is a sum of separate post-member RSS drops. It must not be
interpreted as 198.676 MiB of net end-of-run memory saved because later members can
allocate the same memory again.

## Decision

1. Keep `ensemble.collect_garbage_between_members: false` as the default. The
   matched run added 3.772% wall time and did not reduce peak or retained RSS.
2. Preserve `--gc-between-members` as an opt-in diagnostic for future backend and
   PySDM version comparisons.
3. Treat GC-reclaimable Python cycles and unclosed Matplotlib figures as unsupported
   dominant explanations for this workload. This is an inference from the A/B, not
   a direct allocator-ownership measurement.
4. Prioritize PySDM/Numba/backend allocator lifetime and process isolation. A child-
   process-per-member prototype can test whether RSS returns to the operating system
   at process exit without changing numerical outputs.
5. Keep the column-streaming aggregator: both runs added about 0.26 MiB during the
   aggregation window, far below model-execution retention.

## Reproduction

```powershell
& .\.conda\python.exe scripts\run_ensemble_benchmark.py --config configs\marine.yaml --profile standard --output-dir artifacts\ensemble_benchmark --quiet
& .\.conda\python.exe scripts\run_ensemble_benchmark.py --config configs\marine.yaml --profile standard --gc-between-members --output-dir artifacts\ensemble_benchmark --quiet
& .\.conda\python.exe scripts\compare_ensemble_memory_benchmarks.py --baseline BASELINE_RESULT_DIR --explicit-gc GC_RESULT_DIR --output docs\evidence\ENSEMBLE_MEMORY_OWNERSHIP_20260715.json
```

Every benchmark result stores `ensemble_memory_checkpoints.json`, including RSS,
USS, threads, GC-tracked objects, and open figures at member and aggregation
boundaries. Results Dashboard exposes the table and member-boundary RSS/USS trend.

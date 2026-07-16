# Ensemble Execution Backend A/B Evidence

Date: 2026-07-15
Build: `ensemble-execution-backend-ab-v1-20260715`

## Question

Does one Python process per ensemble member return PySDM/Numba/backend memory to
the operating system strongly enough to justify its runtime and peak-memory cost?

## Matched workload

Both runs used the real `pysdm_parcel` pilot profile:

- 3 deterministic members (`7000`, `7017`, `7034`)
- 60 s parcel duration and 15 s timestep
- 50 background and 50 seeding super-droplets
- identical marine configuration and collision setting
- sampled parent RSS, parent-plus-live-child process-tree RSS, and member-boundary RSS

All 3 members succeeded in both runs and produced identical-size aggregation inputs
(6,142 bytes, 21 variables, 5 time rows).

## Observed A/B

| Measure | In-process | Subprocess | Difference |
|---|---:|---:|---:|
| Full wall time | 248.725 s | 530.714 s | +113.374% |
| Process-tree peak RSS increase | 879.238 MiB | 998.867 MiB | 13.606% worse |
| First-to-last parent member RSS | 37.797 MiB | 0.125 MiB | 99.669% lower |
| Aggregation time | 0.703 s | 0.617 s | secondary |
| Aggregation parent RSS increase | 0.281 MiB | 1.930 MiB | secondary |

The isolated child peak was 1,027.937 MiB maximum and 998.738 MiB median. The
three child elapsed times summed to 529.496 s, with a 170.473 s median.

## Interpretation

Process exit successfully removed almost all cross-member parent RSS retention.
This supports the ownership hypothesis that most retained memory is outside
GC-reclaimable Python cycles and is released with the PySDM/Numba/backend process.

However, the pilot paid interpreter and JIT startup for every member. It more than
doubled runtime and raised the fair parent-plus-child instantaneous peak. Therefore:

- keep `ensemble.execution_backend: in_process` as the default;
- offer `subprocess` as an opt-in retention-control mechanism;
- do not claim it lowers the instantaneous memory requirement for this workload;
- use it when long ensembles accumulate parent RSS across many members, after
  confirming that the machine can tolerate one isolated child's approximately
  1.03 GiB measured peak;
- do not launch the planned 70-execution response qualification blindly. First
  reduce the targeted axes/member count or establish warm-worker reuse that keeps
  bounded lifetime without repeating full startup for every member.

## Reproduction

```powershell
& .\.conda\python.exe scripts\run_ensemble_benchmark.py --config configs\marine.yaml --profile pilot --member-execution-backend in_process --output-dir artifacts\ensemble_backend_ab --quiet
& .\.conda\python.exe scripts\run_ensemble_benchmark.py --config configs\marine.yaml --profile pilot --member-execution-backend subprocess --output-dir artifacts\ensemble_backend_ab --quiet
& .\.conda\python.exe scripts\compare_ensemble_execution_backends.py --in-process IN_PROCESS_RESULT --subprocess SUBPROCESS_RESULT --output docs\evidence\ENSEMBLE_EXECUTION_BACKEND_AB_20260715.json
```

Raw result directories remain local under `artifacts/ensemble_backend_ab`. Compact
machine-readable evidence is preserved in
`docs/evidence/ENSEMBLE_EXECUTION_BACKEND_AB_20260715.json`.

# Higher-resolution common-seed rain-response qualification — 2026-07-15

## Why this run was needed

The earlier collision-ON `rain_standard` qualification used one random seed and a
400-super-droplet finest reference. Absolute rain state passed 5%, but only 2/21
seeding-response checks passed. A single seed could not distinguish numerical
resolution sensitivity from sampling sensitivity.

The new workflow preserves scalar metrics for every ensemble member and compares
only identical seeds between resolution cases. It never substitutes a case mean
for a paired common-random-number comparison.

## Workload

- Result: `20260715_135012_809307_qualification_rain_re_341c9e86`
- Adapter/base: `pysdm_parcel`, `configs/marine.yaml`
- Profile: `rain_response_pilot`
- Microphysics: condensation ON, collision ON, sedimentation OFF
- Design: 4-case one-factor-at-reference
- Reference: 5 s timestep, 800 seeding and 800 background super-droplets
- Next-finest levels: 10 s and 400 super-droplets
- Common random seeds: 32001, 33010, 34019
- Case-seed pairs: 12/12 complete
- Physical executions: 24/24 control/seeding runs successful
- Wall time: 956.4 s

Each result stores `paired_seed_metrics.csv` with one row per case and successful
seed. `numerical_convergence.csv` uses the seed as a condition, and the evidence
requires every configured seed in every resolution case.

## Rain-signal gate

Every 800-reference control and seeding run produced rain above `1e-8 kg/kg`:

| Seed | Control maximum | Seeding maximum | Gate |
|---:|---:|---:|---|
| 32001 | 0.002563 kg/kg | 0.002674 kg/kg | pass |
| 33010 | 0.002473 kg/kg | 0.002662 kg/kg | pass |
| 34019 | 0.002490 kg/kg | 0.002655 kg/kg | pass |

## 5% convergence result

| Metric family | Within 5% | Median | P95 | Maximum | Decision |
|---|---:|---:|---:|---:|---|
| Absolute control/seeding rain state | 36 / 36 | 0.689% | 2.275% | 2.366% | supported |
| Seeding-minus-control response | 4 / 63 | 39.093% | 239.587% | 526.314% | not supported |

All three seeds independently failed response support:

| Seed | Response checks within 5% | Median response error | Maximum response error |
|---:|---:|---:|---:|
| 32001 | 3 / 21 | 15.301% | 526.314% |
| 33010 | 1 / 21 | 39.093% | 172.408% |
| 34019 | 0 / 21 | 79.451% | 234.055% |

The background-super-droplet axis had the largest response error (526.314%),
followed by timestep (240.202%) and seeding-super-droplet count (172.408%). The
800 reference reduced the worst relative error from the previous single-seed
4613%, but it did not make the response quantitatively converged.

## Decision

1. Retain 5% support for absolute parcel rain-water state in this tested profile.
2. Do not claim a converged quantitative seeding enhancement, onset response, or
   conversion response. Every common seed failed the response family.
3. Keep `rain_response_standard` available as the planned 2.5 s / 1600-super-
   droplet / five-seed gate, but do not launch its 70 physical executions blindly.
4. First add process-per-member isolation and resource bounds, then use the pilot's
   axis ranking to define a targeted high-resolution run.
5. Preserve common-seed pairing, complete case-seed coverage, and per-seed rain
   gates as mandatory evidence requirements for future response qualification.

The raw result is intentionally ignored under `artifacts/numerical_qualification/`.
The compact machine-readable record is
[`RAIN_RESPONSE_COMMON_SEED_20260715.json`](RAIN_RESPONSE_COMMON_SEED_20260715.json).

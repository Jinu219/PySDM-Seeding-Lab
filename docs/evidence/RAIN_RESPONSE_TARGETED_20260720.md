# Targeted high-resolution common-seed rain-response qualification — 2026-07-20

## Purpose

The 800-super-droplet pilot established complete common-seed orchestration but did
not support quantitative seeding-response convergence. This targeted run tested
whether the finest and next-finest levels at 2.5/5 s and 800/1600 super-droplets
were sufficient, without paying for the 70-execution three-level profile.

## Workload and execution

- Result: `20260720_153443_866135_qualification_rain_re_8c365f71`
- Adapter/base: `pysdm_parcel`, `configs/marine.yaml`
- Profile: `rain_response_targeted`
- Microphysics: condensation ON, collision ON, sedimentation OFF
- Design: four-case one-factor-at-reference
- Reference: 2.5 s timestep, 1600 seeding and 1600 background super-droplets
- Next-finest levels: 5 s and 800 super-droplets
- Common random seeds: 32001, 33010, 34019, 35028, 36037
- Case-seed pairs: 20/20 complete
- Physical executions: 40/40 control/seeding runs successful
- Failed cases/members: 0/0
- Serial wall time: 1688.8 s (28 min 8.8 s)
- Dry-run estimate: 914.3 s; actual runtime was 1.847x the estimate

The raw result remains under ignored `artifacts/numerical_qualification/`. This
document and its adjacent JSON file are the compact tracked evidence record.

## Rain-signal gate

Every finest-reference control and seeding member exceeded the configured
`1e-8 kg/kg` rain-water floor. The minimum maxima across the five seeds were
`0.002502 kg/kg` for control and `0.002656 kg/kg` for seeding.

## Five-percent convergence result

| Metric family | Within 5% | Median | P95 | Maximum | Decision |
|---|---:|---:|---:|---:|---|
| Absolute control/seeding rain state | 60 / 60 | 0.642% | 2.305% | 4.180% | supported |
| Seeding-minus-control response | 11 / 105 | 34.350% | 296.880% | 2465.158% | not supported |

Every seed independently rejected response-family support:

| Seed | Response checks within 5% | Median response error | Maximum response error |
|---:|---:|---:|---:|
| 32001 | 4 / 21 | 40.049% | 122.472% |
| 33010 | 0 / 21 | 33.977% | 222.310% |
| 34019 | 3 / 21 | 57.979% | 2465.158% |
| 35028 | 0 / 21 | 26.595% | 494.242% |
| 36037 | 4 / 21 | 33.486% | 125.374% |

Maximum relative response differences were 1630.411% for timestep, 2272.468%
for seeding-super-droplet count, and 2465.158% for background-super-droplet count.
All absolute-state metrics passed on every axis; the instability is concentrated
in the smaller seeding-minus-control response.

## Direction is not convergence

At the finest reference, all five seeds had positive final rain enhancement. The
mean final enhancement was `1.3769e-4 kg/kg`; mean accumulated enhancement was
`0.03932`, mean seeding-efficiency score was `0.52157`, and mean
cloud-to-rain conversion delta was `0.05829`. These signs describe this finite
sample only. Their large resolution sensitivity prevents a quantitative effect
claim.

The response-estimand audit deduplicates the finest reference repeated across the
three numerical axes and reports descriptive spread over the five seeds. Final
rain enhancement, accumulated enhancement, conversion delta, and efficiency score
were positive for 5/5 seeds; supersaturation delta was negative for 5/5. Effective
radius delta had mixed signs (1 positive, 4 negative), and final droplet-number
delta was near zero for 5/5. Relative sample standard deviations ranged from
9.62% for efficiency score to 79.54% for effective-radius delta.

These are descriptive statistics, not confidence intervals or significance tests.
The audit is intentionally separate from the next-finest convergence decision.

## Decision

1. Retain 5% support for absolute control and seeding rain state in this profile.
2. Do not claim a converged quantitative seeding enhancement, onset response, or
   conversion response.
3. Do not launch the 70-execution standard profile merely to seek a passing result;
   all five seeds and all three numerical axes already reject response support.
4. Use the implemented estimand audit to keep finite-seed direction and spread
   separate from resolution convergence. Observational validation of the operational
   transition floor remains an independent gate.

Machine-readable evidence:
[`RAIN_RESPONSE_TARGETED_20260720.json`](RAIN_RESPONSE_TARGETED_20260720.json).

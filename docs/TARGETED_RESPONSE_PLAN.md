# Targeted High-Resolution Rain-Response Plan

Date: 2026-07-16

## Purpose

The three-seed `rain_response_pilot` supported absolute parcel rain-water state
but did not support the smaller seeding-minus-control response. The full
`rain_response_standard` profile contains 7 OFAT cases, 5 common seeds, and 70
physical control/seeding executions. This targeted plan retains only the finest
and next-finest level on each numerical axis before that larger plan is considered.

## Planned workload

Profile: `rain_response_targeted`

| Item | Plan |
|---|---:|
| Timestep levels | 2.5 s, 5 s |
| Seeding super-droplet levels | 800, 1600 |
| Background super-droplet levels | 800, 1600 |
| OFAT cases | 4 |
| Common random seeds | 5 |
| Case-seed pairs | 20 |
| Control/seeding executions | 40 |

The finest reference is 2.5 s with 1600 seeding and 1600 background
super-droplets. Each of the other three cases changes exactly one axis to its
next-finest level. Compared with the 70-execution standard profile, this reduces
the planned physical workload by 42.9% while retaining one same-seed convergence
comparison for every numerical axis.

## Dry-run-first safety policy

Generate and inspect the plan without starting PySDM:

```powershell
& .\.conda\python.exe scripts\run_numerical_qualification.py `
  --config configs\marine.yaml `
  --profile rain_response_targeted `
  --adapter pysdm_parcel `
  --dry-run
```

The plan prints the case count, common seeds, model execution count, and a local
serial-runtime estimate. The targeted profile forces `execution.max_workers: 1`
so server parallelism is not introduced into this scientific gate.

The runtime value is based on the recent adapter-level median and is not scaled
for the 1600-super-droplet reference. It may underestimate the physical workload
and is included for planning, not as a scheduling guarantee.

Running without `--dry-run` is rejected before any model starts. A future physical
execution requires the explicit `--confirm-targeted-run` flag after the plan and
resource budget have been reviewed.

## Interpretation boundary

This commit adds and verifies the plan only; it does not generate new physical
evidence. Existing conclusions remain unchanged:

- absolute collision-ON parcel rain-water state is supported for the tested profile;
- quantitative seeding enhancement, onset shift, and conversion response remain
  unsupported;
- sedimentation is disabled, so this is not a surface-precipitation claim.

# Numerical qualification evidence — 2026-07-14

## Workload

- Result: `20260714_200131_749732_qualification_standard_parameter_sweep`
- Adapter: `pysdm_parcel`
- Base configuration: `configs/marine.yaml`
- Profile: `standard`
- Grid: timestep 5/10/15 s × seeding super-droplets 100/200/400 ×
  background super-droplets 100/200/400
- Cases: 27 control-versus-seeding pairs
- PySDM model executions: 54
- Failed cases: 0
- Wall time observed by the command runner: 1,652 s
- Microphysics: condensation ON, collision OFF, sedimentation OFF

The raw result is intentionally ignored by Git under
`artifacts/numerical_qualification/`. It contains the exact config, case results,
convergence table, reports, and `qualification_evidence.json`.

## 5% tolerance result

The next-finest level was compared with the finest reference while the other two
resolution axes remained at their finest values.

| Evidence item | Result |
|---|---:|
| Next-finest checks | 24 |
| Non-zero relative-evidence checks | 12 |
| Near-zero reference checks excluded from percentage support | 12 |
| Non-zero checks within 5% | 12 / 12 |
| Median relative difference | 0.187% |
| P95 relative difference | 1.140% |
| Maximum relative difference | 1.731% |

Maximum relative difference by numerical axis:

| Axis | Maximum |
|---|---:|
| timestep | 0.559% |
| seeding super-droplets | 1.731% |
| background super-droplets | 0.00335% |

The non-zero evidence comes from final effective-radius response, droplet-number
response, activated-water response, and supersaturation response. Rain enhancement,
rain conversion, and efficiency values were zero in this collision-OFF profile and
were therefore not counted as percentage-based support.

## Decision

Keep the default numerical-convergence tolerance at 5% for now. The observed P95
and maximum are comfortably below 5%, so lowering the global default from this one
profile would overstate the evidence.

This is scoped support, not a universal PySDM tolerance. A collision-ON,
rain-producing qualification is still required before applying the same conclusion
to rain enhancement or precipitation-onset claims. Near-zero metrics must continue
to be reviewed using absolute differences.

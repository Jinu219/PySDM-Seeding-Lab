# Collision-ON rain qualification evidence — 2026-07-15

## Workload

- Result: `20260715_104805_311792_qualification_rain_st_c1d20281`
- Adapter: `pysdm_parcel`
- Base configuration: `configs/marine.yaml`
- Profile: `rain_standard`
- Design: one-factor-at-reference (OFAT)
- Reference: 5 s timestep, 400 seeding super-droplets, 400 background
  super-droplets
- Next-finest: 10 s timestep and 200 super-droplets on each resolution axis
- Cases: 7 control-versus-seeding pairs
- PySDM model executions: 14
- Failed cases: 0
- Wall time observed by the command runner: 699 s
- Microphysics: condensation ON, collision ON, sedimentation OFF

The OFAT design executes one finest reference plus the two lower levels on each
of the three numerical axes. It replaces a 27-case Cartesian grid that contained
20 combinations unused by the convergence decision.

## Rain-production gate

The finest reference generated rain well above the configured `1e-8 kg/kg`
signal floor:

| Reference signal | Result |
|---|---:|
| Control maximum/final rain-water mixing ratio | 0.002558 kg/kg |
| Seeding maximum/final rain-water mixing ratio | 0.002634 kg/kg |
| Control rain onset | 355 s |
| Seeding rain onset | 395 s |
| Final seeding-minus-control rain water | 0.0000763 kg/kg (+2.98%) |

This is a collision/coalescence rain-water result inside the parcel. Sedimentation
is not connected, so it is not a surface-precipitation qualification.

## 5% result by metric family

| Metric family | Checks within 5% | Median | P95 | Maximum | Decision |
|---|---:|---:|---:|---:|---|
| Absolute control/seeding rain state | 12 / 12 | 1.431% | 3.285% | 3.285% | Supported for this profile |
| Seeding-minus-control response | 2 / 21 | 109.166% | 3514.452% | 4613.006% | Not supported |

The absolute rain-water state is converged within the existing 5% tolerance at
the next-finest levels. The smaller difference between two collision simulations
is not numerically stable at the same resolution. Large response percentages are
not treated as evidence that the absolute rain state failed; they show that the
seeding effect is much more resolution-sensitive than either state separately.

## Decision

1. Retain 5% as the absolute-state quality threshold for the tested collision-ON
   marine parcel profile.
2. Do not use the current 400-super-droplet / 5-second reference as quantitative
   convergence evidence for seeding enhancement, onset shift, or conversion delta.
3. Keep result-level evidence status as `not_supported_for_profile` until every
   required response family passes; expose the supported absolute-state family
   separately in reports and Results.
4. Next test the response with higher super-droplet resolution and multiple common
   random seeds before considering a publication-facing seeding-effect claim.

The raw result remains local under `artifacts/numerical_qualification/`; the exact
configuration, all case outputs, convergence table, reports, and machine-readable
`qualification_evidence.json` are stored there.

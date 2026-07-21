# v1.0 Scientific Scope

v1.0 is a reproducible **research workflow release** for warm-cloud parcel
experiments. It is not a validated field-efficacy model and does not provide an
externally calibrated drizzle-transition threshold.

The machine-readable source of truth is `release/v1_scientific_scope.json`. Check
it with:

```powershell
& .\.conda\python.exe scripts\check_scientific_scope.py
```

## Supported claim

For the reviewed `rain_response_targeted` collision-ON marine parcel profile, the
absolute control and seeding rain-water state passed every finest-versus-next-finest
5% comparison. This statement is restricted to the tested cases, resolutions, and
five common seeds. It does not establish a converged seeding response magnitude.

## Descriptive observation only

All five finest-reference seeds had positive final seeding-minus-control rain
direction. The response convergence gate nevertheless passed only 11 of 105 checks,
and every seed independently rejected quantitative response support. Direction is
therefore reported descriptively and cannot be interpreted as an effect estimate.

## Operational definition only

The 1% rain-liquid fraction marks an internal spectrum-transition event. It remains
paired with 0.5/1/2% fraction, 20/25/30 micrometre radius, and cadence sensitivity.
It is not an observational standard or a universal onset threshold.

## Explicitly unsupported claims

v1.0 does not support:

- a quantitative seeding enhancement magnitude;
- external calibration or validation of the 1% transition floor;
- real-world cloud-seeding efficacy, causal impact, or operational rainfall gain.

BASTALIAS is a moving-platform spatiotemporal sample. ARM ENA KAZR observes a fixed
Eulerian column through which different parcels advect. Neither dataset supplies
the same Lagrangian parcel history used by the model, and radar reflectivity is not
the model-native rain-liquid fraction. The ARM product itself is intended as a
time-height column product, while the ENA retrieval study notes the challenges of
quantitative evaluation without coincident in-cloud drizzle observations:

- <https://www.arm.gov/data/science-data-products/vaps/kazrarscl>
- <https://doi.org/10.5194/amt-13-1485-2020>

## v1.0 disposition

The direct-observation investigation is complete for v1.0 as a feasibility and
scope decision, not as successful external validation. External calibration remains
future research and cannot be silently promoted into a release claim. This bounded
disposition lets the software release finish without converting unavailable
scientific evidence into a positive result.

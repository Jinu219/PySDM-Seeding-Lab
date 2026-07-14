# Spectrum transition diagnostic basis

Last reviewed: 2026-07-14

## Decision

The diagnostic keeps a baseline rain-size wet-radius boundary of 25 µm and an
operational transition level of 1% rain-size liquid volume among activated liquid.
These two numbers do not have the same evidential status:

- The 20–25 µm cloud/drizzle boundary is supported by aircraft and remote-sensing
  literature. The existing 0.8/1.0/1.2 radius factors therefore audit 20, 25, and
  30 µm boundaries.
- No reviewed source establishes 1% of activated liquid as a universal observed
  drizzle-onset threshold. It remains a project-owned detection floor. New results
  must audit 0.5%, 1%, and 2% fraction levels and report whether the onset-shift
  direction survives that choice.
- Automatic spectrum checkpoints now use a 10 s target interval, snapped to the
  model timestep, with injection boundaries and endpoints inserted exactly. This is
  an onset-diagnostic cadence, not a claim that the parcel model reproduces radar
  sampling.

## Primary evidence

Gerber (1996) separated drizzle liquid water using droplets above 20 µm radius and
reported an experimental coalescence threshold near 19 µm:

- https://doi.org/10.1175/1520-0469(1996)053%3C1649:MOMSCW%3E2.0.CO;2

Stephens and Haynes (2007) describe accretion using drizzle droplets exceeding
20 µm radius:

- https://doi.org/10.1029/2007GL030259

Aircraft measurements in an ACP study used 25 µm as the cloud/drizzle cutoff, with
the instrument bin spanning approximately 20–32 µm:

- https://doi.org/10.5194/acp-12-8223-2012

Lim et al. (2025) describe the 15–40 µm warm-rain size gap and show that rain
initiation depends on both precipitation-embryo size and number. This supports
treating a radius boundary alone as insufficient evidence:

- https://doi.org/10.5194/acp-25-5313-2025

Acquistapace et al. (2017) found drizzle radar structure was best retained near a
2 s integration, while 10 s averaging smeared extremes; many European systems used
10 s integration. The project uses 10 s as a practical upper target and exposes it
as a configurable model-output cadence:

- https://doi.org/10.5194/amt-10-1783-2017

## Interpretation rule

A transition result is suitable for discussion only when the stored result reports:

1. the baseline 25 µm / 1% onset for control and seeding;
2. radius sensitivity across the configured 20–30 µm range;
3. fraction sensitivity across 0.5–2%;
4. checkpoint maximum interval and interpolation method; and
5. direction consistency or an explicit statement that the conclusion changes.

The diagnostic remains an instantaneous radius-bin classification. It is not a
particle-history activation event and is not interchangeable with radar reflectivity,
absolute drizzle liquid-water content, or surface precipitation onset.

# ARM ENA Fixed-Column Candidate Audit — 2026-07-21

## Decision

ARM ENA KAZR/KAZRARSCL is accepted as the next real-observation ingestion target,
but not as direct-temporal parcel validation. The implemented importer therefore
forces every extracted event to `spatiotemporal_proxy`.

## Source review

- ARM describes KAZRARSCL as a fixed-site time-height product combining radar,
  ceilometer, lidar, radiometer, radiosonde, and surface precipitation information.
  Its standard grid is approximately 4 s by 30 m, and ARM cautions that absolute
  reflectivity calibration is not guaranteed for quantitative use.
- Cadeddu et al. (2020) report native ENA KAZR sampling at 2 s by 20 m and analyze
  precipitating stratocumulus on 21 November 2016. Their retrieval combines radar,
  lidar, and microwave observations and explicitly discusses assumptions and
  quantitative validation limitations.
- The ARM Live Data Web Service supports authenticated machine-to-machine query and
  download, while archive-only files may still require a regular ARM order.

Primary sources:

- <https://www.arm.gov/data/science-data-products/vaps/kazrarscl>
- <https://doi.org/10.5194/amt-13-1485-2020>
- <https://doi.org/10.5439/1213419>
- <https://armlive.svcs.arm.gov/>

## Implemented evidence controls

- Credentials are read only from `ARM_USER_ID` and `ARM_ACCESS_TOKEN`; query URLs
  are redacted in errors and never printed.
- Downloads use a temporary `.part` file, atomic replacement, full byte size, and
  SHA-256 recording.
- The importer accepts documented reflectivity aliases, requires matching QC by
  default, checks the time-height array shape, and restricts the selected heights.
- Event extraction requires a persistent number of quality-valid radar gates and
  writes -20/-17/-15 dBZ threshold sensitivity.
- The immutable package records the original source hash, metadata, mapping audit,
  normalized observation contract, and threshold audit.

## Why the v1.0 gate remains open

A fixed zenith beam observes an Eulerian column. Horizontal wind continuously
changes which air parcels occupy that column, so elapsed radar time is not yet the
parcel age used by the simulation. Radar reflectivity is also dominated by large
drops and is not equal to the model-native rain-liquid fraction. Timing uncertainty
alone cannot cover those representativeness and observable-mapping differences.

The remaining promotion evidence is therefore:

1. an independently reviewed parcel trajectory or residence-time mapping;
2. a microphysical mapping from the measured observable to the modeled transition;
3. combined timing, retrieval, and representativeness uncertainty;
4. a pre-declared model-time origin and event definition.

No ARM credentials or real ARM data file were available in this implementation
checkpoint. Tests use a synthetic ARM-format NetCDF solely to verify software
behavior; they are not scientific evidence.

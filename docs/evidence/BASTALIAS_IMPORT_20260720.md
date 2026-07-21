# EUREC4A BASTALIAS Import Evidence — 2026-07-20

## Source

- Dataset: EUREC4A ATR42 BASTALIAS L2 radar–lidar product
- DOI: <https://doi.org/10.25326/316>
- File: `EUREC4A_ATR42_BASTALIAS_F11_20200205_b_L2_v2.0_a_L1.5_v1.4.nc`
- File size: 196,977,022 bytes
- SHA-256: `d70a9d5fa57e193ac6de790db4e5643a34892b41e1a5ef7f3e472a0ba16f0b7d`
- Time units: `Seconds since 2020-2-5 00:00:00.0`
- Source metadata title: `Airborne Basta L2 with Alias data`
- Platform/location: ATR42, Barbados

The raw NetCDF and generated packages are ignored local artifacts. This compact
record preserves the source identity, reviewed extraction choices, and result.

## Reviewed extraction

- Window: 35,400–36,000 s (09:50–10:00 UTC)
- Window samples: 400
- `time_issue_flag == 0`: 400 / 400
- Minimum drizzle pixels: 1
- Minimum persistence: 3 s
- Nominal cadence: 1.5 s
- User-supplied timing uncertainty: 1.5 s
- Model time offset: 0 s, used only to exercise the comparison pipeline

The uncertainty is a timing value only. It excludes spatial representativeness and
parcel-mapping uncertainty. The zero model offset is not a physically established
alignment between the aircraft window and simulation start.

## Threshold sensitivity

| Cloud–drizzle boundary | Variable | Status | Onset from window start | Positive samples |
|---|---|---|---:|---:|
| −15 dBZ | `nb_drizzle_1` | resolved | 10.121 s | 114 |
| −17 dBZ | `nb_drizzle_2` | resolved | 7.121 s | 115 |
| −20 dBZ | `nb_drizzle_3` | resolved | 7.121 s | 119 |

The selected −20 dBZ event began at source time 35,407.121 s and remained detected
through 35,410.121 s for the required 3 s. The 3 s spread across classification
boundaries is retained as a diagnostic, not as parcel-model threshold validation.

## Mapping decision

The importer emitted:

```text
evidence_class = observation
mapping_status = spatiotemporal_proxy
```

The resulting row was compared with all 27 model threshold candidates. The workflow
correctly returned `observational_mapping_review_required` and zero direct-temporal
rows. Candidate error rankings from this exercise have no scientific fit meaning
because the moving aircraft samples different horizontal volumes and the model time
offset is not physically established.

Decision: retain BASTALIAS as a real-data ingestion and classification-sensitivity
case. Do not use it to validate or revise the operational 1% rain-liquid floor. The
external validation gate remains open for a dataset with defensible direct temporal
sampling and parcel-time alignment.

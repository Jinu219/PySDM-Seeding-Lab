# EUREC4A BASTALIAS Observation Import

## Dataset choice

The importer targets the EUREC4A ATR42 BASTALIAS L2 radar–lidar product:

- Dataset DOI: <https://doi.org/10.25326/316>
- Data directory: <https://observations.ipsl.fr/aeris/eurec4a-data/AIRCRAFT/ATR/BASTALIAS/PROCESSED/>
- Dataset description: <https://doi.org/10.5194/essd-14-2021-2022>

The product combines horizontally pointing airborne radar and lidar observations at
approximately 1.5 s resolution. It stores `time`, `time_issue_flag`, and drizzle
pixel counts for three cloud–drizzle reflectivity boundaries:

| Boundary | NetCDF variable |
|---|---|
| −15 dBZ | `nb_drizzle_1` |
| −17 dBZ | `nb_drizzle_2` |
| −20 dBZ | `nb_drizzle_3` |

The −20 dBZ definition is the importer default, but −15 and −17 dBZ remain
selectable so observational classification sensitivity is not hidden.

## Install and extract

The large source NetCDF files are not committed to this repository. Download a
selected file from the public data directory, then install the optional reader:

```powershell
& .\.conda\python.exe -m pip install -r requirements-observations.txt
```

Choose a reviewed time window and make every time-axis assumption explicit:

```powershell
& .\.conda\python.exe scripts\extract_bastalias_drizzle_event.py `
  --netcdf path\to\EUREC4A_ATR42_BASTALIAS_F11_20200205_b_L2_v2.0_a_L1.5_v1.4.nc `
  --event-id EUREC4A_F11_reviewed_window `
  --case control `
  --window-start-s 35400 `
  --window-end-s 36000 `
  --observed-uncertainty-s 1.5 `
  --model-time-offset-s 0 `
  --cloud-threshold-dbz -20 `
  --minimum-drizzle-pixels 1 `
  --minimum-persistence-s 3
```

The window is expressed in the source file's `time` units. Timing uncertainty and
model offset are required rather than inferred. The output package contains the
normalized observation-contract row, a mapping audit, and a manifest with the full
source-file SHA-256 hash. It also evaluates the same event rule at −15, −17, and
−20 dBZ and stores every resolved or unresolved onset in
`bastalias_threshold_sensitivity.csv`.

## Detection and quality rule

The event is the first sequence inside the selected window for which:

1. `time_issue_flag == 0`;
2. the selected `nb_drizzle_*` count meets the pixel threshold;
3. detections are contiguous at the file's nominal cadence; and
4. the sequence lasts at least the requested persistence time.

A quality failure, non-detection, or large time gap breaks persistence. The event
time is stored relative to the selected window start.

## Mandatory interpretation boundary

BASTALIAS observes different horizontal volumes as the aircraft moves. A persistent
sequence can therefore mix spatial structure and temporal evolution. The importer
always emits:

```text
evidence_class = observation
mapping_status = spatiotemporal_proxy
```

Neither CLI options nor CSV editing can make this product a direct temporal history
of one parcel. Candidate scores produced from it are a mapping diagnostic only and
cannot validate or calibrate the model's operational 1% rain-liquid floor. A direct
validation still requires an observational time series whose sampled volume and
time origin can be defensibly mapped to the parcel simulation.

`observed_uncertainty_s` is user-supplied timing uncertainty only. It does not
include spatial representativeness or parcel-mapping uncertainty; the mapping audit
records this limitation explicitly.

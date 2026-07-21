# ARM ENA Fixed-Column Observation Import

This workflow prepares a quality-audited drizzle-onset **proxy** from a local ARM
Eastern North Atlantic (ENA) Ka-band zenith radar NetCDF file. It is closer to a
temporal comparison than the moving-aircraft BASTALIAS sample, but it does not by
itself close the v1.0 direct-temporal validation gate.

## Why this candidate is useful

The ARM KAZR is a vertically pointing fixed-site radar. The ENA study by Cadeddu
et al. reports 2 s and 20 m native KAZR sampling and analyzes precipitating marine
stratocumulus on 21 November 2016. The KAZRARSCL value-added product provides
quality-controlled time-height reflectivity and cloud boundaries at fixed sites.

Sources:

- ARM KAZR dataset: <https://doi.org/10.5439/1213419>
- Cadeddu et al. (2020): <https://doi.org/10.5194/amt-13-1485-2020>
- ARM KAZRARSCL product: <https://www.arm.gov/data/science-data-products/vaps/kazrarscl>
- ARM Live Data Web Service: <https://armlive.svcs.arm.gov/>

ARM requires a free user account for data access. Copy the exact datastream name
from ARM Data Discovery rather than guessing it from a paper citation.

## Credential-safe data retrieval

Credentials are accepted only through environment variables so they do not appear
in process arguments or committed command history:

```powershell
$env:ARM_USER_ID = "your-arm-user-id"
$env:ARM_ACCESS_TOKEN = "your-arm-access-token"

& .\.conda\python.exe scripts\fetch_arm_live_data.py `
  --datastream <exact-datastream-from-data-discovery> `
  --start 2016-11-21 `
  --end 2016-11-22
```

The default command lists matching files. Add `--download` to store immutable
source files under the ignored `artifacts/arm_ena_observations/source` directory.
The client never prints the credential-bearing request URL and removes partial
files after a failed transfer. ARM notes that data not present on its live disk may
need a regular archive order instead.

Remove the environment variables after the download:

```powershell
Remove-Item Env:ARM_USER_ID
Remove-Item Env:ARM_ACCESS_TOKEN
```

## Extract a fixed-column event

After inspecting the NetCDF time coordinate and choosing a scientifically reviewed
window, run:

```powershell
& .\.conda\python.exe scripts\extract_arm_ena_drizzle_event.py `
  --netcdf artifacts\arm_ena_observations\source\<file>.cdf `
  --event-id ENA_20161121_window_001 `
  --case control `
  --window-start-s <seconds-in-file> `
  --window-end-s <seconds-in-file> `
  --observed-uncertainty-s <reviewed-value> `
  --model-time-offset-s <reviewed-value>
```

The importer requires a matching `qc_<reflectivity>` field by default, limits the
height range, detects persistent threshold crossings, and audits -20/-17/-15 dBZ
sensitivity. `--allow-missing-quality` is an explicit weaker mode and is recorded
in the package metadata.

The immutable package contains:

- `observation_events.csv`
- `arm_ena_threshold_sensitivity.csv`
- `mapping_audit.json`
- `arm_ena_observation_manifest.json`, including the full source SHA-256

## Mandatory interpretation boundary

The output is always `spatiotemporal_proxy`. A fixed zenith beam is Eulerian: wind
advects different parcels through the sampled column. Radar reflectivity is also a
sixth-moment-weighted signal, not the parcel model's rain-liquid fraction. A
reflectivity threshold therefore identifies a persistent column echo proxy, not a
particle-history transition.

Promotion to `direct_temporal` requires independent evidence for all of the
following:

1. the sampled air-parcel trajectory and residence time;
2. the mapping from radar observables to the model-native transition quantity;
3. timing, retrieval, and representativeness uncertainty;
4. a pre-declared event definition and model-time origin.

Until those points are reviewed, candidate timing scores cannot validate or revise
the operational 1% model floor.

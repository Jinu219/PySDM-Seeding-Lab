# Transition Observation Validation

This workflow aligns externally defined drizzle-transition events with every
threshold candidate stored in a control-versus-seeding result. It is a comparison
layer: it does not rewrite the simulation result or automatically calibrate the
project's operational 1% rain-liquid floor.

## Observation event CSV contract

Each row represents one event and one model case. The required columns are:

| Column | Meaning |
|---|---|
| `event_id` | Stable event identifier; unique together with `case` |
| `case` | `control` or `seeding` |
| `observed_transition_onset_s` | Onset time relative to the stated observational origin |
| `observed_uncertainty_s` | Non-negative timing uncertainty used for the within-uncertainty audit |
| `model_time_offset_s` | Offset added to the observed time to align it with simulation time |
| `time_origin` | Explicit timing origin, such as `simulation_start` |
| `source_id` | DOI, URL, dataset identifier, or other traceable provenance |
| `evidence_class` | Exactly `observation` or `synthetic` |
| `observation_method` | Instrument, retrieval, or synthetic method |
| `event_definition` | Explicit rule used to declare onset |
| `sampling_context` | Temporal, spatial, or spatiotemporal sampling description |
| `mapping_status` | `direct_temporal`, `spatiotemporal_proxy`, `unresolved`, or `synthetic_workflow` |

An optional `notes` column is preserved. Aligned onset is calculated as:

```text
aligned_observed_onset_s = observed_transition_onset_s + model_time_offset_s
```

Negative aligned times, missing provenance or mapping fields, duplicate event/case
rows, and unknown evidence classes are rejected. Synthetic evidence must use
`synthetic_workflow`; observational evidence cannot use it. The Results Dashboard
provides a downloadable CSV template in its Spectrum-based transition onset section.

## Run the standalone comparison

Use a completed comparison directory containing
`spectrum_transition_onset_robustness.csv`:

```powershell
& .\.conda\python.exe scripts\validate_transition_observations.py `
  --result-dir results\<comparison-result> `
  --observations path\to\observation_events.csv
```

By default, the command creates a new immutable package under
`artifacts/transition_observation_validation/`. Pass `--output-dir` to choose a
different new directory. An existing output directory is never overwritten.

The package contains normalized observation rows, every event-by-candidate
comparison, descriptive candidate scores, a JSON summary, Markdown report, and a
manifest with SHA-256 hashes of both input files.

## Interpretation boundary

Candidate scores rank stored definitions by onset error, RMSE, and the fraction of
resolved comparisons within reported timing uncertainty. The lowest-MAE candidate
is descriptive. It is not a confidence interval, significance test, universal
calibration, or proof that a radius-bin transition equals an observed
particle-history event.

Rows marked `synthetic` validate only the software workflow. A scientific review
requires rows marked `observation` with defensible source provenance, time-origin
mapping, uncertainty, representativeness, and a documented relationship between
the measured event and the model-native rain-liquid fraction.

Only `direct_temporal` rows receive the `observational_comparison_available` workflow
status. Spatial or moving-platform datasets remain
`observational_mapping_review_required` even though their measurements are real.
The EUREC4A BASTALIAS importer and its mandatory proxy boundary are documented in
[`BASTALIAS_OBSERVATION_IMPORT.md`](BASTALIAS_OBSERVATION_IMPORT.md).

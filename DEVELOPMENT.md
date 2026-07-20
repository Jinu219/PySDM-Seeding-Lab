# Development Notes

## 2026-07-20 - Finite v1.0 release gate

- Added a machine-readable `release/v1.0.0.json` gate with five ordered required
  milestones and one explicit scientific blocker.
- Added `scripts/check_release_readiness.py` for human-readable and JSON reports;
  its default non-zero status prevents an incomplete v1.0 from being mistaken for
  a release-ready build.
- Added regression and CI coverage for gate ordering, evidence paths, dependency
  completion, and overall readiness consistency.
- Deferred serial versus 4/8-worker server scaling to v1.1 so it cannot silently
  expand the v1.0 finish line.
- Established the publication boundary: routine commits may reach `develop`, but
  work pauses for the Build the Lab blog before `develop` is merged into `main` and
  tagged `v1.0.0`.

## EUREC4A BASTALIAS observation importer

Changes:
- Extended the transition-observation contract with method, event definition,
  sampling context, and mapping status. Synthetic rows and observational rows now
  have compatible-but-distinct mapping states.
- Added a local NetCDF importer for the public EUREC4A ATR42 BASTALIAS L2 product,
  with lazy optional `netCDF4` dependency loading.
- Added quality-valid persistent drizzle detection for the documented
  `nb_drizzle_1`, `nb_drizzle_2`, and `nb_drizzle_3` variables and automatic
  −15/−17/−20 dBZ onset sensitivity output.
- Added immutable observation packages containing the normalized CSV, mapping audit,
  threshold sensitivity, full source SHA-256, and source metadata.
- Results now distinguishes direct temporal observations from spatial or
  spatiotemporal proxies before presenting candidate scores.

Real-data verification:
- Downloaded the official 196,977,022-byte F11 NetCDF and verified SHA-256
  `d70a9d5fa57e193ac6de790db4e5643a34892b41e1a5ef7f3e472a0ba16f0b7d`.
- The reviewed 09:50–10:00 UTC window contained 400 quality-valid samples. A 3 s
  persistent onset resolved at 10.121 s for −15 dBZ and 7.121 s for −17/−20 dBZ.
- The model comparison correctly remained `observational_mapping_review_required`
  with zero direct-temporal rows. No 1% floor calibration claim is supported.

Scientific boundary:
- BASTALIAS is a moving-aircraft horizontal sample. Its event is always emitted as
  `spatiotemporal_proxy`; neither timing precision nor threshold consistency converts
  it into temporal evolution of one parcel.
- The user-supplied timing uncertainty excludes spatial representativeness and
  parcel-mapping uncertainty.

Validation:
- All 55 fast CI regressions, dependency checks, project integrity, and diff checks
  passed locally.
- Results AppTest rendered with zero exceptions and zero error elements.
- A real F11 observation package and a 27-candidate comparison package completed;
  the latter retained `observational_mapping_review_required` as designed.

Evidence: `docs/evidence/BASTALIAS_IMPORT_20260720.md`

## Observational transition-comparison workflow

Changes:
- Added a strict event/case observation CSV contract with onset uncertainty,
  model-time offset, time origin, source provenance, and explicit
  `observation`/`synthetic` evidence class.
- Added event-by-threshold onset errors, within-uncertainty checks, and descriptive
  candidate MAE/median/RMSE summaries across the existing robustness definitions.
- Added a standalone artifact builder that preserves normalized inputs, detailed
  comparisons, candidate scores, JSON summary, Markdown report, and a manifest with
  SHA-256 input hashes without mutating the source simulation result.
- Added Results Dashboard template upload, evidence-boundary warnings, tables, and
  CSV/JSON downloads.
- Added synthetic workflow regression coverage. Synthetic data is explicitly barred
  from observational interpretation.

Scientific boundary:
- The lowest-error threshold candidate is descriptive, not a universal calibration,
  confidence interval, significance result, or proof of event-definition equivalence.
- External validation remains pending until a real dataset supplies traceable source,
  event definition, time-origin mapping, uncertainty, and representativeness.

Validation:
- All 50 fast CI regressions and project integrity passed locally.
- Results AppTest rendered with zero exceptions and zero error elements.
- The standalone command compared the synthetic fixture with 27 candidates from a
  completed real-PySDM result, wrote 54 detailed comparisons, and retained the
  `synthetic_workflow_only` status.

## Targeted high-resolution common-seed qualification

Execution and evidence:
- Completed the explicitly authorized `rain_response_targeted` profile with real
  `pysdm_parcel`: four OFAT cases, five common seeds, 20 case-seed pairs, and 40/40
  successful control/seeding model runs.
- The serial run finished in 1688.8 s (28 min 8.8 s), 1.847x the adapter-level
  dry-run estimate. No case or ensemble member failed.
- Every seed produced control and seeding rain above the configured floor, and
  common-seed case coverage was complete.
- Absolute rain state passed 60/60 next-finest checks at 5% (maximum 4.180%).
- Seeding response passed only 11/105 checks (median 34.350%, maximum 2465.158%);
  every seed independently rejected response support.
- The finest reference produced positive final rain enhancement for 5/5 seeds,
  but effect direction is not treated as convergence or publication support.

Decision:
- Retain profile-scoped support for absolute rain state only.
- Do not escalate to the 70-execution standard profile as a way to seek a passing
  response result. Diagnose response estimands and uncertainty before more costly
  resolution expansion.

Follow-up implementation:
- Added `response_estimand_audit` to qualification evidence. It deduplicates the
  finest reference repeated across numerical axes and records per-metric seed
  values, mean, sample standard deviation, standard error, range, near-zero count,
  and direction consistency.
- The Results Dashboard renders the audit separately from numerical-convergence
  support and labels it as descriptive rather than inferential evidence.
- Resumed the completed result in place: all 20 members were reused, 0 reran, and
  the updated evidence and reports were rebuilt without a physical model execution.
- All 46 fast regression tests and project integrity passed. Results AppTest
  rendered with zero exceptions and zero error elements.

Evidence: `docs/evidence/RAIN_RESPONSE_TARGETED_20260720.md`

## Windows background-status write hardening

Changes:
- Added bounded exponential-backoff retries when an atomic background-job status
  replacement encounters a transient `PermissionError`.
- Made persisted ensemble and sweep result paths tolerate a Windows 8.3 root alias
  such as `RUNNER~1` when it identifies the same directory as the long-form root.
- Kept the write atomic: readers still see either the old complete JSON document or
  the new one, and abandoned temporary files are removed after success or failure.
- Added a deterministic regression that fails the first two replacements before
  allowing the third attempt to complete, plus a simulated long/short root-alias
  regression.

Validation:
- The four server-execution tests passed three consecutive times on Windows,
  including a real detached placeholder worker in every run.
- Authenticated Actions logs identified the CI-specific subprocess failure as a
  `runneradmin` versus `RUNNER~1` root mismatch; Ubuntu was already green.
- The corrected subprocess test passed twice, and the complete 45-test fast CI
  command plus project integrity passed locally on Windows.

## Cross-platform CI and validated dependency baseline

Changes:
- Added GitHub Actions fast-regression jobs on Windows and Ubuntu using Python 3.13.
- Fast jobs run columnar-cache tests, native diagnostic/workflow mapping tests,
  server execution tests, and the project integrity contract.
- Added a separate Ubuntu real-PySDM integration job for `develop`/`main` pushes and
  manual workflow runs. Pull requests stop after the cross-platform fast gate.
- Added `requirements-ci.txt` with the exact direct-dependency versions validated in
  the local Python 3.13 environment while leaving application requirements flexible.
- Added read-only workflow permissions, dependency caching, concurrency cancellation,
  headless Matplotlib, UTF-8 mode, and explicit timeouts.

Validation:
- The workflow YAML parses successfully and contains both expected jobs.
- The exact dependency baseline matches the local validated environment.
- The exact 43-test fast CI command passed in 54 seconds with project integrity.
- The preceding 45-test full suite, including both real PySDM integrations, remains
  the physics baseline; this infrastructure-only change does not alter simulation behavior.

## Resumable targeted common-seed qualification

Changes:
- Added `--resume-result` for in-place common-seed qualification recovery while
  retaining the targeted profile's explicit `--confirm-targeted-run` gate.
- Added a normalized SHA-256 execution-config fingerprint that excludes changing
  qualification metadata but protects the model, sweep, ensemble, seed, diagnostic,
  and worker contract.
- Persisted sweep and ensemble configs before expensive model work so hard
  interruptions leave a durable resume identity.
- Added member-level artifact validation. Matching members with readable summary and
  primary CSV files are reused; missing, corrupt, failed, or mismatched members rerun.
- Rebuilt ensemble statistics, paired-seed coverage, convergence evidence, reports,
  and manifests after every resume.
- Added append-only resume attempt status and reused/rerun counts to
  `qualification_plan.json`.

Validation:
- A compact common-seed regression removed the finalized member table and one seed's
  primary result. Resume reused the intact seed and reran only the missing seed.
- A second resume reused every member, and a changed execution config was rejected
  before model execution.
- Targeted resume, paired-seed audit, qualification-plan contract, and parallel-sweep
  regressions passed together. No 40-execution physical run was started during this
  implementation test; the later authorized run is documented above.
- All 45 unit/integration tests passed in 265 seconds, including both real PySDM
  integrations. Project integrity and diff whitespace checks passed.

## Literature-bounded transition cadence and interpretation gate

Changes:
- Kept the 1% rain-size liquid fraction as a project-owned operational floor and
  retained mandatory 0.5/1/2% fraction plus 20/25/30 µm radius sensitivity.
- Changed automatic spectrum checkpoints from a 10 s target to a 2 s target,
  snapped to and never finer than the model timestep. Ten seconds is now the
  operational maximum for robust onset-time interpretation.
- Added explicit observation-preferred, operationally bounded, and coarse cadence
  states to each comparison summary.
- Added combined `resolved_robust`, `resolved_cadence_limited`,
  `threshold_sensitive`, and `onset_not_resolved` interpretation states.
- Results displays the combined state and warns when checkpoint cadence limits the
  interpretation; reports include the new evidence fields.
- All 44 unit/integration tests and project integrity passed. Aerosol and Results
  AppTests rendered with zero exceptions and zero error elements.

Evidence boundary:
- Acquistapace et al. (2017) supports the 2 s preferred and 10 s upper cadence
  choices for preserving radar drizzle-onset structure. It does not validate the
  model-native 1% fraction, which remains explicitly operational.

Basis: `docs/SPECTRUM_TRANSITION_BASIS.md`

## Evidence-based Arrow IPC result cache

Changes:
- Replaced the initial PyArrow/Parquet prototype with Arrow IPC behind
  `analysis.dashboard.safe_read_csv` after measuring the real-result workload.
- Kept CSV as the only scientific source of truth; hidden cache files are ignored,
  disposable, absent from manifests, and bypassed when unavailable or disabled.
- Added size/mtime/build fingerprints, stable-source checks, unique temporary files,
  atomic replacement, stale invalidation, and corrupt data/metadata recovery.
- Added a 25,000-cell default eligibility threshold and the
  `PYSDM_COLUMNAR_CACHE_MIN_CELLS` override so small files remain CSV-only.
- Added `scripts/benchmark_columnar_cache.py` for repeatable raw/cold/warm timing
  with exact DataFrame equality, storage ratio, and break-even reporting.

Validation:
- Mixed numeric, integer, Boolean, string, and missing-value data matched CSV with
  `pandas.assert_frame_equal(check_exact=True)` on cache miss and hit.
- Source mutation invalidated the old cache, corrupt Arrow data/metadata rebuilt
  from CSV, and `PYSDM_COLUMNAR_CACHE=0` prevented cache creation.
- On an existing 101 x 505 ensemble statistics file, 20-repeat warm reads improved
  from 16.271 ms CSV to 8.076 ms Arrow (2.015x). Cold build took 61.597 ms,
  estimated break-even was seven total reads, and storage was 1.247x CSV.
- The preceding Parquet screening was rejected: its warm median was 33.058 ms
  versus a 24.981 ms CSV baseline (0.756x).
- All 44 unit/integration tests and project integrity passed. Results AppTest
  loaded stored result data with zero exceptions and zero error elements.

Design: `docs/COLUMNAR_CACHE.md`
Evidence: `docs/evidence/COLUMNAR_CACHE_BENCHMARK_20260720.md`

## Targeted high-resolution response plan

Changes:
- Added a five-seed `rain_response_targeted` profile with two levels on each
  numerical axis: 2.5/5 s and 800/1600 seeding/background super-droplets.
- The OFAT contract generates 4 cases, 20 case-seed pairs, and 40 physical
  control/seeding executions, 42.9% fewer than the three-level standard plan.
- Added case-seed counts, runtime-estimate provenance, serial-duration estimates,
  and explicit confirmation metadata to `qualification_plan` output.
- Forced serial case execution for this profile and added a dry-run-first guard;
  physical execution requires `--confirm-targeted-run`.

Validation:
- The dry-run produced the exact expected axes, seeds, and execution counts.
- A no-dry-run invocation without confirmation exited before starting PySDM.
- No new physical evidence was generated and existing interpretation boundaries
  remain unchanged.

Plan: `docs/TARGETED_RESPONSE_PLAN.md`

## Process-per-member ensemble isolation

Changes:
- Added validated `ensemble.execution_backend` choices: `in_process` (default) and
  `subprocess` (opt-in).
- The isolated path serializes an ensemble-disabled member config, invokes the same
  production `run_experiment` entry point in a fresh interpreter, and preserves
  stdout, stderr, status, return code, elapsed time, and process-tree RSS peak.
- Successful and failed child telemetry is flattened into `member_summary.csv`.
  Ensemble metadata/summary includes aggregate child resource statistics.
- The benchmark now samples the parent plus live descendants as a fair peak measure,
  while member checkpoints continue to measure retained parent RSS.
- Added a matched backend comparison CLI, Results metrics, Parameter Sweep controls,
  validation/integrity contracts, and a real subprocess integration regression.

Execution evidence:
- Matched 3-member real-PySDM pilots completed 3/3 members in both backends.
- Parent first-to-last retention fell 99.669% (37.797 MiB to 0.125 MiB).
- Process-tree peak increase worsened 13.606% (879.238 MiB to 998.867 MiB).
- Wall time worsened 113.374% (248.725 s to 530.714 s).

Decision:
- Keep `in_process` as default and present `subprocess` as a retention-control tool,
  not as a general memory or speed optimization.
- Prototype bounded warm-worker batches before any 70-execution standard run.

Validation:
- All 32 tests passed in 293.2 s, including two real PySDM integrations and both
  successful and failed child-process regression paths.
- Project integrity passed. Parameter Sweep and Results AppTests had zero rendered
  errors and zero exceptions.

Evidence: `docs/evidence/ENSEMBLE_EXECUTION_BACKEND_AB_20260715.md`

## Higher-resolution paired common-seed rain response

Changes:
- Added three-seed `rain_response_pilot` and five-seed `rain_response_standard`
  numerical qualification profiles.
- Preserved convergence scalar metrics in every ensemble member summary and added
  `paired_seed_metrics.csv` as the auditable case × seed source table.
- Numerical convergence now treats random seed as a condition, preventing a seed
  from being compared with another seed or hidden inside a case mean.
- Added complete case-seed coverage validation, per-seed rain-signal requirements,
  per-seed family evidence, portable report fields, and Results tables.

Execution evidence:
- The 24-execution placeholder workflow completed in 56.2 s and validated artifact
  generation only.
- The full collision-ON PySDM pilot completed 24/24 executions in 956.4 s with all
  four cases and all 12 case-seed pairs successful.
- Absolute rain state passed 36/36 5% checks (max 2.366%). Seeding response passed
  4/63 (median 39.093%, max 526.314%); every seed rejected response support.

Decision:
- Keep the paired-seed design as mandatory for stochastic response qualification.
- Do not run the 70-execution standard blindly. First bound retained memory with
  member process isolation, then target the axes identified by this pilot.

Validation:
- All 29 unit/integration tests passed in 263.3 s, including two real PySDM tests
  and a compact 16-execution nested common-seed regression.
- Project integrity passed. Results AppTest loaded the actual PySDM pilot with zero
  exceptions and zero rendered errors and exposed the paired scalar source table.

Evidence: `docs/evidence/RAIN_RESPONSE_COMMON_SEED_20260715.md`

## Ensemble member-boundary retained-memory profiling

Changes:
- Added a process checkpoint profiler for ensemble member completion, optional GC,
  streaming aggregation, result finalization, and CLI return boundaries.
- Each checkpoint records RSS, USS, VMS, thread count, GC generation/object state,
  and open Matplotlib figure count.
- Added `ensemble.collect_garbage_between_members` with blocking boolean validation;
  it defaults to false and is exposed by the benchmark CLI only as an A/B diagnostic.
- Added a matched-workload comparison function and CLI that rejects mismatched
  profiles/workloads and stores peak, retained, slope, and wall-time differences.
- Added Results raw-checkpoint inspection and member-boundary RSS/USS line charts.

Execution evidence:
- Baseline and explicit-GC standard profiles each completed 12 real PySDM members.
- Baseline: 475.329 s, 878.137 MiB peak increase, 252.883 MiB first-to-last
  retention, 23.461 MiB/member fitted slope.
- Explicit GC: 493.260 s, 880.859 MiB peak increase, 256.715 MiB retention,
  24.472 MiB/member slope.
- GC reduced tracked Python objects and caused 198.676 MiB of cumulative transient
  RSS drops, but did not reduce peak or net retained RSS. No figures accumulated.

Decision:
- Keep explicit member-boundary GC disabled by default. The next memory experiment
  is child-process isolation to probe PySDM/Numba/backend allocator lifetime.
- Preserve the streaming aggregator, whose incremental RSS stayed near 0.26 MiB.

Evidence:
- `docs/evidence/ENSEMBLE_MEMORY_OWNERSHIP_20260715.md`
- `docs/evidence/ENSEMBLE_MEMORY_OWNERSHIP_20260715.json`

## Collision-ON rain qualification and OFAT execution design

Changes:
- Added `rain_pilot` and `rain_standard` CLI profiles with collision forced ON,
  explicit rain-signal requirements, and stored signal floors.
- Added a generic `one_factor_at_reference` sweep design. Qualification parameters
  declare `reference: min` or `reference: max`, producing one reference case plus
  each non-reference level varied alone.
- Reduced a three-level, three-axis qualification from 27 to 7 cases while retaining
  every reference and next-finest comparison consumed by the convergence analysis.
- Added absolute control/seeding rain-water metrics to sweep and convergence outputs.
- Qualification evidence now requires physical rain for rain profiles and reports
  `absolute_state` and `seeding_response` metric families separately.
- Results Dashboard and portable reports expose family-level status and the rain
  signal gate instead of presenting one pooled percentage without context.

Execution evidence:
- A 1500-second collision-ON probe produced rain onset at 525 s and non-zero final
  rain water in both control and seeding cases.
- The four-case `rain_pilot` completed in 433 s, detected rain, and appropriately
  rejected 5% support at the 60/100-super-droplet levels.
- The seven-case `rain_standard` completed 14 real PySDM executions in 699 s with
  zero failures. Absolute rain-state convergence passed 12/12 checks with a 3.285%
  maximum; seeding-response convergence passed only 2/21 checks.

Scientific limitation:
- Collision/coalescence is enabled, but sedimentation and surface precipitation are
  not. The supported family is parcel rain-water state, not rainfall at the ground.
- The current numerical reference is insufficient for quantitative seeding-effect
  claims even though its absolute rain state passes the 5% gate.

Validation:
- All 26 unit/integration tests passed in 249 seconds, including two real PySDM
  tests. Project integrity, portable path checks, and Results AppTest passed with
  zero exceptions or rendered errors.

## Absolute result-path budget hardening

Changes:
- Extended the compact nested path policy with a 240-character portable absolute
  path ceiling and workflow-specific descendant reserves for single, comparison,
  ensemble, and sweep results.
- Long scenario/result components are shortened with a readable prefix plus stable
  hash according to the actual remaining absolute-path budget.
- Output roots that leave insufficient room now raise `ResultPathBudgetError`
  before an adapter starts, avoiding another empty 24-case/240-member result.
- Kept full run IDs, scenario names, and sweep parameters in stored metadata rather
  than using filesystem components as the scientific record.

Regression coverage:
- Runs a sweep-ensemble under a deliberately deep output parent and long experiment
  name, then checks every artifact remains within the portable limit.
- Verifies stable shortening of a very long result name.
- Verifies an impossibly deep output root fails early with actionable guidance.
- Project integrity now exercises the complete sweep/case/member/comparison path.
- All 25 unit/integration tests passed in 213 seconds, including the two real PySDM
  integration tests, and the project integrity check passed.

## Full PySDM qualification, transition calibration, and benchmark evidence

Changes:
- Added qualification-evidence evaluation that separates finite non-zero relative
  checks from near-zero references, reports median/P95/maximum errors by numerical
  axis, and scopes the support decision to the tested physics profile.
- Ran the standard 27-case Cartesian `pysdm_parcel` qualification: 54 model
  executions completed without failure. All 12 non-zero next-finest checks were
  below the 5% tolerance, with a 1.731% maximum relative difference.
- Added a refresh mode to rebuild convergence evidence and reports from stored case
  outputs without rerunning PySDM.
- Calibrated spectrum-transition diagnostics around literature-bounded 20--30
  micrometre radius thresholds, added mandatory 0.5/1/2% operational-fraction
  sensitivity, and made automatic checkpoints use a configurable target.
- Added a standalone real-PySDM ensemble benchmark that samples whole-process RSS
  while separately recording CSV schema-discovery and column-streaming I/O phases.
- Ran the 24-member large profile successfully. Peak process RSS increased by
  999.64 MiB, whereas streaming aggregation increased RSS by only 0.27 MiB and
  completed in 3.772 seconds.
- Added on-demand report PDF generation with the publication figure selected in
  Results, while retaining automatic Markdown, HTML, and PDF report artifacts.
- Preserved an actual pre-manifest sweep fixture and added schema-v1 manifest alias
  migration with regression tests for both paths.

Validation performed:
- 23 unit/integration tests passed in 228 seconds, including two real PySDM tests.
- Project integrity validation passed.
- Aerosol and Run AppTests rendered with zero exceptions. Results rendered with no
  Streamlit exceptions; the four displayed execution errors are the expected
  diagnostics for the intentionally preserved 24-case/240-member failed result.
- Qualification and benchmark evidence summaries are stored under `docs/evidence/`;
  large raw artifacts remain local and are intentionally ignored by Git.

Scientific limitation:
- The completed qualification used the marine collision-OFF profile and produced
  zero rain-response metrics. It supports the current 5% default only for the
  non-zero condensation/seeding response metrics in that profile. A collision-ON,
  rain-producing qualification remains required.

## Nested sweep path safety and execution-health propagation

Incident reproduced:
- `20260714_190022_727349_0714_18_58_parameter_sweep` requested 24 parameter
  cases and 10 ensemble members per case.
- All 240 members failed with Windows `FileNotFoundError` / path-too-long errors.
  A representative nested diagnostic destination was 281 characters long.
- The old runner caught the member exceptions and still returned an apparently
  completed sweep containing no comparison time series, so Results showed generic
  empty-data and misleading dry-radius/kappa messages.

Changes:
- Added `simulation/path_policy.py` for safe, length-bounded filesystem tokens and
  explicit nested result directory names.
- Replaced repeated timestamp/experiment-name nesting with compact `case_###`,
  `member_###`, and `comparison`/`single` directories.
- Added durable execution-health payloads to ensemble and sweep metadata/summary,
  including exception type, message, errno, member counts, and case status.
- Added `ExperimentExecutionError`, raised after failure artifacts are written when
  every ensemble member or every sweep case fails.
- Excluded failed cases from convergence and best-case selection, and added
  ensemble-member metric aggregation as a sweep-ranking fallback.
- Added Results execution-health inference for older results and precise messages
  for failed sensitivity, collapse-variable, and plot-data states.
- Added Run-page handling that links a failed execution back to its preserved result
  directory instead of reporting an opaque exception only.

Validation performed:
- 21 unit/integration tests passed in 213 seconds, including two real PySDM tests.
- New regression tests cover compact nested paths below the Windows legacy limit,
  all-member failure preservation, sweep-level failure propagation, older-result
  health inference, and ensemble-aware ranking.
- Aerosol, Run, and Results AppTests rendered with zero exceptions. The reproduced
  failed result now reports 24 failed cases and 240 failed members in Results.
- Project integrity validation passed.

Recommended commit message:

```bash
git commit -m "Harden nested sweep execution failures"
```

## Portable PDF reports, sampled RSS, and numerical qualification

Changes:
- Added ReportLab-based `report.pdf` generation for single, comparison, sweep,
  and ensemble outputs. Available water-budget, spectrum-transition, and
  convergence plots are embedded automatically.
- Added PDF download support and optional legacy-safe loading in Results Dashboard.
- Added sampled whole-process RSS monitoring around streaming ensemble aggregation,
  retaining tracemalloc as a separate allocation scope.
- Added `scripts/run_numerical_qualification.py` with dry-run, `pilot`, and
  `standard` profiles plus a stored `qualification_plan.json` evidence contract.
- Changed generated run IDs from second to microsecond resolution and shortened
  qualification experiment names, preventing rapid sweep collisions and Windows
  path-length failures.
- Added `psutil` and `reportlab` as explicit runtime dependencies.

Validation performed:
- The eight-case placeholder pilot completed all 16 control/seeding model executions
  and wrote numerical convergence, plan, manifest, and report artifacts.
- The generated A4 PDF contained two pages; Poppler rendering and page-by-page visual
  inspection found no clipping, overlap, or missing figure content.
- PDF text extraction confirmed the build ID and numerical-convergence figure caption.
- All 17 unit/integration tests passed in 231 seconds, including real PySDM
  native and control-versus-seeding runs. Aerosol, Run, and Results AppTests
  each rendered with zero exceptions, and project integrity passed.

Recommended commit message:

```bash
git commit -m "Add portable reports and qualification workflow"
```

## Step 0. Clean project scaffold

Legacy experiment traces were removed to start PySDM Seeding Lab as a new independent simulation platform.

Changes:
- Removed sample experiment folders from `experiments/`
- Removed legacy experiment preset configuration
- Kept `experiments/.gitkeep` to preserve the directory
- Updated README project description and roadmap

Recommended commit message:

```bash
git commit -m "Remove legacy experiment traces from project scaffold"
```

## Step 1. Define initial configuration schema

The project now has a canonical configuration schema.

Changes:
- Added `simulation/schema.py`
- Added `schema_version`
- Standardized `configs/default.yaml`
- Standardized `configs/marine.yaml`
- Standardized `configs/urban.yaml`
- Updated `simulation/config.py` to normalize missing fields
- Updated `simulation/validation.py` to validate schema-level constraints
- Added helper functions for nested config access

Recommended commit message:

```bash
git commit -m "Define initial YAML configuration schema"
```

## Step 2. Stabilize Streamlit input pages

The Streamlit interface was updated to use the official configuration schema.

Changes:
- Added `simulation/ui_helpers.py`
- Improved main app overview
- Added scenario loading into `configs/default.yaml`
- Updated environment input page
- Updated aerosol input page with distribution preview
- Updated seeding input page with injection-time constraints
- Updated dynamics input page with direct/future input separation
- Improved run and results pages
- Added schema summary expanders to input pages

Recommended commit message:

```bash
git commit -m "Stabilize Streamlit parameter input pages"
```

## Step 3. Strengthen validation

The validation system now provides structured validation issues with severity levels.

Changes:
- Added `ValidationIssue` dataclass
- Added `validate_config_detailed()`
- Added `validation_summary()`
- Added `validation_report_rows()`
- Kept `validate_config()` backward-compatible by returning blocking error messages only
- Updated Run page to display validation metrics and a detailed report table
- Updated main app page to show validation status
- Added more physical and workflow checks for environment, aerosol, seeding, dynamics, microphysics, and output settings

Recommended commit message:

```bash
git commit -m "Strengthen configuration validation workflow"
```

## Step 4. Organize runner and adapter structure

The simulation execution layer was reorganized to make it easier to connect real PySDM code in Step 5.

Changes:
- Added `simulation/types.py`
- Added `SimulationRunSpec`
- Added `AdapterResult`
- Updated `simulation/builder.py` to build standardized run specs
- Updated `simulation/pysdm_adapter.py` with an adapter registry
- Added `placeholder_warm_cloud` adapter
- Reserved `pysdm_parcel` adapter for the first real PySDM simulation
- Updated `simulation/runner.py` to use run specs and adapter results
- Added `simulation.adapter` to the configuration schema
- Updated app and run page to display adapter information
- Updated validation to check adapter names

Recommended commit message:

```bash
git commit -m "Organize simulation runner and adapter interface"
```

## Step 5. Connect first real PySDM simulation

The first real PySDM adapter was connected under `simulation.adapter = pysdm_parcel`.

Changes:
- Added `simulation/pysdm_parcel_adapter.py`
- Connected `pysdm_parcel` in the adapter registry
- Added lazy imports for `PySDM` and `PySDM_examples`
- Added conversion from app concentration units `cm^-3` to PySDM example spectra units `kg_dry_air^-1`
- Added stateful seeding injection-rate function
- Mapped YAML environment, aerosol, seeding, and microphysics fields into `PySDM_examples.seeding.Settings`
- Added `seeding.number_concentration`
- Updated seeding UI to expose physical seeding concentration
- Added `requirements-pysdm.txt`
- Added CLI runner `scripts/run_config.py`
- Updated Run page to show a clean exception if PySDM is not installed

Recommended commit message:

```bash
git commit -m "Connect initial PySDM parcel seeding adapter"
```

## Fix. CLI import path

Fixed direct CLI execution from the project root.

Problem:
- Running `python scripts/run_config.py` sets `sys.path[0]` to `scripts/`
- The top-level `simulation` package was therefore not importable

Changes:
- Added project-root insertion to `scripts/run_config.py`
- Added `scripts/__init__.py`
- Resolved relative config and output paths from the project root

Recommended commit message:

```bash
git commit -m "Fix CLI project root import path"
```

## Fix. PySDM ConstantMultiplicity sampling API compatibility

Fixed a PySDM adapter crash caused by installed PySDM versions where
`ConstantMultiplicity` does not expose `sample_deterministic()`.

Problem:
- `pysdm_parcel` crashed with:
  `AttributeError: 'ConstantMultiplicity' object has no attribute 'sample_deterministic'`

Changes:
- Added `_sample_spectrum_deterministic()` compatibility helper
- The helper tries `sample_deterministic(...)` first and then `sample(...)`
- Added `scripts/diagnose_pysdm_api.py` for checking installed PySDM / PySDM_examples versions and sampler methods

Recommended commit message:

```bash
git commit -m "Fix PySDM spectrum sampling API compatibility"
```

## Step 6. Improve result storage and progress reporting

Simulation outputs are now saved as structured run directories instead of single CSV files.

Changes:
- Added `simulation/progress.py`
- Added CLI progress reporter
- Updated `simulation/runner.py` to save full run directories
- Saved `config.yaml`, `timeseries.csv`, `summary.json`, `metadata.json`, and `validation_report.json`
- Added time-series summary metrics using `np.trapezoid`
- Updated placeholder and PySDM adapters to emit stage-based progress
- Updated Streamlit Run page with progress bar and status messages
- Updated Results page to read new result directories and legacy CSV files
- Added `.gitignore` for generated results, logs, local envs, and caches

Recommended commit message:

```bash
git commit -m "Save structured simulation results with progress reporting"
```

## Step 7. Build result dashboard

The Results page was upgraded into a dashboard for structured result directories and legacy CSV files.

Changes:
- Added `analysis/dashboard.py`
- Added result discovery utilities
- Added structured result loading utilities
- Added summary flattening and metric formatting helpers
- Added recommended diagnostic column grouping
- Added seeding-active window shading in plots
- Rebuilt `pages/06_results.py` with dashboard tabs
- Added summary metric cards
- Added diagnostic plots for water content, radius, number concentration, and supersaturation
- Added custom variable plot
- Added metadata, config, validation report, and CSV download views
- Updated `analysis/plotting.py` to reuse dashboard plotting utilities

Recommended commit message:

```bash
git commit -m "Add results dashboard for simulation outputs"
```

## Fix. NumPy trapezoid integration

Fixed the integration helper for NumPy environments where `np.trapz` is removed.

Problem:
- `_time_integral()` used `getattr(np, "trapezoid", np.trapz)`
- The fallback argument `np.trapz` was evaluated immediately
- In environments without `np.trapz`, this raised:
  `AttributeError: module 'numpy' has no attribute 'trapz'`

Changes:
- Use `np.trapezoid()` first
- Use `np.trapz()` only as a delayed fallback when it exists
- Raise a clear error only if neither function exists

Recommended commit message:

```bash
git commit -m "Fix NumPy trapezoid integration fallback"
```

## Step 8. Add control vs seeding comparison workflow

The runner can now execute paired control and seeding simulations when `experiment.mode = control_vs_seeding`.

Changes:
- Updated `analysis/comparison.py`
- Added time alignment for control and seeding outputs
- Added `comparison.csv` generation
- Added comparison summary metrics
- Updated `simulation/runner.py` with mode dispatch
- Added `run_single_experiment()`
- Added `run_control_vs_seeding()`
- Updated result directory structure for paired runs
- Updated dashboard result discovery for comparison directories
- Added comparison plots and tables to Results dashboard

Recommended commit message:

```bash
git commit -m "Add control versus seeding comparison workflow"
```

## UI Fix. Compact plot matrix layout

The Results Dashboard plots are now rendered in a compact grid instead of being stacked vertically.

Changes:
- Added `render_plot_grid()` helper inside `pages/06_results.py`
- Added grid column control
- Added maximum plot count control
- Reduced default matplotlib figure size
- Converted diagnostic plots to a compact matrix
- Converted comparison plots to control-vs-seeding and difference matrices
- Converted custom variable plots to a matrix layout

Recommended commit message:

```bash
git commit -m "Compact results dashboard plot layout"
```

## UI Fix. Clarify placeholder result interpretation

The dashboard now makes it explicit when the selected result was generated by the synthetic placeholder adapter.

Problem:
- Placeholder comparison plots looked like real PySDM physics results
- `seeding_active` was included as a comparison variable
- This could make dashboard curves look physically misleading

Changes:
- Added placeholder warning in Results Dashboard
- Excluded `seeding_active` from comparison plot variables
- Reordered comparison variables to prioritize physical diagnostics
- Shortened comparison plot titles
- Added README note explaining placeholder vs real PySDM output

Recommended commit message:

```bash
git commit -m "Clarify placeholder result interpretation in dashboard"
```

## Step 9. Add seeding efficiency metrics

First-pass efficiency metrics were added for control-vs-seeding comparison runs.

Changes:
- Added `analysis/efficiency.py`
- Added single-run efficiency proxies
- Added paired control-vs-seeding efficiency metrics
- Added accumulated rain enhancement
- Added rain-onset time shift
- Added cloud-to-rain conversion proxy
- Added effective-radius and droplet-number response metrics
- Added heuristic `seeding_efficiency_score`
- Updated comparison summary to include efficiency metrics
- Updated Results Dashboard metric cards and JSON views

Recommended commit message:

```bash
git commit -m "Add seeding efficiency metrics"
```

## Step 10. Add parameter sweep workflow

The project now supports parameter sweeps through `experiment.mode = parameter_sweep`.

Changes:
- Added `simulation/sweep.py`
- Added sweep section to config schema
- Added `run_parameter_sweep()` to simulation runner
- Added automatic Cartesian product generation for sweep parameters
- Added per-case execution using `sweep.run_mode`
- Added sweep ranking table generation
- Added `sweep_summary.csv`
- Added Streamlit page `07_parameter_sweep.py`
- Updated Results Dashboard to discover and display sweep results
- Added sweep ranking plot and table

Recommended commit message:

```bash
git commit -m "Add parameter sweep experiment workflow"
```

## Fix. Add missing sweep ranking plot export

Fixed a Streamlit import error on the Results page.

Problem:
- `pages/06_results.py` imported `plot_sweep_ranking`
- Some local copies of `analysis/dashboard.py` did not contain that function
- Streamlit failed with:
  `ImportError: cannot import name 'plot_sweep_ranking' from 'analysis.dashboard'`

Changes:
- Added a top-level `plot_sweep_ranking()` function to `analysis/dashboard.py`
- The function draws a compact horizontal ranking chart for sweep results
- Added defensive handling for empty sweep tables or missing ranking columns

Recommended commit message:

```bash
git commit -m "Fix missing sweep ranking dashboard function"
```

## Fix. Add sweep time-series comparison plots

The initial sweep dashboard overemphasized ranking and did not show the case-wise time evolution of physical variables.

Changes:
- Added sweep case loading utilities to `analysis/dashboard.py`
- Added overlay dataframe builder for sweep cases
- Added sweep overlay plotting function
- Rebuilt sweep dashboard layout around time-series comparison
- Added `Sweep Time Series` tab
- Added variable selection for rain water, cloud water, supersaturation, radius, number concentration, and superdroplet count
- Added comparison mode selection: seeding, control, diff, relative_change_percent
- Moved ranking to secondary summary / table view

Recommended commit message:

```bash
git commit -m "Add sweep time-series comparison plots"
```

## Fix. Replace dashboard module with complete sweep exports

Fixed another Streamlit import error caused by an incomplete local `analysis/dashboard.py`.

Problem:
- `pages/06_results.py` imports sweep time-series helper functions
- The local dashboard module did not include `build_sweep_overlay_dataframe`
- Streamlit failed with:
  `ImportError: cannot import name 'build_sweep_overlay_dataframe'`

Changes:
- Replaced `analysis/dashboard.py` with a complete module
- Guaranteed exports:
  - `plot_sweep_ranking`
  - `sweep_base_variables`
  - `build_sweep_overlay_dataframe`
  - `plot_sweep_overlay`
- Preserved single-run and comparison dashboard utilities

Recommended commit message:

```bash
git commit -m "Fix sweep time-series dashboard imports"
```

## Fix. Make sweep dashboard scientifically diagnostic

The sweep dashboard now emphasizes whether parameter changes actually create different model responses.

Changes:
- Default sweep comparison mode changed from absolute seeding curve to `diff = seeding - control`
- Added spread diagnostics across sweep curves
- Added warning when sweep curves overlap
- Added parameter-response heatmap for two-parameter sweeps
- Added helper functions:
  - `compute_overlay_spread`
  - `sweep_param_columns`
  - `plot_sweep_heatmap`

Recommended commit message:

```bash
git commit -m "Add sweep sensitivity diagnostics"
```

## Fix. Stabilize dashboard imports permanently

Repeated Results page crashes occurred because `pages/06_results.py` imported many functions directly from `analysis.dashboard`, while local copies of `dashboard.py` could lag behind.

Changes:
- Replaced `analysis/dashboard.py` with complete current implementation
- Rewrote `pages/06_results.py` to use `import analysis.dashboard as dash`
- Added a runtime required-function check inside the Results page
- Added `scripts/check_project_integrity.py`
- This makes future dashboard changes less likely to crash with direct `ImportError`

Recommended commit message:

```bash
git commit -m "Stabilize dashboard imports and integrity checks"
```

## Fix. Responsive layout and legend cleanup

Changes:
- Added shared responsive CSS injector in `simulation/ui_helpers.py`
- Applied responsive width styling to main app, Run page, and Results page
- Added build badges so stale code can be identified quickly
- Reworked sweep overlay dataframe assembly to avoid `_x` / `_y` duplicate legend artifacts
- Shortened case labels and ensured they are unique
- Moved legends outside plots and reduced clipping
- Added legend toggle for matrix plots
- Updated integrity check to print dashboard build id

Recommended commit message:

```bash
git commit -m "Improve responsive layout and sweep legend handling"
```

## Fix. Move sweep legends out of plots

Changes:
- Sweep overlay plots hide legends by default
- Added separate case legend tables
- Added curve value summary table
- Increased detailed sweep plot size
- Widened responsive layout further
- Added dashboard helper functions:
  - `build_overlay_legend_table`
  - `build_curve_value_summary`

Recommended commit message:

```bash
git commit -m "Move sweep legends out of plots"
```

## Feature. Experiment scenarios and improved sweep visualization

Changes:
- Added `simulation/experiment_manager.py`
- Added `00_experiment_scenarios.py`
- Reordered Streamlit pages:
  - parameter sweep before run/results
  - run and results moved to 06/07
- Added scenario selection to Run page
- Added cleanup script for old page filenames
- Added colored curve IDs and styled legend tables
- Added seeding-active shaded windows to sweep plots
- Added sweep seeding interval extraction

Recommended commit message:

```bash
git commit -m "Add experiment scenarios and improve sweep visualization"
```

## Fix. Scenario-aware setting pages and duplicate page cleanup

Changes:
- Added direct scenario save support to shared `config_actions()`
- Pages 01–04 can save settings into a selected scenario
- Parameter Sweep page can configure a selected scenario directly
- Run page can run selected scenarios
- Extended experiment manager with `update_scenario_config()` and `scenario_options()`
- Strengthened duplicate page cleanup and integrity checks
- Removed old page filenames from package to avoid Streamlit duplicate pathname errors

Recommended commit message:

```bash
git commit -m "Add scenario-aware settings workflow"
```

## Step 11. Add Growth-pathway diagnostics

Changes:
- Added `analysis/exper2_diagnostics.py`
- Added `diagnostics` section to schema
- Runner enriches adapter output with Growth-pathway diagnostic columns
- Single-run result folders now save `diagnostic_health.json`
- Comparison outputs include Growth Pathway columns and differences
- Dashboard includes an `Growth Pathway Diagnostics` tab
- Parameter Sweep page supports collision ON/OFF sweep
- Dashboard variable ordering now prioritizes Growth Pathway pathway diagnostics

Recommended commit message:

```bash
git commit -m "Add Growth-pathway diagnostic workflow"
```

## Step 12. Add ensemble statistics and plot downloads

Changes:
- Renamed user-facing `Exper2-style` naming to `Growth Pathway Diagnostics`
- Added `analysis/growth_pathway_diagnostics.py`
- Kept `analysis/exper2_diagnostics.py` as a backward-compatible wrapper
- Added `analysis/ensemble_statistics.py`
- Added `ensemble` section to schema
- Runner can now execute ensembles for single and control-vs-seeding runs
- Parameter sweep cases can run as ensembles
- Added `ensemble_statistics.csv`
- Added `member_summary.csv`
- Added `[ensemble]` result type to dashboard
- Added mean ± std and median + IQR plots
- Added PNG download buttons for plots
- Added ensemble metrics to sweep summary rows

Recommended commit message:

```bash
git commit -m "Add ensemble statistics and plot downloads"
```

## Fix. Scenario-named results and simplified sweep dashboard

Changes:
- Added scenario identity helpers to experiment manager
- Run page applies scenario slug/name to `experiment.name`
- Result directories now include scenario slug when running a scenario
- Parameter Sweep applies scenario identity when configuring a scenario
- Sweep dashboard can read ensemble case result directories
- Added recommended sweep variable selection
- Added clearer old-result warning when no variables are plottable
- Added scenario metric in Run Overview

Recommended commit message:

```bash
git commit -m "Use scenario names for results and simplify dashboard"
```

## Fix. Add run progress dashboard and injection-time sweep summary

Changes:
- Added `simulation/run_plan.py`
- Run page now estimates total model runs before execution
- Run page now shows live completed/remaining model-run progress
- Added quick parameter-effect summary plot for sweep results
- Added final/max/min/integral/peak_time_s case summary table
- Added relative-time overlay for injection-start sweeps
- Fixed ensemble result loading bug in dashboard
- Added injection-time sweep detection helper

Recommended commit message:

```bash
git commit -m "Add progress dashboard and injection-time sweep summaries"
```

## Fix. Compact progress card and empty CSV handling

Changes:
- Run page now uses persistent placeholders instead of appending metric rows
- Live progress is displayed in one compact card
- Added `safe_read_csv()` to dashboard
- Dashboard now skips zero-byte / empty CSV result files
- Added incomplete-result toggle in Results Dashboard
- Fixed `pandas.errors.EmptyDataError` when a run is still writing
- Added result readability checks

Recommended commit message:

```bash
git commit -m "Compact run progress and handle incomplete result files"
```

## Fix. Accurate progress events and safe CSV recursion

Changes:
- Runner emits explicit `model_run_complete` after every real model run
- Run page increments Done/Left based on explicit completion events
- Run page shows current sweep case and ensemble member context
- Fixed accidental recursive `safe_read_csv()` call in dashboard
- Dashboard now uses `pd.read_csv()` inside `safe_read_csv()`

Recommended commit message:

```bash
git commit -m "Fix live progress accounting and CSV reader recursion"
```

## Hotfix. Dashboard safe_read_csv recursion

Changes:
- Force `safe_read_csv()` to call `pd.read_csv(path)`
- Added `scripts/fix_dashboard_recursion.py`
- Integrity check now fails if `safe_read_csv()` calls itself recursively

Recommended commit message:

```bash
git commit -m "Fix dashboard CSV reader recursion"
```

## Fix. Sweep case filtering and full-range display

Changes:
- Added case filter controls to sweep plots
- Added full-range sampling instead of `.head(max_cases)`
- Added injection-start information to curve labels
- Added readable formatting for dry radius, kappa, injection time, collision
- Prevents large-radius cases such as 3.0 µm from being hidden by default plot limits

Recommended commit message:

```bash
git commit -m "Add sweep case filters and full-range plotting"
```


## Step 13. Diagnostic provenance, runtime estimation, result-file documentation

Addressed three review items before starting native PySDM diagnostic extraction work
(see `ROADMAP.md` for why extraction now comes before publication-style plots).

Changes:
- Added `analysis/growth_pathway_diagnostics.classify_diagnostic_provenance()` /
  `diagnostic_provenance_rows()`, classifying each Growth Pathway variable as
  native / derived / proxy based on the adapter's raw output columns.
- `simulation/runner.py` now captures raw adapter columns before diagnostic
  enrichment, writes `diagnostic_provenance.json` per run, and embeds the same
  rows into `summary.json` (`adapter_summary.growth_pathway_diagnostic_provenance`).
- Added `simulation/run_timing.py`: records measured wall-clock duration per
  model run to `results/.run_timing_history.json`, and estimates expected
  runtime for upcoming sweep/ensemble runs from the median of recent same-adapter
  runs (falling back to a conservative default when no history exists yet).
- `simulation/run_plan.py` / `pages/06_run.py` Run Plan section now shows
  estimated time per run, estimated total runtime, the basis for that estimate,
  and warns before large, unmeasured sweep/ensemble runs.
- Added `analysis/result_files.py`: a single source of truth describing what
  `config.yaml` / `validation_report.json` / `summary.json` / `metadata.json` /
  `diagnostic_health.json` / `diagnostic_provenance.json` are each for. Runner
  embeds this as `metadata.json["file_roles"]`; dashboard renders it in the
  Files & Metadata tab.
- `analysis/dashboard.py` gained `diagnostic_provenance_dataframe()`,
  `diagnostic_provenance_summary_counts()`, `result_file_roles_dataframe()`,
  registered in both `pages/07_results.py` and
  `scripts/check_project_integrity.py`'s required-export checks.
- Added `ROADMAP.md`, reordering the previously flat "next steps" list so that
  native diagnostic extraction (old #5) precedes publication-style plots
  (old #1-3), avoiding rework when diagnostic calculations change later.
  `README.md`'s stale Step-0-10 roadmap now points to it.

Recommended commit message:

```bash
git commit -m "Add diagnostic provenance tracking, runtime estimation, and result-file docs"
```

## Step 14. Replace Quick Parameter Effect Summary with sound sensitivity analysis

`Quick Parameter Effect Summary` connected sweep cases into a single line ordered
by one chosen parameter, even when other swept parameters (e.g. kappa) varied
at the same time between those cases. For a multi-parameter sweep this silently
mixes several effects into one curve. Removed and replaced with tools that are
correct by construction or explicit about what they assume.

Changes:
- Removed `analysis.dashboard.build_sweep_effect_summary` / `plot_sweep_effect_summary`
  and the "Quick Parameter Effect Summary" UI block.
- Added `analysis.dashboard.sweep_case_metrics_table()`: shared per-case
  final/max/min/integral/peak_time_s summary (same computation as before,
  factored out so multiple analyses can reuse it).
- Added "Fixed-Parameter Sensitivity Summary": uses the existing Case
  filter/focus view so the user explicitly fixes every other swept parameter
  before viewing a 1D sensitivity curve. `varying_sweep_parameters()` checks
  the filtered case set and warns if more than the chosen x-axis parameter is
  still varying, instead of silently plotting a mixed-effects curve.
- Added "Warm-Seeding Collapse Variable Analysis": `add_kappa_koehler_collapse_variable()`
  computes log10(kappa * dry_radius^3), the kappa-Koehler collapse variable
  used in warm hygroscopic seeding sensitivity analysis (Petters & Kreidenweis
  2007). `plot_collapse_variable_response()` scatters response vs. this single
  variable across all dry_radius x kappa cases at once (deliberately not
  requiring other parameters to be fixed, since collapsing onto one variable is
  the point), optionally colored by a third parameter (e.g. injection_start).
- Added `plot_response_surface_heatmap()`: 2D dry_radius x kappa response
  surface for the same on-the-fly variable/statistic choice (complements the
  existing `plot_sweep_heatmap`, which only reads pre-aggregated
  sweep_summary.csv columns and can't compute final/max/integral on demand).
- Registered all new functions in `pages/07_results.py`'s
  `REQUIRED_DASHBOARD_FUNCTIONS`.

Recommended commit message:

```bash
git commit -m "Replace quick parameter summary with fixed-parameter sensitivity and kappa-Koehler collapse analysis"
```

## Step 15 (original Step 13). Publication-style diagnostic plots

Started the publication-plot stage requested in the original project prompt.
`ROADMAP.md` renamed this stage Step 15 after placing native diagnostic
extraction first; both names refer to the same publication-plot work here.

Changes:
- Added `analysis/publication_plots.py`, keeping publication-specific styling,
  units, provenance marks, and conditioning rules separate from result loading.
- Added a Results Dashboard `Publication Plots` tab for comparison, sweep, and
  ensemble results.
- Added a Growth Pathway 2×2 panel with one explicitly selected variable from
  each pathway group. It supports `seeding - control` and control/seeding views.
- Added ensemble 2×2 panels for both mean ± standard deviation and median + IQR.
- Added one-factor-at-a-time dry-radius / kappa / injection-time panels. Every
  non-x parameter is fixed at a user-visible reference condition, so unrelated
  sweep effects are not silently mixed.
- Added a collision OFF / ON panel that keeps only parameter conditions having
  an exact OFF/ON pair and uses shared y limits and matched curve colors.
- Added native/derived/proxy provenance codes directly to panel titles and a
  provenance footer to every exported publication figure.
- Changed PNG export to 300 dpi by default.
- Sweep and ensemble result loading now finds a representative nested
  `diagnostic_provenance.json`, so provenance is also available outside a
  top-level comparison result.
- Tightened the kappa–dry-volume analysis language: the combined coordinate is
  treated as a hypothesis to test rather than a guaranteed collapse.
- Response-surface heatmaps no longer average over additional varying sweep
  parameters by default. The UI asks the user to fix those confounders first.
- Added publication exports to `scripts/check_project_integrity.py` and compiled
  `analysis/publication_plots.py` as part of the integrity check.

Validation performed:
- `python -m py_compile` passed for the new module, dashboard, Results page, and
  integrity script in the local PySDM environment.
- `python scripts/check_project_integrity.py` passed.
- Synthetic tests covered all four publication plot builders, OFAT slicing,
  exact collision pairing, 300-dpi serialization, and confounder rejection.
- A real placeholder 2×2 sweep was run in a temporary directory and verified
  end-to-end through runner → result discovery/loading → provenance loading →
  selected-case four-panel rendering.

Recommended commit message:

```bash
git commit -m "Add publication-style warm-cloud seeding diagnostic panels"
```

## Cross-cutting UX update. Expanded sensitivity design and onboarding

Improved experiment design without taking the Step 16 number reserved by
`ROADMAP.md` for wet-radius and size-bin diagnostics.

Changes:
- Replaced the small fixed common-sweep form with an 18-parameter catalog,
  grouped by scientific purpose and accompanied by short interpretation notes.
- Added seven ready-to-use experiment presets and a preview of sweep cases,
  ensemble members, and actual model-run count.
- Separated physical-sensitivity variables from timestep/super-droplet
  numerical-convergence variables and warns when they are mixed in one grid.
- Made `seeding.injection_duration` an effective sweep variable by deriving
  `injection_end` after every Cartesian-product case is assembled.
- Added background-aerosol super-droplet resolution to the schema, validation,
  configuration pages, and common sweep catalog.
- Rebuilt `app.py` as a Welcome / Start page with the recommended workflow,
  quick navigation, configuration health, scenario loading, and a warm-seeding
  interpretation checklist.
- Added a shared compact visual system and grouped Environment, Aerosol,
  Seeding, and Dynamics controls into bounded cards. Seeding settings now use
  three balanced cards instead of two full-width input stacks.
- Extended dashboard/publication parameter labels for the new sweep variables
  and added sweep-catalog integrity checks.

Validation performed:
- `python scripts/check_project_integrity.py`
- Streamlit AppTest rendering for the Welcome page and pages 01–05
- AppTest interaction with the Activation & hygroscopicity preset (48 cases,
  96 control/seeding model runs)

Recommended commit message:

```bash
git commit -m "Expand warm-cloud sweep design and refresh onboarding UI"
```

## Step 13 completion. Native PySDM scalar diagnostics

Completed the first native-product pass against PySDM / PySDM-examples 2.131.

Changes:
- Added `simulation/native_parcel_simulation.py`, a project-owned parcel builder
  that leaves site-packages untouched while expanding the PySDM product list.
- Added native temperature, pressure, water-vapour mixing ratio, relative
  humidity, wet-radius-partitioned water, cloud/rain concentration, and
  cloud/rain/all-activated effective-radius products.
- Added configurable activation/rain wet-radius thresholds to the schema,
  validation, YAML presets, Aerosol page, Run page, and result metadata.
- Preserved older dashboard column aliases while upgrading Growth Pathway
  provenance to recognize the exact native columns.
- Added total/unactivated/cloud/rain liquid-water products and records the
  maximum partition-closure error in the adapter summary.
- Pinned the tested optional environment to PySDM 2.131 and
  PySDM-examples 2.131.
- Added `tests/test_native_diagnostics.py` with synthetic mapping, threshold
  validation, real PySDM, liquid partition, and runner result-file coverage.
- Added the fast native diagnostic contract to `check_project_integrity.py`.

Validation performed:
- Real 45-second PySDM smoke run: 20 raw columns, native 11 / derived 2 /
  proxy 0, maximum liquid partition error 0.
- `python -m unittest -v tests.test_native_diagnostics`
- `python scripts/check_project_integrity.py`

Recommended commit message:

```bash
git commit -m "Add native PySDM growth-pathway diagnostics"
```

## Step 14/16 milestone. Wet-radius spectrum and threshold robustness

Implemented the first distribution-level diagnostic pass while retaining the
existing roadmap numbering: physical robustness belongs to Step 14 and
wet-radius bin output belongs to Step 16.

Changes:
- Added configurable spectrum bounds, logarithmic bin count, checkpoint times,
  and threshold factors under `diagnostics.wet_radius_spectrum`.
- Added native PySDM `NumberSizeSpectrum` and
  `ParticleVolumeVersusRadiusLogarithmSpectrum` products to the project-owned
  parcel builder.
- Inserted every tested activation/rain threshold as an exact bin edge so
  repartitioning is not blurred by a bin crossing the diagnostic boundary.
- Added `wet_radius_spectrum.csv` and `threshold_robustness.csv` as typed
  auxiliary result tables preserved through runner enrichment and timing.
- Added single and control/seeding spectrum panels to Results Dashboard.
- Added schema validation for bounds, bin count, checkpoints, and baseline
  threshold factor 1.0.
- Added `PROJECT_STATUS.md` as the concise current/completed/next status page.
- Removed tracked Python bytecode from source control; `.gitignore` already
  excludes regenerated cache files.

Validation performed:
- `python -m unittest -v tests.test_native_diagnostics`: 6 tests passed,
  including two real PySDM integration tests.
- `python scripts/check_project_integrity.py`: passed with complete dashboard
  exports and proxy-free synthetic native contract.
- Streamlit AppTest: Aerosol, Run, and Results pages rendered with 0 exceptions.

Recommended commit message:

```bash
git commit -m "Add wet-radius spectrum and threshold robustness"
```

## Research-quality bundle. Conservation, convergence, comparison, and vector export

Completed the first integrated Step 14–16 quality-gate pass without treating the
roadmap steps as isolated UI features.

Changes:
- Added a source-aware total-water budget. Seeding injection is explicitly an
  open source interval; pass/warning/fail uses only control, pre-injection, and
  post-injection closed windows.
- Added `water_budget.csv` for each native run and an aligned
  `water_budget_comparison.csv` for control versus seeding.
- Added aligned `wet_radius_spectrum_comparison.csv` and
  `threshold_robustness_comparison.csv` with seeding-minus-control columns.
- Added an automatic `numerical_convergence.csv` for sweeps containing timestep
  or super-droplet parameters. The acceptance rule checks the next-finest OFAT
  result against the finest available multi-axis reference.
- Added Results tabs for Water Budget and Numerical Convergence, plus signed
  wet-radius and threshold-difference plots.
- Added PNG 300 dpi, editable SVG, and PDF publication downloads with screen,
  journal single-column, and journal double-column style presets.
- Added schema defaults, validation, Aerosol-page quality-gate controls, file-role
  descriptions, summaries, and old-result-safe loading for every new output.
- Added automatic `report.md` generation for single, comparison, sweep, and
  ensemble results, with Results Dashboard preview and download.
- Added schema-versioned `result_manifest.json` generation for every result
  type, including the primary data file and complete artifact map.
- Added current, older, future, invalid, and manifest-free legacy compatibility
  inspection. Results Dashboard displays the detected schema state while still
  loading known legacy directory layouts.
- Reworked ensemble aggregation to retain member CSV paths instead of every full
  dataframe. Variables are stacked one at a time, preserving mean/std/median/IQR
  output while bounding peak aggregation memory independently of variable count.

Validation performed:
- 15 unit/integration tests passed, including a real PySDM control–seeding run.
- The real native smoke run reported 0 closed-window water drift and 0 liquid
  partition residual; injected water was recorded separately as a source change.
- An 8-case placeholder numerical sweep generated and passed its convergence audit.
- PDF/SVG serialization produced valid vector files at the requested journal size.
- Project integrity passed and Aerosol, Run, Results AppTests reported 0 exceptions.
- Manifest regression coverage verifies both current sweep/comparison outputs
  and automatic inference of a manifest-free legacy single result.

Recommended commit message:

```bash
git commit -m "Add integrated research quality diagnostics"
```

## Research-quality second pass. Transition timing, measured aggregation, and HTML reports

Changes:
- Added a spectrum-transition definition based on the rain-size liquid-volume
  fraction among activated liquid, with a configurable default threshold of 1%.
- Added linear checkpoint interpolation for control/seeding transition onset and
  stores onset shift for every activation/rain radius-threshold pair.
- Added `spectrum_transition.csv` and
  `spectrum_transition_onset_robustness.csv`, summary metrics, Results plots,
  threshold-direction audit, schema defaults, validation, and UI controls.
- Instrumented streaming ensemble aggregation with member input bytes, elapsed
  time, output shape, aggregated variable count, and tracemalloc-visible peak
  allocation in `ensemble_aggregation_diagnostics.json`.
- Added self-contained, print-friendly `report.html` for single, comparison,
  sweep, and ensemble results, with Results preview/download and manifest roles.
- Kept old results safe: every new table/report is optional when loaded by the
  dashboard, and existing schema compatibility handling remains unchanged.

Validation performed:
- 16 unit/integration tests passed, including real PySDM native and
  control-versus-seeding runs.
- Synthetic transition crossing resolved control onset at 13.33 s, seeding onset
  at 5 s, and a -8.33 s shift using checkpoint interpolation.
- Streaming and legacy in-memory ensemble statistics matched exactly.
- Aerosol, Run, and Results AppTests rendered with 0 exceptions.
- Project integrity and Python compilation checks passed.

Recommended commit message:

```bash
git commit -m "Add spectrum transition and HTML research reports"
```

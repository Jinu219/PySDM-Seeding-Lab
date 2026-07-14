# Development Notes

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

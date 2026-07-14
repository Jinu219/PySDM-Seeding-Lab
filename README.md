# PySDM Seeding Lab

PySDM Seeding Lab is a research-oriented simulation platform for designing, running, and visualizing cloud seeding experiments based on PySDM.

This project starts from a clean scaffold and does not depend on previous experiment folders or legacy experiment names.  
The goal is to build a reusable platform where cloud environment settings, background aerosol properties, seeding particle parameters, and microphysical options can be configured through YAML files and an interactive Streamlit interface.

## Project Motivation

Until now, PySDM-based cloud seeding simulations often required direct modification of individual Python scripts or notebooks.  
That workflow is useful for quick testing, but it becomes difficult to manage when the number of variables increases.

This project aims to build a more structured workflow:

- Define experiment settings using YAML configuration files
- Modify cloud and seeding parameters through an interactive interface
- Validate input values before running simulations
- Run PySDM simulations through a dedicated adapter layer
- Save simulation results and metadata automatically
- Visualize cloud microphysical evolution and seeding effects
- Extend the system toward sensitivity experiments and optimization workflows

## Core Concept

```text
User Input
    ↓
YAML Configuration
    ↓
Configuration Validation
    ↓
Simulation Builder
    ↓
PySDM Adapter
    ↓
Simulation Runner
    ↓
Result Storage
    ↓
Analysis and Visualization
```

PySDM is treated as the physical simulation engine, while this project provides the surrounding structure for experiment design, execution, and analysis.

## Project Structure

```text
pysdm-seeding-lab/
│
├── app.py
│
├── pages/
│   ├── 01_environment.py
│   ├── 02_aerosol.py
│   ├── 03_seeding.py
│   ├── 04_dynamics.py
│   ├── 05_run.py
│   └── 06_results.py
│
├── configs/
│   ├── default.yaml
│   ├── marine.yaml
│   └── urban.yaml
│
├── simulation/
│   ├── config.py
│   ├── validation.py
│   ├── builder.py
│   ├── runner.py
│   └── pysdm_adapter.py
│
├── analysis/
│   ├── metrics.py
│   ├── distributions.py
│   ├── comparison.py
│   └── plotting.py
│
├── experiments/
│   └── .gitkeep
│
└── results/
```

## Installation

```bash
pip install -r requirements.txt
```

## Run the App

```bash
streamlit run app.py
```

The home page is now the project onboarding page. It explains the recommended
scenario → configuration → sensitivity → run → analysis workflow and provides
direct links to the key pages.

### Sensitivity-design workspace

`05. Parameter Sweep` provides 18 commonly used warm-cloud seeding sweep
parameters in four groups:

- seeding material and dose;
- delivery timing and cloud dynamics;
- cloud state and background aerosol competition;
- microphysics and numerical robustness.

Seven presets cover activation/hygroscopicity, dose response, timing/updraft,
background CCN competition, thermodynamic regime, collision transition, and
numerical convergence. The preview reports the Cartesian case count and the
actual estimated model-run count after ensemble and control/seeding factors.
Physical parameters and numerical-convergence parameters are labelled
separately so they are not accidentally interpreted as the same question.

## Current Status

For the current milestone, completed work, and next acceptance gates, see
[`PROJECT_STATUS.md`](PROJECT_STATUS.md). `ROADMAP.md` owns the prioritized
sequence, while `DEVELOPMENT.md` remains the detailed implementation history.

The project is an active research workbench with scenario management,
configuration validation, parameter sweeps, ensembles, a PySDM parcel adapter,
diagnostic provenance, and publication-oriented result panels. The
`placeholder_warm_cloud` adapter remains available for fast UI testing; use
`pysdm_parcel` for physics-based experiments and review each diagnostic's
native/derived/proxy provenance before drawing conclusions.

### Native PySDM diagnostics

The `pysdm_parcel` adapter uses a project-owned product builder instead of
patching the installed PySDM examples. With the tested PySDM 2.131 environment
it emits native thermodynamic state, radius-partitioned liquid water, cloud/rain
number concentration, and cloud/rain/all-activated effective radius. Default
wet-radius definitions are:

```text
unactivated: 0 ≤ r < 0.5 µm
cloud:       0.5 µm ≤ r < 25 µm
rain:        25 µm ≤ r
```

The thresholds are editable under `02. Background Aerosol Settings → Diagnostic
radius definitions` and are stored in every result's configuration and metadata.
These are radius-bin definitions, not a record of each particle's activation
history. Run `python -m unittest -v tests.test_native_diagnostics` for the real
adapter regression check.

New PySDM runs can also save compact wet-radius number and liquid-volume spectra
at start, injection start/end, and run end. The Results Dashboard displays these
checkpoints and a 0.8/1.0/1.2 activation/rain threshold robustness analysis.
The underlying files are `wet_radius_spectrum.csv` and
`threshold_robustness.csv`.

Research-quality outputs now include source-aware total-water conservation,
control–seeding spectrum differences, and an automatic numerical-convergence
audit for timestep/super-droplet sweeps. Publication panels support 300 dpi PNG,
editable SVG, and PDF with screen, single-column, and double-column presets.
Every new single, comparison, sweep, and ensemble result also includes an
automatic `report.md` summarizing quality gates, outcome metrics, validation,
artifacts, reproduction steps, and interpretation constraints.
The same result directories include a versioned `result_manifest.json` that
declares the result type, primary data file, and artifact map. The Results
Dashboard also infers older directories that predate the manifest and labels
their compatibility explicitly.
Large ensembles are aggregated from stored member CSVs one variable at a time,
so the runner no longer retains every full member dataframe simultaneously.

## Development Roadmap

Steps 0-12 and the first Step 13 native scalar-product pass are complete; see
`DEVELOPMENT.md` for the full changelog. The prioritized plan now lives in
`ROADMAP.md`: benchmark the new streaming ensemble aggregation next; Markdown
reporting and the first result-schema compatibility layer are already connected
to every result type.

## Research Direction

The long-term goal is to explore how seeding particle properties, background aerosol conditions, injection timing, and cloud microphysical processes influence warm-rain formation and precipitation enhancement.

This project is intended to support reproducible simulation workflows, visual experiment design, and systematic cloud seeding sensitivity analysis.

## Configuration Schema

The initial configuration schema is defined in `simulation/schema.py`.

The canonical YAML structure contains the following main sections:

```text
schema_version
experiment
environment
background_aerosol
seeding
dynamics
microphysics
output
```

The same schema is used by:

- `configs/default.yaml`
- `configs/marine.yaml`
- `configs/urban.yaml`
- `simulation/config.py`
- `simulation/validation.py`

Missing fields are automatically filled using the default schema when a configuration file is loaded.

### Main Configuration Groups

```yaml
experiment:
  name:
  mode:
  description:
  random_seed:

environment:
  temperature:
  pressure:
  water_vapour_mixing_ratio:
  relative_humidity:
  initial_altitude:
  updraft_velocity:
  duration:
  timestep:

background_aerosol:
  distribution_type:
  number_concentration:
  dry_radius:
  geometric_sigma:
  kappa:
  particle_density:
  chemical_composition:

seeding:
  enabled:
  material_type:
  dry_radius:
  geometric_sigma:
  kappa:
  particle_density:
  number_superdroplets:
  injection_start:
  injection_end:
  injection_altitude:
  delivery_method:

dynamics:
  updraft_strength:
  downdraft_strength:
  turbulence_intensity:
  entrainment_rate:
  detrainment_rate:
  wind_shear:
  convergence:
  cape:
  cin:

microphysics:
  condensation:
  collision:
  sedimentation:

output:
  base_dir:
  save_config:
  save_summary:
  save_timeseries:
```

## Streamlit Input Pages

The app provides separate pages for editing the working configuration:

- `01_environment.py`: atmospheric thermodynamic and parcel-rise settings
- `02_aerosol.py`: background aerosol size distribution and hygroscopicity
- `03_seeding.py`: seeding particle properties and injection timing
- `04_dynamics.py`: dynamic parameters and future parameterization inputs
- `05_run.py`: validation and simulation execution
- `06_results.py`: result loading and basic visualization

All input pages edit `configs/default.yaml` as the current working configuration.
Scenario files such as `configs/marine.yaml` and `configs/urban.yaml` can be loaded from the main app page.

## Configuration Validation

The validation layer separates issues into three severity levels:

- `error`: blocking issue. The simulation should not run.
- `warning`: runnable but physically or numerically questionable.
- `info`: non-blocking note about current assumptions or unimplemented options.

The Run page displays a validation summary and a table containing:

```text
severity | field | message | suggestion
```

The validation logic is implemented in `simulation/validation.py`.

## Runner and Adapter Architecture

The simulation execution layer is separated into three parts:

```text
configs/default.yaml
    ↓
simulation.builder.build_run_spec()
    ↓
simulation.pysdm_adapter.run_adapter()
    ↓
simulation.runner.run_experiment()
    ↓
results/*.csv
```

### Key Files

- `simulation/types.py`: shared dataclasses for run specifications and adapter results
- `simulation/builder.py`: converts normalized configuration into adapter-facing settings
- `simulation/pysdm_adapter.py`: adapter registry and simulation adapter interface
- `simulation/runner.py`: orchestration layer used by the Streamlit Run page

### Adapter Registry

Available adapters are defined in `simulation/pysdm_adapter.py`.

```text
placeholder_warm_cloud
pysdm_parcel
```

`placeholder_warm_cloud` is the current synthetic test adapter.  
`pysdm_parcel` is reserved for the first real PySDM simulation connection in the next development step.

## Real PySDM Adapter

The first real PySDM adapter is connected through:

```text
simulation.adapter = pysdm_parcel
```

This adapter uses the seeding example framework from `PySDM_examples.seeding` and maps the app configuration into a parcel-based warm-cloud hygroscopic seeding simulation.

### Install Optional PySDM Dependencies

```bash
pip install -r requirements-pysdm.txt
```

or, when working from a local PySDM repository, make sure both `PySDM` and `PySDM_examples` are importable in the active environment.

### Run from Streamlit

1. Open the main app page.
2. Set `Simulation Adapter` to `pysdm_parcel`.
3. Open `05. Run Simulation`.
4. Click `Run Experiment`.

### Run from CLI

```bash
python scripts/run_config.py --adapter pysdm_parcel
```

The previous `placeholder_warm_cloud` adapter is still available for UI testing when PySDM is not installed.

## Result Storage

Each simulation run is now saved as a complete result directory:

```text
results/
└── <run_id>/
    ├── config.yaml
    ├── timeseries.csv
    ├── summary.json
    ├── metadata.json
    └── validation_report.json
```

The runner returns the result directory path instead of a single CSV file.

## Progress Reporting

CLI runs now print coarse progress messages:

```bash
python scripts/run_config.py --adapter pysdm_parcel
```

Example:

```text
[01/05 |  20.00%] runner: Normalizing configuration
[02/05 |  40.00%] runner: Building run specification
[03/05 |  60.00%] runner: Running adapter: pysdm_parcel
...
```

For the real PySDM adapter, the current progress is stage-based.  
Fine-grained per-time-step progress will require deeper integration with the PySDM simulation loop.

## Results Dashboard

The `06. Results Dashboard` page provides a research-oriented view of simulation outputs.

Dashboard features:

- Select structured run directories or legacy CSV files
- Show run overview cards
- Show summary metric cards
- Plot recommended diagnostic groups
  - water content
  - radius
  - number concentration
  - supersaturation
- Shade seeding-active time windows when `seeding_active` is available
- Show custom variable plots
- Inspect `summary.json`, `metadata.json`, `config.yaml`, and `validation_report.json`
- Download the time-series CSV from the dashboard

Reusable dashboard utilities are implemented in:

```text
analysis/dashboard.py
```

## Control vs Seeding Workflow

When `experiment.mode` is set to `control_vs_seeding`, the runner now performs paired simulations:

```text
1. control run  : seeding.enabled = false
2. seeding run  : seeding.enabled = true
3. comparison   : seeding - control
```

The output structure is:

```text
results/
└── <run_id>_control_vs_seeding/
    ├── config.yaml
    ├── metadata.json
    ├── summary.json
    ├── comparison.csv
    ├── validation_report.json
    ├── control/
    │   ├── config.yaml
    │   ├── timeseries.csv
    │   ├── summary.json
    │   ├── metadata.json
    │   └── validation_report.json
    └── seeding/
        ├── config.yaml
        ├── timeseries.csv
        ├── summary.json
        ├── metadata.json
        └── validation_report.json
```

The dashboard detects comparison results automatically and shows:

- control vs seeding curves
- seeding minus control difference
- relative change percent
- comparison summary metrics
- control and seeding tables side by side

## Compact Plot Grid

The Results Dashboard uses a compact plot matrix instead of stacking every figure vertically.

Dashboard controls:

- `Plot grid columns`: choose 1–3 columns
- `Maximum plots in dashboard`: limit the number of plots shown
- Comparison results show both:
  - control vs seeding plot matrix
  - seeding minus control difference plot matrix
- Single-run results show:
  - diagnostic plot matrix
  - custom variable plot matrix

## Placeholder Result Warning

`placeholder_warm_cloud` is only a workflow-test adapter. Its curves are synthetic and should not be interpreted as cloud-physics results.

Use it to test:

- app execution
- result saving
- control vs seeding comparison
- dashboard rendering

Use `pysdm_parcel` for real PySDM-based output.

The Results Dashboard now warns when a selected result comes from the placeholder adapter and excludes workflow columns such as `seeding_active` from comparison-variable plots.

## Seeding Efficiency Metrics

Step 9 adds first-pass efficiency metrics for paired control-vs-seeding simulations.

Main metrics:

```text
rain_enhancement_final
rain_enhancement_final_percent
rain_enhancement_max
accumulated_rain_enhancement
accumulated_rain_enhancement_percent
rain_onset_time_shift_s
effective_radius_final_delta_um
droplet_number_final_delta_cm3
cloud_to_rain_conversion_delta
seeding_efficiency_score
```

Sign convention:

```text
delta = seeding - control
rain_onset_time_shift_s = seeding_onset - control_onset
```

A negative rain-onset shift means rain appeared earlier in the seeding run.

`seeding_efficiency_score` is a heuristic dashboard score for quick ranking.  
It is not a final scientific objective function and should be revised after the real PySDM workflow is validated.

## Parameter Sweep Workflow

When `experiment.mode` is set to `parameter_sweep`, the runner generates all combinations from `sweep.parameters`.

Example:

```yaml
experiment:
  mode: parameter_sweep

sweep:
  run_mode: control_vs_seeding
  max_runs: 100
  ranking_metric: comparison.efficiency.seeding_efficiency_score
  parameters:
    - name: seeding.dry_radius
      values: [5.0e-7, 1.0e-6, 1.5e-6]
    - name: seeding.kappa
      values: [0.8, 1.0, 1.2]
```

The output structure is:

```text
results/
└── <run_id>_parameter_sweep/
    ├── config.yaml
    ├── metadata.json
    ├── summary.json
    ├── sweep_summary.csv
    ├── validation_report.json
    └── cases/
        ├── <case result directory>/
        └── ...
```

The Results Dashboard detects sweep results and shows a ranking chart and summary table.

A Streamlit sweep setup page is available:

```text
05. Parameter Sweep
```

## Sweep Time-Series Comparison

The sweep dashboard now emphasizes case-wise time-series comparison rather than ranking alone.

For a `[sweep]` result, open:

```text
07. Results Dashboard → Sweep Time Series
```

You can compare the same variable across multiple sweep cases:

- `rain_water_mixing_ratio`
- `cloud_water_mixing_ratio`
- `supersaturation`
- `effective_radius_um`
- `droplet_number_concentration_cm3`
- `superdroplet_count`

For each variable, choose:

```text
comparison → seeding / control / diff / relative_change_percent
seeding    → seeding/timeseries.csv
control    → control/timeseries.csv
```

Ranking is now shown only as secondary summary information.

## Sweep Sensitivity Diagnostics

The sweep dashboard now checks whether case curves actually differ.

Important interpretation rule:

```text
If all sweep case curves overlap, the sweep did not produce visible parameter sensitivity.
```

This can mean:

- the result is from `placeholder_warm_cloud`
- the adapter does not actually use the swept parameter
- the selected diagnostic is not sensitive to the parameter
- absolute seeding curves were plotted instead of `diff = seeding - control`

For artificial rain evaluation, use the default sweep view:

```text
Output source = comparison
Comparison mode = diff
Variable = rain_water_mixing_ratio / cloud_water_mixing_ratio / supersaturation
```

The dashboard also includes a parameter-response heatmap for two-dimensional sweeps such as dry radius × κ.

## Project Integrity Check

Before running Streamlit after a dashboard update, run:

```bash
python scripts/check_project_integrity.py
```

This checks that `analysis/dashboard.py` and `pages/06_results.py` are compatible and that all dashboard functions required by the Results page are available.

The Results page now imports `analysis.dashboard` as a module instead of importing many individual functions directly. This prevents repeated `ImportError` crashes when dashboard functions are added over time.

## Responsive Results Layout

The Results dashboard now has:

- wider responsive page layout
- less clipping in plots
- compact case labels
- unique legend labels for sweep cases
- optional legend toggle for plot matrices
- build badges to verify whether the latest code is actually loaded

If the UI still looks old after replacing files:

```bash
Ctrl + C
python scripts/check_project_integrity.py
streamlit run app.py
```

This is important because Streamlit can keep the previous imported module in memory until the process is restarted.

## Sweep Plot Legend Handling

Sweep matrix plots now hide legends inside figures by default.  
Case labels are displayed in separate tables so the plotting area remains large and values are easier to read.

Use:

```text
Dashboard → Case legend table
Sweep Time Series → Case legend / Curve value summary / Overlay data
```

This avoids the old problem where long legends compressed the plot and made axis values hard to read.

## Experiment Scenarios and Page Order

The Streamlit page order is now:

```text
00. Experiment Scenarios
01. Atmospheric Environment
02. Background Aerosol Settings
03. Seeding Particle Settings
04. Dynamic Parameters
05. Parameter Sweep
06. Run Simulation
07. Results Dashboard
```

Use the scenario workflow when you want stable, repeatable experiment setups:

```text
1. Set parameters in pages 01–05
2. Save the setup in 00. Experiment Scenarios with a short memo
3. Select that scenario in 06. Run Simulation
4. Inspect outputs in 07. Results Dashboard
```

If older pages still appear after extracting this update, run:

```bash
python scripts/cleanup_old_pages.py
python scripts/check_project_integrity.py
streamlit run app.py
```

Sweep plots now show seeding-active periods with shaded time windows.  
Curve colors are mapped to case labels in a separate styled legend table.

## Scenario-Aware Settings Pages

Pages 01–05 can now save settings directly into a saved scenario.

Workflow:

```text
00. Experiment Scenarios
  - create scenario with name and memo

01–04. Environment / Aerosol / Seeding / Dynamics
  - choose Save target
  - save settings into Current working config or a saved scenario

05. Parameter Sweep
  - choose the scenario/config source
  - save sweep settings into the same scenario

06. Run Simulation
  - choose Scenario to run
  - inspect config and run

07. Results Dashboard
  - inspect results
```

If Streamlit reports duplicate URL pathnames such as `run`, remove old page files:

```bash
python scripts/cleanup_old_pages.py
python scripts/check_project_integrity.py
streamlit run app.py
```

## Growth-pathway Diagnostics

The platform now adds growth-pathway Follow-up style diagnostic columns to saved timeseries when `diagnostics.exper2_mode` is enabled.

Diagnostic groups:

```text
Thermodynamic response
- water_vapour_mixing_ratio
- supersaturation_percent
- relative_humidity_percent
- temperature_K

Water mass response
- cloud_water_mixing_ratio
- rain_water_mixing_ratio
- all_activated_water_mixing_ratio

Number concentration response
- cloud_droplet_concentration
- rain_droplet_concentration
- all_activated_concentration

Size response
- effective_radius_cloud_um
- effective_radius_rain_um
- effective_radius_all_um
```

The Results Dashboard includes an `Growth Pathway Diagnostics` tab for `[comparison]` and `[sweep]` results.  
For sweep results, start with:

```text
Comparison mode = diff
Diagnostic group = Thermodynamic response or Water mass response
```

The Parameter Sweep page also supports:

```text
microphysics.collision = OFF / ON
```

This is needed to reproduce the growth-pathway finding that rain-water response is strongly tied to collision/coalescence.

### Publication plots

`07. Results Dashboard → Publication Plots` provides 300 dpi figures for:

```text
Growth Pathway four-panel (seeding - control or control vs seeding)
Ensemble mean ± std four-panel
Ensemble median + IQR four-panel
Dry radius / κ / injection-time one-factor sensitivity panel
Matched collision OFF / ON panel
```

Each panel includes units and diagnostic provenance codes (`N` native, `D`
derived, `P` proxy, `?` unavailable). The OFAT panel fixes every non-x sweep
parameter at a visible reference value, and the collision panel only includes
conditions having an exact OFF/ON pair. Response-surface plots do not silently
average across additional varying parameters; fix those parameters in the case
filter first.

## Ensemble Statistics

The platform now supports ensemble execution for `single` and `control_vs_seeding` runs, including each parameter-sweep case.

Enable it in:

```text
05. Parameter Sweep → Ensemble Statistics
```

Key settings:

```text
ensemble.enabled
ensemble.n_members
ensemble.seed_start
ensemble.seed_step
```

When enabled, each case is repeated with different random seeds and summarized into:

```text
ensemble_statistics.csv
member_summary.csv
```

The ensemble statistics table includes:

```text
<variable>_mean
<variable>_std
<variable>_median
<variable>_q25
<variable>_q75
<variable>_n_finite
<variable>_finite_fraction
```

The Results Dashboard now supports:

```text
[ensemble] result type
Ensemble Statistics tab
Mean ± std plot
Median + IQR plot
PNG download buttons for plots
```

For sweep ranking with ensemble cases, use a metric such as:

```text
ensemble.metrics.rain_water_mixing_ratio_diff_final_mean
```

## Scenario-named results and simplified dashboard

When a saved scenario is selected in Run Simulation, the run configuration now automatically uses the scenario slug as `experiment.name`.

Example:

```text
Scenario: dry_radius_kappa_sweep
Result directory: results/20260713_XXXXXX_dry_radius_kappa_sweep_parameter_sweep
```

The dashboard also supports sweep cases that were run as ensemble result directories.  
If a sweep result shows no plottable variables, it usually means the result was generated before the latest dashboard/diagnostic update. Rerun the scenario.

Simplified recommended workflow:

```text
00. Save scenario
01–05. Save settings and sweep into that scenario
06. Select scenario and run
07. Select the result with the same scenario name
```

## Progress dashboard and injection-time sweep simplification

Run Simulation now shows:

```text
Run Plan
- sweep cases
- ensemble members
- control/seeding factor
- estimated model runs

Live Progress
- total model runs
- completed
- remaining
- current stage
- recent completion events
```

For injection-time sweeps, Results Dashboard now provides two easier views:

```text
Quick Parameter Effect Summary
- summarizes each case into final/max/integral/peak_time_s
- plots response metric by sweep parameter

Sweep Time Series
- can switch time axis to relative to injection start
- helps compare post-seeding response when absolute-time curves overlap
```

## Compact progress and safe result loading

The run page now updates one compact progress card instead of appending repeated metric rows.

Progress card:

```text
Progress overview
overall progress bar
stage progress bar
Total / Done / Left / Stage
current status
recent events table
```

The Results Dashboard now skips incomplete or empty result directories by default.  
This prevents:

```text
pandas.errors.EmptyDataError: No columns to parse from file
```

while a run is still writing files. Turn on `Show incomplete / in-progress results` only for debugging.

## Accurate model-run progress

The runner now emits explicit `model_run_complete` progress events after each real single/control/seeding model run finishes.

This makes the Run page progress card update during long sweep + ensemble jobs instead of staying at zero until the end.

The dashboard CSV reader was also fixed to call `pd.read_csv()` directly, preventing recursive `safe_read_csv()` calls.

## Dashboard recursion hotfix

If Results Dashboard shows:

```text
RecursionError: maximum recursion depth exceeded
analysis/dashboard.py → safe_read_csv → return safe_read_csv(path)
```

run:

```bash
python scripts/fix_dashboard_recursion.py
python scripts/check_project_integrity.py
```

The correct line inside `safe_read_csv()` is:

```python
return pd.read_csv(path)
```

## Sweep case filtering and coverage sampling

Sweep plots no longer simply take the first `max_cases` rows.  
When selected cases are more than `max_cases`, cases are sampled across the full sweep grid so large values such as `dry_radius = 3.0 µm` are not silently hidden.

The Results Dashboard also includes:

```text
Case filter / focus view
```

Use it to focus on a subset such as:

```text
dry_radius = all
kappa = 0.8
injection_start = 900 s
```

or:

```text
dry_radius = 3.0 µm
kappa = all
injection_start = all
```

Curve labels now include case id and injection start, for example:

```text
c054, r=3µm, κ=1.2, inj=1200s
```


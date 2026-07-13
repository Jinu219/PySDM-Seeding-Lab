# Development Notes

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


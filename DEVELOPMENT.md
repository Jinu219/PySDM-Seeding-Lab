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


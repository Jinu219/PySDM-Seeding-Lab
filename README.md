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

## Current Status

This project is currently in the clean scaffold stage.

The current version focuses on organizing the project architecture before connecting the first real PySDM simulation.  
The PySDM adapter currently acts as an interface placeholder and will later be connected to an actual warm-cloud hygroscopic seeding simulation.

## Development Roadmap

```text
0. Remove legacy experiment traces
1. Define configuration schema
2. Stabilize Streamlit input pages
3. Strengthen validation
4. Organize runner / adapter structure
5. Connect the first real PySDM simulation
6. Improve result storage structure
7. Build result dashboard
8. Add control vs seeding comparison
9. Add efficiency metrics
10. Add parameter sweep workflow
```

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


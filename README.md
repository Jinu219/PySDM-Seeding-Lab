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


# PySDM Seeding Lab

PySDM Seeding Lab is a research-oriented simulation platform for designing, running, and visualizing cloud seeding experiments based on PySDM.

This project aims to move beyond manually editing Python scripts for each experiment. Instead, it provides a structured workflow where atmospheric conditions, aerosol properties, seeding particle parameters, and microphysical options can be configured through YAML files and an interactive Streamlit interface.

## Project Motivation

Until now, PySDM-based cloud seeding simulations have often required direct modification of individual Python scripts or notebooks. This makes it difficult to manage experiment conditions, compare results, and reproduce previous simulations.

The goal of this project is to build a more organized and visual research workflow:

- Define experiment settings using configuration files
- Modify cloud and seeding parameters through an interactive interface
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

## Main Features

Current scaffold:

Streamlit-based project interface
YAML-based experiment configuration
Atmospheric environment settings
Background aerosol settings
Hygroscopic seeding particle settings
Dynamic parameter input page
Simulation runner interface
PySDM adapter placeholder
Result loading and visualization page
Basic analysis module structure

Planned features:

Real PySDM parcel-based seeding simulation
Control vs seeding experiment workflow
Seeding efficiency metrics
Parameter sweep experiments
Scenario presets such as marine, urban, and mountain cloud environments
Result dashboard for cloud water, rain water, droplet number, and size distribution
Seeding condition ranking and optimization workflow

## Project Structure
```
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
│   ├── urban.yaml
│   └── experiment_presets.yaml
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
│
└── results/
```
## Installation
``` pip install -r requirements.txt``` 

## Run the App
``` streamlit run app.py```

## Configuration Example
```
experiment:
  name: default_seeding_test
  mode: control_vs_seeding

environment:
  temperature: 300.0
  pressure: 100000.0
  water_vapour_mixing_ratio: 0.0222
  relative_humidity: 95.0
  updraft_velocity: 1.0
  duration: 1500
  timestep: 15

background_aerosol:
  number_concentration: 100.0
  dry_radius: 7.5e-8
  geometric_sigma: 1.4
  kappa: 0.5

seeding:
  enabled: true
  material_type: hygroscopic
  dry_radius: 1.0e-6
  kappa: 0.8
  number_superdroplets: 100
  injection_start: 900
  injection_end: 1200

microphysics:
  condensation: true
  collision: false
  sedimentation: false
```
## Development Roadmap
1. Clean project scaffold
2. Define YAML configuration schema
3. Build Streamlit parameter input pages
4. Add configuration validation
5. Create simulation runner and PySDM adapter layer
6. Connect the first real PySDM parcel seeding simulation
7. Save simulation metadata with results
8. Add result dashboard
9. Add control vs seeding comparison workflow
10. Add seeding efficiency metrics
11. Add parameter sweep mode
12. Add seeding condition ranking workflow
    
## Project Status

This project is currently in the initial scaffold stage.

The current version focuses on building the project architecture first. The PySDM adapter is prepared as an interface layer and will later be connected to an actual PySDM-based warm-cloud hygroscopic seeding simulation.

## Research Direction

This project is designed as a foundation for studying cloud seeding efficiency using particle-based cloud microphysics.

The long-term goal is to explore how seeding particle properties, background aerosol conditions, injection timing, and cloud dynamics influence warm-rain formation and precipitation enhancement.

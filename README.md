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

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


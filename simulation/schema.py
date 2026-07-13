from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


SCHEMA_VERSION = 1

EXPERIMENT_MODES = [
    "single",
    "control_vs_seeding",
    "parameter_sweep",
]

ADAPTER_NAMES = [
    "placeholder_warm_cloud",
    "pysdm_parcel",
]

SEEDING_MATERIAL_TYPES = [
    "hygroscopic",
    "custom",
]

DELIVERY_METHODS = [
    "idealized_uniform",
    "aircraft",
    "ground_generator",
    "drone",
]

AEROSOL_DISTRIBUTION_TYPES = [
    "single_lognormal",
    "multi_lognormal",
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "experiment": {
        "name": "default_seeding_test",
        "mode": "control_vs_seeding",
        "description": "Basic warm-cloud hygroscopic seeding configuration.",
        "random_seed": 42,
    },
    "simulation": {
        "adapter": "placeholder_warm_cloud",
        "case_name": "base",
        "notes": "Placeholder adapter is used until the first real PySDM simulation is connected.",
    },
    "environment": {
        "temperature": 300.0,
        "pressure": 100000.0,
        "water_vapour_mixing_ratio": 0.0222,
        "relative_humidity": 95.0,
        "initial_altitude": 0.0,
        "updraft_velocity": 1.0,
        "duration": 1500,
        "timestep": 15,
    },
    "background_aerosol": {
        "distribution_type": "single_lognormal",
        "number_concentration": 100.0,
        "dry_radius": 7.5e-8,
        "geometric_sigma": 1.4,
        "kappa": 0.5,
        "particle_density": 1770.0,
        "chemical_composition": "ammonium_sulfate_like",
    },
    "seeding": {
        "enabled": True,
        "material_type": "hygroscopic",
        "dry_radius": 1.0e-6,
        "geometric_sigma": 1.2,
        "kappa": 0.8,
        "particle_density": 1770.0,
        "number_concentration": 10.0,
        "number_superdroplets": 100,
        "injection_start": 900,
        "injection_end": 1200,
        "injection_altitude": 500.0,
        "delivery_method": "idealized_uniform",
    },
    "dynamics": {
        "updraft_strength": 1.0,
        "downdraft_strength": 0.0,
        "turbulence_intensity": 0.0,
        "entrainment_rate": 0.0,
        "detrainment_rate": 0.0,
        "wind_shear": 0.0,
        "convergence": 0.0,
        "cape": 0.0,
        "cin": 0.0,
    },
    "microphysics": {
        "condensation": True,
        "collision": False,
        "sedimentation": False,
    },
    "sweep": {
        "run_mode": "control_vs_seeding",
        "max_runs": 100,
        "ranking_metric": "comparison.efficiency.seeding_efficiency_score",
        "parameters": [
            {
                "name": "seeding.dry_radius",
                "values": [5.0e-7, 1.0e-6, 1.5e-6],
            },
            {
                "name": "seeding.kappa",
                "values": [0.8, 1.0, 1.2],
            },
        ],
    },
    "output": {
        "base_dir": "results",
        "save_config": True,
        "save_summary": True,
        "save_timeseries": True,
    },
}


FIELD_UNITS: Dict[str, Dict[str, str]] = {
    "environment": {
        "temperature": "K",
        "pressure": "Pa",
        "water_vapour_mixing_ratio": "kg/kg",
        "relative_humidity": "%",
        "initial_altitude": "m",
        "updraft_velocity": "m/s",
        "duration": "s",
        "timestep": "s",
    },
    "background_aerosol": {
        "number_concentration": "cm^-3",
        "dry_radius": "m",
        "geometric_sigma": "-",
        "kappa": "-",
        "particle_density": "kg/m^3",
    },
    "seeding": {
        "dry_radius": "m",
        "geometric_sigma": "-",
        "kappa": "-",
        "particle_density": "kg/m^3",
        "number_concentration": "cm^-3",
        "number_superdroplets": "count",
        "injection_start": "s",
        "injection_end": "s",
        "injection_altitude": "m",
    },
    "dynamics": {
        "updraft_strength": "m/s",
        "downdraft_strength": "m/s",
        "turbulence_intensity": "-",
        "entrainment_rate": "1/m",
        "detrainment_rate": "1/m",
        "wind_shear": "1/s",
        "convergence": "1/s",
        "cape": "J/kg",
        "cin": "J/kg",
    },
}


def default_config() -> Dict[str, Any]:
    """Return a deep copy of the canonical default configuration."""
    return deepcopy(DEFAULT_CONFIG)


def deep_merge(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge user configuration into the default schema while preserving unknown custom fields."""
    merged = deepcopy(default)

    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value

    return merged


def normalize_config(config: Dict[str, Any] | None) -> Dict[str, Any]:
    """Fill missing fields using the canonical schema."""
    return deep_merge(DEFAULT_CONFIG, config or {})


def schema_summary() -> List[Dict[str, str]]:
    """Return a table-friendly summary of schema fields and units."""
    rows: List[Dict[str, str]] = []

    def walk(prefix: str, obj: Dict[str, Any]) -> None:
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                walk(full_key, value)
            else:
                section = prefix.split(".")[0] if prefix else ""
                unit = FIELD_UNITS.get(section, {}).get(key, "")
                rows.append(
                    {
                        "field": full_key,
                        "default": str(value),
                        "unit": unit,
                        "type": type(value).__name__,
                    }
                )

    walk("", DEFAULT_CONFIG)
    return rows

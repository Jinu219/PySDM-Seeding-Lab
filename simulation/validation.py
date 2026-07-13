from __future__ import annotations

from typing import Any, Dict, List

from simulation.schema import (
    AEROSOL_DISTRIBUTION_TYPES,
    DELIVERY_METHODS,
    EXPERIMENT_MODES,
    SEEDING_MATERIAL_TYPES,
    SCHEMA_VERSION,
    normalize_config,
)


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate core physical and workflow constraints before running a simulation."""
    cfg = normalize_config(config)
    errors: List[str] = []

    schema_version = cfg.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}.")

    experiment = cfg.get("experiment", {})
    env = cfg.get("environment", {})
    aero = cfg.get("background_aerosol", {})
    seed = cfg.get("seeding", {})
    dyn = cfg.get("dynamics", {})
    microphysics = cfg.get("microphysics", {})

    if experiment.get("mode") not in EXPERIMENT_MODES:
        errors.append(f"experiment.mode must be one of {EXPERIMENT_MODES}.")

    if env.get("temperature", 0) <= 0:
        errors.append("environment.temperature must be positive.")

    if env.get("pressure", 0) <= 0:
        errors.append("environment.pressure must be positive.")

    if env.get("water_vapour_mixing_ratio", -1) < 0:
        errors.append("environment.water_vapour_mixing_ratio must be non-negative.")

    if not 0 <= env.get("relative_humidity", -1) <= 200:
        errors.append("environment.relative_humidity should be between 0 and 200 percent.")

    if env.get("duration", 0) <= 0:
        errors.append("environment.duration must be positive.")

    if env.get("timestep", 0) <= 0:
        errors.append("environment.timestep must be positive.")

    if env.get("timestep", 0) > env.get("duration", 0):
        errors.append("environment.timestep must not be greater than environment.duration.")

    if aero.get("distribution_type") not in AEROSOL_DISTRIBUTION_TYPES:
        errors.append(f"background_aerosol.distribution_type must be one of {AEROSOL_DISTRIBUTION_TYPES}.")

    if aero.get("number_concentration", 0) < 0:
        errors.append("background_aerosol.number_concentration must be non-negative.")

    if aero.get("dry_radius", 0) <= 0:
        errors.append("background_aerosol.dry_radius must be positive.")

    if aero.get("geometric_sigma", 0) <= 1:
        errors.append("background_aerosol.geometric_sigma must be greater than 1.")

    if aero.get("kappa", 0) < 0:
        errors.append("background_aerosol.kappa must be non-negative.")

    if aero.get("particle_density", 0) <= 0:
        errors.append("background_aerosol.particle_density must be positive.")

    if seed.get("material_type") not in SEEDING_MATERIAL_TYPES:
        errors.append(f"seeding.material_type must be one of {SEEDING_MATERIAL_TYPES}.")

    if seed.get("delivery_method") not in DELIVERY_METHODS:
        errors.append(f"seeding.delivery_method must be one of {DELIVERY_METHODS}.")

    if seed.get("enabled", False):
        if seed.get("dry_radius", 0) <= 0:
            errors.append("seeding.dry_radius must be positive.")

        if seed.get("geometric_sigma", 0) <= 1:
            errors.append("seeding.geometric_sigma must be greater than 1.")

        if seed.get("kappa", 0) < 0:
            errors.append("seeding.kappa must be non-negative.")

        if seed.get("particle_density", 0) <= 0:
            errors.append("seeding.particle_density must be positive.")

        if seed.get("number_superdroplets", 0) <= 0:
            errors.append("seeding.number_superdroplets must be positive.")

        if seed.get("injection_start", 0) < 0:
            errors.append("seeding.injection_start must be non-negative.")

        if seed.get("injection_end", 0) <= seed.get("injection_start", 0):
            errors.append("seeding.injection_end must be greater than seeding.injection_start.")

        if seed.get("injection_end", 0) > env.get("duration", 0):
            errors.append("seeding.injection_end must not exceed environment.duration.")

    if dyn.get("turbulence_intensity", 0) < 0:
        errors.append("dynamics.turbulence_intensity must be non-negative.")

    if dyn.get("entrainment_rate", 0) < 0:
        errors.append("dynamics.entrainment_rate must be non-negative.")

    if dyn.get("detrainment_rate", 0) < 0:
        errors.append("dynamics.detrainment_rate must be non-negative.")

    for key in ["condensation", "collision", "sedimentation"]:
        if not isinstance(microphysics.get(key), bool):
            errors.append(f"microphysics.{key} must be true or false.")

    return errors

from typing import Any, Dict, List


def validate_config(config: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    env = config.get("environment", {})
    seed = config.get("seeding", {})
    aero = config.get("background_aerosol", {})

    if env.get("temperature", 0) <= 0:
        errors.append("temperature must be positive.")

    if env.get("pressure", 0) <= 0:
        errors.append("pressure must be positive.")

    if env.get("duration", 0) <= 0:
        errors.append("duration must be positive.")

    if env.get("timestep", 0) <= 0:
        errors.append("timestep must be positive.")

    if aero.get("dry_radius", 0) <= 0:
        errors.append("background aerosol dry_radius must be positive.")

    if aero.get("kappa", 0) < 0:
        errors.append("background aerosol kappa must be non-negative.")

    if seed.get("enabled", False):
        if seed.get("dry_radius", 0) <= 0:
            errors.append("seeding dry_radius must be positive.")
        if seed.get("kappa", 0) < 0:
            errors.append("seeding kappa must be non-negative.")
        if seed.get("injection_end", 0) <= seed.get("injection_start", 0):
            errors.append("injection_end must be greater than injection_start.")

    return errors

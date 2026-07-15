from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from simulation.schema import (
    ADAPTER_NAMES,
    AEROSOL_DISTRIBUTION_TYPES,
    DELIVERY_METHODS,
    ENSEMBLE_EXECUTION_BACKENDS,
    EXPERIMENT_MODES,
    SEEDING_MATERIAL_TYPES,
    SCHEMA_VERSION,
    normalize_config,
)


@dataclass(frozen=True)
class ValidationIssue:
    """A structured validation issue for UI display and future metadata saving."""

    severity: str
    field: str
    message: str
    suggestion: str = ""


def _issue(severity: str, field: str, message: str, suggestion: str = "") -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        field=field,
        message=message,
        suggestion=suggestion,
    )


def validate_config_detailed(config: Dict[str, Any]) -> List[ValidationIssue]:
    """Validate configuration and return structured errors, warnings, and info messages."""
    cfg = normalize_config(config)
    issues: List[ValidationIssue] = []

    schema_version = cfg.get("schema_version")
    experiment = cfg.get("experiment", {})
    simulation = cfg.get("simulation", {})
    env = cfg.get("environment", {})
    aero = cfg.get("background_aerosol", {})
    seed = cfg.get("seeding", {})
    dyn = cfg.get("dynamics", {})
    microphysics = cfg.get("microphysics", {})
    diagnostics = cfg.get("diagnostics", {})
    sweep = cfg.get("sweep", {})
    ensemble = cfg.get("ensemble", {})
    qualification = cfg.get("qualification", {})
    output = cfg.get("output", {})

    # -------------------------------------------------------------------------
    # Schema and workflow checks
    # -------------------------------------------------------------------------
    if schema_version != SCHEMA_VERSION:
        issues.append(
            _issue(
                "error",
                "schema_version",
                f"schema_version must be {SCHEMA_VERSION}.",
                "Reset the configuration or update it using the current schema.",
            )
        )

    if not experiment.get("name"):
        issues.append(
            _issue(
                "warning",
                "experiment.name",
                "experiment.name is empty.",
                "Give each run a descriptive name for reproducibility.",
            )
        )

    if experiment.get("mode") not in EXPERIMENT_MODES:
        issues.append(
            _issue(
                "error",
                "experiment.mode",
                f"experiment.mode must be one of {EXPERIMENT_MODES}.",
                "Choose a supported experiment mode from the main page.",
            )
        )

    if not isinstance(experiment.get("random_seed"), int):
        issues.append(
            _issue(
                "warning",
                "experiment.random_seed",
                "random_seed is not an integer.",
                "Use an integer seed if stochastic reproducibility is needed.",
            )
        )

    sweep_design = str(sweep.get("design", "cartesian"))
    if sweep_design not in {"cartesian", "one_factor_at_reference"}:
        issues.append(
            _issue(
                "error",
                "sweep.design",
                "sweep.design must be cartesian or one_factor_at_reference.",
                "Use one_factor_at_reference only when every parameter declares a reference.",
            )
        )
    elif sweep_design == "one_factor_at_reference":
        for index, parameter in enumerate(sweep.get("parameters", [])):
            values = parameter.get("values", [])
            reference = parameter.get("reference")
            reference_is_selector = isinstance(reference, str) and reference in {
                "min",
                "max",
            }
            reference_is_explicit = any(reference == value for value in values)
            if not reference_is_selector and not reference_is_explicit:
                issues.append(
                    _issue(
                        "error",
                        f"sweep.parameters.{index}.reference",
                        "Each one-factor parameter needs reference=min, reference=max, "
                        "or an explicit value present in values.",
                        "Mark the finest numerical level as the reference.",
                    )
                )

    if not isinstance(ensemble.get("collect_garbage_between_members", False), bool):
        issues.append(
            _issue(
                "error",
                "ensemble.collect_garbage_between_members",
                "collect_garbage_between_members must be true or false.",
                "Leave it false for normal runs; enable it only for memory A/B tests.",
            )
        )

    if ensemble.get("execution_backend", "in_process") not in ENSEMBLE_EXECUTION_BACKENDS:
        issues.append(
            _issue(
                "error",
                "ensemble.execution_backend",
                f"execution_backend must be one of {ENSEMBLE_EXECUTION_BACKENDS}.",
                "Use in_process for minimum overhead or subprocess for member-level memory isolation.",
            )
        )

    execution = cfg.get("execution", {})
    max_workers = execution.get("max_workers", 1)
    if isinstance(max_workers, bool) or not isinstance(max_workers, int):
        issues.append(
            _issue(
                "error",
                "execution.max_workers",
                "max_workers must be an integer.",
                "Use 1 for serial execution or a positive worker count for a server sweep.",
            )
        )
    elif not 1 <= max_workers <= 256:
        issues.append(
            _issue(
                "error",
                "execution.max_workers",
                "max_workers must be between 1 and 256.",
                "Choose a worker count that also fits the server memory budget.",
            )
        )

    if qualification.get("common_random_seed_pairing", False):
        if not ensemble.get("enabled", False):
            issues.append(
                _issue(
                    "error",
                    "qualification.common_random_seed_pairing",
                    "Common-seed pairing requires ensemble execution.",
                    "Enable ensemble and use at least two members.",
                )
            )
        if int(ensemble.get("n_members", 0)) < 2:
            issues.append(
                _issue(
                    "error",
                    "ensemble.n_members",
                    "Common-seed qualification requires at least two members.",
                    "Use two or more deterministic member seeds.",
                )
            )


    # -------------------------------------------------------------------------
    # Simulation adapter checks
    # -------------------------------------------------------------------------
    if simulation.get("adapter") not in ADAPTER_NAMES:
        issues.append(
            _issue(
                "error",
                "simulation.adapter",
                f"simulation.adapter must be one of {ADAPTER_NAMES}.",
                "Choose a supported simulation adapter.",
            )
        )

    if simulation.get("adapter") == "pysdm_parcel":
        issues.append(
            _issue(
                "info",
                "simulation.adapter",
                "pysdm_parcel adapter is selected.",
                "This requires PySDM and PySDM-examples to be installed in the active Python environment.",
            )
        )

    # -------------------------------------------------------------------------
    # Environment checks
    # -------------------------------------------------------------------------
    temperature = env.get("temperature", 0)
    pressure = env.get("pressure", 0)
    qv = env.get("water_vapour_mixing_ratio", -1)
    rh = env.get("relative_humidity", -1)
    duration = env.get("duration", 0)
    timestep = env.get("timestep", 0)
    updraft = env.get("updraft_velocity", 0)

    if temperature <= 0:
        issues.append(
            _issue(
                "error",
                "environment.temperature",
                "temperature must be positive.",
                "Use Kelvin units.",
            )
        )
    elif temperature < 230 or temperature > 320:
        issues.append(
            _issue(
                "warning",
                "environment.temperature",
                "temperature is outside a typical warm-cloud test range.",
                "Check whether this is intentional.",
            )
        )

    if pressure <= 0:
        issues.append(
            _issue(
                "error",
                "environment.pressure",
                "pressure must be positive.",
                "Use Pa units, for example 100000 Pa.",
            )
        )
    elif pressure < 30000 or pressure > 110000:
        issues.append(
            _issue(
                "warning",
                "environment.pressure",
                "pressure is outside a common tropospheric range.",
                "Check whether this pressure level is intended.",
            )
        )

    if qv < 0:
        issues.append(
            _issue(
                "error",
                "environment.water_vapour_mixing_ratio",
                "water_vapour_mixing_ratio must be non-negative.",
                "Use kg/kg units.",
            )
        )
    elif qv > 0.04:
        issues.append(
            _issue(
                "warning",
                "environment.water_vapour_mixing_ratio",
                "water_vapour_mixing_ratio is very high.",
                "Check units. The schema expects kg/kg, not g/kg.",
            )
        )

    if not 0 <= rh <= 200:
        issues.append(
            _issue(
                "error",
                "environment.relative_humidity",
                "relative_humidity should be between 0 and 200 percent.",
                "Use percent units.",
            )
        )
    elif rh < 70:
        issues.append(
            _issue(
                "warning",
                "environment.relative_humidity",
                "relative_humidity is low for warm-cloud activation experiments.",
                "Cloud droplets may not activate unless the parcel becomes supersaturated.",
            )
        )
    elif rh > 105:
        issues.append(
            _issue(
                "info",
                "environment.relative_humidity",
                "relative_humidity is above saturation.",
                "This may be useful for idealized activation tests.",
            )
        )

    if duration <= 0:
        issues.append(
            _issue(
                "error",
                "environment.duration",
                "duration must be positive.",
                "Use seconds.",
            )
        )

    if timestep <= 0:
        issues.append(
            _issue(
                "error",
                "environment.timestep",
                "timestep must be positive.",
                "Use seconds.",
            )
        )
    elif duration > 0 and timestep > duration:
        issues.append(
            _issue(
                "error",
                "environment.timestep",
                "timestep must not be greater than duration.",
                "Reduce timestep or increase duration.",
            )
        )
    elif timestep > 60:
        issues.append(
            _issue(
                "warning",
                "environment.timestep",
                "timestep is relatively large for microphysics evolution.",
                "Check numerical stability and temporal resolution.",
            )
        )

    if updraft < 0:
        issues.append(
            _issue(
                "warning",
                "environment.updraft_velocity",
                "updraft_velocity is negative.",
                "This represents downdraft-like motion and may not match seeding test assumptions.",
            )
        )

    # -------------------------------------------------------------------------
    # Background aerosol checks
    # -------------------------------------------------------------------------
    if aero.get("distribution_type") not in AEROSOL_DISTRIBUTION_TYPES:
        issues.append(
            _issue(
                "error",
                "background_aerosol.distribution_type",
                f"distribution_type must be one of {AEROSOL_DISTRIBUTION_TYPES}.",
                "Choose a supported aerosol distribution type.",
            )
        )

    if aero.get("number_concentration", 0) < 0:
        issues.append(
            _issue(
                "error",
                "background_aerosol.number_concentration",
                "number_concentration must be non-negative.",
                "Use cm^-3 units.",
            )
        )
    elif aero.get("number_concentration", 0) > 5000:
        issues.append(
            _issue(
                "warning",
                "background_aerosol.number_concentration",
                "number_concentration is very high.",
                "Check whether this is intended for a heavily polluted case.",
            )
        )

    if int(aero.get("number_superdroplets", 0)) <= 0:
        issues.append(
            _issue(
                "error",
                "background_aerosol.number_superdroplets",
                "number_superdroplets must be positive.",
                "Use at least 1 super-droplet; run a convergence sweep before quantitative analysis.",
            )
        )
    elif int(aero.get("number_superdroplets", 0)) < 20:
        issues.append(
            _issue(
                "warning",
                "background_aerosol.number_superdroplets",
                "The background aerosol spectrum is represented by very few super-droplets.",
                "Increase the count or demonstrate numerical convergence.",
            )
        )

    if aero.get("dry_radius", 0) <= 0:
        issues.append(
            _issue(
                "error",
                "background_aerosol.dry_radius",
                "dry_radius must be positive.",
                "Use meters, for example 7.5e-8 for 75 nm.",
            )
        )
    elif aero.get("dry_radius", 0) > 5e-6:
        issues.append(
            _issue(
                "warning",
                "background_aerosol.dry_radius",
                "dry_radius is unusually large for background aerosol.",
                "Check whether the value is in meters rather than micrometers.",
            )
        )

    if aero.get("geometric_sigma", 0) <= 1:
        issues.append(
            _issue(
                "error",
                "background_aerosol.geometric_sigma",
                "geometric_sigma must be greater than 1.",
                "Use a value such as 1.3–1.8 for a lognormal distribution.",
            )
        )

    if aero.get("kappa", 0) < 0:
        issues.append(
            _issue(
                "error",
                "background_aerosol.kappa",
                "kappa must be non-negative.",
                "Use κ >= 0.",
            )
        )
    elif aero.get("kappa", 0) > 1.5:
        issues.append(
            _issue(
                "warning",
                "background_aerosol.kappa",
                "kappa is high for common atmospheric aerosol mixtures.",
                "Check whether this material assumption is intended.",
            )
        )

    if aero.get("particle_density", 0) <= 0:
        issues.append(
            _issue(
                "error",
                "background_aerosol.particle_density",
                "particle_density must be positive.",
                "Use kg/m^3 units.",
            )
        )

    # -------------------------------------------------------------------------
    # Seeding checks
    # -------------------------------------------------------------------------
    if seed.get("material_type") not in SEEDING_MATERIAL_TYPES:
        issues.append(
            _issue(
                "error",
                "seeding.material_type",
                f"material_type must be one of {SEEDING_MATERIAL_TYPES}.",
                "Choose a supported material type.",
            )
        )

    if seed.get("delivery_method") not in DELIVERY_METHODS:
        issues.append(
            _issue(
                "error",
                "seeding.delivery_method",
                f"delivery_method must be one of {DELIVERY_METHODS}.",
                "Choose a supported delivery method.",
            )
        )

    if not seed.get("enabled", False):
        issues.append(
            _issue(
                "info",
                "seeding.enabled",
                "Seeding is disabled.",
                "This run can be treated as a control simulation.",
            )
        )
    else:
        if seed.get("dry_radius", 0) <= 0:
            issues.append(
                _issue(
                    "error",
                    "seeding.dry_radius",
                    "dry_radius must be positive.",
                    "Use meters, for example 1.0e-6 for 1 µm.",
                )
            )
        elif seed.get("dry_radius", 0) < aero.get("dry_radius", 0):
            issues.append(
                _issue(
                    "warning",
                    "seeding.dry_radius",
                    "seeding dry radius is smaller than background aerosol dry radius.",
                    "Check whether this matches the intended seeding design.",
                )
            )
        elif seed.get("dry_radius", 0) > 1e-5:
            issues.append(
                _issue(
                    "warning",
                    "seeding.dry_radius",
                    "seeding dry radius is very large.",
                    "Check units. The schema expects meters.",
                )
            )

        if seed.get("geometric_sigma", 0) <= 1:
            issues.append(
                _issue(
                    "error",
                    "seeding.geometric_sigma",
                    "geometric_sigma must be greater than 1.",
                    "Use a value greater than 1 for a lognormal distribution.",
                )
            )

        if seed.get("kappa", 0) < 0:
            issues.append(
                _issue(
                    "error",
                    "seeding.kappa",
                    "kappa must be non-negative.",
                    "Use κ >= 0.",
                )
            )
        elif seed.get("kappa", 0) > 1.5:
            issues.append(
                _issue(
                    "warning",
                    "seeding.kappa",
                    "seeding kappa is high.",
                    "Check whether this is intended for highly hygroscopic material.",
                )
            )

        if seed.get("particle_density", 0) <= 0:
            issues.append(
                _issue(
                    "error",
                    "seeding.particle_density",
                    "particle_density must be positive.",
                    "Use kg/m^3 units.",
                )
            )

        if seed.get("number_concentration", 0) < 0:
            issues.append(
                _issue(
                    "error",
                    "seeding.number_concentration",
                    "number_concentration must be non-negative.",
                    "Use cm^-3 units.",
                )
            )
        elif seed.get("number_concentration", 0) == 0:
            issues.append(
                _issue(
                    "warning",
                    "seeding.number_concentration",
                    "seeding number concentration is zero.",
                    "Injected super-droplets may have zero physical multiplicity.",
                )
            )

        if seed.get("number_superdroplets", 0) <= 0:
            issues.append(
                _issue(
                    "error",
                    "seeding.number_superdroplets",
                    "number_superdroplets must be positive.",
                    "Use at least 1 super-droplet.",
                )
            )

        if seed.get("injection_start", 0) < 0:
            issues.append(
                _issue(
                    "error",
                    "seeding.injection_start",
                    "injection_start must be non-negative.",
                    "Use seconds from simulation start.",
                )
            )

        if seed.get("injection_end", 0) <= seed.get("injection_start", 0):
            issues.append(
                _issue(
                    "error",
                    "seeding.injection_end",
                    "injection_end must be greater than injection_start.",
                    "Increase injection_end or decrease injection_start.",
                )
            )

        if duration > 0 and seed.get("injection_end", 0) > duration:
            issues.append(
                _issue(
                    "error",
                    "seeding.injection_end",
                    "injection_end must not exceed environment.duration.",
                    "Keep injection time inside the simulation window.",
                )
            )

        injection_duration = seed.get("injection_end", 0) - seed.get("injection_start", 0)
        if injection_duration > 0 and duration > 0 and injection_duration / duration > 0.7:
            issues.append(
                _issue(
                    "warning",
                    "seeding.injection_end",
                    "injection duration occupies more than 70% of the simulation.",
                    "Check whether this should be continuous seeding.",
                )
            )

    # -------------------------------------------------------------------------
    # Dynamics checks
    # -------------------------------------------------------------------------
    if dyn.get("turbulence_intensity", 0) < 0:
        issues.append(
            _issue(
                "error",
                "dynamics.turbulence_intensity",
                "turbulence_intensity must be non-negative.",
                "Use a non-negative value.",
            )
        )

    if dyn.get("entrainment_rate", 0) < 0:
        issues.append(
            _issue(
                "error",
                "dynamics.entrainment_rate",
                "entrainment_rate must be non-negative.",
                "Use a non-negative value.",
            )
        )

    if dyn.get("detrainment_rate", 0) < 0:
        issues.append(
            _issue(
                "error",
                "dynamics.detrainment_rate",
                "detrainment_rate must be non-negative.",
                "Use a non-negative value.",
            )
        )

    if dyn.get("entrainment_rate", 0) > 0 or dyn.get("detrainment_rate", 0) > 0:
        issues.append(
            _issue(
                "info",
                "dynamics.entrainment_rate",
                "Entrainment or detrainment is configured.",
                "These values are stored but will only affect results after the adapter implements the parameterization.",
            )
        )

    if dyn.get("cape", 0) > 0 or dyn.get("cin", 0) > 0:
        issues.append(
            _issue(
                "info",
                "dynamics.cape",
                "CAPE/CIN values are configured.",
                "These are currently scenario descriptors, not direct PySDM inputs.",
            )
        )

    # -------------------------------------------------------------------------
    # Microphysics and output checks
    # -------------------------------------------------------------------------
    for key in ["condensation", "collision", "sedimentation"]:
        if not isinstance(microphysics.get(key), bool):
            issues.append(
                _issue(
                    "error",
                    f"microphysics.{key}",
                    f"microphysics.{key} must be true or false.",
                    "Use YAML boolean values.",
                )
            )

    if not microphysics.get("condensation", True):
        issues.append(
            _issue(
                "warning",
                "microphysics.condensation",
                "condensation is disabled.",
                "Warm-cloud seeding tests usually require condensation growth.",
            )
        )

    activation_radius = diagnostics.get("activation_radius_threshold", 0)
    rain_radius = diagnostics.get("rain_radius_threshold", 0)
    if activation_radius <= 0:
        issues.append(
            _issue(
                "error",
                "diagnostics.activation_radius_threshold",
                "activation_radius_threshold must be positive.",
                "Use a wet-radius threshold such as 0.5e-6 m.",
            )
        )
    if rain_radius <= 0:
        issues.append(
            _issue(
                "error",
                "diagnostics.rain_radius_threshold",
                "rain_radius_threshold must be positive.",
                "Use a wet-radius threshold such as 25e-6 m.",
            )
        )
    if activation_radius > 0 and rain_radius > 0 and activation_radius >= rain_radius:
        issues.append(
            _issue(
                "error",
                "diagnostics.rain_radius_threshold",
                "rain_radius_threshold must exceed activation_radius_threshold.",
                "Keep cloud and rain radius ranges ordered and non-overlapping.",
            )
        )

    spectrum_cfg = diagnostics.get("wet_radius_spectrum", {})
    if not isinstance(spectrum_cfg, dict):
        issues.append(
            _issue(
                "error",
                "diagnostics.wet_radius_spectrum",
                "wet_radius_spectrum must be a mapping.",
                "Reset this section to the default spectrum configuration.",
            )
        )
    else:
        spectrum_enabled = spectrum_cfg.get("enabled", True)
        if not isinstance(spectrum_enabled, bool):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.wet_radius_spectrum.enabled",
                    "enabled must be true or false.",
                    "Use a YAML boolean value.",
                )
            )

        minimum_radius = spectrum_cfg.get("min_radius", 0.05e-6)
        maximum_radius = spectrum_cfg.get("max_radius", 1000.0e-6)
        n_bins = spectrum_cfg.get("n_bins", 32)
        factors = spectrum_cfg.get("threshold_factors", [0.8, 1.0, 1.2])
        checkpoints = spectrum_cfg.get("checkpoint_times", [])
        checkpoint_interval = spectrum_cfg.get("checkpoint_interval_seconds", 10.0)

        if not isinstance(n_bins, int) or isinstance(n_bins, bool) or not 8 <= n_bins <= 256:
            issues.append(
                _issue(
                    "error",
                    "diagnostics.wet_radius_spectrum.n_bins",
                    "n_bins must be an integer between 8 and 256.",
                    "Use 32 bins for the default checkpoint diagnostic.",
                )
            )

        numeric_bounds = isinstance(minimum_radius, (int, float)) and isinstance(
            maximum_radius, (int, float)
        )
        if not numeric_bounds or minimum_radius <= 0 or maximum_radius <= minimum_radius:
            issues.append(
                _issue(
                    "error",
                    "diagnostics.wet_radius_spectrum.min_radius",
                    "Spectrum bounds must satisfy 0 < min_radius < max_radius.",
                    "Use SI metres, for example 0.05e-6 to 1000e-6.",
                )
            )

        valid_factors = (
            isinstance(factors, list)
            and bool(factors)
            and all(isinstance(value, (int, float)) and value > 0 for value in factors)
        )
        if not valid_factors:
            issues.append(
                _issue(
                    "error",
                    "diagnostics.wet_radius_spectrum.threshold_factors",
                    "threshold_factors must be a non-empty list of positive numbers.",
                    "Use [0.8, 1.0, 1.2] for the default robustness test.",
                )
            )
        elif not any(abs(float(value) - 1.0) < 1.0e-12 for value in factors):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.wet_radius_spectrum.threshold_factors",
                    "threshold_factors must include the baseline factor 1.0.",
                    "Add 1.0 so robustness results retain the configured definition.",
                )
            )
        elif numeric_bounds and activation_radius > 0 and rain_radius > 0:
            if minimum_radius >= activation_radius * min(factors):
                issues.append(
                    _issue(
                        "error",
                        "diagnostics.wet_radius_spectrum.min_radius",
                        "min_radius must be below the smallest tested activation threshold.",
                        "Decrease min_radius or narrow threshold_factors.",
                    )
                )
            if maximum_radius <= rain_radius * max(factors):
                issues.append(
                    _issue(
                        "error",
                        "diagnostics.wet_radius_spectrum.max_radius",
                        "max_radius must exceed the largest tested rain threshold.",
                        "Increase max_radius or narrow threshold_factors.",
                    )
                )

        if not isinstance(checkpoints, list) or not all(
            isinstance(value, (int, float)) for value in checkpoints
        ):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.wet_radius_spectrum.checkpoint_times",
                    "checkpoint_times must be a list of times in seconds.",
                    "Use [] for automatic start/injection/end checkpoints.",
                )
            )
        elif any(float(value) < 0 or (duration > 0 and float(value) > duration) for value in checkpoints):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.wet_radius_spectrum.checkpoint_times",
                    "Every checkpoint must fall inside the simulation duration.",
                    "Remove out-of-range values or use [] for automatic checkpoints.",
                )
            )

        if (
            not isinstance(checkpoint_interval, (int, float))
            or isinstance(checkpoint_interval, bool)
            or checkpoint_interval <= 0
        ):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.wet_radius_spectrum.checkpoint_interval_seconds",
                    "checkpoint_interval_seconds must be positive.",
                    "Use 10 seconds for the observation-informed onset-timing cadence.",
                )
            )

    water_budget_cfg = diagnostics.get("water_budget", {})
    if not isinstance(water_budget_cfg, dict):
        issues.append(
            _issue(
                "error",
                "diagnostics.water_budget",
                "water_budget must be a mapping.",
                "Reset this section to the default quality-gate configuration.",
            )
        )
    else:
        warning_drift = water_budget_cfg.get("warning_relative_drift_percent", 0.01)
        failure_drift = water_budget_cfg.get("failure_relative_drift_percent", 0.1)
        if not isinstance(water_budget_cfg.get("enabled", True), bool):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.water_budget.enabled",
                    "enabled must be true or false.",
                    "Use a YAML boolean value.",
                )
            )
        valid_budget_limits = all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
            for value in (warning_drift, failure_drift)
        )
        if not valid_budget_limits or warning_drift >= failure_drift:
            issues.append(
                _issue(
                    "error",
                    "diagnostics.water_budget.failure_relative_drift_percent",
                    "Water-budget limits must satisfy 0 < warning < failure.",
                    "Use 0.01% warning and 0.1% failure for the default quality gate.",
                )
            )

    convergence_cfg = diagnostics.get("numerical_convergence", {})
    if not isinstance(convergence_cfg, dict):
        issues.append(
            _issue(
                "error",
                "diagnostics.numerical_convergence",
                "numerical_convergence must be a mapping.",
                "Reset this section to the default convergence configuration.",
            )
        )
    else:
        convergence_enabled = convergence_cfg.get("enabled", True)
        tolerance = convergence_cfg.get("relative_tolerance_percent", 5.0)
        reference_floor = convergence_cfg.get("relative_reference_floor", 1.0e-12)
        convergence_metrics = convergence_cfg.get("metrics", [])
        if not isinstance(convergence_enabled, bool):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.numerical_convergence.enabled",
                    "enabled must be true or false.",
                    "Use a YAML boolean value.",
                )
            )
        if (
            not isinstance(tolerance, (int, float))
            or isinstance(tolerance, bool)
            or tolerance <= 0
        ):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.numerical_convergence.relative_tolerance_percent",
                    "relative_tolerance_percent must be positive.",
                    "Use 5.0 for a 5% next-finest resolution criterion.",
                )
            )
        if (
            not isinstance(reference_floor, (int, float))
            or isinstance(reference_floor, bool)
            or reference_floor <= 0
        ):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.numerical_convergence.relative_reference_floor",
                    "relative_reference_floor must be positive.",
                    "Use 1e-12 unless the selected metric has a justified absolute scale.",
                )
            )
        if not isinstance(convergence_metrics, list) or not all(
            isinstance(metric, str) for metric in convergence_metrics
        ):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.numerical_convergence.metrics",
                    "metrics must be a list of summary-column names.",
                    "Use [] to select the available default metrics automatically.",
                )
            )

    transition_cfg = diagnostics.get("spectrum_transition", {})
    if not isinstance(transition_cfg, dict):
        issues.append(
            _issue(
                "error",
                "diagnostics.spectrum_transition",
                "spectrum_transition must be a mapping.",
                "Reset this section to the default transition configuration.",
            )
        )
    else:
        transition_enabled = transition_cfg.get("enabled", True)
        transition_threshold = transition_cfg.get("rain_volume_fraction_threshold", 0.01)
        transition_thresholds = transition_cfg.get(
            "rain_volume_fraction_thresholds", [0.005, 0.01, 0.02]
        )
        if not isinstance(transition_enabled, bool):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.spectrum_transition.enabled",
                    "enabled must be true or false.",
                    "Use a YAML boolean value.",
                )
            )
        valid_transition_threshold = (
            isinstance(transition_threshold, (int, float))
            and not isinstance(transition_threshold, bool)
            and 0 < float(transition_threshold) < 1
        )
        if not valid_transition_threshold:
            issues.append(
                _issue(
                    "error",
                    "diagnostics.spectrum_transition.rain_volume_fraction_threshold",
                    "rain_volume_fraction_threshold must be between 0 and 1.",
                    "Use 0.01 for a 1% activated-liquid transition threshold.",
                )
            )
        valid_transition_thresholds = (
            isinstance(transition_thresholds, list)
            and bool(transition_thresholds)
            and all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and 0 < float(value) < 1
                for value in transition_thresholds
            )
        )
        if not valid_transition_thresholds:
            issues.append(
                _issue(
                    "error",
                    "diagnostics.spectrum_transition.rain_volume_fraction_thresholds",
                    "rain_volume_fraction_thresholds must be a non-empty list between 0 and 1.",
                    "Use [0.005, 0.01, 0.02] to bracket the operational 1% baseline.",
                )
            )
        elif valid_transition_threshold and not any(
            abs(float(value) - float(transition_threshold)) < 1.0e-12
            for value in transition_thresholds
        ):
            issues.append(
                _issue(
                    "error",
                    "diagnostics.spectrum_transition.rain_volume_fraction_thresholds",
                    "The sensitivity thresholds must include rain_volume_fraction_threshold.",
                    "Include the operational baseline so the audit can identify it explicitly.",
                )
            )
    if microphysics.get("collision", False):
        issues.append(
            _issue(
                "info",
                "microphysics.collision",
                "collision is enabled.",
                "The current adapter must support collision for this option to affect results.",
            )
        )

    if not output.get("base_dir"):
        issues.append(
            _issue(
                "error",
                "output.base_dir",
                "output.base_dir is empty.",
                "Set an output directory such as results.",
            )
        )

    return issues


def validation_summary(config: Dict[str, Any]) -> Dict[str, int]:
    """Return counts by validation severity."""
    issues = validate_config_detailed(config)
    return {
        "error": sum(issue.severity == "error" for issue in issues),
        "warning": sum(issue.severity == "warning" for issue in issues),
        "info": sum(issue.severity == "info" for issue in issues),
        "total": len(issues),
    }


def validation_report_rows(config: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return a table-friendly validation report."""
    return [asdict(issue) for issue in validate_config_detailed(config)]


def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    Backward-compatible validation function.

    Returns only error messages, so existing code can use:
    errors = validate_config(config)
    """
    return [
        issue.message
        for issue in validate_config_detailed(config)
        if issue.severity == "error"
    ]

from __future__ import annotations

from typing import Any, Callable, Dict

import numpy as np
import pandas as pd

from simulation.progress import ProgressCallback, emit_progress
from simulation.schema import diagnostic_radius_thresholds
from simulation.types import AdapterResult, SimulationRunSpec
from simulation.wet_radius_spectrum import (
    ROBUSTNESS_TABLE_NAME,
    SPECTRUM_TABLE_NAME,
    build_spectrum_bin_edges,
    build_threshold_robustness_table,
    build_wet_radius_spectrum_table,
    resolve_spectrum_checkpoint_times,
    wet_radius_spectrum_config,
)


R_DRY_AIR = 287.05  # J kg^-1 K^-1


def _require_pysdm() -> Dict[str, Any]:
    """
    Import PySDM and PySDM-examples lazily.

    This keeps the Streamlit app usable even when PySDM is not installed.
    The actual import is only required when the `pysdm_parcel` adapter is selected.
    """
    try:
        import PySDM
        import PySDM_examples
        from PySDM import Formulae
        from PySDM.initialisation.sampling.spectral_sampling import ConstantMultiplicity
        from PySDM.initialisation.spectra import Lognormal
        from PySDM.physics import si
        from PySDM_examples.seeding.settings import Settings
        from simulation.native_parcel_simulation import (
            NATIVE_PRODUCT_BUILD_ID,
            NativeParcelSimulation,
        )
    except Exception as exc:  # pragma: no cover - depends on external PySDM install
        raise RuntimeError(
            "PySDM parcel adapter requires PySDM and PySDM-examples.\n\n"
            "Install them with:\n"
            "  pip install PySDM PySDM-examples\n\n"
            "If you are using a local PySDM repository, activate the correct environment "
            "and make sure PySDM and PySDM_examples are importable through PYTHONPATH."
        ) from exc

    return {
        "Formulae": Formulae,
        "ConstantMultiplicity": ConstantMultiplicity,
        "Lognormal": Lognormal,
        "si": si,
        "Settings": Settings,
        "Simulation": NativeParcelSimulation,
        "native_product_build_id": NATIVE_PRODUCT_BUILD_ID,
        "pysdm_version": getattr(PySDM, "__version__", "unknown"),
        "pysdm_examples_version": getattr(PySDM_examples, "__version__", "unknown"),
    }


def _air_density_kg_m3(pressure_pa: float, temperature_k: float) -> float:
    """Return dry-air density from ideal-gas approximation."""
    return pressure_pa / (R_DRY_AIR * temperature_k)


def _number_concentration_cm3_to_per_kg(
    number_concentration_cm3: float,
    pressure_pa: float,
    temperature_k: float,
) -> float:
    """
    Convert number concentration from cm^-3 to kg_dry_air^-1.

    PySDM seeding examples define aerosol spectra using number per dry-air mass.
    The app UI stores concentration in cm^-3, so this converter bridges the two.
    """
    number_concentration_m3 = number_concentration_cm3 * 1.0e6
    rho_d = _air_density_kg_m3(pressure_pa=pressure_pa, temperature_k=temperature_k)
    return number_concentration_m3 / rho_d


def _make_injection_rate(
    *,
    enabled: bool,
    injection_start_s: float,
    injection_end_s: float,
    timestep_s: float,
    total_superdroplets: int,
) -> Callable[[float], int]:
    """
    Build a stateful PySDM seeding-rate function.

    PySDM's Seeding dynamic expects a callable that receives the current model time
    and returns how many super-droplets should be injected at that step.
    """
    if not enabled or total_superdroplets <= 0:
        return lambda time_s: 0

    active_duration_s = max(injection_end_s - injection_start_s, timestep_s)
    n_active_steps = max(1, int(np.ceil(active_duration_s / timestep_s)))
    per_step = max(1, int(np.ceil(total_superdroplets / n_active_steps)))

    state = {"remaining": int(total_superdroplets)}

    def injection_rate(time_s: float) -> int:
        if state["remaining"] <= 0:
            return 0

        if injection_start_s <= float(time_s) <= injection_end_s:
            n_to_inject = min(per_step, state["remaining"])
            state["remaining"] -= n_to_inject
            return int(n_to_inject)

        return 0

    return injection_rate


def _sample_spectrum_deterministic(sampler: Any, *, n_sd: int, backend: Any | None = None):
    """
    Sample a PySDM spectrum while tolerating PySDM API differences.

    Some installed PySDM versions expose `sample_deterministic(...)`, while
    others expose a more generic `sample(...)` method. This helper keeps the
    adapter compatible with both.
    """
    method_names = (
        "sample_deterministic",
        "sample",
    )

    last_error: Exception | None = None

    for method_name in method_names:
        method = getattr(sampler, method_name, None)
        if not callable(method):
            continue

        call_attempts = []
        if backend is not None:
            call_attempts.extend(
                [
                    lambda: method(n_sd=n_sd, backend=backend),
                    lambda: method(n_sd, backend=backend),
                ]
            )

        call_attempts.extend(
            [
                lambda: method(n_sd=n_sd),
                lambda: method(n_sd),
            ]
        )

        for call in call_attempts:
            try:
                return call()
            except TypeError as exc:
                last_error = exc

    available = [name for name in dir(sampler) if not name.startswith("_")]
    raise AttributeError(
        "Could not sample spectrum from ConstantMultiplicity. "
        "Tried methods: sample_deterministic, sample. "
        f"Available public attributes/methods: {available}"
    ) from last_error

def _configure_settings(spec: SimulationRunSpec, progress_callback: ProgressCallback = None) -> Any:
    """Create and override PySDM_examples.seeding.Settings from app configuration."""
    emit_progress(progress_callback, "adapter", 1, 5, "Creating PySDM Settings")
    modules = _require_pysdm()

    Formulae = modules["Formulae"]
    ConstantMultiplicity = modules["ConstantMultiplicity"]
    Lognormal = modules["Lognormal"]
    Settings = modules["Settings"]
    si = modules["si"]

    settings_dict = spec.settings
    env = settings_dict.get("environment", {})
    aero = settings_dict.get("background_aerosol", {})
    seed = settings_dict.get("seeding", {})
    microphysics = settings_dict.get("microphysics", {})

    random_seed = int(spec.config.get("experiment", {}).get("random_seed", 42))
    formulae = Formulae(seed=random_seed)

    duration_s = int(env.get("duration", 1500))
    timestep_s = int(env.get("timestep", 15))
    temperature_k = float(env.get("temperature", 300.0))
    pressure_pa = float(env.get("pressure", 100000.0))
    qv_kg_kg = float(env.get("water_vapour_mixing_ratio", 0.0222))
    updraft_m_s = float(env.get("updraft_velocity", 1.0))
    activation_radius_m, rain_radius_m = diagnostic_radius_thresholds(spec.config)

    n_sd_initial = int(aero.get("number_superdroplets", 100))
    # Older scenario files predate the explicit background super-droplet field.
    if "number_superdroplets" not in aero:
        n_sd_initial = 100

    seeding_enabled = bool(seed.get("enabled", True))
    n_sd_seeding = int(seed.get("number_superdroplets", 100)) if seeding_enabled else 1

    injection_rate = _make_injection_rate(
        enabled=seeding_enabled,
        injection_start_s=float(seed.get("injection_start", 900)),
        injection_end_s=float(seed.get("injection_end", 1200)),
        timestep_s=timestep_s,
        total_superdroplets=n_sd_seeding,
    )

    settings = Settings(
        super_droplet_injection_rate=injection_rate,
        n_sd_initial=n_sd_initial,
        n_sd_seeding=n_sd_seeding,
        rain_water_radius_threshold=rain_radius_m * si.m,
        formulae=formulae,
        enable_collisions=bool(microphysics.get("collision", False)),
    )

    # Environment overrides
    settings.t_max = duration_s * si.s
    settings.timestep = timestep_s * si.s
    settings.initial_temperature = temperature_k * si.K
    settings.initial_total_pressure = pressure_pa * si.Pa
    settings.initial_water_vapour_mixing_ratio = qv_kg_kg
    settings.w_min = updraft_m_s * si.m / si.s
    settings.w_max = updraft_m_s * si.m / si.s
    settings.updraft = lambda _t: updraft_m_s * si.m / si.s

    emit_progress(progress_callback, "adapter", 2, 5, "Mapping aerosol and seeding spectra")

    # Background aerosol spectrum
    background_n_per_kg = _number_concentration_cm3_to_per_kg(
        number_concentration_cm3=float(aero.get("number_concentration", 100.0)),
        pressure_pa=pressure_pa,
        temperature_k=temperature_k,
    )
    settings.initial_aerosol_kappa = float(aero.get("kappa", 0.5))
    settings.initial_aerosol_dry_radii = Lognormal(
        norm_factor=background_n_per_kg * settings.mass_of_dry_air,
        m_mode=float(aero.get("dry_radius", 7.5e-8)) * si.m,
        s_geom=float(aero.get("geometric_sigma", 1.4)),
    )

    # Seeding particle spectrum and composition
    seeding_n_per_kg = _number_concentration_cm3_to_per_kg(
        number_concentration_cm3=float(seed.get("number_concentration", 10.0)),
        pressure_pa=pressure_pa,
        temperature_k=temperature_k,
    )

    seed_sampler = ConstantMultiplicity(
        Lognormal(
            norm_factor=seeding_n_per_kg * settings.mass_of_dry_air,
            m_mode=float(seed.get("dry_radius", 1.0e-6)) * si.m,
            s_geom=float(seed.get("geometric_sigma", 1.2)),
        )
    )
    r_dry_seed, seed_multiplicity = _sample_spectrum_deterministic(
        seed_sampler,
        n_sd=n_sd_seeding,
    )

    v_dry_seed = formulae.trivia.volume(radius=r_dry_seed)
    seed_kappa = float(seed.get("kappa", 0.8))

    settings.seeded_particle_multiplicity = seed_multiplicity
    settings.seeded_particle_extensive_attributes = {
        "signed water mass": [0.0001 * si.ng] * n_sd_seeding,
        "dry volume": v_dry_seed,
        "kappa times dry volume": seed_kappa * v_dry_seed,
    }

    return settings


def _extract_product(products: Dict[str, np.ndarray], *names: str) -> np.ndarray | None:
    """Find a product array by trying multiple possible product names."""
    for name in names:
        if name in products:
            return np.asarray(products[name])
    return None


def _output_to_dataframe(output: Dict[str, Any], spec: SimulationRunSpec) -> pd.DataFrame:
    """Convert PySDM example output dictionary into the app's standard timeseries DataFrame."""
    products = output.get("products", {})

    time = _extract_product(products, "time", "Time")
    if time is None:
        env = spec.settings.get("environment", {})
        duration = int(env.get("duration", 1500))
        timestep = int(env.get("timestep", 15))
        time = np.arange(0, duration + timestep, timestep)

    df = pd.DataFrame({"time_s": np.asarray(time, dtype=float)})

    product_mapping = {
        "temperature_K": ("temperature_K", "T"),
        "pressure_Pa": ("pressure_Pa", "p"),
        "water_vapour_mixing_ratio": (
            "water_vapour_mixing_ratio",
            "water vapour mixing ratio",
        ),
        "unactivated_water_mixing_ratio": ("unactivated_water_mixing_ratio",),
        "cloud_water_mixing_ratio": ("cloud_water_mixing_ratio",),
        "rain_water_mixing_ratio": (
            "rain_water_mixing_ratio",
            "rain water mixing ratio",
        ),
        "total_liquid_water_mixing_ratio": ("total_liquid_water_mixing_ratio",),
        "cloud_droplet_concentration": (
            "cloud_droplet_concentration",
            "n_drop",
            "droplet concentration",
            "n_drop_cm3",
        ),
        "rain_droplet_concentration": ("rain_droplet_concentration",),
        "effective_radius_cloud_um": (
            "effective_radius_cloud_um",
            "r_eff",
            "effective radius",
            "effective_radius",
        ),
        "effective_radius_rain_um": ("effective_radius_rain_um",),
        "effective_radius_all_um": ("effective_radius_all_um",),
        "superdroplet_count": (
            "superdroplet_count",
            "sd_count",
            "super droplet count",
        ),
    }

    for out_name, candidates in product_mapping.items():
        values = _extract_product(products, *candidates)
        if values is not None:
            df[out_name] = np.asarray(values, dtype=float)

    relative_humidity = _extract_product(products, "relative_humidity", "RH")
    if relative_humidity is not None:
        relative_humidity = np.asarray(relative_humidity, dtype=float)
        finite = relative_humidity[np.isfinite(relative_humidity)]
        if finite.size and np.nanquantile(np.abs(finite), 0.95) <= 2.0:
            relative_humidity = relative_humidity * 100.0
        df["relative_humidity_percent"] = relative_humidity
        df["supersaturation_percent"] = relative_humidity - 100.0

    # Backward-compatible aliases used by older dashboards and summaries.
    if "cloud_droplet_concentration" in df.columns:
        df["droplet_number_concentration_cm3"] = df["cloud_droplet_concentration"]
    if "rain_droplet_concentration" in df.columns:
        df["rain_drop_number_concentration"] = df["rain_droplet_concentration"]
    if "effective_radius_all_um" in df.columns:
        df["effective_radius_um"] = df["effective_radius_all_um"]

    seed = spec.settings.get("seeding", {})
    injection_start = float(seed.get("injection_start", np.inf))
    injection_end = float(seed.get("injection_end", -np.inf))
    seeding_enabled = bool(seed.get("enabled", False))
    df["seeding_active"] = (
        seeding_enabled
        & (df["time_s"] >= injection_start)
        & (df["time_s"] <= injection_end)
    ).astype(int)

    return df


def run_pysdm_parcel_simulation(
    spec: SimulationRunSpec,
    progress_callback: ProgressCallback = None,
) -> AdapterResult:
    """
    Run the PySDM parcel seeding simulation with project-owned native products.

    `PySDM_examples.seeding.Settings` remains the compatible settings layer;
    `NativeParcelSimulation` owns the builder and diagnostic product list.
    """
    modules = _require_pysdm()
    Simulation = modules["Simulation"]

    settings = _configure_settings(spec, progress_callback=progress_callback)

    env = spec.settings.get("environment", {})
    duration = int(env.get("duration", 1500))
    timestep = int(env.get("timestep", 15))
    expected_steps = int(duration / max(timestep, 1)) + 1

    emit_progress(progress_callback, "adapter", 3, 5, "Initializing PySDM Simulation object")
    activation_radius_m, _ = diagnostic_radius_thresholds(spec.config)
    spectrum_cfg = wet_radius_spectrum_config(spec.config)
    spectrum_enabled = bool(spectrum_cfg.get("enabled", True))
    spectrum_edges = build_spectrum_bin_edges(spec.config) if spectrum_enabled else np.asarray([])
    spectrum_checkpoints = (
        resolve_spectrum_checkpoint_times(spec.config) if spectrum_enabled else []
    )
    simulation = Simulation(
        settings=settings,
        activation_radius_threshold=activation_radius_m,
        spectrum_radius_bin_edges=spectrum_edges if spectrum_enabled else None,
        spectrum_checkpoint_times=tuple(spectrum_checkpoints),
    )

    emit_progress(
        progress_callback,
        "adapter",
        4,
        5,
        f"Running PySDM simulation internally; expected output steps: {expected_steps}",
    )
    output = simulation.run()

    emit_progress(progress_callback, "adapter", 5, 5, "Converting PySDM output to DataFrame")
    df = _output_to_dataframe(output, spec)
    activation_radius_m, rain_radius_m = diagnostic_radius_thresholds(spec.config)
    spectrum_df = build_wet_radius_spectrum_table(
        output.get("spectra", {}),
        spectrum_edges,
        spec.config,
    )
    robustness_df = build_threshold_robustness_table(spectrum_df, spec.config)

    summary = {
        "adapter": "pysdm_parcel",
        "is_placeholder": False,
        "n_time_steps": int(len(df)),
        "native_product_build_id": modules["native_product_build_id"],
        "native_diagnostic_columns": [
            column
            for column in (
                "temperature_K",
                "pressure_Pa",
                "water_vapour_mixing_ratio",
                "relative_humidity_percent",
                "cloud_water_mixing_ratio",
                "rain_water_mixing_ratio",
                "cloud_droplet_concentration",
                "rain_droplet_concentration",
                "effective_radius_cloud_um",
                "effective_radius_rain_um",
                "effective_radius_all_um",
            )
            if column in df.columns
        ],
        "wet_radius_spectrum_rows": int(len(spectrum_df)),
        "threshold_robustness_rows": int(len(robustness_df)),
    }

    if "rain_water_mixing_ratio" in df:
        summary["final_rain_water_mixing_ratio"] = float(df["rain_water_mixing_ratio"].iloc[-1])
        summary["max_rain_water_mixing_ratio"] = float(df["rain_water_mixing_ratio"].max())

    if "effective_radius_um" in df:
        summary["final_effective_radius_um"] = float(df["effective_radius_um"].iloc[-1])
        summary["max_effective_radius_um"] = float(df["effective_radius_um"].max())

    if "droplet_number_concentration_cm3" in df:
        summary["final_droplet_number_concentration_cm3"] = float(
            df["droplet_number_concentration_cm3"].iloc[-1]
        )

    closure_columns = {
        "total_liquid_water_mixing_ratio",
        "unactivated_water_mixing_ratio",
        "cloud_water_mixing_ratio",
        "rain_water_mixing_ratio",
    }
    if closure_columns.issubset(df.columns):
        partition_sum = (
            df["unactivated_water_mixing_ratio"]
            + df["cloud_water_mixing_ratio"]
            + df["rain_water_mixing_ratio"]
        )
        closure_error = (df["total_liquid_water_mixing_ratio"] - partition_sum).abs()
        summary["liquid_water_partition_max_abs_error"] = float(closure_error.max())

    if not robustness_df.empty:
        final_time = float(robustness_df["time_s"].max())
        final_baseline = robustness_df[
            np.isclose(robustness_df["time_s"], final_time)
            & np.isclose(robustness_df["activation_factor"], 1.0)
            & np.isclose(robustness_df["rain_factor"], 1.0)
        ]
        if not final_baseline.empty:
            summary["final_threshold_baseline"] = {
                str(key): float(value)
                for key, value in final_baseline.iloc[0].to_dict().items()
            }

    metadata = {
        **spec.metadata,
        "adapter_note": (
            "Real PySDM parcel adapter using a project-owned native product builder "
            "and PySDM_examples.seeding.Settings."
        ),
        "requires": ["PySDM", "PySDM-examples"],
        "pysdm_version": modules["pysdm_version"],
        "pysdm_examples_version": modules["pysdm_examples_version"],
        "native_product_build_id": modules["native_product_build_id"],
        "diagnostic_radius_thresholds": {
            "activation_radius_m": activation_radius_m,
            "activation_radius_um": activation_radius_m * 1.0e6,
            "rain_radius_m": rain_radius_m,
            "rain_radius_um": rain_radius_m * 1.0e6,
            "range_convention": "lower inclusive, upper exclusive",
        },
        "native_product_names": sorted(output.get("products", {}).keys()),
        "wet_radius_spectrum": {
            "enabled": spectrum_enabled,
            "configured_log_bins": int(spectrum_cfg.get("n_bins", 32)),
            "actual_bins_after_threshold_insertion": max(0, int(len(spectrum_edges) - 1)),
            "radius_bin_edges_um": (spectrum_edges * 1.0e6).tolist(),
            "checkpoint_times_s": spectrum_checkpoints,
            "checkpoint_interval_seconds": float(
                spectrum_cfg.get("checkpoint_interval_seconds", 10.0)
            ),
            "checkpoint_policy": (
                "Explicit checkpoint_times when provided; otherwise regular cadence plus "
                "start, injection boundaries, and run end, snapped to the model timestep."
            ),
            "threshold_factors": [
                float(value)
                for value in spectrum_cfg.get("threshold_factors", [0.8, 1.0, 1.2])
            ],
            "number_product": "NumberSizeSpectrum (bin-integrated, m^-3)",
            "volume_product": (
                "ParticleVolumeVersusRadiusLogarithmSpectrum "
                "(dV_liquid/V_air per dln(r))"
            ),
        },
    }

    return AdapterResult(
        timeseries=df,
        metadata=metadata,
        summary=summary,
        tables={
            SPECTRUM_TABLE_NAME: spectrum_df,
            ROBUSTNESS_TABLE_NAME: robustness_df,
        }
        if spectrum_enabled
        else {},
    )

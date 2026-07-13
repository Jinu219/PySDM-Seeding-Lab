from __future__ import annotations

from typing import Any, Callable, Dict

import numpy as np
import pandas as pd

from simulation.types import AdapterResult, SimulationRunSpec


R_DRY_AIR = 287.05  # J kg^-1 K^-1


def _require_pysdm() -> Dict[str, Any]:
    """
    Import PySDM and PySDM-examples lazily.

    This keeps the Streamlit app usable even when PySDM is not installed.
    The actual import is only required when the `pysdm_parcel` adapter is selected.
    """
    try:
        from PySDM import Formulae
        from PySDM.initialisation.sampling.spectral_sampling import ConstantMultiplicity
        from PySDM.initialisation.spectra import Lognormal
        from PySDM.physics import si
        from PySDM_examples.seeding.settings import Settings
        from PySDM_examples.seeding.simulation import Simulation
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
        "Simulation": Simulation,
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

def _configure_settings(spec: SimulationRunSpec) -> Any:
    """Create and override PySDM_examples.seeding.Settings from app configuration."""
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

    n_sd_initial = int(aero.get("number_superdroplets", 100))
    # The UI currently stores initial SD count in background_aerosol only implicitly.
    # If not provided, keep the MVP default of 100.
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
        rain_water_radius_threshold=25.0 * si.um,
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
        "rain_water_mixing_ratio": ("rain water mixing ratio", "rain_water_mixing_ratio"),
        "effective_radius_um": ("r_eff", "effective radius", "effective_radius"),
        "droplet_number_concentration_cm3": ("n_drop", "droplet concentration", "n_drop_cm3"),
        "superdroplet_count": ("sd_count", "super droplet count", "sd_count"),
    }

    for out_name, candidates in product_mapping.items():
        values = _extract_product(products, *candidates)
        if values is not None:
            df[out_name] = np.asarray(values, dtype=float)

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


def run_pysdm_parcel_simulation(spec: SimulationRunSpec) -> AdapterResult:
    """
    Run the first real PySDM parcel seeding simulation.

    This adapter uses `PySDM_examples.seeding.Settings` and
    `PySDM_examples.seeding.simulation.Simulation` as the initial bridge.
    """
    modules = _require_pysdm()
    Simulation = modules["Simulation"]

    settings = _configure_settings(spec)
    simulation = Simulation(settings=settings)
    output = simulation.run()

    df = _output_to_dataframe(output, spec)

    summary = {
        "adapter": "pysdm_parcel",
        "is_placeholder": False,
        "n_time_steps": int(len(df)),
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

    metadata = {
        **spec.metadata,
        "adapter_note": "Real PySDM parcel adapter using PySDM_examples.seeding.",
        "requires": ["PySDM", "PySDM-examples"],
    }

    return AdapterResult(
        timeseries=df,
        metadata=metadata,
        summary=summary,
    )

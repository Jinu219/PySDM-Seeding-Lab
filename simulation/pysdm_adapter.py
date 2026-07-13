from __future__ import annotations

from typing import Callable, Dict

import numpy as np
import pandas as pd

from simulation.progress import ProgressCallback, emit_progress
from simulation.types import AdapterResult, SimulationRunSpec


AdapterFunction = Callable[[SimulationRunSpec, ProgressCallback], AdapterResult]


def run_placeholder_warm_cloud(
    spec: SimulationRunSpec,
    progress_callback: ProgressCallback = None,
) -> AdapterResult:
    """
    Temporary warm-cloud-like placeholder adapter.

    This adapter does not call PySDM yet.
    It only preserves the final adapter interface so that UI, runner,
    result storage, and analysis can be developed before or alongside
    the real PySDM simulation.
    """
    emit_progress(progress_callback, "adapter", 1, 4, "Preparing placeholder settings")

    settings = spec.settings
    env = settings.get("environment", {})
    seed = settings.get("seeding", {})
    aero = settings.get("background_aerosol", {})
    microphysics = settings.get("microphysics", {})

    duration = int(env.get("duration", 1500))
    timestep = int(env.get("timestep", 15))
    time_s = np.arange(0, duration + timestep, timestep)

    emit_progress(progress_callback, "adapter", 2, 4, f"Computing synthetic {len(time_s)}-step time series")

    updraft = float(env.get("updraft_velocity", 1.0))
    rh = float(env.get("relative_humidity", 95.0))
    background_kappa = float(aero.get("kappa", 0.5))
    background_radius = float(aero.get("dry_radius", 7.5e-8))

    seeding_enabled = bool(seed.get("enabled", False))
    collision_enabled = bool(microphysics.get("collision", False))

    injection_start = int(seed.get("injection_start", duration + 1))
    injection_end = int(seed.get("injection_end", duration + 1))
    seeding_active = (time_s >= injection_start) & (time_s <= injection_end)

    seed_radius = float(seed.get("dry_radius", 1.0e-6))
    seed_kappa = float(seed.get("kappa", 0.8))
    seed_factor = (seed_radius / max(background_radius, 1e-12)) * (seed_kappa + 0.1)

    supersaturation = np.maximum(0.0, (rh - 100.0) / 100.0) + 0.001 * updraft * (1 - np.exp(-time_s / 300))
    cloud_water = 1e-3 * (1 - np.exp(-time_s / 300)) * max(updraft, 0.1) * (1 + 0.1 * background_kappa)

    rain_delay = np.maximum(time_s - 600, 0)
    rain_water = 2e-4 * (1 - np.exp(-rain_delay / 400))

    if seeding_enabled:
        cloud_water = cloud_water + seeding_active.astype(float) * 1e-5 * min(seed_factor, 50)
        seeded_growth = 1e-4 * min(seed_factor / 10, 5) * (1 - np.exp(-(np.maximum(time_s - injection_start, 0)) / 300))
        rain_water = rain_water + seeded_growth

    if collision_enabled:
        rain_water = rain_water * 1.5

    droplet_number = 100 + 20 * np.sin(time_s / max(duration, 1) * np.pi)
    if seeding_enabled:
        droplet_number = droplet_number + seeding_active.astype(float) * 5

    rain_drop_number = 5 + 10 * (rain_water / max(rain_water.max(), 1e-12))
    mean_radius_m = background_radius * (1 + 5 * cloud_water / max(cloud_water.max(), 1e-12))

    emit_progress(progress_callback, "adapter", 3, 4, "Formatting placeholder output")

    df = pd.DataFrame(
        {
            "time_s": time_s,
            "supersaturation": supersaturation,
            "cloud_water_mixing_ratio": cloud_water,
            "rain_water_mixing_ratio": rain_water,
            "droplet_number_concentration": droplet_number,
            "rain_drop_number_concentration": rain_drop_number,
            "mean_radius_m": mean_radius_m,
            "seeding_active": seeding_active.astype(int),
        }
    )

    summary = {
        "adapter": "placeholder_warm_cloud",
        "is_placeholder": True,
        "n_time_steps": int(len(df)),
        "final_cloud_water_mixing_ratio": float(df["cloud_water_mixing_ratio"].iloc[-1]),
        "final_rain_water_mixing_ratio": float(df["rain_water_mixing_ratio"].iloc[-1]),
        "max_rain_water_mixing_ratio": float(df["rain_water_mixing_ratio"].max()),
    }

    metadata = {
        **spec.metadata,
        "adapter_note": "Synthetic placeholder output. Use pysdm_parcel for real PySDM output.",
    }

    emit_progress(progress_callback, "adapter", 4, 4, "Placeholder adapter finished")

    return AdapterResult(
        timeseries=df,
        metadata=metadata,
        summary=summary,
    )


def run_pysdm_parcel(
    spec: SimulationRunSpec,
    progress_callback: ProgressCallback = None,
) -> AdapterResult:
    """Run the first real PySDM parcel seeding adapter."""
    from simulation.pysdm_parcel_adapter import run_pysdm_parcel_simulation

    return run_pysdm_parcel_simulation(spec, progress_callback=progress_callback)


ADAPTER_REGISTRY: Dict[str, AdapterFunction] = {
    "placeholder_warm_cloud": run_placeholder_warm_cloud,
    "pysdm_parcel": run_pysdm_parcel,
}


def available_adapters() -> list[str]:
    """Return available adapter names."""
    return sorted(ADAPTER_REGISTRY.keys())


def run_adapter(
    spec: SimulationRunSpec,
    progress_callback: ProgressCallback = None,
) -> AdapterResult:
    """Run the adapter selected in the SimulationRunSpec."""
    adapter_name = spec.adapter_name

    if adapter_name not in ADAPTER_REGISTRY:
        raise ValueError(
            f"Unknown adapter: {adapter_name}. "
            f"Available adapters: {available_adapters()}"
        )

    result = ADAPTER_REGISTRY[adapter_name](spec, progress_callback)
    result.require_timeseries()
    return result


def run_pysdm_simulation(settings: dict) -> pd.DataFrame:
    """
    Backward-compatible function kept for older calls.

    New code should use:
        build_run_spec(config) -> run_adapter(spec)
    """
    spec = SimulationRunSpec(
        run_id="legacy_call",
        experiment_name="legacy",
        experiment_mode="single",
        adapter_name="placeholder_warm_cloud",
        case_name="legacy",
        config={},
        settings=settings,
        metadata={"source": "legacy run_pysdm_simulation call"},
    )
    return run_placeholder_warm_cloud(spec).timeseries

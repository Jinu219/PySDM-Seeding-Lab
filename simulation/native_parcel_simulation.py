from __future__ import annotations

"""Project-owned PySDM parcel simulation with native diagnostic products.

PySDM_examples.seeding is intentionally kept as the source of the Settings
object, but its Simulation exposes only a small product collection.  This
module owns the builder so the lab can request the thermodynamic, water-mass,
number-concentration, and size products needed by the Growth Pathway analysis
without modifying the installed PySDM package.
"""

from typing import Any

import numpy as np

from PySDM import Builder, products
from PySDM.backends import CPU
from PySDM.dynamics import AmbientThermodynamics, Coalescence, Condensation, Seeding
from PySDM.dynamics.collisions.collision_kernels import Geometric
from PySDM.environments import Parcel
from PySDM.initialisation.sampling.spectral_sampling import ConstantMultiplicity


NATIVE_PRODUCT_BUILD_ID = "native-parcel-products-20260714"


def _sample_initial_spectrum(spectrum: Any, *, n_sd: int, backend: Any):
    """Sample across the PySDM 2.x ConstantMultiplicity API variants."""
    sampler = ConstantMultiplicity(spectrum)
    last_error: Exception | None = None
    for method_name in ("sample_deterministic", "sample"):
        method = getattr(sampler, method_name, None)
        if not callable(method):
            continue
        for call in (
            lambda: method(n_sd=n_sd, backend=backend),
            lambda: method(n_sd=n_sd),
            lambda: method(n_sd),
        ):
            try:
                return call()
            except TypeError as exc:
                last_error = exc
    raise RuntimeError("Could not sample the initial aerosol spectrum.") from last_error


class NativeParcelSimulation:
    """Warm-cloud parcel model exposing a research-ready native product set."""

    def __init__(self, settings: Any, *, activation_radius_threshold: float):
        activation_radius = float(activation_radius_threshold)
        rain_radius = float(settings.rain_water_radius_threshold)
        if not 0 < activation_radius < rain_radius:
            raise ValueError(
                "Diagnostic radius thresholds must satisfy "
                "0 < activation_radius_threshold < rain_water_radius_threshold."
            )

        builder = Builder(
            n_sd=settings.n_sd_seeding + settings.n_sd_initial,
            backend=CPU(
                formulae=settings.formulae,
                override_jit_flags={"parallel": False},
            ),
            environment=Parcel(
                dt=settings.timestep,
                mass_of_dry_air=settings.mass_of_dry_air,
                w=settings.updraft,
                initial_water_vapour_mixing_ratio=settings.initial_water_vapour_mixing_ratio,
                p0=settings.initial_total_pressure,
                T0=settings.initial_temperature,
            ),
        )
        builder.add_dynamic(AmbientThermodynamics())
        builder.add_dynamic(Condensation())
        if settings.enable_collisions:
            builder.add_dynamic(Coalescence(collision_kernel=Geometric()))
        builder.add_dynamic(
            Seeding(
                super_droplet_injection_rate=settings.super_droplet_injection_rate,
                seeded_particle_multiplicity=settings.seeded_particle_multiplicity,
                seeded_particle_extensive_attributes=settings.seeded_particle_extensive_attributes,
            )
        )

        r_dry, n_in_dv = _sample_initial_spectrum(
            settings.initial_aerosol_dry_radii,
            n_sd=settings.n_sd_initial,
            backend=builder.particulator.backend,
        )
        attributes = builder.particulator.environment.init_attributes(
            n_in_dv=n_in_dv,
            kappa=settings.initial_aerosol_kappa,
            r_dry=r_dry,
        )

        cloud_range = (activation_radius, rain_radius)
        rain_range = (rain_radius, np.inf)
        activated_range = (activation_radius, np.inf)
        unactivated_range = (0.0, activation_radius)

        self.particulator = builder.build(
            attributes={
                key: np.pad(
                    array=value,
                    pad_width=(0, settings.n_sd_seeding),
                    mode="constant",
                    constant_values=np.nan if key == "multiplicity" else 0,
                )
                for key, value in attributes.items()
            },
            products=(
                products.SuperDropletCountPerGridbox(name="superdroplet_count"),
                products.Time(name="time"),
                products.AmbientTemperature(name="temperature_K", var="T"),
                products.AmbientPressure(name="pressure_Pa", var="p"),
                products.AmbientWaterVapourMixingRatio(
                    name="water_vapour_mixing_ratio",
                    var="water_vapour_mixing_ratio",
                ),
                products.AmbientRelativeHumidity(name="relative_humidity", var="RH"),
                products.WaterMixingRatio(
                    radius_range=unactivated_range,
                    name="unactivated_water_mixing_ratio",
                ),
                products.WaterMixingRatio(
                    radius_range=cloud_range,
                    name="cloud_water_mixing_ratio",
                ),
                products.WaterMixingRatio(
                    radius_range=rain_range,
                    name="rain_water_mixing_ratio",
                ),
                products.WaterMixingRatio(name="total_liquid_water_mixing_ratio"),
                products.ParticleConcentration(
                    radius_range=cloud_range,
                    name="cloud_droplet_concentration",
                    unit="cm^-3",
                ),
                products.ParticleConcentration(
                    radius_range=rain_range,
                    name="rain_droplet_concentration",
                    unit="cm^-3",
                ),
                products.EffectiveRadius(
                    radius_range=cloud_range,
                    name="effective_radius_cloud_um",
                    unit="um",
                ),
                products.EffectiveRadius(
                    radius_range=rain_range,
                    name="effective_radius_rain_um",
                    unit="um",
                ),
                products.EffectiveRadius(
                    radius_range=activated_range,
                    name="effective_radius_all_um",
                    unit="um",
                ),
            ),
        )
        self.n_steps = int(settings.t_max // settings.timestep)

    def run(self) -> dict[str, dict[str, np.ndarray]]:
        output: dict[str, dict[str, list[float]] | dict[str, np.ndarray]] = {
            "products": {key: [] for key in self.particulator.products}
        }
        product_rows = output["products"]
        assert isinstance(product_rows, dict)

        for step in range(self.n_steps + 1):
            if step:
                self.particulator.run(steps=1)
            for key in product_rows:
                value = self.particulator.products[key].get()
                if not isinstance(value, float):
                    (value,) = value
                product_rows[key].append(float(value))

        return {
            "products": {
                key: np.asarray(values, dtype=float)
                for key, values in product_rows.items()
            }
        }

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from simulation.schema import AEROSOL_DISTRIBUTION_TYPES
from simulation.ui_helpers import (
    config_actions,
    load_working_config,
    page_header,
    schema_expander,
    unit_label,
)


page_header(
    "02. Background Aerosol Settings",
    "배경 에어로졸의 dry-size distribution과 hygroscopicity를 설정합니다.",
)

cfg = load_working_config()
st.info("아래 Save target에서 Current working config 또는 저장된 scenario를 선택해 이 페이지의 설정을 저장할 수 있습니다.")
aero = cfg.setdefault("background_aerosol", {})
diagnostics = cfg.setdefault("diagnostics", {})


def _comma_separated_numbers(value: object) -> str:
    if not isinstance(value, list):
        return ""
    return ", ".join(f"{float(item):g}" for item in value)


def _parse_number_list(text: str) -> list[float]:
    if not text.strip():
        return []
    return [float(item.strip()) for item in text.split(",") if item.strip()]

col1, col2 = st.columns([1, 1.2])

with col1.container(border=True):
    st.markdown("#### Aerosol properties")
    distribution_type = aero.get("distribution_type", "single_lognormal")
    aero["distribution_type"] = st.selectbox(
        "Distribution type",
        AEROSOL_DISTRIBUTION_TYPES,
        index=AEROSOL_DISTRIBUTION_TYPES.index(distribution_type)
        if distribution_type in AEROSOL_DISTRIBUTION_TYPES
        else 0,
    )
    aero["number_concentration"] = st.number_input(
        "Number concentration" + unit_label("background_aerosol", "number_concentration"),
        min_value=0.0,
        value=float(aero.get("number_concentration", 100.0)),
        step=10.0,
    )
    aero["number_superdroplets"] = st.number_input(
        "Number of background super-droplets" + unit_label("background_aerosol", "number_superdroplets"),
        min_value=1,
        value=int(aero.get("number_superdroplets", 100)),
        step=10,
        help="Numerical representation count. Verify convergence before quantitative interpretation.",
    )
    aero["dry_radius"] = st.number_input(
        "Geometric mean dry radius" + unit_label("background_aerosol", "dry_radius"),
        min_value=1e-10,
        value=float(aero.get("dry_radius", 7.5e-8)),
        step=1e-8,
        format="%.2e",
    )
    aero["geometric_sigma"] = st.number_input(
        "Geometric standard deviation" + unit_label("background_aerosol", "geometric_sigma"),
        min_value=1.01,
        value=float(aero.get("geometric_sigma", 1.4)),
        step=0.05,
    )
    aero["kappa"] = st.number_input(
        "κ hygroscopicity parameter" + unit_label("background_aerosol", "kappa"),
        min_value=0.0,
        value=float(aero.get("kappa", 0.5)),
        step=0.1,
    )
    aero["particle_density"] = st.number_input(
        "Particle density" + unit_label("background_aerosol", "particle_density"),
        min_value=1.0,
        value=float(aero.get("particle_density", 1770.0)),
        step=10.0,
    )
    aero["chemical_composition"] = st.text_input(
        "Chemical composition",
        value=str(aero.get("chemical_composition", "ammonium_sulfate_like")),
    )

with col2.container(border=True):
    st.subheader("Aerosol Distribution Preview")

    r = np.logspace(-9, -5, 300)
    r_mean = float(aero.get("dry_radius", 7.5e-8))
    sigma = float(aero.get("geometric_sigma", 1.4))
    n = float(aero.get("number_concentration", 100.0))

    dist = n / (np.sqrt(2 * np.pi) * np.log(sigma)) * np.exp(
        -((np.log(r) - np.log(r_mean)) ** 2) / (2 * np.log(sigma) ** 2)
    )

    fig, ax = plt.subplots()
    ax.plot(r * 1e6, dist)
    ax.set_xscale("log")
    ax.set_xlabel("Dry radius [µm]")
    ax.set_ylabel("dN / dln(r)")
    ax.set_title("Background aerosol dry-size distribution")
    st.pyplot(fig)

    st.caption("Preview는 단일 lognormal distribution을 기준으로 표시됩니다.")

with st.expander("Diagnostic radius definitions", expanded=False):
    st.caption(
        "PySDM native products를 unactivated / cloud / rain 구간으로 나누는 wet-radius 기준입니다. "
        "모든 결과 metadata에 함께 저장됩니다."
    )
    threshold_col1, threshold_col2 = st.columns(2)
    with threshold_col1:
        activation_um = st.number_input(
            "Activation threshold [µm]",
            min_value=0.01,
            value=float(diagnostics.get("activation_radius_threshold", 0.5e-6)) * 1.0e6,
            step=0.1,
            format="%.2f",
        )
    with threshold_col2:
        rain_um = st.number_input(
            "Rain threshold [µm]",
            min_value=0.1,
            value=float(diagnostics.get("rain_radius_threshold", 25.0e-6)) * 1.0e6,
            step=1.0,
            format="%.1f",
        )
    diagnostics["activation_radius_threshold"] = float(activation_um) * 1.0e-6
    diagnostics["rain_radius_threshold"] = float(rain_um) * 1.0e-6
    if activation_um >= rain_um:
        st.error("Rain threshold must be larger than the activation threshold.")

    st.markdown("##### Wet-radius spectrum checkpoints")
    st.caption(
        "Stores compact wet-radius number/volume spectra at selected times. "
        "An empty checkpoint list uses a regular cadence plus start, injection start/end, and run end."
    )
    spectrum_cfg = diagnostics.setdefault("wet_radius_spectrum", {})
    spectrum_cfg["enabled"] = st.toggle(
        "Save wet-radius spectrum diagnostics",
        value=bool(spectrum_cfg.get("enabled", True)),
    )
    spectrum_col1, spectrum_col2, spectrum_col3 = st.columns(3)
    with spectrum_col1:
        spectrum_min_um = st.number_input(
            "Minimum wet radius [µm]",
            min_value=0.001,
            value=float(spectrum_cfg.get("min_radius", 0.05e-6)) * 1.0e6,
            step=0.01,
            format="%.3f",
        )
    with spectrum_col2:
        spectrum_max_um = st.number_input(
            "Maximum wet radius [µm]",
            min_value=1.0,
            value=float(spectrum_cfg.get("max_radius", 1000.0e-6)) * 1.0e6,
            step=100.0,
            format="%.1f",
        )
    with spectrum_col3:
        spectrum_cfg["n_bins"] = st.number_input(
            "Base logarithmic bins",
            min_value=8,
            max_value=256,
            value=int(spectrum_cfg.get("n_bins", 32)),
            step=4,
        )
    spectrum_cfg["min_radius"] = float(spectrum_min_um) * 1.0e-6
    spectrum_cfg["max_radius"] = float(spectrum_max_um) * 1.0e-6

    factors_text = st.text_input(
        "Threshold factors",
        value=_comma_separated_numbers(spectrum_cfg.get("threshold_factors", [0.8, 1.0, 1.2])),
        help="Applied to both activation and rain thresholds. Include 1.0 for the baseline.",
    )
    checkpoints_text = st.text_input(
        "Checkpoint times [s] (optional)",
        value=_comma_separated_numbers(spectrum_cfg.get("checkpoint_times", [])),
        placeholder="blank = automatic",
    )
    spectrum_cfg["checkpoint_interval_seconds"] = st.number_input(
        "Automatic checkpoint interval [s]",
        min_value=0.1,
        value=float(spectrum_cfg.get("checkpoint_interval_seconds", 10.0)),
        step=5.0,
        help=(
            "Used only when the explicit checkpoint list is blank. The default 10 s cadence "
            "follows drizzle-onset radar integration studies and is snapped to the model timestep."
        ),
    )
    try:
        spectrum_cfg["threshold_factors"] = _parse_number_list(factors_text)
        spectrum_cfg["checkpoint_times"] = _parse_number_list(checkpoints_text)
    except ValueError:
        st.error("Threshold factors and checkpoint times must be comma-separated numbers.")

    if spectrum_min_um >= activation_um:
        st.error("Spectrum minimum must be below the activation threshold.")
    if spectrum_max_um <= rain_um:
        st.error("Spectrum maximum must exceed the rain threshold.")

with st.expander("Research quality gates", expanded=False):
    st.caption(
        "Water-budget gates evaluate only closed intervals; the seeding injection window is "
        "treated as an external source. Numerical convergence compares the next-finest sweep "
        "level with the finest available timestep/super-droplet reference."
    )
    water_budget_cfg = diagnostics.setdefault("water_budget", {})
    convergence_cfg = diagnostics.setdefault("numerical_convergence", {})
    transition_cfg = diagnostics.setdefault("spectrum_transition", {})

    quality_col1, quality_col2 = st.columns(2)
    with quality_col1.container(border=True):
        st.markdown("##### Total-water budget")
        water_budget_cfg["enabled"] = st.toggle(
            "Enable water-budget diagnostic",
            value=bool(water_budget_cfg.get("enabled", True)),
        )
        water_budget_cfg["warning_relative_drift_percent"] = st.number_input(
            "Warning drift [%]",
            min_value=1.0e-6,
            value=float(water_budget_cfg.get("warning_relative_drift_percent", 0.01)),
            format="%.6f",
        )
        water_budget_cfg["failure_relative_drift_percent"] = st.number_input(
            "Failure drift [%]",
            min_value=1.0e-6,
            value=float(water_budget_cfg.get("failure_relative_drift_percent", 0.1)),
            format="%.6f",
        )
        if (
            water_budget_cfg["warning_relative_drift_percent"]
            >= water_budget_cfg["failure_relative_drift_percent"]
        ):
            st.error("Failure drift must be larger than warning drift.")

    with quality_col2.container(border=True):
        st.markdown("##### Numerical convergence")
        convergence_cfg["enabled"] = st.toggle(
            "Analyze numerical convergence sweeps",
            value=bool(convergence_cfg.get("enabled", True)),
        )
        convergence_cfg["relative_tolerance_percent"] = st.number_input(
            "Next-finest tolerance [%]",
            min_value=0.001,
            value=float(convergence_cfg.get("relative_tolerance_percent", 5.0)),
            step=0.5,
        )
        st.caption(
            "Leave diagnostics.numerical_convergence.metrics empty to analyze the available "
            "default rain-response metrics."
        )

    with st.container(border=True):
        st.markdown("##### Spectrum transition onset")
        transition_cfg["enabled"] = st.toggle(
            "Analyze spectrum-based transition onset",
            value=bool(transition_cfg.get("enabled", True)),
        )
        transition_cfg["rain_volume_fraction_threshold"] = st.number_input(
            "Rain-size liquid fraction threshold [-]",
            min_value=0.0001,
            max_value=0.9999,
            value=float(transition_cfg.get("rain_volume_fraction_threshold", 0.01)),
            step=0.005,
            format="%.4f",
            help=(
                "Onset is the first interpolated checkpoint where rain-size liquid volume "
                "exceeds this fraction of activated liquid volume."
            ),
        )
        transition_thresholds_text = st.text_input(
            "Transition fraction sensitivity levels",
            value=_comma_separated_numbers(
                transition_cfg.get(
                    "rain_volume_fraction_thresholds", [0.005, 0.01, 0.02]
                )
            ),
            help=(
                "The 1% value is an operational baseline rather than an observational standard. "
                "These levels test whether onset direction is stable around that choice."
            ),
        )
        try:
            transition_cfg["rain_volume_fraction_thresholds"] = _parse_number_list(
                transition_thresholds_text
            )
        except ValueError:
            st.error("Transition fraction levels must be comma-separated numbers.")

config_actions(cfg, "Save Aerosol Settings")
schema_expander()

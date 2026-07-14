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

config_actions(cfg, "Save Aerosol Settings")
schema_expander()

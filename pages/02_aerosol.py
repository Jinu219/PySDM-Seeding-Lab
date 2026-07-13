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
aero = cfg.setdefault("background_aerosol", {})

col1, col2 = st.columns([1, 1.2])

with col1:
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

with col2:
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

config_actions(cfg, "Save Aerosol Settings")
schema_expander()

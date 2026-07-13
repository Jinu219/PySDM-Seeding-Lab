import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from simulation.config import load_config, save_config

CONFIG_PATH = "configs/default.yaml"

st.title("02. Background Aerosol Settings")

cfg = load_config(CONFIG_PATH)
aero = cfg.setdefault("background_aerosol", {})

col1, col2 = st.columns([1, 1])

with col1:
    aero["number_concentration"] = st.number_input(
        "Aerosol number concentration [cm⁻³]",
        value=float(aero.get("number_concentration", 100.0)),
    )
    aero["dry_radius"] = st.number_input(
        "Geometric mean dry radius [m]",
        value=float(aero.get("dry_radius", 7.5e-8)),
        format="%.2e",
    )
    aero["geometric_sigma"] = st.number_input(
        "Geometric standard deviation [-]",
        value=float(aero.get("geometric_sigma", 1.4)),
    )
    aero["kappa"] = st.number_input(
        "κ hygroscopicity parameter [-]",
        value=float(aero.get("kappa", 0.5)),
    )

with col2:
    r = np.logspace(-9, -5, 200)
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

if st.button("Save Aerosol Settings"):
    save_config(cfg, CONFIG_PATH)
    st.success("Aerosol settings saved.")

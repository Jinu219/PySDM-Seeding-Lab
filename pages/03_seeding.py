import streamlit as st
from simulation.config import load_config, save_config

CONFIG_PATH = "configs/default.yaml"

st.title("03. Seeding Particle Settings")

cfg = load_config(CONFIG_PATH)
seed = cfg.setdefault("seeding", {})

seed["enabled"] = st.toggle("Enable seeding", value=bool(seed.get("enabled", True)))

col1, col2 = st.columns(2)

with col1:
    seed["material_type"] = st.selectbox(
        "Seeding material type",
        ["hygroscopic", "glaciogenic", "custom"],
        index=["hygroscopic", "glaciogenic", "custom"].index(seed.get("material_type", "hygroscopic")),
    )
    seed["dry_radius"] = st.number_input(
        "Seeding particle dry radius [m]",
        value=float(seed.get("dry_radius", 1.0e-6)),
        format="%.2e",
    )
    seed["kappa"] = st.number_input(
        "Seeding particle κ [-]",
        value=float(seed.get("kappa", 0.8)),
    )
    seed["number_superdroplets"] = st.number_input(
        "Number of seeding super-droplets",
        value=int(seed.get("number_superdroplets", 100)),
        step=10,
    )

with col2:
    seed["injection_start"] = st.number_input(
        "Injection start time [s]",
        value=int(seed.get("injection_start", 900)),
        step=60,
    )
    seed["injection_end"] = st.number_input(
        "Injection end time [s]",
        value=int(seed.get("injection_end", 1200)),
        step=60,
    )
    seed["injection_altitude"] = st.number_input(
        "Injection altitude [m]",
        value=float(seed.get("injection_altitude", 500.0)),
    )
    seed["delivery_method"] = st.selectbox(
        "Delivery method",
        ["idealized_uniform", "aircraft", "ground_generator", "drone"],
        index=["idealized_uniform", "aircraft", "ground_generator", "drone"].index(
            seed.get("delivery_method", "idealized_uniform")
        ),
    )

if st.button("Save Seeding Settings"):
    save_config(cfg, CONFIG_PATH)
    st.success("Seeding settings saved.")

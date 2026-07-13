import streamlit as st

from simulation.schema import DELIVERY_METHODS, SEEDING_MATERIAL_TYPES
from simulation.ui_helpers import (
    config_actions,
    load_working_config,
    page_header,
    schema_expander,
    unit_label,
)


page_header(
    "03. Seeding Particle Settings",
    "시딩 입자의 물성, 주입 시간, 주입 방식을 설정합니다.",
)

cfg = load_working_config()
seed = cfg.setdefault("seeding", {})
env = cfg.setdefault("environment", {})

duration = int(env.get("duration", 1500))

seed["enabled"] = st.toggle("Enable seeding", value=bool(seed.get("enabled", True)))

col1, col2 = st.columns(2)

with col1:
    material_type = seed.get("material_type", "hygroscopic")
    seed["material_type"] = st.selectbox(
        "Seeding material type",
        SEEDING_MATERIAL_TYPES,
        index=SEEDING_MATERIAL_TYPES.index(material_type)
        if material_type in SEEDING_MATERIAL_TYPES
        else 0,
    )
    seed["dry_radius"] = st.number_input(
        "Seeding particle dry radius" + unit_label("seeding", "dry_radius"),
        min_value=1e-10,
        value=float(seed.get("dry_radius", 1.0e-6)),
        step=1e-7,
        format="%.2e",
    )
    seed["geometric_sigma"] = st.number_input(
        "Geometric standard deviation" + unit_label("seeding", "geometric_sigma"),
        min_value=1.01,
        value=float(seed.get("geometric_sigma", 1.2)),
        step=0.05,
    )
    seed["kappa"] = st.number_input(
        "Seeding particle κ" + unit_label("seeding", "kappa"),
        min_value=0.0,
        value=float(seed.get("kappa", 0.8)),
        step=0.1,
    )
    seed["particle_density"] = st.number_input(
        "Particle density" + unit_label("seeding", "particle_density"),
        min_value=1.0,
        value=float(seed.get("particle_density", 1770.0)),
        step=10.0,
    )
    seed["number_concentration"] = st.number_input(
        "Seeding number concentration" + unit_label("seeding", "number_concentration"),
        min_value=0.0,
        value=float(seed.get("number_concentration", 10.0)),
        step=1.0,
    )
    seed["number_superdroplets"] = st.number_input(
        "Number of seeding super-droplets" + unit_label("seeding", "number_superdroplets"),
        min_value=1,
        value=int(seed.get("number_superdroplets", 100)),
        step=10,
    )

with col2:
    current_start = min(int(seed.get("injection_start", 900)), duration - 1 if duration > 1 else 0)
    current_end = min(int(seed.get("injection_end", 1200)), duration)

    seed["injection_start"] = st.number_input(
        "Injection start time" + unit_label("seeding", "injection_start"),
        min_value=0,
        max_value=max(duration - 1, 0),
        value=max(0, current_start),
        step=60,
    )
    seed["injection_end"] = st.number_input(
        "Injection end time" + unit_label("seeding", "injection_end"),
        min_value=int(seed["injection_start"]) + 1,
        max_value=duration,
        value=max(int(seed["injection_start"]) + 1, current_end),
        step=60,
    )
    seed["injection_altitude"] = st.number_input(
        "Injection altitude" + unit_label("seeding", "injection_altitude"),
        min_value=0.0,
        value=float(seed.get("injection_altitude", 500.0)),
        step=100.0,
    )

    delivery_method = seed.get("delivery_method", "idealized_uniform")
    seed["delivery_method"] = st.selectbox(
        "Delivery method",
        DELIVERY_METHODS,
        index=DELIVERY_METHODS.index(delivery_method)
        if delivery_method in DELIVERY_METHODS
        else 0,
    )

    st.subheader("Injection Summary")
    st.write(f"Injection duration: `{seed['injection_end'] - seed['injection_start']} s`")
    st.write(f"Relative simulation time: `{seed['injection_start']}–{seed['injection_end']} s / {duration} s`")

if not seed["enabled"]:
    st.warning("Seeding is disabled. In this state, the simulation should behave as a control run.")

config_actions(cfg, "Save Seeding Settings")
schema_expander()

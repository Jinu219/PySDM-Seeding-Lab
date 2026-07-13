import streamlit as st

from simulation.ui_helpers import (
    config_actions,
    load_working_config,
    page_header,
    schema_expander,
    unit_label,
)


page_header(
    "01. Atmospheric Environment",
    "초기 대기 상태와 parcel 상승 조건을 설정합니다.",
)

cfg = load_working_config()
env = cfg.setdefault("environment", {})
dyn = cfg.setdefault("dynamics", {})

st.subheader("Thermodynamic Settings")

col1, col2 = st.columns(2)

with col1:
    env["temperature"] = st.number_input(
        "Initial temperature" + unit_label("environment", "temperature"),
        min_value=1.0,
        value=float(env.get("temperature", 300.0)),
        step=1.0,
    )
    env["pressure"] = st.number_input(
        "Initial pressure" + unit_label("environment", "pressure"),
        min_value=1.0,
        value=float(env.get("pressure", 100000.0)),
        step=100.0,
    )
    env["water_vapour_mixing_ratio"] = st.number_input(
        "Water-vapor mixing ratio" + unit_label("environment", "water_vapour_mixing_ratio"),
        min_value=0.0,
        value=float(env.get("water_vapour_mixing_ratio", 0.0222)),
        step=0.001,
        format="%.5f",
    )
    env["relative_humidity"] = st.slider(
        "Relative humidity" + unit_label("environment", "relative_humidity"),
        min_value=0.0,
        max_value=200.0,
        value=float(env.get("relative_humidity", 95.0)),
        step=1.0,
    )

with col2:
    env["initial_altitude"] = st.number_input(
        "Initial altitude" + unit_label("environment", "initial_altitude"),
        value=float(env.get("initial_altitude", 0.0)),
        step=100.0,
    )
    env["updraft_velocity"] = st.number_input(
        "Updraft velocity" + unit_label("environment", "updraft_velocity"),
        value=float(env.get("updraft_velocity", 1.0)),
        step=0.1,
    )
    env["duration"] = st.number_input(
        "Simulation duration" + unit_label("environment", "duration"),
        min_value=1,
        value=int(env.get("duration", 1500)),
        step=60,
    )
    env["timestep"] = st.number_input(
        "Timestep" + unit_label("environment", "timestep"),
        min_value=1,
        max_value=int(env.get("duration", 1500)),
        value=min(int(env.get("timestep", 15)), int(env.get("duration", 1500))),
        step=1,
    )

dyn["updraft_strength"] = env["updraft_velocity"]

st.info("현재 MVP에서는 environment.updraft_velocity와 dynamics.updraft_strength를 같은 값으로 동기화합니다.")

config_actions(cfg, "Save Environment Settings")
schema_expander()

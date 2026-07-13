import streamlit as st
from simulation.config import load_config, save_config

CONFIG_PATH = "configs/default.yaml"

st.title("01. Atmospheric Environment")

cfg = load_config(CONFIG_PATH)
env = cfg.setdefault("environment", {})

col1, col2 = st.columns(2)

with col1:
    env["temperature"] = st.number_input("Initial temperature [K]", value=float(env.get("temperature", 300.0)))
    env["pressure"] = st.number_input("Initial pressure [Pa]", value=float(env.get("pressure", 100000.0)))
    env["water_vapour_mixing_ratio"] = st.number_input(
        "Water-vapor mixing ratio [kg/kg]",
        value=float(env.get("water_vapour_mixing_ratio", 0.0222)),
        format="%.5f",
    )
    env["relative_humidity"] = st.number_input(
        "Relative humidity [%]",
        value=float(env.get("relative_humidity", 95.0)),
    )

with col2:
    env["updraft_velocity"] = st.number_input("Updraft velocity [m/s]", value=float(env.get("updraft_velocity", 1.0)))
    env["duration"] = st.number_input("Simulation duration [s]", value=int(env.get("duration", 1500)), step=60)
    env["timestep"] = st.number_input("Timestep [s]", value=int(env.get("timestep", 15)), step=1)
    env["initial_altitude"] = st.number_input("Initial altitude [m]", value=float(env.get("initial_altitude", 0.0)))

if st.button("Save Environment Settings"):
    save_config(cfg, CONFIG_PATH)
    st.success("Environment settings saved.")

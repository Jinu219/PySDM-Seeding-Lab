import streamlit as st
from simulation.config import load_config, save_config

CONFIG_PATH = "configs/default.yaml"

st.title("04. Dynamic Parameter")

cfg = load_config(CONFIG_PATH)
dyn = cfg.setdefault("dynamics", {})

st.warning(
    '''
    현재 MVP에서는 updraft velocity만 PySDM 실행에 직접 연결하는 것을 목표로 합니다.
    Turbulence, entrainment, detrainment, wind shear 등은 이후 parameterization을 추가하면서 연결합니다.
    '''
)

col1, col2 = st.columns(2)

with col1:
    dyn["updraft_strength"] = st.number_input("Updraft strength [m/s]", value=float(dyn.get("updraft_strength", 1.0)))
    dyn["downdraft_strength"] = st.number_input("Downdraft strength [m/s]", value=float(dyn.get("downdraft_strength", 0.0)))
    dyn["turbulence_intensity"] = st.number_input("Turbulence intensity [-]", value=float(dyn.get("turbulence_intensity", 0.0)))
    dyn["entrainment_rate"] = st.number_input("Entrainment rate [1/m]", value=float(dyn.get("entrainment_rate", 0.0)), format="%.2e")

with col2:
    dyn["detrainment_rate"] = st.number_input("Detrainment rate [1/m]", value=float(dyn.get("detrainment_rate", 0.0)), format="%.2e")
    dyn["wind_shear"] = st.number_input("Wind shear [1/s]", value=float(dyn.get("wind_shear", 0.0)), format="%.2e")
    dyn["convergence"] = st.number_input("Convergence [1/s]", value=float(dyn.get("convergence", 0.0)), format="%.2e")
    dyn["cape"] = st.number_input("CAPE [J/kg]", value=float(dyn.get("cape", 0.0)))
    dyn["cin"] = st.number_input("CIN [J/kg]", value=float(dyn.get("cin", 0.0)))

if st.button("Save Dynamic Settings"):
    save_config(cfg, CONFIG_PATH)
    st.success("Dynamic settings saved.")

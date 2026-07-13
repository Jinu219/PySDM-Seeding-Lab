from pathlib import Path

import streamlit as st

from simulation.config import load_config, save_config
from simulation.schema import EXPERIMENT_MODES, schema_summary
from simulation.ui_helpers import scenario_loader


st.set_page_config(
    page_title="PySDM Seeding Lab",
    page_icon="☁️",
    layout="wide",
)

st.title("☁️ PySDM Seeding Lab")
st.caption("Visual experiment designer for PySDM-based cloud seeding simulations")

st.markdown(
    """
    PySDM Seeding Lab은 PySDM 기반 cloud seeding simulation을
    코드 직접 수정 방식이 아니라 configuration과 시각적 입력 화면 중심으로 관리하기 위한 연구용 플랫폼입니다.
    """
)

st.divider()

st.subheader("Working Configuration")

scenarios = scenario_loader()
selected_scenario = st.selectbox(
    "Load scenario into working config",
    list(scenarios.keys()),
    index=0,
)

col_load, col_note = st.columns([1, 2])
with col_load:
    if st.button("Load Selected Scenario", use_container_width=True):
        source_path = Path(scenarios[selected_scenario])
        cfg_to_load = load_config(source_path)
        save_config(cfg_to_load, "configs/default.yaml")
        st.success(f"Loaded {selected_scenario} into configs/default.yaml")

with col_note:
    st.info("Streamlit pages edit `configs/default.yaml` as the current working configuration.")

cfg = load_config("configs/default.yaml")

experiment = cfg.get("experiment", {})
environment = cfg.get("environment", {})
aerosol = cfg.get("background_aerosol", {})
seeding = cfg.get("seeding", {})
microphysics = cfg.get("microphysics", {})

st.subheader("Current Experiment Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Experiment", experiment.get("name", "unnamed"))
    st.metric("Mode", experiment.get("mode", "single"))

with col2:
    st.metric("Temperature", f"{environment.get('temperature', 'NA')} K")
    st.metric("Pressure", f"{environment.get('pressure', 'NA')} Pa")

with col3:
    st.metric("Background κ", aerosol.get("kappa", "NA"))
    st.metric("Aerosol radius", f"{aerosol.get('dry_radius', 'NA')} m")

with col4:
    st.metric("Seeding", "ON" if seeding.get("enabled", False) else "OFF")
    st.metric("Collision", "ON" if microphysics.get("collision", False) else "OFF")

st.divider()

st.subheader("Experiment Mode")

mode = st.selectbox(
    "Mode",
    EXPERIMENT_MODES,
    index=EXPERIMENT_MODES.index(experiment.get("mode", "control_vs_seeding"))
    if experiment.get("mode", "control_vs_seeding") in EXPERIMENT_MODES
    else 0,
)

experiment["mode"] = mode
cfg["experiment"] = experiment

if st.button("Save Experiment Mode", use_container_width=True):
    save_config(cfg, "configs/default.yaml")
    st.success("Experiment mode saved.")

with st.expander("Configuration schema summary"):
    st.dataframe(schema_summary(), use_container_width=True)

st.info("왼쪽 사이드바에서 Environment, Aerosol, Seeding, Dynamics, Run, Results 페이지를 선택해서 설정을 수정하세요.")

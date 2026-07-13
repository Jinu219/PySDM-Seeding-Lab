import streamlit as st
from pathlib import Path
from simulation.config import load_config

st.set_page_config(
    page_title="PySDM Seeding Lab",
    page_icon="☁️",
    layout="wide",
)

st.title("☁️ PySDM Seeding Lab")
st.caption("Cloud seeding simulation designer based on PySDM")

config_path = Path("configs/default.yaml")
cfg = load_config(config_path)

st.subheader("Project Overview")
st.write(
    '''
    이 앱은 PySDM 기반 cloud seeding 실험을 화면에서 설정하고,
    Control / Seeding / Sensitivity 실험을 재현 가능하게 관리하기 위한 연구용 플랫폼입니다.
    '''
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Experiment", cfg.get("experiment", {}).get("name", "unnamed"))
    st.metric("Mode", cfg.get("experiment", {}).get("mode", "single"))

with col2:
    env = cfg.get("environment", {})
    st.metric("Temperature", f"{env.get('temperature', 'NA')} K")
    st.metric("Pressure", f"{env.get('pressure', 'NA')} Pa")

with col3:
    seed = cfg.get("seeding", {})
    st.metric("Seeding", "ON" if seed.get("enabled", False) else "OFF")
    st.metric("Collision", "ON" if cfg.get("microphysics", {}).get("collision", False) else "OFF")

st.info("왼쪽 사이드바에서 Environment, Aerosol, Seeding, Dynamics, Run, Results 페이지를 선택하세요.")

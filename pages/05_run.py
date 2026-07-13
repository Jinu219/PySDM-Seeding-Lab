from pathlib import Path

import streamlit as st

from simulation.config import load_config
from simulation.runner import run_experiment
from simulation.validation import validate_config


CONFIG_PATH = "configs/default.yaml"

st.title("05. Run Simulation")
st.caption("현재 working configuration을 검증하고 simulation runner를 실행합니다.")

cfg = load_config(CONFIG_PATH)

st.subheader("Run Options")
st.write(f"Experiment name: `{cfg.get('experiment', {}).get('name', 'unnamed')}`")
st.write(f"Experiment mode: `{cfg.get('experiment', {}).get('mode', 'single')}`")

st.subheader("Configuration Validation")
errors = validate_config(cfg)

if errors:
    st.error("Configuration has errors.")
    for err in errors:
        st.write(f"- {err}")
else:
    st.success("Configuration is valid.")

with st.expander("Current configuration"):
    st.json(cfg)

if st.button("Run Experiment", disabled=bool(errors), use_container_width=True):
    with st.spinner("Running simulation..."):
        result_path = run_experiment(cfg, output_dir=Path(cfg.get("output", {}).get("base_dir", "results")))
    st.success(f"Experiment finished. Result saved to: {result_path}")

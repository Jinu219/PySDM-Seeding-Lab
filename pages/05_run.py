import streamlit as st
from pathlib import Path
from simulation.config import load_config
from simulation.validation import validate_config
from simulation.runner import run_experiment

CONFIG_PATH = "configs/default.yaml"

st.title("05. Run Simulation")

cfg = load_config(CONFIG_PATH)

st.subheader("Current Configuration")
st.json(cfg)

errors = validate_config(cfg)

if errors:
    st.error("Configuration has errors.")
    for err in errors:
        st.write(f"- {err}")
else:
    st.success("Configuration is valid.")

if st.button("Run Experiment", disabled=bool(errors)):
    with st.spinner("Running simulation..."):
        result_path = run_experiment(cfg, output_dir=Path("results"))
    st.success(f"Experiment finished. Result saved to: {result_path}")

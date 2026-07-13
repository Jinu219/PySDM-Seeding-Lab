from pathlib import Path

import pandas as pd
import streamlit as st

from simulation.config import load_config
from simulation.runner import run_experiment
from simulation.validation import (
    validate_config,
    validation_report_rows,
    validation_summary,
)


CONFIG_PATH = "configs/default.yaml"

st.title("05. Run Simulation")
st.caption("현재 working configuration을 검증하고 simulation runner를 실행합니다.")

cfg = load_config(CONFIG_PATH)

experiment = cfg.get("experiment", {})
simulation = cfg.get("simulation", {})
output = cfg.get("output", {})

st.subheader("Run Options")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Experiment", experiment.get("name", "unnamed"))

with col2:
    st.metric("Mode", experiment.get("mode", "single"))

with col3:
    st.metric("Adapter", simulation.get("adapter", "placeholder_warm_cloud"))
    st.metric("Output Dir", output.get("base_dir", "results"))

st.subheader("Configuration Validation")

summary = validation_summary(cfg)
errors = validate_config(cfg)
report_rows = validation_report_rows(cfg)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Errors", summary["error"])
m2.metric("Warnings", summary["warning"])
m3.metric("Info", summary["info"])
m4.metric("Total Issues", summary["total"])

if summary["error"] > 0:
    st.error("Configuration has blocking errors. Fix them before running the simulation.")
elif summary["warning"] > 0:
    st.warning("Configuration is runnable, but warnings should be reviewed.")
else:
    st.success("Configuration is valid.")

if report_rows:
    report_df = pd.DataFrame(report_rows)
    severity_filter = st.multiselect(
        "Show severities",
        ["error", "warning", "info"],
        default=["error", "warning", "info"],
    )
    if severity_filter:
        report_df = report_df[report_df["severity"].isin(severity_filter)]
    st.dataframe(report_df, use_container_width=True)
else:
    st.info("No validation issues found.")

with st.expander("Current configuration"):
    st.json(cfg)

run_disabled = summary["error"] > 0

if st.button("Run Experiment", disabled=run_disabled, use_container_width=True):
    with st.spinner("Running simulation..."):
        result_path = run_experiment(
            cfg,
            output_dir=Path(output.get("base_dir", "results")),
        )
    st.success(f"Experiment finished. Result saved to: {result_path}")

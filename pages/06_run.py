from pathlib import Path

import pandas as pd
import streamlit as st

from simulation.config import load_config
from simulation.experiment_manager import apply_scenario_identity, list_scenarios, load_scenario_config, read_scenario
from simulation.runner import run_experiment
from simulation.validation import (
    validate_config,
    validation_report_rows,
    validation_summary,
)
from simulation.ui_helpers import build_badge, inject_responsive_css


CONFIG_PATH = "configs/default.yaml"
UI_BUILD_ID = "scenario-names-simple-dashboard-20260713"

inject_responsive_css()
st.title("06. Run Simulation")
st.caption("현재 working configuration을 검증하고 simulation runner를 실행합니다.")
st.info("Simple workflow: select scenario → check result name preview → Run Experiment → open Results Dashboard.")
build_badge("UI build", UI_BUILD_ID)

working_cfg = load_config(CONFIG_PATH)
scenarios = list_scenarios()

scenario_options = ["Current working config"] + [
    f"{item['name']} · {item.get('created_at', '')}" for item in scenarios
]

selected_scenario_label = st.selectbox("Scenario to run", scenario_options)

scenario_memo = ""
if selected_scenario_label == "Current working config":
    cfg = working_cfg
    selected_scenario = None
else:
    selected_scenario = scenarios[scenario_options.index(selected_scenario_label) - 1]
    scenario_payload = read_scenario(selected_scenario["path"])
    cfg = apply_scenario_identity(scenario_payload.get("config", {}), selected_scenario["path"])
    scenario_memo = scenario_payload.get("metadata", {}).get("memo", "")

experiment = cfg.get("experiment", {})
simulation = cfg.get("simulation", {})
output = cfg.get("output", {})

if scenario_memo:
    st.markdown("Scenario memo")
    st.info(scenario_memo)

st.subheader("Run Options")
run_name_preview = cfg.get("experiment", {}).get("name", "experiment")
st.success(f"Result name preview: `{run_name_preview}`")
st.caption("The result directory will include this scenario/experiment name.")
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
    progress_bar = st.progress(0)
    status_box = st.empty()

    def report_progress(stage: str, current: int, total: int, message: str) -> None:
        progress_bar.progress(min(current / max(total, 1), 1.0))
        status_box.info(f"[{current}/{total}] {stage}: {message}")

    try:
        with st.spinner("Running simulation..."):
            result_path = run_experiment(
                cfg,
                output_dir=Path(output.get("base_dir", "results")),
                progress_callback=report_progress,
            )
        progress_bar.progress(1.0)
        status_box.success(f"Finished: {result_path}")
        st.success(f"Experiment finished. Result directory: {result_path}")
    except Exception as exc:
        st.error("Simulation failed.")
        st.exception(exc)

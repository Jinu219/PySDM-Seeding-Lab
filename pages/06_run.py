from pathlib import Path

import pandas as pd
import streamlit as st

from simulation.config import load_config
from simulation.experiment_manager import apply_scenario_identity, list_scenarios, load_scenario_config, read_scenario
from simulation.runner import run_experiment
from simulation.run_plan import estimate_run_plan, run_plan_rows
from simulation.validation import (
    validate_config,
    validation_report_rows,
    validation_summary,
)
from simulation.ui_helpers import build_badge, inject_responsive_css


CONFIG_PATH = "configs/default.yaml"
UI_BUILD_ID = "progress-dashboard-20260713"

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

plan = estimate_run_plan(cfg)

st.subheader("Run Plan")
p1, p2, p3, p4 = st.columns(4)
p1.metric("Sweep cases", plan.case_count)
p2.metric("Ensemble members", plan.ensemble_members)
p3.metric("Control/seeding factor", plan.control_factor)
p4.metric("Estimated model runs", plan.total_model_runs)

st.caption(plan.description)

if plan.total_model_runs >= 100:
    st.warning("This run is large. Consider testing with fewer sweep cases or ensemble members first.")

with st.expander("Run plan details"):
    st.dataframe(pd.DataFrame(run_plan_rows(cfg)), use_container_width=True)

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
    plan = estimate_run_plan(cfg)

    st.subheader("Live Progress")
    overall_bar = st.progress(0)
    stage_bar = st.progress(0)

    metric_total, metric_done, metric_remaining, metric_current = st.columns(4)
    status_box = st.empty()
    event_box = st.empty()

    progress_state = {
        "completed_runs": 0,
        "seen_completion_events": set(),
        "events": [],
    }

    def add_completed_run(event_key: str, label: str) -> None:
        if event_key in progress_state["seen_completion_events"]:
            return

        progress_state["seen_completion_events"].add(event_key)
        progress_state["completed_runs"] = min(
            progress_state["completed_runs"] + 1,
            max(plan.total_model_runs, 1),
        )
        progress_state["events"].append(label)
        progress_state["events"] = progress_state["events"][-8:]

    def report_progress(stage: str, current: int, total: int, message: str) -> None:
        # Local stage progress
        stage_fraction = min(current / max(total, 1), 1.0)
        stage_bar.progress(stage_fraction)

        # Estimate completed model runs from high-level runner stages.
        # For control_vs_seeding, comparison stage 3 begins after control has finished,
        # and stage 4 begins after seeding has finished.
        if stage == "comparison" and current == 3:
            add_completed_run(f"{stage}:{len(progress_state['seen_completion_events'])}:control", "Completed control run")
        elif stage == "comparison" and current == 4:
            add_completed_run(f"{stage}:{len(progress_state['seen_completion_events'])}:seeding", "Completed seeding run")
        elif stage == "runner" and current == 4 and plan.control_factor == 1:
            add_completed_run(f"{stage}:{len(progress_state['seen_completion_events'])}:single", "Completed single run")

        completed = progress_state["completed_runs"]
        total_runs = max(plan.total_model_runs, 1)
        remaining = max(total_runs - completed, 0)
        overall_bar.progress(min(completed / total_runs, 1.0))

        metric_total.metric("Total model runs", total_runs)
        metric_done.metric("Completed", completed)
        metric_remaining.metric("Remaining", remaining)
        metric_current.metric("Current stage", stage)

        status_box.info(
            f"Stage [{current}/{total}] {stage}: {message}\n\n"
            f"Overall model-run progress: {completed}/{total_runs}"
        )

        if progress_state["events"]:
            event_box.code("\n".join(progress_state["events"][-8:]))

    try:
        with st.spinner("Running simulation..."):
            result_path = run_experiment(
                cfg,
                output_dir=Path(output.get("base_dir", "results")),
                progress_callback=report_progress,
            )

        progress_state["completed_runs"] = max(progress_state["completed_runs"], plan.total_model_runs)
        overall_bar.progress(1.0)
        stage_bar.progress(1.0)
        status_box.success(f"Finished: {result_path}")
        metric_done.metric("Completed", plan.total_model_runs)
        metric_remaining.metric("Remaining", 0)

        st.success(f"Experiment finished. Result directory: {result_path}")
        st.info("Open 07. Results Dashboard and select the result folder with this scenario name.")
    except Exception as exc:
        st.error("Simulation failed.")
        st.exception(exc)

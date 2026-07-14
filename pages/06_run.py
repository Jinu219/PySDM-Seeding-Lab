from pathlib import Path
import re

import pandas as pd
import streamlit as st

from simulation.config import load_config
from simulation.experiment_manager import apply_scenario_identity, list_scenarios, load_scenario_config, read_scenario
from simulation.runner import run_experiment
from simulation.run_plan import estimate_run_plan, run_plan_rows
from simulation.run_timing import format_seconds
from simulation.schema import diagnostic_radius_thresholds
from simulation.validation import (
    validate_config,
    validation_report_rows,
    validation_summary,
)
from simulation.ui_helpers import build_badge, inject_responsive_css


CONFIG_PATH = "configs/default.yaml"
UI_BUILD_ID = "native-diagnostic-run-plan-20260714"

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

t1, t2 = st.columns(2)
t1.metric("Estimated time per run", format_seconds(plan.estimated_seconds_per_run))
t2.metric("Estimated total runtime", plan.estimated_total_duration)
st.caption(f"Runtime estimate basis: {plan.runtime_basis}")

st.caption(plan.description)

if plan.runtime_warning:
    st.warning(plan.runtime_warning)
elif plan.total_model_runs >= 100:
    st.warning("This run is large. Consider testing with fewer sweep cases or ensemble members first.")

with st.expander("Run plan details"):
    st.dataframe(pd.DataFrame(run_plan_rows(cfg)), use_container_width=True)

activation_radius_m, rain_radius_m = diagnostic_radius_thresholds(cfg)
with st.expander("Native diagnostic definitions", expanded=False):
    diagnostic_cols = st.columns(3)
    diagnostic_cols[0].metric("Activation cutoff", f"{activation_radius_m * 1.0e6:g} µm")
    diagnostic_cols[1].metric("Rain cutoff", f"{rain_radius_m * 1.0e6:g} µm")
    diagnostic_cols[2].metric("Range convention", "lower ≤ r < upper")
    st.caption(
        "pysdm_parcel은 이 wet-radius 경계로 unactivated/cloud/rain water, concentration, "
        "effective radius를 native product로 분리합니다. 경계값은 result metadata에도 저장됩니다."
    )

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

    progress_card = st.container(border=True)
    with progress_card:
        overview_text = st.empty()
        overall_bar = st.progress(0)
        stage_bar = st.progress(0)

        metric_cols = st.columns(4)
        metric_total_box = metric_cols[0].empty()
        metric_done_box = metric_cols[1].empty()
        metric_remaining_box = metric_cols[2].empty()
        metric_stage_box = metric_cols[3].empty()

        status_box = st.empty()
        event_box = st.empty()

    progress_state = {
        "completed_runs": 0,
        "events": [],
        "current_sweep_case": None,
        "current_ensemble_member": None,
    }

    def render_progress(stage: str, current: int, total: int, message: str) -> None:
        total_runs = max(plan.total_model_runs, 1)
        completed = min(progress_state["completed_runs"], total_runs)
        remaining = max(total_runs - completed, 0)
        overall_fraction = min(completed / total_runs, 1.0)
        stage_fraction = min(current / max(total, 1), 1.0)

        context_parts = []
        if progress_state.get("current_sweep_case"):
            context_parts.append(f"sweep {progress_state['current_sweep_case']}")
        if progress_state.get("current_ensemble_member"):
            context_parts.append(f"member {progress_state['current_ensemble_member']}")
        context = " · ".join(context_parts)

        overview_text.markdown(
            f"""
            **Progress overview**  
            `{completed} / {total_runs}` model runs completed · `{remaining}` remaining · current stage: `{stage}`  
            {context}
            """
        )
        overall_bar.progress(overall_fraction)
        stage_bar.progress(stage_fraction)

        metric_total_box.metric("Total", total_runs)
        metric_done_box.metric("Done", completed)
        metric_remaining_box.metric("Left", remaining)
        metric_stage_box.metric("Stage", stage)

        status_box.info(f"Stage [{current}/{total}] {stage}: {message}")

        if progress_state["events"]:
            event_box.dataframe(
                pd.DataFrame({"Recent events": progress_state["events"][-8:][::-1]}),
                use_container_width=True,
                hide_index=True,
            )

    def add_completed_run(label: str) -> None:
        total_runs = max(plan.total_model_runs, 1)
        if progress_state["completed_runs"] >= total_runs:
            return

        progress_state["completed_runs"] += 1
        completed = progress_state["completed_runs"]
        progress_state["events"].append(f"{completed}/{total_runs} · {label}")

    def _parse_sweep_message(message: str) -> None:
        match = re.search(r"sweep case\s+(\d+)/(\d+)", message)
        if match:
            progress_state["current_sweep_case"] = f"{match.group(1)}/{match.group(2)}"

    def _parse_ensemble_message(message: str) -> None:
        match = re.search(r"ensemble member\s+(\d+)/(\d+)", message)
        if match:
            progress_state["current_ensemble_member"] = f"{match.group(1)}/{match.group(2)}"

    def report_progress(stage: str, current: int, total: int, message: str) -> None:
        if stage == "sweep":
            _parse_sweep_message(message)
        elif stage == "ensemble":
            _parse_ensemble_message(message)

        if stage == "model_run_complete":
            add_completed_run(message)
            render_progress("model run", 1, 1, message)
            return

        render_progress(stage, current, total, message)

    try:
        render_progress("queued", 0, 1, "Waiting to start")
        with st.spinner("Running simulation..."):
            result_path = run_experiment(
                cfg,
                output_dir=Path(output.get("base_dir", "results")),
                progress_callback=report_progress,
            )

        progress_state["completed_runs"] = plan.total_model_runs
        progress_state["events"].append("All runs completed")
        render_progress("finished", 1, 1, f"Finished: {result_path}")

        st.success(f"Experiment finished. Result directory: {result_path}")
        st.info("Open 07. Results Dashboard and select the result folder with this scenario name.")
    except Exception as exc:
        st.error("Simulation failed.")
        st.exception(exc)

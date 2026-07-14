from pathlib import Path

import pandas as pd
import streamlit as st

from simulation.config import load_config, save_config
from simulation.schema import ADAPTER_NAMES, EXPERIMENT_MODES
from simulation.sweep import count_sweep_cases
from simulation.ui_helpers import inject_responsive_css, scenario_loader
from simulation.validation import validation_summary


st.set_page_config(
    page_title="Welcome · PySDM Seeding Lab",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_responsive_css()

cfg = load_config("configs/default.yaml")
experiment = cfg.get("experiment", {})
simulation = cfg.get("simulation", {})
environment = cfg.get("environment", {})
aerosol = cfg.get("background_aerosol", {})
seeding = cfg.get("seeding", {})
microphysics = cfg.get("microphysics", {})
summary = validation_summary(cfg)

st.markdown('<div class="lab-kicker">Start here</div>', unsafe_allow_html=True)
st.title("Welcome to PySDM Seeding Lab")
st.markdown(
    """
    <div class="lab-hero">
      <h2>Warm hygroscopic cloud seeding을 재현 가능한 실험으로 설계하세요.</h2>
      <p>
        시나리오 정의 → 대기·에어로졸·시딩 설정 → sensitivity/ensemble 실행 →
        control–seeding 비교와 Growth Pathway 진단까지 한 흐름으로 관리하는 연구용 워크벤치입니다.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

start_col, sweep_col, run_col, result_col = st.columns(4)
with start_col:
    st.page_link("pages/00_experiment_scenarios.py", label="1 · Create scenario", icon="🧭", use_container_width=True)
with sweep_col:
    st.page_link("pages/05_parameter_sweep.py", label="2 · Design sensitivity", icon="🧪", use_container_width=True)
with run_col:
    st.page_link("pages/06_run.py", label="3 · Run experiment", icon="▶️", use_container_width=True)
with result_col:
    st.page_link("pages/07_results.py", label="4 · Analyze results", icon="📊", use_container_width=True)

st.subheader("Recommended workflow")
workflow_left, workflow_right = st.columns(2)
with workflow_left:
    st.markdown(
        """
        <div class="lab-step"><strong>01 · Scenario</strong><br><span>실험 이름·메모와 재현 가능한 YAML 기준점을 만듭니다.</span></div>
        <div class="lab-step"><strong>02 · Environment & aerosol</strong><br><span>온도·수증기·상승류와 배경 CCN regime을 정의합니다.</span></div>
        <div class="lab-step"><strong>03 · Seeding</strong><br><span>dry radius, κ, 농도, 분포 폭과 주입 구간을 설정합니다.</span></div>
        <div class="lab-step"><strong>04 · Dynamics</strong><br><span>현재 adapter에 실제 연결된 입력과 향후 parameterization을 구분합니다.</span></div>
        """,
        unsafe_allow_html=True,
    )
with workflow_right:
    st.markdown(
        """
        <div class="lab-step"><strong>05 · Sensitivity design</strong><br><span>한 번에 1–3개 물리 변수를 선택하고 numerical convergence는 별도로 검사합니다.</span></div>
        <div class="lab-step"><strong>06 · Run plan</strong><br><span>case × ensemble × control/seeding의 실제 model-run 수를 확인합니다.</span></div>
        <div class="lab-step"><strong>07 · Results</strong><br><span>diff = seeding − control과 thermodynamic → rain pathway를 순서대로 해석합니다.</span></div>
        <div class="lab-step"><strong>08 · Publication</strong><br><span>provenance가 표시된 OFAT, ensemble, collision, four-panel을 내보냅니다.</span></div>
        """,
        unsafe_allow_html=True,
    )

st.subheader("Current working configuration")
snapshot_cols = st.columns(6)
snapshot_cols[0].metric("Experiment", experiment.get("name", "unnamed"))
snapshot_cols[1].metric("Mode", experiment.get("mode", "single"))
snapshot_cols[2].metric("Adapter", simulation.get("adapter", "unknown"))
snapshot_cols[3].metric("Updraft", f"{environment.get('updraft_velocity', 'NA')} m s⁻¹")
snapshot_cols[4].metric("Seeding", "ON" if seeding.get("enabled", False) else "OFF")
snapshot_cols[5].metric("Collision", "ON" if microphysics.get("collision", False) else "OFF")

status_col, quick_col = st.columns([1, 1.35])
with status_col:
    with st.container(border=True):
        st.markdown("#### Configuration health")
        health_cols = st.columns(3)
        health_cols[0].metric("Errors", summary["error"])
        health_cols[1].metric("Warnings", summary["warning"])
        health_cols[2].metric("Info", summary["info"])
        if summary["error"]:
            st.error("Blocking configuration errors exist. Open Run Simulation for details.")
        elif summary["warning"]:
            st.warning("Runnable configuration, but warnings should be reviewed.")
        else:
            st.success("Configuration is valid.")

        if simulation.get("adapter") == "placeholder_warm_cloud":
            st.info("Placeholder 결과는 UI 검증용입니다. 물리 결론에는 `pysdm_parcel`을 사용하세요.")

with quick_col:
    with st.container(border=True):
        st.markdown("#### Quick-start scenario")
        scenarios = scenario_loader()
        selected_scenario = st.selectbox(
            "Load into current working config",
            list(scenarios.keys()),
            index=0,
            key="welcome_scenario_loader",
        )
        st.caption("현재 작업 설정을 교체합니다. 저장된 experiment scenario 파일은 변경하지 않습니다.")
        if st.button("Load selected scenario", use_container_width=True):
            source_path = Path(scenarios[selected_scenario])
            cfg_to_load = load_config(source_path)
            save_config(cfg_to_load, "configs/default.yaml")
            st.success(f"Loaded {selected_scenario}. Open the next page to continue.")
            st.rerun()

        active_sweep_parameters = cfg.get("sweep", {}).get("parameters", [])
        sweep_cases = count_sweep_cases(cfg) if active_sweep_parameters else 0
        st.caption(
            f"Current sweep: {len(active_sweep_parameters)} parameter(s), {sweep_cases} case(s). "
            f"Background aerosol: N={aerosol.get('number_concentration', 'NA')} cm⁻³, κ={aerosol.get('kappa', 'NA')}."
        )

st.subheader("How to interpret a warm-seeding experiment")
interpretation_rows = [
    {"Order": 1, "Question": "수증기·과포화도가 반응했는가?", "Primary diagnostics": "water_vapour_mixing_ratio_diff, supersaturation_percent_diff"},
    {"Order": 2, "Question": "구름물과 활성화 입자가 변했는가?", "Primary diagnostics": "cloud_water_mixing_ratio_diff, all_activated_*_diff"},
    {"Order": 3, "Question": "입자 크기 성장이 나타났는가?", "Primary diagnostics": "effective_radius_all_um_diff"},
    {"Order": 4, "Question": "collision–coalescence를 거쳐 rain response로 이어졌는가?", "Primary diagnostics": "rain_water_mixing_ratio_diff, rain_droplet_concentration_diff"},
    {"Order": 5, "Question": "결과가 random seed와 수치해상도에 견고한가?", "Primary diagnostics": "ensemble bands + timestep/super-droplet convergence"},
]
st.dataframe(pd.DataFrame(interpretation_rows), use_container_width=True, hide_index=True)

with st.expander("Advanced quick settings", expanded=False):
    advanced_col1, advanced_col2 = st.columns(2)
    with advanced_col1:
        mode = st.selectbox(
            "Experiment mode",
            EXPERIMENT_MODES,
            index=EXPERIMENT_MODES.index(experiment.get("mode", "control_vs_seeding"))
            if experiment.get("mode", "control_vs_seeding") in EXPERIMENT_MODES
            else 0,
        )
    with advanced_col2:
        adapter = st.selectbox(
            "Simulation adapter",
            ADAPTER_NAMES,
            index=ADAPTER_NAMES.index(simulation.get("adapter", "placeholder_warm_cloud"))
            if simulation.get("adapter", "placeholder_warm_cloud") in ADAPTER_NAMES
            else 0,
        )

    if st.button("Save mode and adapter", use_container_width=True):
        cfg.setdefault("experiment", {})["mode"] = mode
        cfg.setdefault("simulation", {})["adapter"] = adapter
        save_config(cfg, "configs/default.yaml")
        st.success("Mode and adapter saved.")

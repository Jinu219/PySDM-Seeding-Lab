from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from simulation.config import load_config
from simulation.experiment_manager import (
    apply_scenario_to_working_config,
    list_scenarios,
    load_scenario_config,
    read_scenario,
    save_scenario,
)
from simulation.ui_helpers import build_badge, inject_responsive_css


inject_responsive_css()

st.title("00. Experiment Scenarios")
st.caption("실험 시나리오를 저장하고, 저장된 시나리오를 working config에 적용합니다.")
build_badge("Scenario page build", "scenario-target-save-20260713")

st.info(
    "권장 흐름: 01~05 페이지에서 세팅값 조정 → 저장 대상에서 scenario 선택 → "
    "06 Run Simulation에서 해당 시나리오를 선택해 실행 → 07 Results에서 확인"
)

working_cfg = load_config("configs/default.yaml")

tab_save, tab_manage = st.tabs(["Save current settings", "Load / apply scenario"])

with tab_save:
    st.subheader("Save current configuration as scenario")

    name = st.text_input("Scenario name", value="dry_radius_kappa_sweep")
    memo = st.text_area(
        "Experiment memo",
        value="목적: seeding dry radius와 κ 변화가 rain water / cloud water / supersaturation에 미치는 영향 확인",
        height=120,
    )
    overwrite = st.checkbox("Overwrite if scenario name already exists", value=False)

    st.write("Current working config preview")
    with st.expander("Show current config"):
        st.json(working_cfg)

    if st.button("Save Scenario", use_container_width=True):
        try:
            path = save_scenario(
                name=name,
                memo=memo,
                config=working_cfg,
                overwrite=overwrite,
            )
            st.success(f"Scenario saved: {path}")
        except FileExistsError as exc:
            st.error(str(exc))
            st.info("Enable overwrite or choose another scenario name.")

with tab_manage:
    st.subheader("Saved scenarios")

    scenarios = list_scenarios()

    if not scenarios:
        st.warning("No saved scenarios yet.")
        st.stop()

    scenario_df = pd.DataFrame(scenarios)
    st.dataframe(scenario_df, use_container_width=True)

    labels = [
        f"{item['name']} · {item.get('created_at', '')} · {item.get('memo', '')[:40]}"
        for item in scenarios
    ]
    selected_label = st.selectbox("Select scenario", labels)
    selected = scenarios[labels.index(selected_label)]
    selected_path = Path(selected["path"])

    payload = read_scenario(selected_path)
    metadata = payload.get("metadata", {})
    scenario_cfg = payload.get("config", {})

    st.subheader(metadata.get("name", selected_path.stem))
    st.write(f"Path: `{selected_path}`")
    st.write(f"Created: `{metadata.get('created_at', '')}`")
    st.markdown("Memo")
    st.info(metadata.get("memo", ""))

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Apply to working config", use_container_width=True):
            apply_scenario_to_working_config(selected_path)
            st.success("Applied scenario to configs/default.yaml")
            st.info("Now open Parameter Sweep or Run Simulation.")

    with col2:
        if st.button("Run page에서 이 시나리오 사용", use_container_width=True):
            apply_scenario_to_working_config(selected_path)
            st.success("Scenario applied. Go to Run Simulation page.")

    with st.expander("Scenario config"):
        st.json(scenario_cfg)

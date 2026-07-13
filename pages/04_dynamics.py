import streamlit as st

from simulation.ui_helpers import (
    config_actions,
    load_working_config,
    page_header,
    schema_expander,
    unit_label,
)


page_header(
    "04. Dynamic Parameters",
    "상승류, 난류, entrainment 등 동역학 관련 값을 정리합니다.",
)

cfg = load_working_config()
dyn = cfg.setdefault("dynamics", {})
env = cfg.setdefault("environment", {})

st.warning(
    """
    현재 MVP에서는 `updraft_strength`만 직접적인 모델 입력 후보로 관리합니다.
    turbulence, entrainment, detrainment, wind shear, convergence, CAPE, CIN은
    이후 parameterization을 추가하면서 PySDM adapter와 연결할 예정입니다.
    """
)

col1, col2 = st.columns(2)

with col1:
    dyn["updraft_strength"] = st.number_input(
        "Updraft strength" + unit_label("dynamics", "updraft_strength"),
        value=float(dyn.get("updraft_strength", env.get("updraft_velocity", 1.0))),
        step=0.1,
    )
    dyn["downdraft_strength"] = st.number_input(
        "Downdraft strength" + unit_label("dynamics", "downdraft_strength"),
        value=float(dyn.get("downdraft_strength", 0.0)),
        step=0.1,
    )
    dyn["turbulence_intensity"] = st.number_input(
        "Turbulence intensity" + unit_label("dynamics", "turbulence_intensity"),
        min_value=0.0,
        value=float(dyn.get("turbulence_intensity", 0.0)),
        step=0.05,
    )
    dyn["entrainment_rate"] = st.number_input(
        "Entrainment rate" + unit_label("dynamics", "entrainment_rate"),
        min_value=0.0,
        value=float(dyn.get("entrainment_rate", 0.0)),
        step=1e-5,
        format="%.2e",
    )

with col2:
    dyn["detrainment_rate"] = st.number_input(
        "Detrainment rate" + unit_label("dynamics", "detrainment_rate"),
        min_value=0.0,
        value=float(dyn.get("detrainment_rate", 0.0)),
        step=1e-5,
        format="%.2e",
    )
    dyn["wind_shear"] = st.number_input(
        "Wind shear" + unit_label("dynamics", "wind_shear"),
        value=float(dyn.get("wind_shear", 0.0)),
        step=1e-4,
        format="%.2e",
    )
    dyn["convergence"] = st.number_input(
        "Convergence" + unit_label("dynamics", "convergence"),
        value=float(dyn.get("convergence", 0.0)),
        step=1e-4,
        format="%.2e",
    )
    dyn["cape"] = st.number_input(
        "CAPE" + unit_label("dynamics", "cape"),
        min_value=0.0,
        value=float(dyn.get("cape", 0.0)),
        step=100.0,
    )
    dyn["cin"] = st.number_input(
        "CIN" + unit_label("dynamics", "cin"),
        min_value=0.0,
        value=float(dyn.get("cin", 0.0)),
        step=10.0,
    )

sync = st.checkbox("Sync dynamics.updraft_strength to environment.updraft_velocity", value=True)
if sync:
    env["updraft_velocity"] = dyn["updraft_strength"]
    st.info("environment.updraft_velocity will be updated when you save.")

config_actions(cfg, "Save Dynamic Settings")
schema_expander()

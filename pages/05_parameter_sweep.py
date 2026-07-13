from __future__ import annotations

import streamlit as st

from simulation.config import save_config
from simulation.experiment_manager import scenario_options, read_scenario, update_scenario_config
from simulation.schema import EXPERIMENT_MODES
from simulation.sweep import count_sweep_cases
from simulation.ui_helpers import load_working_config, page_header, schema_expander


page_header(
    "05. Parameter Sweep",
    "여러 seeding condition 조합을 자동으로 생성하고 실행하기 위한 sweep 설정입니다.",
)

working_cfg = load_working_config()

st.subheader("Scenario / Config Source")
scenario_items = scenario_options(include_working_config=True)
scenario_labels = [item["label"] for item in scenario_items]
selected_scenario_label = st.selectbox(
    "Configure sweep for",
    scenario_labels,
    key="parameter_sweep_scenario_source",
)
selected_scenario = scenario_items[scenario_labels.index(selected_scenario_label)]

if selected_scenario.get("is_working_config", False):
    cfg = working_cfg
    scenario_memo = ""
else:
    payload = read_scenario(selected_scenario["path"])
    cfg = payload.get("config", {})
    scenario_memo = payload.get("metadata", {}).get("memo", "")

if scenario_memo:
    st.markdown("Scenario memo")
    st.info(scenario_memo)

sweep = cfg.setdefault("sweep", {})
experiment = cfg.setdefault("experiment", {})

st.subheader("Sweep Mode")

enable_sweep = st.toggle(
    "Set experiment.mode = parameter_sweep",
    value=experiment.get("mode") == "parameter_sweep",
)

if enable_sweep:
    experiment["mode"] = "parameter_sweep"
else:
    if experiment.get("mode") == "parameter_sweep":
        experiment["mode"] = "control_vs_seeding"

sweep["run_mode"] = st.selectbox(
    "Run mode for each sweep case",
    ["control_vs_seeding", "single"],
    index=["control_vs_seeding", "single"].index(sweep.get("run_mode", "control_vs_seeding"))
    if sweep.get("run_mode", "control_vs_seeding") in ["control_vs_seeding", "single"]
    else 0,
)

sweep["max_runs"] = st.number_input(
    "Maximum allowed cases",
    min_value=1,
    value=int(sweep.get("max_runs", 100)),
    step=10,
)

sweep["ranking_metric"] = st.text_input(
    "Ranking metric",
    value=str(
        sweep.get(
            "ranking_metric",
            "comparison.efficiency.seeding_efficiency_score",
        )
    ),
)

st.divider()
st.subheader("Common Sweep Parameters")

st.caption("값은 comma-separated list로 입력합니다. Dry radius는 UI에서는 µm로 입력하고 config에는 m로 저장합니다.")

col1, col2 = st.columns(2)

with col1:
    use_radius = st.checkbox("Sweep seeding dry radius [µm]", value=True)
    radius_values_um = st.text_input("Dry radius values [µm]", value="0.5, 1.0, 1.5")

    use_kappa = st.checkbox("Sweep seeding κ", value=True)
    kappa_values = st.text_input("κ values", value="0.8, 1.0, 1.2")

    use_injection = st.checkbox("Sweep injection start [s]", value=False)
    injection_values = st.text_input("Injection start values [s]", value="600, 900, 1200")

with col2:
    use_seed_conc = st.checkbox("Sweep seeding number concentration [cm⁻³]", value=False)
    seed_conc_values = st.text_input("Seeding concentration values [cm⁻³]", value="1, 10, 100")

    use_updraft = st.checkbox("Sweep updraft velocity [m/s]", value=False)
    updraft_values = st.text_input("Updraft velocity values [m/s]", value="0.5, 1.0, 1.5")

    use_duration = st.checkbox("Sweep injection duration [s]", value=False)
    duration_values = st.text_input("Injection duration values [s]", value="120, 300, 600")

    use_collision = st.checkbox("Sweep collision ON/OFF", value=False)


def parse_float_list(text: str) -> list[float]:
    values = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        values.append(float(item))
    return values


params = []

try:
    if use_radius:
        params.append(
            {
                "name": "seeding.dry_radius",
                "values": [value * 1.0e-6 for value in parse_float_list(radius_values_um)],
            }
        )

    if use_kappa:
        params.append(
            {
                "name": "seeding.kappa",
                "values": parse_float_list(kappa_values),
            }
        )

    if use_injection:
        params.append(
            {
                "name": "seeding.injection_start",
                "values": [int(value) for value in parse_float_list(injection_values)],
            }
        )

    if use_seed_conc:
        params.append(
            {
                "name": "seeding.number_concentration",
                "values": parse_float_list(seed_conc_values),
            }
        )

    if use_updraft:
        params.append(
            {
                "name": "environment.updraft_velocity",
                "values": parse_float_list(updraft_values),
            }
        )

    if use_duration:
        params.append(
            {
                "name": "seeding.injection_duration",
                "values": [int(value) for value in parse_float_list(duration_values)],
            }
        )

    if use_collision:
        params.append(
            {
                "name": "microphysics.collision",
                "values": [False, True],
            }
        )

    # injection_duration is a UI convenience. The runner does not know derived parameters yet,
    # so store only direct parameters in the initial MVP.
    params = [param for param in params if param["name"] != "seeding.injection_duration"]

    sweep["parameters"] = params

    n_cases = count_sweep_cases(cfg) if params else 0

    st.subheader("Sweep Preview")
    st.metric("Number of cases", n_cases)

    if n_cases > int(sweep.get("max_runs", 100)):
        st.error("Number of cases exceeds max_runs. Reduce values or increase max_runs.")
    elif n_cases == 0:
        st.warning("No active sweep parameters selected.")
    else:
        st.success("Sweep configuration is valid.")

    st.json({"sweep": sweep})

except Exception as exc:
    st.error("Failed to parse sweep values.")
    st.exception(exc)

if st.button("Save Sweep Settings", use_container_width=True):
    cfg["experiment"] = experiment
    cfg["sweep"] = sweep

    if selected_scenario.get("is_working_config", False):
        save_config(cfg, "configs/default.yaml")
        st.success("Sweep settings saved to configs/default.yaml")
    else:
        update_scenario_config(selected_scenario["path"], config=cfg)
        st.success(f"Sweep settings saved to scenario: {selected_scenario['name']}")

schema_expander()

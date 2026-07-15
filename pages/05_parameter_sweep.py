from __future__ import annotations

import itertools
import math
from typing import Any

import pandas as pd
import streamlit as st

from simulation.config import save_config
from simulation.experiment_manager import (
    apply_scenario_identity,
    read_scenario,
    scenario_options,
    update_scenario_config,
)
from simulation.sweep import count_sweep_cases
from simulation.sweep_catalog import (
    CATEGORY_DESCRIPTIONS,
    COMMON_SWEEP_PARAMETERS,
    SENSITIVITY_PRESETS,
    SWEEP_CATALOG_BUILD_ID,
    SweepParameterSpec,
    parameter_spec_lookup,
    parameter_specs_by_category,
    preset_parameters,
)
from simulation.ui_helpers import (
    build_badge,
    load_working_config,
    page_header,
    schema_expander,
)


page_header(
    "05. Parameter Sweep",
    "물리 가설과 수치수렴을 분리해 warm-cloud seeding sensitivity experiment를 설계합니다.",
)
build_badge("Sweep catalog build", SWEEP_CATALOG_BUILD_ID)

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
    cfg = apply_scenario_identity(payload.get("config", {}), selected_scenario["path"])
    scenario_memo = payload.get("metadata", {}).get("memo", "")

if scenario_memo:
    st.info(scenario_memo)

sweep = cfg.setdefault("sweep", {})
experiment = cfg.setdefault("experiment", {})
ensemble = cfg.setdefault("ensemble", {})

with st.container(border=True):
    st.subheader("Execution Design")
    mode_col, runs_col, metric_col = st.columns([1, 1, 1.4])
    with mode_col:
        enable_sweep = st.toggle(
            "Enable parameter sweep",
            value=experiment.get("mode") == "parameter_sweep",
        )
        experiment["mode"] = "parameter_sweep" if enable_sweep else (
            "control_vs_seeding" if experiment.get("mode") == "parameter_sweep" else experiment.get("mode", "control_vs_seeding")
        )
        sweep["run_mode"] = st.selectbox(
            "Run mode per case",
            ["control_vs_seeding", "single"],
            index=["control_vs_seeding", "single"].index(sweep.get("run_mode", "control_vs_seeding"))
            if sweep.get("run_mode", "control_vs_seeding") in ["control_vs_seeding", "single"]
            else 0,
        )
    with runs_col:
        sweep["max_runs"] = st.number_input(
            "Maximum allowed cases",
            min_value=1,
            value=int(sweep.get("max_runs", 100)),
            step=10,
        )
    with metric_col:
        sweep["ranking_metric"] = st.text_input(
            "Ranking metric",
            value=str(
                sweep.get(
                    "ranking_metric",
                    "ensemble.metrics.rain_water_mixing_ratio_diff_final_mean",
                )
            ),
        )

with st.container(border=True):
    st.subheader("Ensemble Statistics")
    ensemble_col, members_col, seed_col, step_col = st.columns([1.2, 1, 1, 1])
    with ensemble_col:
        ensemble["enabled"] = st.toggle(
            "Repeat each case as ensemble",
            value=bool(ensemble.get("enabled", False)),
        )
    with members_col:
        ensemble["n_members"] = st.number_input(
            "Members",
            min_value=1,
            max_value=100,
            value=int(ensemble.get("n_members", 5)),
            step=1,
        )
    with seed_col:
        ensemble["seed_start"] = st.number_input(
            "Seed start",
            min_value=0,
            value=int(ensemble.get("seed_start", 1000)),
            step=1,
        )
    with step_col:
        ensemble["seed_step"] = st.number_input(
            "Seed step",
            min_value=1,
            value=int(ensemble.get("seed_step", 1)),
            step=1,
        )

    if ensemble.get("enabled", False):
        backend_col, gc_col = st.columns([1.3, 1])
        with backend_col:
            backend_options = ["in_process", "subprocess"]
            current_backend = str(ensemble.get("execution_backend", "in_process"))
            ensemble["execution_backend"] = st.selectbox(
                "Member execution backend",
                backend_options,
                index=(
                    backend_options.index(current_backend)
                    if current_backend in backend_options
                    else 0
                ),
                format_func=lambda value: (
                    "In-process (faster)"
                    if value == "in_process"
                    else "Subprocess (memory-isolated)"
                ),
                help=(
                    "Subprocess starts a fresh Python process for every member so native/JIT "
                    "memory is returned to the OS when that member exits."
                ),
            )
        with gc_col:
            ensemble["collect_garbage_between_members"] = st.toggle(
                "Explicit GC between members",
                value=bool(
                    ensemble.get("collect_garbage_between_members", False)
                ),
                disabled=ensemble["execution_backend"] == "subprocess",
                help="Diagnostic A/B option for the in-process backend.",
            )
        if ensemble["execution_backend"] == "subprocess":
            st.info(
                "Memory isolation is enabled. Each member keeps its config, status, stdout, "
                "stderr, elapsed time, and child-process peak RSS in the result folder. "
                "Interpreter and PySDM/Numba startup overhead is paid once per member."
            )
        st.caption(
            "Ensemble은 stochastic uncertainty용입니다. timestep/super-droplet sweep은 별도의 numerical convergence 실험으로 해석하세요."
        )


def _widget_suffix(name: str) -> str:
    return name.replace(".", "__")


def _use_key(spec: SweepParameterSpec) -> str:
    return f"common_sweep_use__{_widget_suffix(spec.name)}"


def _values_key(spec: SweepParameterSpec) -> str:
    return f"common_sweep_values__{_widget_suffix(spec.name)}"


def _format_existing_values(spec: SweepParameterSpec, values: list[Any]) -> str:
    if spec.value_type == "bool":
        return "false, true"
    formatted = []
    for value in values:
        numeric = float(value) / spec.input_scale
        if spec.value_type == "int":
            formatted.append(str(int(round(numeric))))
        else:
            formatted.append(f"{numeric:g}")
    return ", ".join(formatted)


def _parse_values(spec: SweepParameterSpec, raw_text: str) -> list[Any]:
    if spec.value_type == "bool":
        return [False, True]

    values = []
    for item in raw_text.split(","):
        item = item.strip()
        if not item:
            continue
        numeric = float(item)
        if not math.isfinite(numeric):
            raise ValueError(f"{spec.label}: non-finite value '{item}' is not allowed")
        if spec.value_type == "int":
            if not numeric.is_integer():
                raise ValueError(f"{spec.label}: '{item}' must be an integer")
            values.append(int(numeric * spec.input_scale))
        else:
            values.append(float(numeric * spec.input_scale))

    if not values:
        raise ValueError(f"{spec.label}: enter at least one value")
    if len(set(values)) != len(values):
        raise ValueError(f"{spec.label}: duplicate values are not allowed")
    return values


catalog_lookup = parameter_spec_lookup()
existing_params = {
    str(param.get("name")): list(param.get("values", []))
    for param in sweep.get("parameters", [])
    if param.get("name") and isinstance(param.get("values", []), list)
}

source_identity = str(
    selected_scenario.get("path", "configs/default.yaml")
    if not selected_scenario.get("is_working_config", False)
    else "configs/default.yaml"
)
source_state_key = "common_sweep_widget_source"
source_changed = st.session_state.get(source_state_key) != source_identity

for spec in COMMON_SWEEP_PARAMETERS:
    if source_changed:
        st.session_state[_use_key(spec)] = spec.name in existing_params
    else:
        st.session_state.setdefault(_use_key(spec), spec.name in existing_params)
    if spec.value_type != "bool":
        initial_values = existing_params.get(spec.name)
        initial_text = _format_existing_values(spec, initial_values) if initial_values else spec.default_values
        if source_changed:
            st.session_state[_values_key(spec)] = initial_text
        else:
            st.session_state.setdefault(_values_key(spec), initial_text)

st.session_state[source_state_key] = source_identity

st.divider()
st.subheader("Common Sweep Parameters")
st.caption(
    "18개 common parameter를 물리 목적별로 나눴습니다. 한 번에 모두 켜기보다 preset 또는 1–3개 핵심 변수를 선택하세요."
)

preset_col, apply_col = st.columns([3, 1])
with preset_col:
    selected_preset = st.selectbox(
        "Sensitivity experiment preset",
        list(SENSITIVITY_PRESETS.keys()),
        key="sensitivity_experiment_preset",
    )
    st.caption(str(SENSITIVITY_PRESETS[selected_preset]["description"]))
with apply_col:
    st.write("")
    st.write("")
    apply_preset = st.button("Apply preset", use_container_width=True)

if apply_preset:
    selected_parameters = dict(preset_parameters(selected_preset))
    for spec in COMMON_SWEEP_PARAMETERS:
        st.session_state[_use_key(spec)] = spec.name in selected_parameters
        if spec.value_type != "bool" and spec.name in selected_parameters:
            st.session_state[_values_key(spec)] = selected_parameters[spec.name]
    st.rerun()

category_tabs = st.tabs(list(CATEGORY_DESCRIPTIONS.keys()))
for tab, (category, specs) in zip(category_tabs, parameter_specs_by_category().items()):
    with tab:
        st.caption(CATEGORY_DESCRIPTIONS[category])
        parameter_columns = st.columns(2)
        for idx, spec in enumerate(specs):
            with parameter_columns[idx % 2]:
                with st.container(border=True):
                    enabled = st.checkbox(
                        spec.label,
                        key=_use_key(spec),
                        help=spec.why,
                    )
                    role_label = "Numerical convergence" if spec.role == "numerical" else "Physical sensitivity"
                    st.markdown(
                        f'<div class="lab-parameter-note"><strong>{role_label}</strong> · {spec.why}</div>',
                        unsafe_allow_html=True,
                    )
                    if spec.value_type == "bool":
                        st.caption("Values: OFF, ON")
                    else:
                        st.text_input(
                            spec.value_label,
                            key=_values_key(spec),
                            disabled=not enabled,
                        )

params: list[dict[str, Any]] = []
parse_error: Exception | None = None
for spec in COMMON_SWEEP_PARAMETERS:
    if not st.session_state.get(_use_key(spec), False):
        continue
    try:
        raw_text = spec.default_values if spec.value_type == "bool" else str(st.session_state[_values_key(spec)])
        params.append({"name": spec.name, "values": _parse_values(spec, raw_text)})
    except Exception as exc:
        parse_error = exc
        break

# Preserve advanced dotted-key parameters that are not yet part of the common catalog.
custom_params = [
    {"name": name, "values": values}
    for name, values in existing_params.items()
    if name not in catalog_lookup
]
if custom_params:
    preserve_custom = st.checkbox(
        f"Preserve {len(custom_params)} custom sweep parameter(s)",
        value=True,
        help=", ".join(param["name"] for param in custom_params),
    )
    if preserve_custom:
        params.extend(custom_params)

sweep["parameters"] = params
n_cases = count_sweep_cases(cfg) if params else 0
ensemble_factor = int(ensemble.get("n_members", 1)) if ensemble.get("enabled", False) else 1
mode_factor = 2 if sweep.get("run_mode") == "control_vs_seeding" else 1
estimated_model_runs = n_cases * ensemble_factor * mode_factor

st.subheader("Sweep Preview")
preview_cols = st.columns(4)
preview_cols[0].metric("Active parameters", len(params))
preview_cols[1].metric("Sweep cases", n_cases)
preview_cols[2].metric("Ensemble members", ensemble_factor)
preview_cols[3].metric("Estimated model runs", estimated_model_runs)

sweep_is_valid = True
if parse_error is not None:
    sweep_is_valid = False
    st.error(f"Failed to parse sweep values: {parse_error}")
elif n_cases > int(sweep.get("max_runs", 100)):
    sweep_is_valid = False
    st.error("Number of cases exceeds max_runs. Reduce parameter values or increase the limit intentionally.")
elif n_cases == 0:
    sweep_is_valid = False
    st.warning("No active sweep parameters selected.")

physical_specs = [catalog_lookup[param["name"]] for param in params if param["name"] in catalog_lookup and catalog_lookup[param["name"]].role == "physical"]
numerical_specs = [catalog_lookup[param["name"]] for param in params if param["name"] in catalog_lookup and catalog_lookup[param["name"]].role == "numerical"]
if physical_specs and numerical_specs:
    st.warning(
        "Physical sensitivity와 numerical convergence parameter가 같은 Cartesian grid에 섞여 있습니다. "
        "먼저 numerical convergence preset으로 해상도를 정한 뒤 물리 sweep을 별도로 실행하는 편이 해석에 안전합니다."
    )

if cfg.get("simulation", {}).get("adapter") == "placeholder_warm_cloud":
    ineffective = [
        spec.label
        for spec in physical_specs + numerical_specs
        if not spec.placeholder_effective
    ]
    if ineffective:
        st.info(
            "placeholder_warm_cloud는 다음 선택값을 실제 물리에 반영하지 않습니다: "
            + ", ".join(ineffective)
            + ". UI 점검 후 pysdm_parcel로 실행하세요."
        )

param_map = {param["name"]: param["values"] for param in params}
start_values = param_map.get("seeding.injection_start", [cfg.get("seeding", {}).get("injection_start", 0)])
duration_values = param_map.get("seeding.injection_duration", [])
simulation_duration = int(cfg.get("environment", {}).get("duration", 0))
if duration_values:
    invalid_windows = [
        (int(start), int(duration))
        for start, duration in itertools.product(start_values, duration_values)
        if int(start) + int(duration) > simulation_duration
    ]
    if invalid_windows:
        sweep_is_valid = False
        st.error(
            f"{len(invalid_windows)} injection window(s) exceed environment.duration={simulation_duration} s. "
            f"Example: start={invalid_windows[0][0]} s + duration={invalid_windows[0][1]} s."
        )

if params:
    preview_rows = []
    for param in params:
        spec = catalog_lookup.get(param["name"])
        preview_rows.append(
            {
                "parameter": param["name"],
                "role": spec.role if spec else "custom",
                "n_values": len(param["values"]),
                "values": str(param["values"]),
            }
        )
    with st.expander("Active parameter table", expanded=False):
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

if sweep_is_valid:
    st.success("Sweep configuration is internally consistent.")

if st.button("Save Sweep Settings", use_container_width=True, disabled=not sweep_is_valid):
    cfg["experiment"] = experiment
    cfg["sweep"] = sweep
    cfg["ensemble"] = ensemble

    if selected_scenario.get("is_working_config", False):
        save_config(cfg, "configs/default.yaml")
        st.success("Sweep settings saved to configs/default.yaml")
    else:
        update_scenario_config(selected_scenario["path"], config=cfg)
        st.success(f"Sweep settings saved to scenario: {selected_scenario['name']}")

schema_expander()

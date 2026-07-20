from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import analysis.dashboard as dash
from analysis.reporting import build_pdf_report, figure_to_png_bytes as report_figure_to_png_bytes
from simulation.ui_helpers import build_badge, inject_responsive_css


def render_plot_grid(plot_items, *, n_cols: int = 2) -> None:
    """Render matplotlib figures in a compact Streamlit grid."""
    if not plot_items:
        st.info("No plots to display.")
        return

    n_cols = max(1, int(n_cols))
    rows = [plot_items[i : i + n_cols] for i in range(0, len(plot_items), n_cols)]

    for row in rows:
        cols = st.columns(n_cols)
        for idx, item in enumerate(row):
            title, fig = item
            with cols[idx]:
                st.caption(title)
                st.pyplot(fig, use_container_width=True)
                safe_title = "".join(ch if ch.isalnum() or ch in ["_", "-"] else "_" for ch in str(title))[:80]
                st.download_button(
                    "Download PNG",
                    data=dash.figure_to_png_bytes(fig),
                    file_name=f"{safe_title}.png",
                    mime="image/png",
                    use_container_width=True,
                    key=f"download_{safe_title}_{idx}_{id(fig)}",
                )


def render_publication_downloads(
    fig,
    *,
    file_stem: str,
    key_prefix: str,
    report_context=None,
) -> None:
    """Render figure files and an optional full research PDF containing the figure."""
    columns = st.columns(4 if report_context else 3)
    downloads = (
        ("PNG 300 dpi", dash.figure_to_png_bytes(fig, dpi=300), "png", "image/png"),
        ("SVG vector", dash.figure_to_svg_bytes(fig), "svg", "image/svg+xml"),
        ("PDF vector", dash.figure_to_pdf_bytes(fig), "pdf", "application/pdf"),
    )
    for column, (label, payload, extension, mime) in zip(columns, downloads):
        with column:
            st.download_button(
                f"Download {label}",
                data=payload,
                file_name=f"{file_stem}.{extension}",
                mime=mime,
                use_container_width=True,
                key=f"{key_prefix}_{extension}",
            )
    if report_context:
        state_key = f"{key_prefix}_prepared_report_pdf"
        with columns[-1]:
            if st.button(
                "Prepare report PDF",
                use_container_width=True,
                key=f"{key_prefix}_prepare_report_pdf",
            ):
                st.session_state[state_key] = build_pdf_report(
                    summary=report_context["summary"],
                    metadata={
                        **report_context["metadata"],
                        "selected_publication_figure": file_stem,
                    },
                    validation_rows=report_context["validation_rows"],
                    config=report_context["config"],
                    figures=[
                        (
                            f"Selected publication figure: {file_stem.replace('_', ' ')}",
                            report_figure_to_png_bytes(fig, dpi=300),
                        )
                    ],
                )
            if state_key in st.session_state:
                st.download_button(
                    "Download report + figure",
                    data=st.session_state[state_key],
                    file_name=f"{file_stem}_research_report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"{key_prefix}_report_pdf",
                )


def select_publication_pathway_variables(
    available_variables,
    *,
    key_prefix: str,
):
    """Select exactly one variable per growth-pathway panel."""
    groups = dash.growth_pathway_variable_groups(list(available_variables))
    selected = {}
    columns = st.columns(2)
    for idx, (group, variables) in enumerate(groups.items()):
        preferred = dash.DEFAULT_PATHWAY_VARIABLES.get(group)
        default = preferred if preferred in variables else variables[0]
        with columns[idx % 2]:
            selected[group] = st.selectbox(
                group,
                variables,
                index=variables.index(default),
                key=f"{key_prefix}_{idx}",
                format_func=dash.publication_variable_label,
            )
    return selected


REQUIRED_DASHBOARD_FUNCTIONS = [
    "discover_results",
    "load_result",
    "flatten_summary",
    "format_metric_value",
    "available_numeric_columns",
    "recommended_column_groups",
    "comparison_base_variables",
    "plot_time_series",
    "plot_selected_variable",
    "plot_control_vs_seeding",
    "plot_difference",
    "plot_sweep_ranking",
    "sweep_base_variables",
    "sweep_execution_status_table",
    "build_sweep_overlay_dataframe",
    "plot_sweep_overlay",
    "compute_overlay_spread",
    "sweep_param_columns",
    "plot_sweep_heatmap",
    "build_overlay_legend_table",
    "recommended_sweep_variables",
    "short_sweep_param_name",
    "format_sweep_param_value",
    "filter_sweep_dataframe",
    "result_is_readable",
    "likely_injection_time_sweep",
    "sweep_case_metrics_table",
    "varying_sweep_parameters",
    "plot_parameter_sensitivity",
    "add_kappa_koehler_collapse_variable",
    "plot_collapse_variable_response",
    "plot_response_surface_heatmap",
    "build_sweep_overlay_dataframe_relative_time",
    "plot_ensemble_uncertainty",
    "ensemble_available_bases",
    "figure_to_png_bytes",
    "figure_to_svg_bytes",
    "figure_to_pdf_bytes",
    "apply_publication_style",
    "growth_pathway_all_variables",
    "growth_pathway_variable_groups",
    "diagnostic_provenance_dataframe",
    "diagnostic_provenance_summary_counts",
    "result_file_roles_dataframe",
    "load_sweep_case_publication_data",
    "sweep_case_display_label",
    "matched_collision_cases",
    "plot_growth_pathway_four_panel",
    "plot_ensemble_uncertainty_panel",
    "plot_one_factor_sensitivity_panel",
    "plot_collision_off_on_panel",
    "plot_wet_radius_spectrum",
    "plot_threshold_robustness",
    "plot_wet_radius_spectrum_difference",
    "plot_threshold_robustness_difference",
    "spectrum_checkpoint_times",
    "threshold_robustness_metrics",
    "plot_water_budget",
    "plot_numerical_convergence",
    "plot_spectrum_transition",
    "convergence_metrics",
    "publication_parameter_label",
    "publication_variable_label",
    "comparison_seeding_intervals",
]

missing = [name for name in REQUIRED_DASHBOARD_FUNCTIONS if not hasattr(dash, name)]
if missing:
    st.error("Dashboard module is incomplete. Replace `analysis/dashboard.py` with the latest version.")
    st.code("\n".join(missing))
    st.info("If you already replaced the file, fully stop Streamlit and run it again. Old modules can remain in memory until restart.")
    st.stop()


RESULTS_UI_BUILD_ID = "transition-cadence-quality-20260720"

inject_responsive_css()
st.title("07. Results Dashboard")
st.caption("Simulation output, case-wise time-series comparison, summary metrics, and diagnostics.")
build_badge("Results page build", RESULTS_UI_BUILD_ID)
build_badge("Dashboard module build", getattr(dash, "DASHBOARD_BUILD_ID", "unknown"))

result_dir = Path("results")
entries = dash.discover_results(result_dir)

if not entries:
    st.info("No result files found. Run an experiment first.")
    st.stop()

show_incomplete = st.toggle(
    "Show incomplete / in-progress results",
    value=False,
    help="Turn on only when you want to inspect a run that is still being written.",
)
if not show_incomplete:
    entries = [entry for entry in entries if dash.result_is_readable(entry)]

if not entries:
    st.warning("No completed readable result files found yet. Wait until the run finishes or enable incomplete results.")
    st.stop()

st.info("If the build badge below does not change after update, stop Streamlit completely (`Ctrl+C`) and run `streamlit run app.py` again.")

selected_entry = st.selectbox(
    "Select result",
    entries,
    format_func=lambda entry: entry.label,
)

loaded = dash.load_result(selected_entry)
df = loaded["timeseries"]

if df.empty:
    st.warning(
        "This result directory exists, but its primary CSV is empty or still being written. "
        "Wait for the run to finish, then refresh Results Dashboard."
    )
    with st.expander("Detected files"):
        st.write(selected_entry.path)
    st.stop()
ensemble_df = loaded.get("ensemble", pd.DataFrame())
member_summary_df = loaded.get("member_summary", pd.DataFrame())
sweep_df = loaded.get("sweep", pd.DataFrame())
comparison_df = loaded.get("comparison", pd.DataFrame())
control_df = loaded.get("control", pd.DataFrame())
seeding_df = loaded.get("seeding", pd.DataFrame())
wet_radius_spectrum_df = loaded.get("wet_radius_spectrum", pd.DataFrame())
threshold_robustness_df = loaded.get("threshold_robustness", pd.DataFrame())
control_spectrum_df = loaded.get("control_wet_radius_spectrum", pd.DataFrame())
seeding_spectrum_df = loaded.get("seeding_wet_radius_spectrum", pd.DataFrame())
control_robustness_df = loaded.get("control_threshold_robustness", pd.DataFrame())
seeding_robustness_df = loaded.get("seeding_threshold_robustness", pd.DataFrame())
wet_radius_spectrum_comparison_df = loaded.get("wet_radius_spectrum_comparison", pd.DataFrame())
threshold_robustness_comparison_df = loaded.get("threshold_robustness_comparison", pd.DataFrame())
water_budget_df = loaded.get("water_budget", pd.DataFrame())
control_water_budget_df = loaded.get("control_water_budget", pd.DataFrame())
seeding_water_budget_df = loaded.get("seeding_water_budget", pd.DataFrame())
water_budget_comparison_df = loaded.get("water_budget_comparison", pd.DataFrame())
numerical_convergence_df = loaded.get("numerical_convergence", pd.DataFrame())
paired_seed_metrics_df = loaded.get("paired_seed_metrics", pd.DataFrame())
spectrum_transition_df = loaded.get("spectrum_transition", pd.DataFrame())
spectrum_transition_robustness_df = loaded.get(
    "spectrum_transition_onset_robustness", pd.DataFrame()
)
ensemble_aggregation_diagnostics = loaded.get("ensemble_aggregation_diagnostics", {})
ensemble_benchmark = loaded.get("ensemble_benchmark", {})
ensemble_memory_checkpoints = loaded.get("ensemble_memory_checkpoints", {})
summary = loaded["summary"]
metadata = loaded["metadata"]
config = loaded["config"]
validation = loaded["validation"]
files = loaded["files"]
diagnostic_provenance_rows = loaded.get("diagnostic_provenance", [])
report_markdown = loaded.get("report_markdown", "")
report_html = loaded.get("report_html", "")
report_pdf = loaded.get("report_pdf", b"")
result_compatibility = loaded.get("result_compatibility", {})

is_ensemble = selected_entry.result_type == "ensemble"
is_sweep = selected_entry.result_type == "parameter_sweep"
is_comparison = selected_entry.result_type == "comparison"

flat_summary_for_notice = dash.flatten_summary(summary)
is_placeholder = any(
    flat_summary_for_notice.get(key) is True
    for key in [
        "adapter_summary.is_placeholder",
        "comparison.control.adapter_summary.is_placeholder",
        "comparison.seeding.adapter_summary.is_placeholder",
    ]
)

st.subheader("Run Overview")
st.caption(f"Result folder name: `{selected_entry.path.name}`")

overview_cols = st.columns(6)
overview_cols[0].metric("Rows", f"{len(df)}")
overview_cols[1].metric(
    "End time",
    dash.format_metric_value(float(df["time_s"].iloc[-1])) + " s" if "time_s" in df.columns and len(df) else "NA",
)
overview_cols[2].metric(
    "Adapter",
    metadata.get("adapter_name", summary.get("adapter_name", metadata.get("source", "unknown"))),
)
overview_cols[3].metric(
    "Type",
    selected_entry.result_type,
)
overview_cols[4].metric(
    "Scenario",
    config.get("experiment", {}).get("scenario_slug", config.get("experiment", {}).get("name", "-")),
)
overview_cols[5].metric(
    "Result schema",
    result_compatibility.get("result_schema_version", "unknown"),
)

if is_ensemble:
    st.write(f"Ensemble run directory: `{selected_entry.path}`")
elif is_sweep:
    st.write(f"Sweep run directory: `{selected_entry.path}`")
elif is_comparison:
    st.write(f"Comparison run directory: `{selected_entry.path}`")
else:
    if "seeding_active" in df.columns:
        active_steps = int(df["seeding_active"].fillna(0).sum())
        st.caption(f"Seeding active steps: {active_steps}")
    if selected_entry.is_run_directory:
        st.write(f"Run directory: `{selected_entry.path}`")
    else:
        st.write(f"Legacy CSV: `{selected_entry.path}`")

if is_placeholder:
    st.warning(
        "This result was generated by `placeholder_warm_cloud`. "
        "The curves are synthetic workflow-test signals, not physically meaningful PySDM output. "
        "Use `simulation.adapter = pysdm_parcel` for real PySDM results."
    )

st.divider()

if is_ensemble:
    tab_dashboard, tab_growth, tab_publication, tab_ensemble, tab_tables, tab_files, tab_config = st.tabs(
        ["Dashboard", "Growth Pathway Diagnostics", "Publication Plots", "Ensemble Statistics", "Tables", "Files & Metadata", "Config / Validation"]
    )
    tab_exper2 = tab_growth
    tab_comparison = None
    tab_spectrum = None
    tab_water_budget = None
    tab_convergence = None
    tab_timeseries = None
    tab_ranking = None
elif is_sweep:
    tab_dashboard, tab_growth, tab_publication, tab_convergence, tab_timeseries, tab_ranking, tab_files, tab_config = st.tabs(
        ["Dashboard", "Growth Pathway Diagnostics", "Publication Plots", "Numerical Convergence", "Sweep Time Series", "Sweep Ranking Table", "Files & Metadata", "Config / Validation"]
    )
    tab_exper2 = tab_growth
    tab_comparison = None
    tab_spectrum = None
    tab_water_budget = None
    tab_tables = tab_ranking
elif is_comparison:
    tab_dashboard, tab_exper2, tab_publication, tab_spectrum, tab_water_budget, tab_comparison, tab_tables, tab_files, tab_config = st.tabs(
        ["Dashboard", "Growth Pathway Diagnostics", "Publication Plots", "Wet-radius Spectrum", "Water Budget", "Control vs Seeding", "Tables", "Files & Metadata", "Config / Validation"]
    )
    tab_convergence = None
else:
    tab_dashboard, tab_spectrum, tab_water_budget, tab_tables, tab_files, tab_config = st.tabs(
        ["Dashboard", "Wet-radius Spectrum", "Water Budget", "Timeseries Table", "Files & Metadata", "Config / Validation"]
    )
    tab_comparison = None
    tab_exper2 = None
    tab_timeseries = None
    tab_ranking = None
    tab_publication = None
    tab_convergence = None

with tab_dashboard:
    st.subheader("Summary Metrics")

    flat_summary = dash.flatten_summary(summary)

    if is_ensemble:
        preferred_metrics = [
            "ensemble.n_success",
            "ensemble.n_failed",
            "ensemble.metrics.rain_water_mixing_ratio_diff_final_mean",
            "ensemble.metrics.rain_water_mixing_ratio_diff_integral_mean",
        ]
    elif is_sweep:
        preferred_metrics = [
            "n_cases",
            "best_case.ranking_value",
            "best_case.case_name",
            "ranking_metric",
            "n_cases",
        ]
    elif is_comparison:
        preferred_metrics = [
            "comparison.efficiency.seeding_efficiency_score",
            "comparison.efficiency.accumulated_rain_enhancement",
            "comparison.efficiency.accumulated_rain_enhancement_percent",
            "comparison.efficiency.rain_enhancement_final",
            "comparison.efficiency.rain_enhancement_final_percent",
            "comparison.efficiency.rain_onset_time_shift_s",
            "comparison.efficiency.cloud_to_rain_conversion_delta",
        ]
    else:
        preferred_metrics = [
            "metrics.final_rain_water_mixing_ratio",
            "metrics.max_rain_water_mixing_ratio",
            "metrics.accumulated_rain_water_proxy",
            "metrics.cloud_to_rain_conversion_proxy",
            "metrics.rain_onset_time_s",
            "metrics.final_effective_radius_um",
            "metrics.final_droplet_number_concentration_cm3",
            "metrics.final_superdroplet_count",
            "metrics.n_seeding_active_steps",
        ]

    metric_items = [(key, flat_summary.get(key)) for key in preferred_metrics if key in flat_summary]

    if metric_items:
        metric_cols = st.columns(min(4, len(metric_items)))
        for idx, (key, value) in enumerate(metric_items):
            metric_cols[idx % len(metric_cols)].metric(
                key.split(".")[-1],
                dash.format_metric_value(value),
            )
    else:
        st.info("No summary metrics available yet.")

    st.divider()

    display_left, display_right = st.columns([2, 1])
    with display_left:
        matrix_cols = st.slider("Plot grid columns", min_value=1, max_value=3, value=2)
        max_plots = st.slider("Maximum plots in dashboard", min_value=2, max_value=8, value=4)
    with display_right:
        st.info("Matrix plot legends are shown as separate tables so the plot area stays large.")
        show_case_tables = st.toggle("Show case legend tables", value=True)

    if is_ensemble:
        st.subheader("Ensemble Uncertainty Matrix")
        st.caption("Ensemble statistics are shown as mean ± std by default. Use the Ensemble Statistics tab for detailed median/IQR plots.")

        bases = dash.ensemble_available_bases(ensemble_df)
        default_bases = [base for base in [
            "rain_water_mixing_ratio_diff",
            "cloud_water_mixing_ratio_diff",
            "all_activated_water_mixing_ratio_diff",
            "water_vapour_mixing_ratio_diff",
            "supersaturation_percent_diff",
            "effective_radius_all_um_diff",
        ] if base in bases]
        selected_bases = st.multiselect(
            "Variables",
            bases,
            default=default_bases[: min(4, len(default_bases))] if default_bases else bases[: min(4, len(bases))],
            key="ensemble_dashboard_vars",
        )
        ensemble_items = [
            (base, dash.plot_ensemble_uncertainty(ensemble_df, base_variable=base, mode="mean_std"))
            for base in selected_bases[:max_plots]
        ]
        render_plot_grid(ensemble_items, n_cols=matrix_cols)

    elif is_sweep:
        st.subheader("Sweep Case Time-Series Matrix")
        st.caption(
            "각 sweep case의 시간 변화 곡선을 한 그래프에 겹쳐서 보여줍니다. "
            "기본값은 diff = seeding - control이며, 인공강우 효과 판단은 이 차이 곡선에서 시작합니다."
        )

        sweep_execution_df = dash.sweep_execution_status_table(selected_entry.path, sweep_df)
        failed_case_count = int(
            (sweep_execution_df["execution_status"] == "failed").sum()
        ) if not sweep_execution_df.empty else 0
        partial_case_count = int(
            (sweep_execution_df["execution_status"] == "partial").sum()
        ) if not sweep_execution_df.empty else 0
        successful_case_count = int(
            (sweep_execution_df["execution_status"] == "success").sum()
        ) if not sweep_execution_df.empty else 0
        failed_member_count = int(sweep_execution_df["member_failed"].sum()) if not sweep_execution_df.empty else 0
        successful_member_count = int(sweep_execution_df["member_success"].sum()) if not sweep_execution_df.empty else 0
        all_sweep_cases_failed = bool(
            len(sweep_execution_df) > 0 and failed_case_count == len(sweep_execution_df)
        )

        if failed_case_count or partial_case_count:
            message = (
                f"실행 상태: 성공 {successful_case_count}, 부분 성공 {partial_case_count}, "
                f"실패 {failed_case_count} case. Ensemble member는 성공 {successful_member_count}, "
                f"실패 {failed_member_count}개입니다."
            )
            if all_sweep_cases_failed:
                st.error(message + " 파라미터 필터는 정상이나 분석할 시계열이 생성되지 않았습니다.")
            else:
                st.warning(message + " 실패 case는 민감도·순위·수렴성 분석에서 제외해야 합니다.")
            with st.expander("Execution failures / partial cases", expanded=all_sweep_cases_failed):
                problem_rows = sweep_execution_df[
                    sweep_execution_df["execution_status"].isin(["failed", "partial"])
                ]
                st.dataframe(problem_rows, use_container_width=True, hide_index=True)

        curve_source = st.selectbox(
            "Case output source",
            ["comparison", "seeding", "control"],
            index=0,
            help="comparison은 각 case의 comparison.csv를 사용합니다. seeding/control은 각 case 내부의 timeseries.csv를 사용합니다.",
        )

        comparison_mode = "diff"
        if curve_source == "comparison":
            comparison_mode = st.selectbox(
                "Comparison curve",
                ["diff", "seeding", "control", "relative_change_percent"],
                index=0,
                help="diff는 seeding - control입니다.",
            )

        available_vars = dash.sweep_base_variables(selected_entry.path, sweep_df, curve_source=curve_source)

        sweep_df = sweep_df.copy()
        param_filter_cols = dash.sweep_param_columns(sweep_df)

        with st.expander("Case filter / focus view", expanded=True):
            st.caption(
                "Plot은 모든 case를 자동으로 다 보여주지 않습니다. "
                "예를 들어 dry radius가 3.0 µm까지 있어도 max cases가 작거나 앞쪽 case만 선택되면 안 보일 수 있습니다. "
                "여기서 원하는 parameter 값만 남겨서 비교하세요."
            )

            filters = {}
            filter_cols = st.columns(min(3, max(len(param_filter_cols), 1)))
            for idx, param_col in enumerate(param_filter_cols):
                unique_values = list(sweep_df[param_col].dropna().unique())
                if len(unique_values) == 0 or len(unique_values) > 30:
                    continue

                try:
                    unique_values = sorted(unique_values)
                except Exception:
                    pass

                with filter_cols[idx % len(filter_cols)]:
                    selected_values = st.multiselect(
                        dash.short_sweep_param_name(param_col),
                        unique_values,
                        default=unique_values,
                        format_func=lambda value, col=param_col: dash.format_sweep_param_value(col, value),
                        key=f"dashboard_filter_{param_col}",
                    )
                filters[param_col] = selected_values

            filtered_sweep_df = dash.filter_sweep_dataframe(sweep_df, filters)
            st.metric("Selected cases", len(filtered_sweep_df))
            if len(filtered_sweep_df) == 0:
                st.warning("No cases selected. Adjust filters.")

        st.subheader("Fixed-Parameter Sensitivity Summary")
        st.caption(
            "선택된(필터링된) case들을 final/max/integral 등 scalar 값으로 요약해서 하나의 parameter에 대한 "
            "순수한 sensitivity curve를 봅니다. 다른 parameter가 함께 변하고 있으면 곡선이 여러 효과가 섞인 "
            "것일 수 있으므로, 위 Case filter에서 나머지 parameter를 고정한 뒤 사용하세요."
        )

        param_cols_for_summary = dash.sweep_param_columns(sweep_df)

        if available_vars and param_cols_for_summary and len(filtered_sweep_df) > 0:
            default_var_candidates = [
                "rain_water_mixing_ratio",
                "cloud_water_mixing_ratio",
                "all_activated_water_mixing_ratio",
                "supersaturation_percent",
            ]
            default_var = next((var for var in default_var_candidates if var in available_vars), available_vars[0])

            s_col1, s_col2, s_col3 = st.columns(3)
            with s_col1:
                sensitivity_variable = st.selectbox(
                    "Response variable",
                    available_vars,
                    index=available_vars.index(default_var),
                    key="sensitivity_variable",
                )
            with s_col2:
                sensitivity_parameter = st.selectbox(
                    "Parameter (x-axis)",
                    param_cols_for_summary,
                    index=0,
                    key="sensitivity_parameter",
                    format_func=dash.short_sweep_param_name,
                )
            with s_col3:
                sensitivity_statistic = st.selectbox(
                    "Statistic",
                    ["final", "max", "integral", "peak_time_s", "min"],
                    index=1,
                    key="sensitivity_statistic",
                )

            sensitivity_metrics_df = dash.sweep_case_metrics_table(
                selected_entry.path,
                filtered_sweep_df,
                variable=sensitivity_variable,
                curve_source="comparison",
                comparison_mode="diff",
            )

            other_param_cols = [c for c in param_cols_for_summary if c != sensitivity_parameter]
            still_varying = dash.varying_sweep_parameters(sensitivity_metrics_df, other_param_cols)

            if still_varying:
                st.warning(
                    "이 필터링된 case 집합에서 아직 함께 변하고 있는 parameter가 있습니다: "
                    + ", ".join(dash.short_sweep_param_name(c) for c in still_varying)
                    + ". 아래 곡선은 여러 parameter의 효과가 섞여 있을 수 있습니다. "
                    "위 Case filter에서 해당 parameter들을 하나의 값으로 고정하는 것을 권장합니다."
                )
            else:
                st.success(f"다른 parameter는 모두 고정되어 있습니다. {dash.short_sweep_param_name(sensitivity_parameter)}에 대한 순수한 sensitivity curve입니다.")

            sensitivity_fig = dash.plot_parameter_sensitivity(
                sensitivity_metrics_df,
                x_parameter=sensitivity_parameter,
                statistic=sensitivity_statistic,
                variable=sensitivity_variable,
            )
            st.pyplot(sensitivity_fig, use_container_width=True)
            st.download_button(
                "Download sensitivity plot",
                data=dash.figure_to_png_bytes(sensitivity_fig),
                file_name=f"sensitivity_{sensitivity_variable}_{sensitivity_statistic}_vs_{dash.short_sweep_param_name(sensitivity_parameter)}.png",
                mime="image/png",
                use_container_width=True,
                key="sensitivity_download",
            )
            with st.expander("Sensitivity summary table", expanded=False):
                st.dataframe(sensitivity_metrics_df, use_container_width=True)

            if dash.likely_injection_time_sweep(sweep_df):
                st.info("Injection-time sweep detected. Use `Sweep Time Series` → `Time axis = relative to injection start` to compare post-seeding responses more clearly.")
        else:
            if all_sweep_cases_failed:
                st.error(
                    "Sensitivity summary를 만들 수 없습니다. 모든 case 실행이 실패해 response time series가 없습니다. "
                    "위 Execution failures 표에서 member 오류를 먼저 확인하세요."
                )
            else:
                st.info("No sensitivity summary available. Select at least one case and make sure the sweep varies at least one parameter.")

        st.subheader("Warm-Seeding Collapse Variable Analysis")
        st.caption(
            r"κ-Köhler의 κ·dry-volume 항에서 유도한 $\log_{10}[\kappa(r_{dry}/1m)^3]$ 좌표에 "
            "서로 다른 dry radius–κ 조합이 실제로 수렴하는지 검정합니다. 수렴을 전제하지 않으며, "
            "주입 시각·collision 등 다른 조건은 위 Case filter로 고정해야 합니다."
        )

        collapse_default_var_candidates = [
            "rain_water_mixing_ratio",
            "cloud_water_mixing_ratio",
            "all_activated_water_mixing_ratio",
            "supersaturation_percent",
        ]
        collapse_default_variable = next(
            (var for var in collapse_default_var_candidates if var in available_vars),
            available_vars[0] if available_vars else None,
        )
        collapse_variable_name = (
            st.selectbox(
                "Collapse-analysis response variable",
                available_vars,
                index=available_vars.index(collapse_default_variable),
                key="collapse_response_variable",
            )
            if collapse_default_variable
            else None
        )

        collapse_metrics_df = (
            dash.add_kappa_koehler_collapse_variable(
                dash.sweep_case_metrics_table(
                    selected_entry.path,
                    filtered_sweep_df,
                    variable=collapse_variable_name,
                    curve_source="comparison",
                    comparison_mode="diff",
                )
            )
            if collapse_variable_name
            else pd.DataFrame()
        )

        if not collapse_metrics_df.empty and dash.COLLAPSE_VARIABLE_COLUMN in collapse_metrics_df.columns:
            collapse_confounders = dash.varying_sweep_parameters(
                collapse_metrics_df,
                [
                    col
                    for col in param_cols_for_summary
                    if col not in {"param.seeding.dry_radius", "param.seeding.kappa"}
                ],
            )
            if collapse_confounders:
                st.warning(
                    "Collapse 좌표 외에 함께 변하는 조건이 남아 있습니다: "
                    + ", ".join(dash.short_sweep_param_name(col) for col in collapse_confounders)
                    + ". 색상 하나로 구분할 수는 있지만, 정량적 collapse 판정 전에는 모두 고정하거나 facet으로 분리하세요."
                )

            c_col1, c_col2 = st.columns(2)
            with c_col1:
                collapse_statistic = st.selectbox(
                    "Statistic",
                    ["final", "max", "integral", "peak_time_s", "min"],
                    index=1,
                    key="collapse_statistic",
                )
            with c_col2:
                color_by_options = ["(none)"] + collapse_confounders
                color_by_choice = st.selectbox(
                    "Color by",
                    color_by_options,
                    index=0,
                    key="collapse_color_by",
                    format_func=lambda c: "(none)" if c == "(none)" else dash.short_sweep_param_name(c),
                )

            collapse_fig = dash.plot_collapse_variable_response(
                collapse_metrics_df,
                statistic=collapse_statistic,
                variable=collapse_variable_name,
                color_by=None if color_by_choice == "(none)" else color_by_choice,
            )
            st.pyplot(collapse_fig, use_container_width=True)
            st.download_button(
                "Download collapse-variable plot",
                data=dash.figure_to_png_bytes(collapse_fig),
                file_name=f"collapse_variable_{collapse_variable_name}_{collapse_statistic}.png",
                mime="image/png",
                use_container_width=True,
                key="collapse_download",
            )

            if "param.seeding.dry_radius" in param_cols_for_summary and "param.seeding.kappa" in param_cols_for_summary:
                with st.expander("2D response surface (dry_radius x kappa)", expanded=False):
                    st.caption("동일한 데이터를 dry_radius × κ 격자 위에 표시합니다. 다른 parameter가 변하면 평균으로 섞지 않고, 먼저 Case filter에서 고정하라는 안내를 표시합니다.")
                    surface_fig = dash.plot_response_surface_heatmap(
                        collapse_metrics_df,
                        x_param="param.seeding.dry_radius",
                        y_param="param.seeding.kappa",
                        statistic=collapse_statistic,
                        variable=collapse_variable_name,
                    )
                    st.pyplot(surface_fig, use_container_width=True)
        else:
            has_collapse_parameters = {
                "param.seeding.dry_radius",
                "param.seeding.kappa",
            }.issubset(param_cols_for_summary)
            if all_sweep_cases_failed and has_collapse_parameters:
                st.error(
                    "dry_radius와 kappa는 함께 변화했지만 모든 case가 실패해 collapse response를 계산할 수 없습니다."
                )
            elif has_collapse_parameters:
                st.info(
                    "dry_radius와 kappa는 함께 변화했지만 선택된 case에서 사용할 response time series가 없습니다."
                )
            else:
                st.info("이 sweep은 dry_radius와 kappa를 함께 변화시키지 않아 collapse variable을 계산할 수 없습니다.")

        default_vars = [
            var
            for var in [
                "water_vapour_mixing_ratio",
                "supersaturation_percent",
                "cloud_water_mixing_ratio",
                "rain_water_mixing_ratio",
                "all_activated_water_mixing_ratio",
                "effective_radius_all_um",
            ]
            if var in available_vars
        ]

        recommended_vars = dash.recommended_sweep_variables(available_vars)
        selected_vars = st.multiselect(
            "Variables to compare across cases",
            available_vars,
            default=recommended_vars[: min(4, len(recommended_vars))],
        )

        if not available_vars:
            if all_sweep_cases_failed:
                st.error(
                    "No plottable variables: 모든 sweep case 실행이 실패했습니다. "
                    "이 결과는 파라미터 조합만 보존하며 물리·민감도 해석에는 사용할 수 없습니다."
                )
            else:
                st.warning(
                    "No plottable variables found for this sweep result. "
                    "The selected cases are missing readable comparison/ensemble time-series files."
                )

        case_count_for_plot = max(len(filtered_sweep_df), 1)
        max_cases = st.slider(
            "Maximum cases per plot",
            min_value=1,
            max_value=max(case_count_for_plot, 1),
            value=min(24, case_count_for_plot),
            help="If this is smaller than selected cases, cases are sampled across the full parameter range instead of only taking the first cases.",
        )

        shaded_intervals = dash.sweep_seeding_intervals(selected_entry.path, sweep_df)
        if shaded_intervals:
            st.caption("Shaded time window indicates seeding-active period.")

        plot_items = []
        spread_rows = []
        for var in selected_vars[:max_plots]:
            overlay_df = dash.build_sweep_overlay_dataframe(
                selected_entry.path,
                filtered_sweep_df,
                variable=var,
                curve_source=curve_source,
                comparison_mode=comparison_mode,
                max_cases=max_cases,
            )
            label = f"{curve_source}:{comparison_mode}" if curve_source == "comparison" else curve_source
            plot_items.append((var, dash.plot_sweep_overlay(overlay_df, variable=var, curve_label=label, show_legend=False, shaded_intervals=shaded_intervals)))
            spread_rows.append({"variable": var, **dash.compute_overlay_spread(overlay_df)})

        render_plot_grid(plot_items, n_cols=matrix_cols)

        if show_case_tables and selected_vars:
            first_var = selected_vars[0]
            first_overlay_df = dash.build_sweep_overlay_dataframe(
                selected_entry.path,
                filtered_sweep_df,
                variable=first_var,
                curve_source=curve_source,
                comparison_mode=comparison_mode,
                max_cases=max_cases,
            )
            with st.expander("Case legend table", expanded=False):
                st.caption("Legend is separated from plots to avoid shrinking the plotting area.")
                st.dataframe(dash.style_curve_legend_table(dash.build_overlay_legend_table(first_overlay_df)), use_container_width=True)

        if spread_rows:
            st.subheader("Parameter Sensitivity Check")
            spread_df = pd.DataFrame(spread_rows)
            st.dataframe(spread_df, use_container_width=True)
            if bool(spread_df["curves_overlap"].all()):
                st.error(
                    "All selected sweep curves overlap within numerical tolerance. "
                    "This means the current sweep is not producing visible parameter sensitivity. "
                    "Check whether this is a placeholder result, whether the adapter actually uses the swept parameters, "
                    "and whether you are plotting `diff = seeding - control` rather than only absolute seeding curves."
                )
            elif bool(spread_df["curves_overlap"].any()):
                st.warning(
                    "Some variables show no spread across sweep cases. "
                    "Those variables may not be sensitive to the selected parameters under the current setup."
                )

        with st.expander("Show sweep ranking as secondary information"):
            if sweep_df.empty:
                st.info("No sweep summary table found.")
            else:
                numeric_cols = [col for col in sweep_df.columns if pd.api.types.is_numeric_dtype(sweep_df[col])]
                if numeric_cols:
                    metric = st.selectbox(
                        "Ranking metric column",
                        numeric_cols,
                        index=numeric_cols.index("ranking_value") if "ranking_value" in numeric_cols else 0,
                    )
                    top_n = st.slider(
                        "Top N ranking",
                        min_value=3,
                        max_value=min(20, len(sweep_df)),
                        value=min(10, len(sweep_df)),
                    )
                    st.pyplot(dash.plot_sweep_ranking(sweep_df, metric=metric, top_n=top_n), use_container_width=True)

    elif is_comparison:
        st.subheader("Comparison Plot Matrix")
        st.caption("Control and seeding curves are shown side by side.")

        bases = dash.comparison_base_variables(comparison_df)
        default_order = [
            "rain_water_mixing_ratio",
            "cloud_water_mixing_ratio",
            "supersaturation",
            "effective_radius_um",
            "droplet_number_concentration_cm3",
            "superdroplet_count",
        ]
        selected_bases = [base for base in default_order if base in bases]
        selected_bases += [base for base in bases if base not in selected_bases]
        selected_bases = selected_bases[:max_plots]

        plot_items = []
        for base in selected_bases:
            plot_items.append((f"Control vs Seeding · {base}", dash.plot_control_vs_seeding(comparison_df, base)))

        render_plot_grid(plot_items, n_cols=matrix_cols)

        st.subheader("Difference Plot Matrix")
        st.caption("Difference is computed as seeding minus control.")
        diff_items = []
        for base in selected_bases:
            diff_items.append((f"Seeding - Control · {base}", dash.plot_difference(comparison_df, base)))

        render_plot_grid(diff_items, n_cols=matrix_cols)

    else:
        st.subheader("Diagnostic Plot Matrix")

        if "time_s" not in df.columns:
            st.warning("This result does not contain `time_s`, so time-series plots cannot be displayed.")
        else:
            groups = dash.recommended_column_groups(df)
            plot_items = []

            for group_name, columns in groups.items():
                fig = dash.plot_time_series(
                    df,
                    columns,
                    title=group_name,
                    ylabel=group_name,
                    show_seeding_window=True,
                )
                plot_items.append((group_name, fig))

            render_plot_grid(plot_items[:max_plots], n_cols=matrix_cols)

        st.divider()

        st.subheader("Custom Variable Plot")

        numeric_cols = dash.available_numeric_columns(df)
        if "time_s" in df.columns and numeric_cols:
            selected_columns = st.multiselect(
                "Variables",
                numeric_cols,
                default=numeric_cols[: min(4, len(numeric_cols))],
            )
            custom_items = [
                (column, dash.plot_selected_variable(df, column))
                for column in selected_columns[:max_plots]
            ]
            render_plot_grid(custom_items, n_cols=matrix_cols)
        else:
            st.info("No numeric variables available for custom plotting.")



if is_ensemble:
    with tab_ensemble:
        st.subheader("Ensemble Statistics")
        st.caption("Mean ± std and median + IQR uncertainty views for repeated random seeds.")

        ensemble_runtime = summary.get("ensemble", {})
        execution_backend = str(
            ensemble_runtime.get(
                "execution_backend",
                metadata.get("ensemble_execution_backend", "in_process"),
            )
        )
        member_process_resources = ensemble_runtime.get(
            "member_process_resources",
            metadata.get("member_process_resources", {}),
        )
        runtime_cols = st.columns(4)
        runtime_cols[0].metric("Member backend", execution_backend)
        runtime_cols[1].metric(
            "Successful members",
            ensemble_runtime.get("n_success", metadata.get("n_success", 0)),
        )
        runtime_cols[2].metric(
            "Failed members",
            ensemble_runtime.get("n_failed", metadata.get("n_failed", 0)),
        )
        runtime_cols[3].metric(
            "Max isolated child RSS",
            (
                f"{(member_process_resources.get('max_child_process_tree_rss_bytes') or 0) / (1024.0**2):.1f} MiB"
                if execution_backend == "subprocess"
                else "N/A"
            ),
        )
        if execution_backend == "subprocess":
            st.caption(str(member_process_resources.get("scope", "")))

        if ensemble_aggregation_diagnostics:
            st.markdown("#### Streaming aggregation benchmark")
            benchmark_cols = st.columns(6)
            benchmark_cols[0].metric(
                "Member input",
                f"{ensemble_aggregation_diagnostics.get('total_input_bytes', 0) / 1.0e6:.3f} MB",
            )
            benchmark_cols[1].metric(
                "Aggregation time",
                f"{ensemble_aggregation_diagnostics.get('elapsed_seconds', 0.0):.3f} s",
            )
            benchmark_cols[2].metric(
                "Traced peak",
                f"{ensemble_aggregation_diagnostics.get('python_peak_traced_bytes', 0) / 1.0e6:.3f} MB",
            )
            benchmark_cols[3].metric(
                "Process RSS peak",
                f"{(ensemble_aggregation_diagnostics.get('process_rss', {}).get('peak_rss_bytes') or 0) / 1.0e6:.3f} MB",
            )
            benchmark_cols[4].metric(
                "Variables",
                ensemble_aggregation_diagnostics.get("aggregated_variables", 0),
            )
            benchmark_cols[5].metric(
                "CSV scan rate",
                f"{(ensemble_aggregation_diagnostics.get('estimated_scan_mib_per_second') or 0):.2f} MiB/s",
            )
            phase_cols = st.columns(3)
            phase_cols[0].metric(
                "Schema discovery",
                f"{ensemble_aggregation_diagnostics.get('schema_discovery_seconds', 0.0):.3f} s",
            )
            phase_cols[1].metric(
                "Column streaming",
                f"{ensemble_aggregation_diagnostics.get('column_streaming_seconds', 0.0):.3f} s",
            )
            phase_cols[2].metric(
                "Estimated CSV scanned",
                f"{ensemble_aggregation_diagnostics.get('estimated_csv_bytes_scanned', 0) / (1024.0**2):.2f} MiB",
            )
            st.caption(str(ensemble_aggregation_diagnostics.get("memory_scope", "")))
            process_rss_scope = ensemble_aggregation_diagnostics.get("process_rss", {}).get("scope", "")
            if process_rss_scope:
                st.caption(str(process_rss_scope))

        if ensemble_benchmark:
            st.markdown("#### End-to-end PySDM benchmark")
            full_rss = ensemble_benchmark.get("full_process_rss", {})
            process_tree_rss = full_rss.get("process_tree", {})
            benchmark_backend = ensemble_benchmark.get(
                "member_execution_backend", "in_process"
            )
            full_cols = st.columns(5)
            full_cols[0].metric(
                "Profile",
                ensemble_benchmark.get("profile", "unknown"),
            )
            full_cols[1].metric(
                "Backend",
                benchmark_backend,
            )
            full_cols[2].metric(
                "Full wall time",
                f"{ensemble_benchmark.get('full_run_elapsed_seconds', 0.0):.1f} s",
            )
            full_cols[3].metric(
                "Process-tree peak RSS",
                f"{(process_tree_rss.get('peak_rss_bytes') or full_rss.get('peak_rss_bytes') or 0) / (1024.0**2):.1f} MiB",
            )
            full_cols[4].metric(
                "Parent peak increase",
                f"{(full_rss.get('peak_rss_increase_bytes') or 0) / (1024.0**2):.1f} MiB",
            )
            memory_checkpoints = ensemble_benchmark.get(
                "memory_checkpoint_summary", {}
            )
            if memory_checkpoints:
                retained_cols = st.columns(4)
                retained_cols[0].metric(
                    "Member boundaries",
                    memory_checkpoints.get("n_member_boundaries", 0),
                )
                retained_cols[1].metric(
                    "First-to-last member RSS",
                    f"{(memory_checkpoints.get('member_boundary_rss_increase_bytes') or 0) / (1024.0**2):.1f} MiB",
                )
                retained_cols[2].metric(
                    "RSS slope/member",
                    f"{(memory_checkpoints.get('member_boundary_rss_slope_bytes_per_member') or 0) / (1024.0**2):.2f} MiB",
                )
                retained_cols[3].metric(
                    "GC event RSS reclaimed (sum)",
                    f"{(memory_checkpoints.get('gc_reclaimed_rss_total_bytes') or 0) / (1024.0**2):.1f} MiB",
                )
                st.caption(str(memory_checkpoints.get("scope", "")))
                gc_enabled = bool(
                    ensemble_benchmark.get("collect_garbage_between_members", False)
                )
                st.caption(
                    f"Member-boundary explicit GC: {'ON' if gc_enabled else 'OFF'}. "
                    "The reclaimed value is the sum of per-member RSS drops, not net "
                    "end-of-run memory saved."
                )
            checkpoint_rows = ensemble_memory_checkpoints.get("checkpoints", [])
            if checkpoint_rows:
                with st.expander("Show member/stage memory checkpoints"):
                    checkpoint_df = pd.DataFrame(checkpoint_rows)
                    visible_columns = [
                        column
                        for column in (
                            "elapsed_seconds",
                            "stage",
                            "current",
                            "total",
                            "rss_bytes",
                            "uss_bytes",
                            "gc_tracked_objects",
                            "num_threads",
                            "matplotlib_open_figures",
                        )
                        if column in checkpoint_df.columns
                    ]
                    st.dataframe(
                        checkpoint_df[visible_columns],
                        use_container_width=True,
                        hide_index=True,
                    )
                    member_boundaries = checkpoint_df[
                        checkpoint_df.get("stage", pd.Series(dtype=str)).eq(
                            "ensemble_member_complete"
                        )
                    ].copy()
                    if not member_boundaries.empty:
                        member_boundaries["rss_mib"] = (
                            pd.to_numeric(member_boundaries["rss_bytes"], errors="coerce")
                            / (1024.0**2)
                        )
                        member_boundaries["uss_mib"] = (
                            pd.to_numeric(member_boundaries["uss_bytes"], errors="coerce")
                            / (1024.0**2)
                        )
                        st.line_chart(
                            member_boundaries.set_index("current")[["rss_mib", "uss_mib"]]
                        )
            st.caption(str(ensemble_benchmark.get("interpretation", "")))

        bases = dash.ensemble_available_bases(ensemble_df)
        if not bases:
            st.info("No ensemble variables found.")
        else:
            selected_base = st.selectbox("Variable", bases, key="ensemble_stats_base")
            mode = st.radio(
                "Uncertainty view",
                ["mean_std", "median_iqr"],
                horizontal=True,
                index=0,
                format_func=lambda value: "Mean ± std" if value == "mean_std" else "Median + IQR",
            )

            fig = dash.plot_ensemble_uncertainty(
                ensemble_df,
                base_variable=selected_base,
                mode=mode,
                figsize=(11.5, 5.8),
            )
            st.pyplot(fig, use_container_width=True)
            st.download_button(
                "Download this plot as PNG",
                data=dash.figure_to_png_bytes(fig),
                file_name=f"ensemble_{selected_base}_{mode}.png",
                mime="image/png",
                use_container_width=True,
            )

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Member Summary")
                st.dataframe(member_summary_df, use_container_width=True)
            with col2:
                st.subheader("Ensemble Summary JSON")
                st.json(summary.get("ensemble", {}))


if tab_publication is not None:
    with tab_publication:
        st.subheader("Publication-style Diagnostic Plots")
        build_badge("Publication plots build", getattr(dash, "PUBLICATION_PLOTS_BUILD_ID", "unknown"))
        publication_style = st.selectbox(
            "Figure style preset",
            list(dash.PUBLICATION_STYLE_PRESETS),
            index=list(dash.PUBLICATION_STYLE_PRESETS).index("journal_double_column"),
            format_func=lambda value: value.replace("_", " ").title(),
            key="publication_style_preset",
        )
        st.caption(
            "PNG 300 dpi, SVG, PDF로 내보낼 수 있는 패널입니다. 축 단위와 diagnostic provenance를 그림 안에 기록하며, "
            "sweep 패널은 다른 조건을 고정하거나 정확히 짝지은 case만 비교합니다."
        )
        publication_report_context = {
            "summary": summary,
            "metadata": metadata,
            "validation_rows": validation if isinstance(validation, list) else [],
            "config": config,
        }

        provenance_counts = dash.diagnostic_provenance_summary_counts(diagnostic_provenance_rows)
        if provenance_counts.get("proxy", 0) > 0:
            st.warning(
                f"이 결과에는 proxy diagnostic {provenance_counts['proxy']}개가 포함되어 있습니다. "
                "그림의 [P] 표시는 근사값이며, 정량적 논문 결론 전에 native extraction을 확인하세요."
            )
        elif diagnostic_provenance_rows:
            st.success("이 결과의 Growth Pathway diagnostic에는 proxy가 없습니다. [N]은 native, [D]는 직접 계산값입니다.")
        elif not diagnostic_provenance_rows:
            st.info("이 결과에는 provenance 파일이 없어 그림에 [?]로 표시됩니다. 최신 코드로 다시 실행하면 기록됩니다.")

        if is_comparison:
            st.markdown("#### Growth Pathway Four-panel")
            publication_bases = dash.comparison_base_variables(comparison_df)
            selected_pathway_variables = select_publication_pathway_variables(
                publication_bases,
                key_prefix="publication_comparison_pathway",
            )
            publication_mode = st.radio(
                "Curve mode",
                ["diff", "control_vs_seeding"],
                horizontal=True,
                key="publication_comparison_mode",
                format_func=lambda value: "Seeding − control" if value == "diff" else "Control vs seeding",
            )
            if selected_pathway_variables:
                publication_fig = dash.plot_growth_pathway_four_panel(
                    comparison_df,
                    variables_by_group=selected_pathway_variables,
                    mode=publication_mode,
                    provenance_rows=diagnostic_provenance_rows,
                    seeding_intervals=dash.comparison_seeding_intervals(comparison_df),
                )
                dash.apply_publication_style(publication_fig, publication_style)
                st.pyplot(publication_fig, use_container_width=True)
                render_publication_downloads(
                    publication_fig,
                    file_stem=f"growth_pathway_four_panel_{publication_mode}",
                    key_prefix="publication_comparison_download",
                    report_context=publication_report_context,
                )
            else:
                st.info("Four-panel에 사용할 Growth Pathway 변수가 없습니다.")

        elif is_ensemble:
            st.markdown("#### Ensemble Uncertainty Four-panel")
            ensemble_publication_bases = dash.ensemble_available_bases(ensemble_df)
            preferred_ensemble_bases = [
                value
                for value in [
                    "supersaturation_percent_diff",
                    "all_activated_water_mixing_ratio_diff",
                    "all_activated_concentration_diff",
                    "effective_radius_all_um_diff",
                    "rain_water_mixing_ratio_diff",
                ]
                if value in ensemble_publication_bases
            ]
            selected_ensemble_bases = st.multiselect(
                "Variables (maximum 4)",
                ensemble_publication_bases,
                default=(preferred_ensemble_bases or ensemble_publication_bases)[:4],
                key="publication_ensemble_variables",
                format_func=dash.publication_variable_label,
            )
            if len(selected_ensemble_bases) > 4:
                st.warning("앞의 4개 변수만 패널에 표시됩니다.")
            ensemble_publication_mode = st.radio(
                "Uncertainty summary",
                ["mean_std", "median_iqr"],
                horizontal=True,
                key="publication_ensemble_mode",
                format_func=lambda value: "Mean ± std" if value == "mean_std" else "Median + IQR",
            )
            if selected_ensemble_bases:
                ensemble_publication_fig = dash.plot_ensemble_uncertainty_panel(
                    ensemble_df,
                    base_variables=selected_ensemble_bases[:4],
                    mode=ensemble_publication_mode,
                    provenance_rows=diagnostic_provenance_rows,
                )
                dash.apply_publication_style(ensemble_publication_fig, publication_style)
                st.pyplot(ensemble_publication_fig, use_container_width=True)
                render_publication_downloads(
                    ensemble_publication_fig,
                    file_stem=f"ensemble_four_panel_{ensemble_publication_mode}",
                    key_prefix="publication_ensemble_download",
                    report_context=publication_report_context,
                )
            else:
                st.info("Ensemble publication panel에 사용할 변수가 없습니다.")

        elif is_sweep:
            publication_available_variables = dash.sweep_base_variables(
                selected_entry.path,
                sweep_df,
                curve_source="comparison",
            )

            st.markdown("#### Selected-case Growth Pathway Four-panel")
            st.caption("Sweep case 하나를 선택해 조건이 섞이지 않은 control–seeding 성장 경로를 그립니다.")
            publication_case_df = filtered_sweep_df if len(filtered_sweep_df) else sweep_df
            if len(publication_case_df):
                publication_case_index = st.selectbox(
                    "Sweep case",
                    list(publication_case_df.index),
                    key="publication_sweep_case",
                    format_func=lambda index: dash.sweep_case_display_label(publication_case_df.loc[index]),
                )
                publication_case_kind, publication_case_data = dash.load_sweep_case_publication_data(
                    selected_entry.path,
                    publication_case_df.loc[publication_case_index],
                )
                if publication_case_kind == "comparison":
                    case_bases = dash.comparison_base_variables(publication_case_data)
                    selected_case_pathway_variables = select_publication_pathway_variables(
                        case_bases,
                        key_prefix="publication_sweep_case_pathway",
                    )
                    case_mode = st.radio(
                        "Selected-case curve mode",
                        ["diff", "control_vs_seeding"],
                        horizontal=True,
                        key="publication_sweep_case_mode",
                        format_func=lambda value: "Seeding − control" if value == "diff" else "Control vs seeding",
                    )
                    if selected_case_pathway_variables:
                        case_publication_fig = dash.plot_growth_pathway_four_panel(
                            publication_case_data,
                            variables_by_group=selected_case_pathway_variables,
                            mode=case_mode,
                            provenance_rows=diagnostic_provenance_rows,
                            seeding_intervals=dash.comparison_seeding_intervals(publication_case_data),
                        )
                        dash.apply_publication_style(case_publication_fig, publication_style)
                        st.pyplot(case_publication_fig, use_container_width=True)
                        render_publication_downloads(
                            case_publication_fig,
                            file_stem=f"sweep_case_growth_pathway_{case_mode}",
                            key_prefix="publication_sweep_case_download",
                            report_context=publication_report_context,
                        )
                elif publication_case_kind == "ensemble":
                    case_ensemble_bases = dash.ensemble_available_bases(publication_case_data)
                    selected_case_ensemble_bases = st.multiselect(
                        "Selected-case ensemble variables (maximum 4)",
                        case_ensemble_bases,
                        default=case_ensemble_bases[:4],
                        key="publication_sweep_case_ensemble_variables",
                        format_func=dash.publication_variable_label,
                    )
                    case_ensemble_mode = st.radio(
                        "Selected-case uncertainty summary",
                        ["mean_std", "median_iqr"],
                        horizontal=True,
                        key="publication_sweep_case_ensemble_mode",
                        format_func=lambda value: "Mean ± std" if value == "mean_std" else "Median + IQR",
                    )
                    if selected_case_ensemble_bases:
                        case_publication_fig = dash.plot_ensemble_uncertainty_panel(
                            publication_case_data,
                            base_variables=selected_case_ensemble_bases[:4],
                            mode=case_ensemble_mode,
                            provenance_rows=diagnostic_provenance_rows,
                        )
                        dash.apply_publication_style(case_publication_fig, publication_style)
                        st.pyplot(case_publication_fig, use_container_width=True)
                        render_publication_downloads(
                            case_publication_fig,
                            file_stem=f"sweep_case_ensemble_{case_ensemble_mode}",
                            key_prefix="publication_sweep_case_ensemble_download",
                            report_context=publication_report_context,
                        )
                else:
                    st.info("선택한 sweep case에서 comparison.csv 또는 ensemble_statistics.csv를 찾지 못했습니다.")

            st.divider()
            st.markdown("#### Dry radius / κ / Injection-time Separated Panel")
            st.caption(
                "One-factor-at-a-time(OFAT) 방식입니다. 각 패널의 x축 parameter만 변화시키고, "
                "나머지는 아래 기준 조건으로 고정합니다."
            )
            if publication_available_variables:
                ofat_default_candidates = [
                    "rain_water_mixing_ratio_diff",
                    "rain_water_mixing_ratio",
                    "all_activated_water_mixing_ratio_diff",
                    "all_activated_water_mixing_ratio",
                    "supersaturation_percent_diff",
                    "supersaturation_percent",
                ]
                ofat_default_variable = next(
                    (var for var in ofat_default_candidates if var in publication_available_variables),
                    publication_available_variables[0],
                )
                ofat_col1, ofat_col2 = st.columns(2)
                with ofat_col1:
                    ofat_variable = st.selectbox(
                        "Response variable",
                        publication_available_variables,
                        index=publication_available_variables.index(ofat_default_variable),
                        key="publication_ofat_variable",
                        format_func=dash.publication_variable_label,
                    )
                with ofat_col2:
                    ofat_statistic = st.selectbox(
                        "Response statistic",
                        ["final", "max", "integral", "peak_time_s", "min"],
                        index=1,
                        key="publication_ofat_statistic",
                    )

                ofat_metrics_df = dash.sweep_case_metrics_table(
                    selected_entry.path,
                    sweep_df,
                    variable=ofat_variable,
                    curve_source="comparison",
                    comparison_mode="diff",
                )
                ofat_parameter_columns = dash.sweep_param_columns(ofat_metrics_df)
                preferred_ofat_parameters = [
                    parameter
                    for parameter in [
                        "param.seeding.dry_radius",
                        "param.seeding.kappa",
                        "param.seeding.injection_start",
                    ]
                    if parameter in ofat_parameter_columns
                ]
                selected_ofat_parameters = st.multiselect(
                    "Panel x-axes (maximum 3)",
                    ofat_parameter_columns,
                    default=preferred_ofat_parameters[:3],
                    key="publication_ofat_parameters",
                    format_func=dash.publication_parameter_label,
                )
                if len(selected_ofat_parameters) > 3:
                    st.warning("앞의 3개 parameter만 패널에 표시됩니다.")

                reference_values = {}
                if ofat_parameter_columns:
                    st.caption("Reference condition (각 패널에서 해당 x축 parameter 값은 무시됩니다)")
                    reference_columns = st.columns(min(3, len(ofat_parameter_columns)))
                    for idx, parameter in enumerate(ofat_parameter_columns):
                        values = list(ofat_metrics_df[parameter].dropna().unique())
                        try:
                            values = sorted(values)
                        except Exception:
                            pass
                        if not values:
                            continue
                        default_index = 0 if parameter.endswith("collision") else len(values) // 2
                        with reference_columns[idx % len(reference_columns)]:
                            reference_values[parameter] = st.selectbox(
                                dash.publication_parameter_label(parameter),
                                values,
                                index=default_index,
                                key=f"publication_ofat_reference_{parameter}",
                                format_func=lambda value, col=parameter: dash.format_sweep_param_value(col, value),
                            )

                if selected_ofat_parameters:
                    display_ofat_variable = (
                        ofat_variable
                        if ofat_variable.endswith("_diff")
                        else f"{ofat_variable}_diff"
                    )
                    ofat_fig = dash.plot_one_factor_sensitivity_panel(
                        ofat_metrics_df,
                        parameters=selected_ofat_parameters[:3],
                        all_parameter_columns=ofat_parameter_columns,
                        reference_values=reference_values,
                        statistic=ofat_statistic,
                        variable=display_ofat_variable,
                        provenance_rows=diagnostic_provenance_rows,
                    )
                    dash.apply_publication_style(ofat_fig, publication_style)
                    st.pyplot(ofat_fig, use_container_width=True)
                    render_publication_downloads(
                        ofat_fig,
                        file_stem=f"ofat_sensitivity_{ofat_variable}_{ofat_statistic}",
                        key_prefix="publication_ofat_download",
                        report_context=publication_report_context,
                    )
            else:
                st.info("OFAT panel에 사용할 sweep 변수가 없습니다.")

            st.divider()
            st.markdown("#### Collision OFF / ON Panel")
            collision_column = "param.microphysics.collision"
            if collision_column in sweep_df.columns and sweep_df[collision_column].nunique(dropna=True) >= 2:
                st.caption("동일한 나머지 parameter 조합에 OFF와 ON case가 모두 존재할 때만 짝으로 포함합니다.")
                matched_collision_df, collision_pairing_df = dash.matched_collision_cases(sweep_df)
                matched_pair_count = int(collision_pairing_df["matched"].sum()) if not collision_pairing_df.empty else 0
                st.metric("Matched OFF/ON conditions", matched_pair_count)
                with st.expander("Collision pairing audit", expanded=False):
                    st.dataframe(collision_pairing_df, use_container_width=True, hide_index=True)

                if matched_pair_count and publication_available_variables:
                    collision_variable = st.selectbox(
                        "Collision response variable",
                        publication_available_variables,
                        key="publication_collision_variable",
                        format_func=dash.publication_variable_label,
                    )
                    collision_max_pairs = st.slider(
                        "Maximum matched conditions",
                        min_value=1,
                        max_value=max(matched_pair_count, 1),
                        value=min(6, matched_pair_count),
                        key="publication_collision_max_pairs",
                    )
                    collision_text = matched_collision_df[collision_column].astype(str).str.strip().str.lower()
                    collision_off_df = matched_collision_df[collision_text.isin(["false", "0", "off", "no"])]
                    collision_on_df = matched_collision_df[collision_text.isin(["true", "1", "on", "yes"])]
                    collision_off_overlay = dash.build_sweep_overlay_dataframe(
                        selected_entry.path,
                        collision_off_df,
                        variable=collision_variable,
                        curve_source="comparison",
                        comparison_mode="diff",
                        max_cases=collision_max_pairs,
                    )
                    collision_on_overlay = dash.build_sweep_overlay_dataframe(
                        selected_entry.path,
                        collision_on_df,
                        variable=collision_variable,
                        curve_source="comparison",
                        comparison_mode="diff",
                        max_cases=collision_max_pairs,
                    )
                    display_collision_variable = (
                        collision_variable
                        if collision_variable.endswith("_diff")
                        else f"{collision_variable}_diff"
                    )
                    collision_fig = dash.plot_collision_off_on_panel(
                        collision_off_overlay,
                        collision_on_overlay,
                        variable=display_collision_variable,
                        provenance_rows=diagnostic_provenance_rows,
                        shaded_intervals=dash.sweep_seeding_intervals(selected_entry.path, matched_collision_df),
                    )
                    dash.apply_publication_style(collision_fig, publication_style)
                    st.pyplot(collision_fig, use_container_width=True)
                    render_publication_downloads(
                        collision_fig,
                        file_stem=f"collision_off_on_{collision_variable}",
                        key_prefix="publication_collision_download",
                        report_context=publication_report_context,
                    )
                else:
                    st.info("동일 조건으로 짝지을 수 있는 collision OFF/ON case가 없습니다.")
            else:
                st.info("이 sweep에는 collision OFF와 ON이 모두 포함되어 있지 않습니다.")


if (is_sweep or is_comparison) and tab_exper2 is not None:
    with tab_exper2:
        st.subheader("Seeding Growth Pathway Diagnostic View")
        st.caption(
            "성장 경로 분석 구조에 맞춰 thermodynamic → water mass → number concentration → size response를 봅니다. "
            "기본 비교는 diff = seeding - control입니다."
        )

        if is_sweep:
            curve_source = "comparison"
            comparison_mode = st.radio(
                "Comparison mode",
                ["diff", "seeding", "control", "relative_change_percent"],
                horizontal=True,
                index=0,
                key="exper2_sweep_mode",
            )

            available_vars = dash.sweep_base_variables(selected_entry.path, sweep_df, curve_source=curve_source)
            groups = dash.growth_pathway_variable_groups(available_vars)

            if not groups:
                st.warning("No growth-pathway diagnostic variables are available in this sweep result. This is usually an old result. Rerun the scenario after the latest update.")
            else:
                selected_group = st.selectbox("Growth pathway diagnostic group", list(groups.keys()))
                selected_vars = groups[selected_group]

                max_cases_exper2 = st.slider(
                    "Maximum cases to overlay",
                    min_value=2,
                    max_value=min(30, len(sweep_df)) if len(sweep_df) >= 2 else 2,
                    value=min(12, len(sweep_df)) if len(sweep_df) >= 2 else 2,
                    key="exper2_max_cases",
                )
                matrix_cols_exper2 = st.slider(
                    "Plot columns",
                    min_value=1,
                    max_value=3,
                    value=2,
                    key="exper2_matrix_cols",
                )

                shaded_intervals = dash.sweep_seeding_intervals(selected_entry.path, sweep_df)
                if shaded_intervals:
                    st.caption("Shaded time window indicates seeding-active period.")

                plot_items = []
                spread_rows = []
                legend_df = pd.DataFrame()
                for var in selected_vars:
                    overlay_df = dash.build_sweep_overlay_dataframe(
                        selected_entry.path,
                        sweep_df,
                        variable=var,
                        curve_source=curve_source,
                        comparison_mode=comparison_mode,
                        max_cases=max_cases_exper2,
                    )
                    if legend_df.empty:
                        legend_df = dash.build_overlay_legend_table(overlay_df)
                    plot_items.append(
                        (
                            var,
                            dash.plot_sweep_overlay(
                                overlay_df,
                                variable=var,
                                curve_label=f"comparison:{comparison_mode}",
                                show_legend=False,
                                shaded_intervals=shaded_intervals,
                            ),
                        )
                    )
                    spread_rows.append({"variable": var, **dash.compute_overlay_spread(overlay_df)})

                render_plot_grid(plot_items, n_cols=matrix_cols_exper2)

                with st.expander("Case legend table", expanded=False):
                    st.dataframe(dash.style_curve_legend_table(legend_df), use_container_width=True)

                st.subheader("Growth Pathway Sensitivity Check")
                st.dataframe(pd.DataFrame(spread_rows), use_container_width=True)

        elif is_comparison:
            groups = dash.growth_pathway_variable_groups(dash.comparison_base_variables(comparison_df))

            if not groups:
                st.info("No growth-pathway diagnostic variables are available in this comparison result.")
            else:
                selected_group = st.selectbox("Growth pathway diagnostic group", list(groups.keys()))
                selected_vars = groups[selected_group]
                mode = st.radio(
                    "Curve mode",
                    ["diff", "control_vs_seeding"],
                    horizontal=True,
                    index=0,
                    key="exper2_comparison_mode",
                )

                plot_items = []
                if mode == "diff":
                    for var in selected_vars:
                        plot_items.append((f"Δ {var}", dash.plot_difference(comparison_df, var)))
                else:
                    for var in selected_vars:
                        plot_items.append((var, dash.plot_control_vs_seeding(comparison_df, var)))

                render_plot_grid(plot_items, n_cols=2)


if is_sweep:
    with tab_timeseries:
        st.subheader("Sweep Time-Series Comparison")
        st.caption(
            "여기서 sweep의 핵심 결과를 봅니다. "
            "dry radius, κ 등 case 조건이 다른 곡선들을 같은 변수 기준으로 겹쳐서 비교합니다. "
            "상세 탭에서는 legend를 항상 표시해 case를 구분하기 쉽게 했습니다."
        )

        curve_source = st.radio(
            "Output source",
            ["comparison", "seeding", "control"],
            horizontal=True,
            key="sweep_ts_source",
        )

        comparison_mode = "diff"
        if curve_source == "comparison":
            comparison_mode = st.radio(
                "Comparison mode",
                ["diff", "seeding", "control", "relative_change_percent"],
                horizontal=True,
                key="sweep_ts_mode",
            )

        filtered_sweep_df = sweep_df.copy()
        with st.expander("Case filter / focus view", expanded=True):
            param_filter_cols = dash.sweep_param_columns(sweep_df)
            filters = {}
            filter_cols = st.columns(min(3, max(len(param_filter_cols), 1)))
            for idx, param_col in enumerate(param_filter_cols):
                unique_values = list(sweep_df[param_col].dropna().unique())
                if len(unique_values) == 0 or len(unique_values) > 30:
                    continue
                try:
                    unique_values = sorted(unique_values)
                except Exception:
                    pass
                with filter_cols[idx % len(filter_cols)]:
                    selected_values = st.multiselect(
                        dash.short_sweep_param_name(param_col),
                        unique_values,
                        default=unique_values,
                        format_func=lambda value, col=param_col: dash.format_sweep_param_value(col, value),
                        key=f"sweep_ts_filter_{param_col}",
                    )
                filters[param_col] = selected_values

            filtered_sweep_df = dash.filter_sweep_dataframe(sweep_df, filters)
            st.metric("Selected cases", len(filtered_sweep_df))

        available_vars = dash.sweep_base_variables(selected_entry.path, filtered_sweep_df, curve_source=curve_source)
        selected_var = st.selectbox("Variable", available_vars, key="sweep_ts_variable") if available_vars else None

        case_count_for_detail = max(len(filtered_sweep_df), 1)
        max_cases = st.slider(
            "Maximum cases to overlay",
            min_value=1,
            max_value=case_count_for_detail,
            value=min(24, case_count_for_detail),
            key="sweep_ts_max_cases",
            help="If smaller than selected cases, cases are sampled across the full selected parameter range.",
        )

        time_axis_mode = st.selectbox(
            "Time axis",
            ["absolute time", "relative to injection start"],
            index=1 if dash.likely_injection_time_sweep(sweep_df) else 0,
            key="sweep_time_axis_mode",
        )

        if selected_var:
            if time_axis_mode == "relative to injection start" and "param.seeding.injection_start" in sweep_df.columns:
                overlay_df = dash.build_sweep_overlay_dataframe_relative_time(
                    selected_entry.path,
                    filtered_sweep_df,
                    variable=selected_var,
                    curve_source=curve_source,
                    comparison_mode=comparison_mode,
                    time_reference_param="param.seeding.injection_start",
                    max_cases=max_cases,
                )
            else:
                overlay_df = dash.build_sweep_overlay_dataframe(
                    selected_entry.path,
                    filtered_sweep_df,
                    variable=selected_var,
                    curve_source=curve_source,
                    comparison_mode=comparison_mode,
                    max_cases=max_cases,
                )

            detailed_shaded_intervals = dash.sweep_seeding_intervals(selected_entry.path, sweep_df)
            if detailed_shaded_intervals:
                st.caption("Shaded time window indicates seeding-active period.")

            curve_label = f"{curve_source}:{comparison_mode}" if curve_source == "comparison" else curve_source
            st.pyplot(
                dash.plot_sweep_overlay(
                    overlay_df,
                    variable=selected_var,
                    curve_label=curve_label,
                    figsize=(11.5, 5.6),
                    show_legend=False,
                    shaded_intervals=detailed_shaded_intervals,
                ),
                use_container_width=True,
            )

            legend_tab, summary_tab, data_tab = st.tabs(["Case legend", "Curve value summary", "Overlay data"])
            with legend_tab:
                st.dataframe(dash.style_curve_legend_table(dash.build_overlay_legend_table(overlay_df)), use_container_width=True)
            with summary_tab:
                st.dataframe(dash.build_curve_value_summary(overlay_df), use_container_width=True)
            with data_tab:
                st.dataframe(overlay_df, use_container_width=True)

            spread = dash.compute_overlay_spread(overlay_df)
            st.subheader("Parameter Sensitivity Check")
            metric_cols = st.columns(4)
            metric_cols[0].metric("Cases", dash.format_metric_value(spread.get("n_cases")))
            metric_cols[1].metric("Max spread", dash.format_metric_value(spread.get("max_abs_spread")))
            metric_cols[2].metric("Mean spread", dash.format_metric_value(spread.get("mean_abs_spread")))
            metric_cols[3].metric("Final spread", dash.format_metric_value(spread.get("final_abs_spread")))

            if spread.get("curves_overlap"):
                st.error(
                    "The selected variable curves overlap across sweep cases. "
                    "For a real sensitivity experiment, this is a red flag: either the selected parameter is not affecting the model output, "
                    "the adapter is not receiving the changed config values, or the selected diagnostic is not sensitive enough."
                )
        else:
            st.info("No available variables found in sweep cases.")

if is_comparison and tab_comparison is not None:
    with tab_comparison:
        st.subheader("Control vs Seeding Analysis")

        bases = dash.comparison_base_variables(comparison_df)
        if not bases:
            st.info("No comparable variables found.")
        else:
            selected_base = st.selectbox("Variable for detailed comparison", bases, key="detailed_comparison_base")

            col1, col2 = st.columns(2)
            with col1:
                st.pyplot(dash.plot_control_vs_seeding(comparison_df, selected_base), use_container_width=True)
            with col2:
                st.pyplot(dash.plot_difference(comparison_df, selected_base), use_container_width=True)

            rel_col = f"{selected_base}_relative_change_percent"
            if rel_col in comparison_df.columns:
                st.subheader("Relative Change")
                st.line_chart(comparison_df.set_index("time_s")[rel_col])

        st.subheader("Efficiency Metrics JSON")
        st.json(summary.get("comparison", {}).get("efficiency", {}))

        st.subheader("Comparison Summary JSON")
        st.json(summary.get("comparison", summary))

if tab_spectrum is not None:
    with tab_spectrum:
        st.subheader("Wet-radius Spectrum and Threshold Robustness")
        st.caption(
            "Native PySDM checkpoint spectra show how particle number and liquid volume move "
            "through unactivated, cloud, and rain wet-radius ranges. Threshold robustness "
            "repartitions the same spectrum, so it does not require another model run."
        )

        if is_comparison:
            spectrum_frames = [control_spectrum_df, seeding_spectrum_df]
            robustness_frames = [control_robustness_df, seeding_robustness_df]
        else:
            spectrum_frames = [wet_radius_spectrum_df]
            robustness_frames = [threshold_robustness_df]

        checkpoint_times = dash.spectrum_checkpoint_times(*spectrum_frames)
        if not checkpoint_times:
            st.info(
                "No wet-radius spectrum is stored in this result. Run a new `pysdm_parcel` "
                "experiment with spectrum diagnostics enabled."
            )
        else:
            selected_checkpoint = st.selectbox(
                "Checkpoint time [s]",
                checkpoint_times,
                index=len(checkpoint_times) - 1,
                format_func=lambda value: f"{value:g} s",
                key="wet_radius_checkpoint",
            )
            spectrum_value_options = [
                column
                for column in dash.SPECTRUM_VALUE_LABELS
                if any(column in frame.columns for frame in spectrum_frames)
            ]
            selected_spectrum_value = st.selectbox(
                "Spectrum quantity",
                spectrum_value_options,
                format_func=lambda value: dash.SPECTRUM_VALUE_LABELS[value],
                key="wet_radius_value",
            )

            if is_comparison:
                plot_col1, plot_col2 = st.columns(2)
                with plot_col1:
                    st.pyplot(
                        dash.plot_wet_radius_spectrum(
                            control_spectrum_df,
                            checkpoint_time_s=selected_checkpoint,
                            value_column=selected_spectrum_value,
                            title="Control wet-radius spectrum",
                        ),
                        use_container_width=True,
                    )
                with plot_col2:
                    st.pyplot(
                        dash.plot_wet_radius_spectrum(
                            seeding_spectrum_df,
                            checkpoint_time_s=selected_checkpoint,
                            value_column=selected_spectrum_value,
                            title="Seeding wet-radius spectrum",
                        ),
                        use_container_width=True,
                    )
                if not wet_radius_spectrum_comparison_df.empty:
                    st.pyplot(
                        dash.plot_wet_radius_spectrum_difference(
                            wet_radius_spectrum_comparison_df,
                            checkpoint_time_s=selected_checkpoint,
                            value_column=selected_spectrum_value,
                        ),
                        use_container_width=True,
                    )
            else:
                st.pyplot(
                    dash.plot_wet_radius_spectrum(
                        wet_radius_spectrum_df,
                        checkpoint_time_s=selected_checkpoint,
                        value_column=selected_spectrum_value,
                    ),
                    use_container_width=True,
                )

            robustness_metric_options = sorted(
                {
                    metric
                    for frame in robustness_frames
                    for metric in dash.threshold_robustness_metrics(frame)
                }
            )
            if robustness_metric_options:
                selected_robustness_metric = st.selectbox(
                    "Robustness metric",
                    robustness_metric_options,
                    index=(
                        robustness_metric_options.index("rain_volume_fraction_of_activated")
                        if "rain_volume_fraction_of_activated" in robustness_metric_options
                        else 0
                    ),
                    format_func=lambda value: dash.ROBUSTNESS_METRIC_LABELS[value],
                    key="threshold_robustness_metric",
                )
                if is_comparison:
                    robust_col1, robust_col2 = st.columns(2)
                    with robust_col1:
                        st.pyplot(
                            dash.plot_threshold_robustness(
                                control_robustness_df,
                                checkpoint_time_s=selected_checkpoint,
                                metric=selected_robustness_metric,
                                title="Control threshold robustness",
                            ),
                            use_container_width=True,
                        )
                    with robust_col2:
                        st.pyplot(
                            dash.plot_threshold_robustness(
                                seeding_robustness_df,
                                checkpoint_time_s=selected_checkpoint,
                                metric=selected_robustness_metric,
                                title="Seeding threshold robustness",
                            ),
                            use_container_width=True,
                        )
                    if not threshold_robustness_comparison_df.empty:
                        st.pyplot(
                            dash.plot_threshold_robustness_difference(
                                threshold_robustness_comparison_df,
                                checkpoint_time_s=selected_checkpoint,
                                metric=selected_robustness_metric,
                            ),
                            use_container_width=True,
                        )
                else:
                    st.pyplot(
                        dash.plot_threshold_robustness(
                            threshold_robustness_df,
                            checkpoint_time_s=selected_checkpoint,
                            metric=selected_robustness_metric,
                        ),
                        use_container_width=True,
                    )

            if is_comparison and not spectrum_transition_df.empty:
                st.divider()
                st.markdown("#### Spectrum-based transition onset")
                transition_summary = (
                    summary.get("comparison", {})
                    .get("research_quality", {})
                    .get("spectrum_transition", {})
                )
                transition_cols = st.columns(4)
                transition_cols[0].metric(
                    "Control onset",
                    dash.format_metric_value(transition_summary.get("control_transition_onset_s"))
                    + " s",
                )
                transition_cols[1].metric(
                    "Seeding onset",
                    dash.format_metric_value(transition_summary.get("seeding_transition_onset_s"))
                    + " s",
                )
                transition_cols[2].metric(
                    "Onset shift",
                    dash.format_metric_value(transition_summary.get("transition_onset_shift_s"))
                    + " s",
                )
                transition_cols[3].metric(
                    "Interpretation status",
                    str(transition_summary.get("interpretation_status", "unresolved")),
                )
                st.caption(str(transition_summary.get("onset_method", "")))
                cadence_status = transition_summary.get(
                    "checkpoint_cadence_status", "unresolved"
                )
                maximum_interval = dash.format_metric_value(
                    transition_summary.get("maximum_checkpoint_interval_s")
                )
                if cadence_status == "coarse_relative_to_literature":
                    st.warning(
                        f"Checkpoint cadence: {cadence_status} (maximum {maximum_interval} s). "
                        "Treat interpolated onset timing as cadence-limited."
                    )
                else:
                    st.caption(
                        f"Checkpoint cadence: {cadence_status} (maximum {maximum_interval} s)."
                    )
                st.pyplot(
                    dash.plot_spectrum_transition(spectrum_transition_df),
                    use_container_width=True,
                )
                with st.expander("Transition onset threshold audit"):
                    st.dataframe(
                        spectrum_transition_robustness_df,
                        use_container_width=True,
                    )

            with st.expander("Checkpoint data tables"):
                if is_comparison:
                    st.markdown("**Control spectrum**")
                    st.dataframe(control_spectrum_df, use_container_width=True)
                    st.markdown("**Seeding spectrum**")
                    st.dataframe(seeding_spectrum_df, use_container_width=True)
                    st.markdown("**Control threshold robustness**")
                    st.dataframe(control_robustness_df, use_container_width=True)
                    st.markdown("**Seeding threshold robustness**")
                    st.dataframe(seeding_robustness_df, use_container_width=True)
                    st.markdown("**Seeding − control spectrum**")
                    st.dataframe(wet_radius_spectrum_comparison_df, use_container_width=True)
                    st.markdown("**Seeding − control threshold robustness**")
                    st.dataframe(threshold_robustness_comparison_df, use_container_width=True)
                else:
                    st.dataframe(wet_radius_spectrum_df, use_container_width=True)
                    st.dataframe(threshold_robustness_df, use_container_width=True)

if tab_water_budget is not None:
    with tab_water_budget:
        st.subheader("Total-water Budget Quality Gate")
        st.caption(
            "The injection interval is an external water source and is excluded from the "
            "closed-system drift verdict. Control and post-injection intervals are evaluated "
            "against their own references."
        )

        if is_comparison:
            quality_summary = summary.get("comparison", {}).get("research_quality", {}).get(
                "water_budget", {}
            )
            budget_columns = st.columns(2)
            for column, case_name, budget_frame in zip(
                budget_columns,
                ("control", "seeding"),
                (control_water_budget_df, seeding_water_budget_df),
            ):
                case_summary = quality_summary.get(case_name, {})
                with column:
                    st.markdown(f"#### {case_name.title()}")
                    st.metric("Status", str(case_summary.get("status", "unavailable")).upper())
                    st.metric(
                        "Maximum closed-window drift",
                        dash.format_metric_value(
                            case_summary.get("max_abs_closed_window_relative_drift_percent")
                        )
                        + " %",
                    )
                    st.pyplot(
                        dash.plot_water_budget(
                            budget_frame,
                            title=f"{case_name.title()} total-water budget",
                        ),
                        use_container_width=True,
                    )
            if not water_budget_comparison_df.empty:
                with st.expander("Control–seeding aligned water-budget table"):
                    st.dataframe(water_budget_comparison_df, use_container_width=True)
        else:
            budget_summary = summary.get("adapter_summary", {}).get("water_budget", {})
            if water_budget_df.empty:
                st.info("No native total-water budget is stored for this result.")
            else:
                metrics = st.columns(3)
                metrics[0].metric("Status", str(budget_summary.get("status", "unavailable")).upper())
                metrics[1].metric(
                    "Maximum closed-window drift",
                    dash.format_metric_value(
                        budget_summary.get("max_abs_closed_window_relative_drift_percent")
                    )
                    + " %",
                )
                metrics[2].metric(
                    "Liquid partition residual",
                    dash.format_metric_value(
                        budget_summary.get("max_abs_liquid_partition_residual")
                    ),
                )
                st.pyplot(dash.plot_water_budget(water_budget_df), use_container_width=True)
                st.dataframe(water_budget_df, use_container_width=True)

if tab_convergence is not None:
    with tab_convergence:
        st.subheader("Numerical Convergence Quality Gate")
        st.caption(
            "Each timestep or super-droplet axis is varied one at a time while the other "
            "numerical axes stay at their finest available values. The verdict compares "
            "resolution rank 1 with the rank 0 reference."
        )
        convergence_summary = summary.get("numerical_convergence", {})
        convergence_evidence = summary.get("numerical_convergence_evidence", {})
        if numerical_convergence_df.empty:
            st.info(
                "This sweep does not contain a generated numerical_convergence.csv. Use the "
                "Numerical convergence preset or include timestep/super-droplet parameters."
            )
        else:
            convergence_cols = st.columns(4)
            convergence_cols[0].metric(
                "Status",
                str(convergence_summary.get("status", "unavailable")).upper(),
            )
            convergence_cols[1].metric(
                "Next-finest checks",
                convergence_summary.get("n_next_finest_checks", 0),
            )
            convergence_cols[2].metric(
                "Converged",
                convergence_summary.get("n_converged", 0),
            )
            convergence_cols[3].metric(
                "Maximum error",
                dash.format_metric_value(
                    convergence_summary.get("max_next_finest_relative_difference_percent")
                )
                + " %",
            )
            if convergence_evidence.get("available"):
                st.markdown("#### Empirical tolerance evidence")
                evidence_cols = st.columns(4)
                evidence_cols[0].metric(
                    "5% support",
                    str(convergence_evidence.get("status", "unknown")).replace("_", " ").upper(),
                )
                evidence_cols[1].metric(
                    "Relative checks",
                    convergence_evidence.get("n_relative_evidence_checks", 0),
                )
                evidence_cols[2].metric(
                    "P95 difference",
                    dash.format_metric_value(
                        convergence_evidence.get("p95_relative_difference_percent")
                    ) + " %",
                )
                evidence_cols[3].metric(
                    "Near-zero exclusions",
                    convergence_evidence.get("n_near_zero_reference_checks", 0),
                )
                if convergence_evidence.get("common_random_seed_pairing"):
                    common_seed_cols = st.columns(3)
                    common_seed_cols[0].metric(
                        "Observed common seeds",
                        convergence_evidence.get("n_common_random_seeds", 0),
                    )
                    common_seed_cols[1].metric(
                        "Seed coverage",
                        "COMPLETE"
                        if convergence_evidence.get("common_seed_coverage_complete")
                        else "INCOMPLETE",
                    )
                    common_seed_cols[2].metric(
                        "Pairing rule",
                        "SAME SEED PER RESOLUTION",
                    )
                    seed_rows = []
                    for seed, seed_summary in convergence_evidence.get(
                        "common_seed_evidence", {}
                    ).items():
                        seed_rows.append(
                            {
                                "random_seed": seed,
                                "status": seed_summary.get("status"),
                                "checks": seed_summary.get("n_checks"),
                                "within_tolerance": seed_summary.get(
                                    "n_checks_within_tolerance"
                                ),
                                "median_difference_percent": seed_summary.get(
                                    "median_relative_difference_percent"
                                ),
                                "max_difference_percent": seed_summary.get(
                                    "max_relative_difference_percent"
                                ),
                            }
                        )
                    if seed_rows:
                        st.dataframe(
                            pd.DataFrame(seed_rows),
                            use_container_width=True,
                            hide_index=True,
                        )
                family_evidence = convergence_evidence.get(
                    "metric_family_evidence", {}
                )
                if family_evidence:
                    family_rows = []
                    for family, family_summary in family_evidence.items():
                        family_rows.append(
                            {
                                "metric_family": str(family).replace("_", " "),
                                "status": family_summary.get("status"),
                                "checks": family_summary.get("n_checks"),
                                "within_tolerance": family_summary.get(
                                    "n_checks_within_tolerance"
                                ),
                                "median_difference_percent": family_summary.get(
                                    "median_relative_difference_percent"
                                ),
                                "p95_difference_percent": family_summary.get(
                                    "p95_relative_difference_percent"
                                ),
                                "max_difference_percent": family_summary.get(
                                    "max_relative_difference_percent"
                                ),
                            }
                        )
                    st.dataframe(
                        pd.DataFrame(family_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                if convergence_evidence.get("rain_signal_required"):
                    rain_cols = st.columns(2)
                    rain_cols[0].metric(
                        "Required rain signal",
                        "DETECTED"
                        if convergence_evidence.get("rain_signal_detected")
                        else "MISSING",
                    )
                    rain_cols[1].metric(
                        "Rain signal floor",
                        dash.format_metric_value(
                            convergence_evidence.get("rain_signal_floor_kg_kg")
                        )
                        + " kg/kg",
                    )
                    rain_by_seed = convergence_evidence.get("rain_signal_by_seed", {})
                    if rain_by_seed:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "random_seed": seed,
                                        "rain_signal_detected": row.get("detected"),
                                        **row.get("reference_values_kg_kg", {}),
                                    }
                                    for seed, row in rain_by_seed.items()
                                ]
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
                st.caption(str(convergence_evidence.get("interpretation", "")))
                if not paired_seed_metrics_df.empty:
                    with st.expander("Show paired common-seed scalar source table"):
                        st.caption(
                            "One row per successful resolution case and random seed. "
                            "The convergence table compares only rows with identical seeds."
                        )
                        st.dataframe(
                            paired_seed_metrics_df,
                            use_container_width=True,
                            hide_index=True,
                        )
            available_convergence_metrics = dash.convergence_metrics(numerical_convergence_df)
            selected_convergence_metric = st.selectbox(
                "Response metric",
                available_convergence_metrics,
                key="numerical_convergence_metric",
            )
            st.pyplot(
                dash.plot_numerical_convergence(
                    numerical_convergence_df,
                    metric=selected_convergence_metric,
                ),
                use_container_width=True,
            )
            st.dataframe(numerical_convergence_df, use_container_width=True)

with tab_tables:
    if is_ensemble:
        st.subheader("Ensemble Statistics Table")
        st.dataframe(ensemble_df, use_container_width=True)
        st.download_button(
            "Download ensemble statistics CSV",
            data=ensemble_df.to_csv(index=False).encode("utf-8"),
            file_name="ensemble_statistics.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.subheader("Member Summary")
        st.dataframe(member_summary_df, use_container_width=True)
        st.download_button(
            "Download member summary CSV",
            data=member_summary_df.to_csv(index=False).encode("utf-8"),
            file_name="member_summary.csv",
            mime="text/csv",
            use_container_width=True,
        )
    elif is_sweep:
        st.subheader("Parameter Response Heatmap")
        st.caption("2개 sweep parameter를 축으로 두고, 선택한 metric의 반응을 봅니다. Ranking보다 먼저 parameter-response 구조를 확인하세요.")

        param_cols = dash.sweep_param_columns(sweep_df)
        numeric_cols = [col for col in sweep_df.columns if pd.api.types.is_numeric_dtype(sweep_df[col])]

        preferred_metric_candidates = [
            "comparison.efficiency.accumulated_rain_enhancement",
            "comparison.efficiency.rain_enhancement_final",
            "comparison.efficiency.cloud_to_rain_conversion_delta",
            "comparison.efficiency.seeding_efficiency_score",
            "ranking_value",
        ]
        default_metric = next((col for col in preferred_metric_candidates if col in numeric_cols), numeric_cols[0] if numeric_cols else None)

        if len(param_cols) >= 2 and default_metric is not None:
            hcol1, hcol2, hcol3 = st.columns(3)
            with hcol1:
                x_param = st.selectbox("X parameter", param_cols, index=0)
            with hcol2:
                y_param = st.selectbox("Y parameter", param_cols, index=1 if len(param_cols) > 1 else 0)
            with hcol3:
                metric = st.selectbox(
                    "Metric",
                    numeric_cols,
                    index=numeric_cols.index(default_metric) if default_metric in numeric_cols else 0,
                )

            st.pyplot(
                dash.plot_sweep_heatmap(sweep_df, x_param=x_param, y_param=y_param, metric=metric),
                use_container_width=True,
            )
        else:
            st.info("Heatmap requires at least two numeric sweep parameter columns.")

        st.subheader("Sweep Summary Table")
        st.caption("Ranking은 보조 정보입니다. 각 case의 시간 변화는 `Sweep Time Series` 탭에서 확인하세요.")
        st.dataframe(sweep_df, use_container_width=True)
        st.download_button(
            "Download sweep summary CSV",
            data=sweep_df.to_csv(index=False).encode("utf-8"),
            file_name="sweep_summary.csv",
            mime="text/csv",
            use_container_width=True,
        )
    elif is_comparison:
        st.subheader("Comparison Table")
        st.dataframe(comparison_df, use_container_width=True)

        st.download_button(
            "Download comparison CSV",
            data=comparison_df.to_csv(index=False).encode("utf-8"),
            file_name="comparison.csv",
            mime="text/csv",
            use_container_width=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Control Timeseries")
            st.dataframe(control_df, use_container_width=True)
        with col2:
            st.subheader("Seeding Timeseries")
            st.dataframe(seeding_df, use_container_width=True)
    else:
        st.subheader("Timeseries")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "Download timeseries CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="timeseries.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tab_files:
    st.subheader("Files")

    compatibility_status = str(result_compatibility.get("status", "unknown"))
    compatibility_message = str(result_compatibility.get("message", ""))
    if compatibility_status in {
        "invalid_manifest",
        "future_schema",
        "requires_newer_reader",
        "unsupported_older_schema",
        "missing_primary_data",
    }:
        st.warning(compatibility_message)
    elif compatibility_status == "legacy_without_manifest":
        st.info(compatibility_message)
    elif compatibility_message:
        st.success(compatibility_message)

    for key, path in files.items():
        if path and Path(path).exists():
            st.write(f"- `{key}`: `{Path(path).name}`")

    if report_markdown:
        st.subheader("Automatic Research Report")
        st.download_button(
            "Download report.md",
            data=report_markdown.encode("utf-8"),
            file_name=f"{selected_entry.path.name}_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
        with st.expander("Preview report", expanded=False):
            st.markdown(report_markdown)

    if report_html:
        st.download_button(
            "Download report.html",
            data=report_html.encode("utf-8"),
            file_name=f"{selected_entry.path.name}_report.html",
            mime="text/html",
            use_container_width=True,
        )
        with st.expander("Preview print-friendly HTML report", expanded=False):
            st.html(report_html)

    if report_pdf:
        st.download_button(
            "Download report.pdf",
            data=report_pdf,
            file_name=f"{selected_entry.path.name}_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.subheader("What is each file for?")
    st.caption(
        "summary.json / metadata.json / validation_report.json은 서로 다른 질문에 답합니다: "
        "validation_report는 '설정이 타당한가'(실행 전), summary는 '결과적으로 무엇이 나왔는가'(실행 후), "
        "metadata는 '이 결과가 언제·어떻게 만들어졌는가'입니다."
    )
    file_roles_df = dash.result_file_roles_dataframe(metadata)
    if not file_roles_df.empty:
        st.dataframe(file_roles_df, use_container_width=True, hide_index=True)
    else:
        st.info("이 결과는 file_roles 메타데이터가 기록되기 전 버전으로 생성되었습니다. 다시 실행하면 표시됩니다.")

    diagnostic_provenance_rows_loaded = loaded.get("diagnostic_provenance", [])
    if diagnostic_provenance_rows_loaded:
        st.subheader("Growth Pathway Diagnostic Provenance")
        st.caption(
            "각 진단 변수가 PySDM adapter의 실측값(native)인지, native 값으로부터 계산된 값(derived)인지, "
            "adapter가 제공하지 않아 근사한 값(proxy)인지 보여줍니다. 논문/보고서 작성 시 어떤 수치가 "
            "직접 측정치인지 확인하는 용도입니다."
        )
        provenance_counts = dash.diagnostic_provenance_summary_counts(diagnostic_provenance_rows_loaded)
        pc1, pc2, pc3 = st.columns(3)
        pc1.metric("Native", provenance_counts.get("native", 0))
        pc2.metric("Derived", provenance_counts.get("derived", 0))
        pc3.metric("Proxy", provenance_counts.get("proxy", 0))
        if provenance_counts.get("proxy", 0) > 0:
            st.caption("Proxy 변수가 있는 결과는 정성적 경향 파악용으로만 사용하고, 정량적 결론에는 주의하세요.")
        else:
            st.success("Proxy diagnostic 0개 · native/derived product contract를 충족합니다.")
        st.dataframe(
            dash.diagnostic_provenance_dataframe(diagnostic_provenance_rows_loaded),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Summary JSON")
    st.json(summary)

    st.subheader("Metadata JSON")
    st.json(metadata)

with tab_config:
    st.subheader("Configuration")
    st.json(config)

    st.subheader("Validation Report")
    if isinstance(validation, list) and validation:
        st.dataframe(pd.DataFrame(validation), use_container_width=True)
    elif isinstance(validation, list):
        st.success("No validation issues were stored for this run.")
    else:
        st.json(validation)

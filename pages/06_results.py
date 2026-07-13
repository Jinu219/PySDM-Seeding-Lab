from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from analysis.dashboard import (
    available_numeric_columns,
    comparison_base_variables,
    discover_results,
    flatten_summary,
    format_metric_value,
    load_result,
    plot_control_vs_seeding,
    plot_difference,
    plot_selected_variable,
    plot_time_series,
    recommended_column_groups,
)


st.title("06. Results Dashboard")
st.caption("Simulation output, summary metrics, metadata, and time-series diagnostics.")

result_dir = Path("results")
entries = discover_results(result_dir)

if not entries:
    st.info("No result files found. Run an experiment first.")
    st.stop()

selected_entry = st.selectbox(
    "Select result",
    entries,
    format_func=lambda entry: entry.label,
)

loaded = load_result(selected_entry)
df = loaded["timeseries"]
comparison_df = loaded.get("comparison", pd.DataFrame())
control_df = loaded.get("control", pd.DataFrame())
seeding_df = loaded.get("seeding", pd.DataFrame())
summary = loaded["summary"]
metadata = loaded["metadata"]
config = loaded["config"]
validation = loaded["validation"]
files = loaded["files"]

is_comparison = selected_entry.result_type == "comparison"

st.subheader("Run Overview")

overview_cols = st.columns(4)
overview_cols[0].metric("Rows", f"{len(df)}")
overview_cols[1].metric(
    "End time",
    format_metric_value(float(df["time_s"].iloc[-1])) + " s" if "time_s" in df.columns and len(df) else "NA",
)
overview_cols[2].metric(
    "Adapter",
    metadata.get("adapter_name", summary.get("adapter_name", metadata.get("source", "unknown"))),
)
overview_cols[3].metric(
    "Type",
    selected_entry.result_type,
)

if is_comparison:
    st.write(f"Comparison run directory: `{selected_entry.path}`")
else:
    if "seeding_active" in df.columns:
        active_steps = int(df["seeding_active"].fillna(0).sum())
        st.caption(f"Seeding active steps: {active_steps}")
    if selected_entry.is_run_directory:
        st.write(f"Run directory: `{selected_entry.path}`")
    else:
        st.write(f"Legacy CSV: `{selected_entry.path}`")

st.divider()

if is_comparison:
    tab_dashboard, tab_comparison, tab_tables, tab_files, tab_config = st.tabs(
        ["Dashboard", "Control vs Seeding", "Tables", "Files & Metadata", "Config / Validation"]
    )
else:
    tab_dashboard, tab_tables, tab_files, tab_config = st.tabs(
        ["Dashboard", "Timeseries Table", "Files & Metadata", "Config / Validation"]
    )
    tab_comparison = None

with tab_dashboard:
    st.subheader("Summary Metrics")

    flat_summary = flatten_summary(summary)

    if is_comparison:
        preferred_metrics = [
            "comparison.delta_final_rain_water_mixing_ratio",
            "comparison.relative_final_rain_water_mixing_ratio_percent",
            "comparison.delta_accumulated_rain_water_proxy",
            "comparison.relative_accumulated_rain_water_proxy_percent",
            "comparison.delta_final_effective_radius_um",
            "comparison.delta_final_droplet_number_concentration_cm3",
            "comparison.delta_final_superdroplet_count",
        ]
    else:
        preferred_metrics = [
            "metrics.final_rain_water_mixing_ratio",
            "metrics.max_rain_water_mixing_ratio",
            "metrics.accumulated_rain_water_proxy",
            "metrics.rain_onset_time_s",
            "metrics.final_effective_radius_um",
            "metrics.final_droplet_number_concentration_cm3",
            "metrics.final_superdroplet_count",
            "metrics.n_seeding_active_steps",
        ]

    metric_items = [(key, flat_summary.get(key)) for key in preferred_metrics if key in flat_summary]

    if not metric_items:
        if "rain_water_mixing_ratio" in df.columns:
            metric_items.append(("final_rain_water_mixing_ratio", float(df["rain_water_mixing_ratio"].iloc[-1])))
            metric_items.append(("max_rain_water_mixing_ratio", float(df["rain_water_mixing_ratio"].max())))
        if "effective_radius_um" in df.columns:
            metric_items.append(("final_effective_radius_um", float(df["effective_radius_um"].iloc[-1])))
        if "superdroplet_count" in df.columns:
            metric_items.append(("final_superdroplet_count", float(df["superdroplet_count"].iloc[-1])))
        if "seeding_active" in df.columns:
            metric_items.append(("n_seeding_active_steps", int(df["seeding_active"].sum())))

    if metric_items:
        metric_cols = st.columns(min(4, len(metric_items)))
        for idx, (key, value) in enumerate(metric_items):
            metric_cols[idx % len(metric_cols)].metric(
                key.split(".")[-1],
                format_metric_value(value),
            )
    else:
        st.info("No summary metrics available yet.")

    st.divider()

    if is_comparison:
        st.subheader("Comparison Preview")

        bases = comparison_base_variables(comparison_df)
        default_candidates = [
            "rain_water_mixing_ratio",
            "effective_radius_um",
            "droplet_number_concentration_cm3",
            "superdroplet_count",
        ]
        default_base = next((item for item in default_candidates if item in bases), bases[0] if bases else None)

        if default_base is None:
            st.info("No comparable variables found.")
        else:
            selected_base = st.selectbox("Comparison variable", bases, index=bases.index(default_base))
            fig1 = plot_control_vs_seeding(comparison_df, selected_base)
            st.pyplot(fig1)
            fig2 = plot_difference(comparison_df, selected_base)
            st.pyplot(fig2)

    else:
        st.subheader("Recommended Diagnostic Plots")

        if "time_s" not in df.columns:
            st.warning("This result does not contain `time_s`, so time-series plots cannot be displayed.")
        else:
            groups = recommended_column_groups(df)

            if not groups:
                st.info("No recommended numeric diagnostic columns were found.")
            else:
                for group_name, columns in groups.items():
                    st.markdown(f"#### {group_name}")
                    fig = plot_time_series(
                        df,
                        columns,
                        title=group_name,
                        ylabel=group_name,
                        show_seeding_window=True,
                    )
                    st.pyplot(fig)

        st.divider()

        st.subheader("Custom Variable Plot")

        numeric_cols = available_numeric_columns(df)
        if "time_s" in df.columns and numeric_cols:
            selected_column = st.selectbox("Variable", numeric_cols)
            fig = plot_selected_variable(df, selected_column)
            st.pyplot(fig)
        else:
            st.info("No numeric variables available for custom plotting.")

if is_comparison and tab_comparison is not None:
    with tab_comparison:
        st.subheader("Control vs Seeding Analysis")

        bases = comparison_base_variables(comparison_df)
        if not bases:
            st.info("No comparable variables found.")
        else:
            selected_base = st.selectbox("Variable for detailed comparison", bases, key="detailed_comparison_base")

            col1, col2 = st.columns(2)
            with col1:
                st.pyplot(plot_control_vs_seeding(comparison_df, selected_base))
            with col2:
                st.pyplot(plot_difference(comparison_df, selected_base))

            rel_col = f"{selected_base}_relative_change_percent"
            if rel_col in comparison_df.columns:
                st.subheader("Relative Change")
                st.line_chart(comparison_df.set_index("time_s")[rel_col])

        st.subheader("Comparison Summary JSON")
        st.json(summary.get("comparison", summary))

with tab_tables:
    if is_comparison:
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

    for key, path in files.items():
        if path and Path(path).exists():
            st.write(f"- `{key}`: `{Path(path).name}`")

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

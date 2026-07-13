from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import yaml


st.title("06. Results")
st.caption("저장된 simulation output을 확인하고 기본 time-series plot을 표시합니다.")

result_dir = Path("results")
result_dir.mkdir(exist_ok=True)

result_dirs = sorted(
    [p for p in result_dir.iterdir() if p.is_dir() and (p / "timeseries.csv").exists()],
    reverse=True,
)
legacy_csvs = sorted(result_dir.glob("*.csv"), reverse=True)

options = result_dirs + legacy_csvs

if not options:
    st.info("No result files found. Run an experiment first.")
    st.stop()


def option_label(path: Path) -> str:
    if path.is_dir():
        return f"[run directory] {path.name}"
    return f"[legacy csv] {path.name}"


selected = st.selectbox("Select result", options, format_func=option_label)

if selected.is_dir():
    timeseries_path = selected / "timeseries.csv"
    summary_path = selected / "summary.json"
    metadata_path = selected / "metadata.json"
    config_path = selected / "config.yaml"
else:
    timeseries_path = selected
    summary_path = None
    metadata_path = None
    config_path = None

df = pd.read_csv(timeseries_path)

if selected.is_dir():
    st.subheader("Run Files")
    st.write(f"Run directory: `{selected}`")
    st.write(f"Timeseries: `{timeseries_path.name}`")

    col1, col2 = st.columns(2)

    with col1:
        if summary_path and summary_path.exists():
            with summary_path.open("r", encoding="utf-8") as f:
                summary = json.load(f)
            st.subheader("Summary")
            st.json(summary)

    with col2:
        if metadata_path and metadata_path.exists():
            with metadata_path.open("r", encoding="utf-8") as f:
                metadata = json.load(f)
            st.subheader("Metadata")
            st.json(metadata)

    if config_path and config_path.exists():
        with st.expander("Configuration used for this run"):
            with config_path.open("r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            st.json(cfg)

st.subheader("Result Table")
st.dataframe(df, use_container_width=True)

st.subheader("Time Series")

numeric_cols = [c for c in df.columns if c != "time_s" and pd.api.types.is_numeric_dtype(df[c])]
if "time_s" in df.columns and numeric_cols:
    y_col = st.selectbox("Variable", numeric_cols)
    fig, ax = plt.subplots()
    ax.plot(df["time_s"], df[y_col])
    ax.set_xlabel("Time [s]")
    ax.set_ylabel(y_col)
    ax.set_title(y_col)
    st.pyplot(fig)
else:
    st.warning("The selected result does not contain plottable time-series data.")

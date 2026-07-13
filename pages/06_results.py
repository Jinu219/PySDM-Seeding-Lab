from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


st.title("06. Results")
st.caption("저장된 simulation output을 확인하고 기본 time-series plot을 표시합니다.")

result_dir = Path("results")
result_files = sorted(result_dir.glob("*.csv"), reverse=True)

if not result_files:
    st.info("No result files found. Run an experiment first.")
    st.stop()

selected = st.selectbox("Select result file", result_files, format_func=lambda p: p.name)
df = pd.read_csv(selected)

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
    st.warning("The selected file does not contain plottable time-series data.")

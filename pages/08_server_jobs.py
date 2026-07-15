from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from simulation.server_jobs import job_table_rows, list_background_jobs
from simulation.ui_helpers import inject_responsive_css


PROJECT_ROOT = Path(__file__).resolve().parents[1]

inject_responsive_css()
st.title("08. Server Jobs")
st.caption(
    "Detached experiment workers continue running when the browser disconnects or "
    "the Streamlit page is refreshed."
)

refresh_col, results_col = st.columns([1, 3])
with refresh_col:
    if st.button("Refresh job status", width="stretch"):
        st.rerun()
with results_col:
    st.info(
        "When a job finishes, open **07. Results Dashboard** from the sidebar "
        "to inspect its result directory."
    )

records = list_background_jobs(PROJECT_ROOT, limit=50)
if not records:
    st.info("No background jobs have been submitted from this project yet.")
    st.stop()

rows = job_table_rows(records)
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

labels = [
    f"{record.get('job_id')} · {record.get('state')} · {record.get('experiment_name')}"
    for record in records
]
selected_label = st.selectbox("Inspect job", labels)
record = records[labels.index(selected_label)]

total = max(int(record.get("total_model_runs", 0)), 0)
completed = max(int(record.get("completed_model_runs", 0)), 0)
fraction = 1.0 if record.get("state") == "succeeded" else (
    min(completed, total) / total if total else 0.0
)

metric_cols = st.columns(5)
metric_cols[0].metric("State", str(record.get("state", "unknown")))
metric_cols[1].metric("PID", str(record.get("pid") or "-"))
metric_cols[2].metric("Workers", int(record.get("configured_workers", 1)))
metric_cols[3].metric("Model runs", f"{completed}/{total}")
metric_cols[4].metric("Progress", f"{fraction * 100:.1f}%")
st.progress(fraction)
st.info(
    f"Stage: `{record.get('stage', 'unknown')}` · {record.get('message', '')}"
)

if record.get("result_dir"):
    st.success(f"Result directory: `{record['result_dir']}`")
if record.get("error"):
    st.error(str(record["error"]))

with st.expander("Job record", expanded=False):
    st.json(record)

log_path = Path(str(record.get("log_path", "")))
with st.expander("Worker log (latest 200 lines)", expanded=record.get("state") == "failed"):
    if log_path.is_file():
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            st.code("\n".join(lines[-200:]) or "(log is empty)", language="text")
        except OSError as exc:
            st.warning(f"Could not read worker log: {exc}")
    else:
        st.caption("The worker log has not been created yet.")

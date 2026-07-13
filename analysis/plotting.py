from __future__ import annotations

import pandas as pd

from analysis.dashboard import plot_selected_variable, plot_time_series


def plot_basic_time_series(df: pd.DataFrame, column: str):
    """Backward-compatible single-column time-series plot."""
    return plot_selected_variable(df, column)

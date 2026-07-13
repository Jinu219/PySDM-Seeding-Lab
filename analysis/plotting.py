import matplotlib.pyplot as plt
import pandas as pd


def plot_time_series(df: pd.DataFrame, column: str):
    fig, ax = plt.subplots()
    ax.plot(df["time_s"], df[column])
    ax.set_xlabel("Time [s]")
    ax.set_ylabel(column)
    ax.set_title(column)
    return fig

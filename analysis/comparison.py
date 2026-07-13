import pandas as pd


def difference(seed_df: pd.DataFrame, control_df: pd.DataFrame, column: str) -> pd.Series:
    return seed_df[column] - control_df[column]


def relative_change_percent(seed_df: pd.DataFrame, control_df: pd.DataFrame, column: str) -> pd.Series:
    denominator = control_df[column].replace(0, pd.NA)
    return (seed_df[column] - control_df[column]) / denominator * 100.0

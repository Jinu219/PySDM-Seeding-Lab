import pandas as pd


def final_value(df: pd.DataFrame, column: str) -> float:
    return float(df[column].iloc[-1])


def maximum_value(df: pd.DataFrame, column: str) -> float:
    return float(df[column].max())


def accumulated_precipitation_proxy(df: pd.DataFrame, column: str = "rain_water_mixing_ratio") -> float:
    '''
    임시 proxy metric입니다.
    실제 강수량 계산이 연결되면 surface precipitation 또는 rain rate 적분으로 교체합니다.
    '''
    return float(df[column].sum())

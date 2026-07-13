from typing import Any, Dict
import numpy as np
import pandas as pd


def run_pysdm_simulation(settings: Dict[str, Any]) -> pd.DataFrame:
    '''
    PySDM과 실제로 연결되는 adapter입니다.

    현재 파일은 프로젝트 구조 검증을 위한 placeholder입니다.
    이후 기존 seeding_no_collisions.ipynb, collision_onoff, Experiment 2~4 코드를
    이 함수 내부 또는 별도 class로 연결하면 됩니다.

    반환값은 반드시 time_s column을 포함한 pandas DataFrame 형태를 권장합니다.
    '''
    env = settings.get("environment", {})
    seed = settings.get("seeding", {})
    microphysics = settings.get("microphysics", {})

    duration = int(env.get("duration", 1500))
    timestep = int(env.get("timestep", 15))
    time_s = np.arange(0, duration + timestep, timestep)

    updraft = float(env.get("updraft_velocity", 1.0))
    seeding_enabled = bool(seed.get("enabled", False))
    collision_enabled = bool(microphysics.get("collision", False))

    injection_start = int(seed.get("injection_start", duration + 1))
    injection_end = int(seed.get("injection_end", duration + 1))

    injection_mask = (time_s >= injection_start) & (time_s <= injection_end)

    # Placeholder synthetic signals.
    # 실제 PySDM 연결 후 이 부분을 교체합니다.
    cloud_water = 1e-3 * (1 - np.exp(-time_s / 300)) * max(updraft, 0.1)
    rain_water = 2e-4 * (1 - np.exp(-(np.maximum(time_s - 600, 0)) / 400))

    if seeding_enabled:
        cloud_water = cloud_water + injection_mask.astype(float) * 2e-4
        rain_water = rain_water + 1.5e-4 * (1 - np.exp(-(np.maximum(time_s - injection_start, 0)) / 300))

    if collision_enabled:
        rain_water = rain_water * 1.5

    droplet_number = 100 + 20 * np.sin(time_s / max(duration, 1) * np.pi)
    rain_number = 5 + 10 * (rain_water / max(rain_water.max(), 1e-12))

    return pd.DataFrame(
        {
            "time_s": time_s,
            "cloud_water_mixing_ratio": cloud_water,
            "rain_water_mixing_ratio": rain_water,
            "droplet_number_concentration": droplet_number,
            "rain_drop_number_concentration": rain_number,
        }
    )

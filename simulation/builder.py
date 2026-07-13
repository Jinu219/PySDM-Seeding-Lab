from typing import Any, Dict


def build_simulation_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    '''
    YAML config를 PySDM 실행에 필요한 settings dictionary로 변환하는 계층입니다.

    현재는 config를 정리해서 그대로 넘기는 MVP 단계입니다.
    이후 PySDM Settings class 또는 기존 seeding simulation 코드에 맞게 변환합니다.
    '''
    env = config.get("environment", {})
    aero = config.get("background_aerosol", {})
    seed = config.get("seeding", {})
    microphysics = config.get("microphysics", {})

    return {
        "environment": env,
        "background_aerosol": aero,
        "seeding": seed,
        "microphysics": microphysics,
    }

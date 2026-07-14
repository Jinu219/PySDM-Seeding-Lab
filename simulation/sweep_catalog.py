from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping


SWEEP_CATALOG_BUILD_ID = "warm-cloud-sweep-catalog-20260714"


@dataclass(frozen=True)
class SweepParameterSpec:
    name: str
    category: str
    label: str
    value_label: str
    default_values: str
    value_type: str = "float"
    input_scale: float = 1.0
    role: str = "physical"
    why: str = ""
    placeholder_effective: bool = False


CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    "Seeding material & dose": (
        "활성화 가능성, 흡습성, 입자 스펙트럼 폭과 물리적 시딩량을 검사합니다."
    ),
    "Delivery & cloud dynamics": (
        "언제, 얼마나 오래 투입하는지와 상승류 시간척도의 상호작용을 검사합니다."
    ),
    "Cloud & background aerosol": (
        "초기 열역학 상태와 배경 CCN 경쟁이 시딩 반응을 억제하거나 증폭하는지 검사합니다."
    ),
    "Microphysics & numerical robustness": (
        "collision–coalescence 의존성과 timestep/super-droplet 수에 대한 수치수렴을 검사합니다."
    ),
}


COMMON_SWEEP_PARAMETERS: List[SweepParameterSpec] = [
    SweepParameterSpec(
        name="seeding.dry_radius",
        category="Seeding material & dose",
        label="Seeding dry radius",
        value_label="Dry radius values [µm]",
        default_values="0.5, 1.0, 1.5",
        input_scale=1.0e-6,
        why="κ와 함께 Köhler activation 및 초기 용질량을 결정합니다.",
        placeholder_effective=True,
    ),
    SweepParameterSpec(
        name="seeding.kappa",
        category="Seeding material & dose",
        label="Seeding hygroscopicity κ",
        value_label="κ values [–]",
        default_values="0.4, 0.8, 1.2",
        why="시딩 물질의 흡습성과 임계과포화도를 제어합니다.",
        placeholder_effective=True,
    ),
    SweepParameterSpec(
        name="seeding.geometric_sigma",
        category="Seeding material & dose",
        label="Seeding size-distribution width",
        value_label="Geometric σ values [–]",
        default_values="1.1, 1.2, 1.4",
        why="동일 평균반경에서도 활성화 가능한 큰 입자 tail의 양을 바꿉니다.",
    ),
    SweepParameterSpec(
        name="seeding.number_concentration",
        category="Seeding material & dose",
        label="Seeding number concentration",
        value_label="Concentration values [cm⁻³]",
        default_values="1, 10, 100",
        why="시딩량–반응 dose curve와 과도한 CCN 경쟁 가능성을 검사합니다.",
    ),
    SweepParameterSpec(
        name="seeding.number_superdroplets",
        category="Seeding material & dose",
        label="Seeding super-droplet resolution",
        value_label="Seeding super-droplet counts",
        default_values="50, 100, 200, 400",
        value_type="int",
        role="numerical",
        why="물리적 농도가 아니라 시딩 스펙트럼의 Monte-Carlo 표현 수렴성을 검사합니다.",
    ),
    SweepParameterSpec(
        name="seeding.injection_start",
        category="Delivery & cloud dynamics",
        label="Injection start",
        value_label="Injection start values [s]",
        default_values="600, 900, 1200",
        value_type="int",
        why="시딩 시점과 과포화·구름수 성장 단계의 정합성을 검사합니다.",
        placeholder_effective=True,
    ),
    SweepParameterSpec(
        name="seeding.injection_duration",
        category="Delivery & cloud dynamics",
        label="Injection duration",
        value_label="Injection duration values [s]",
        default_values="120, 300, 600",
        value_type="int",
        why="동일 입자 특성에서 짧은 pulse와 지속 투입의 차이를 검사합니다.",
        placeholder_effective=True,
    ),
    SweepParameterSpec(
        name="environment.updraft_velocity",
        category="Delivery & cloud dynamics",
        label="Updraft velocity",
        value_label="Updraft values [m s⁻¹]",
        default_values="0.5, 1.0, 1.5",
        why="냉각·과포화 생성 시간척도와 입자 활성화 경쟁을 제어합니다.",
        placeholder_effective=True,
    ),
    SweepParameterSpec(
        name="environment.temperature",
        category="Cloud & background aerosol",
        label="Initial temperature",
        value_label="Temperature values [K]",
        default_values="283, 293, 300",
        why="포화수증기압과 parcel 열역학 경로를 변화시킵니다.",
    ),
    SweepParameterSpec(
        name="environment.pressure",
        category="Cloud & background aerosol",
        label="Initial pressure",
        value_label="Pressure values [Pa]",
        default_values="80000, 90000, 100000",
        why="공기밀도와 cm⁻³→kg⁻¹ 농도 변환에 영향을 줍니다.",
    ),
    SweepParameterSpec(
        name="environment.water_vapour_mixing_ratio",
        category="Cloud & background aerosol",
        label="Water-vapour mixing ratio",
        value_label="Water-vapour mixing-ratio values [kg kg⁻¹]",
        default_values="0.012, 0.018, 0.0222",
        why="초기 수증기 공급과 과포화 도달 가능성을 직접 제어합니다.",
    ),
    SweepParameterSpec(
        name="background_aerosol.number_concentration",
        category="Cloud & background aerosol",
        label="Background aerosol concentration",
        value_label="Background concentration values [cm⁻³]",
        default_values="50, 100, 300, 1000",
        why="배경 CCN 경쟁과 clean/polluted cloud regime을 구분합니다.",
    ),
    SweepParameterSpec(
        name="background_aerosol.dry_radius",
        category="Cloud & background aerosol",
        label="Background aerosol dry radius",
        value_label="Background dry-radius values [µm]",
        default_values="0.03, 0.075, 0.15",
        input_scale=1.0e-6,
        why="배경 입자의 활성화 용이성과 시딩 입자 대비 크기 경쟁을 바꿉니다.",
        placeholder_effective=True,
    ),
    SweepParameterSpec(
        name="background_aerosol.kappa",
        category="Cloud & background aerosol",
        label="Background aerosol κ",
        value_label="Background κ values [–]",
        default_values="0.1, 0.5, 0.9",
        why="배경 CCN의 흡습성과 시딩 입자의 상대적 이점을 바꿉니다.",
        placeholder_effective=True,
    ),
    SweepParameterSpec(
        name="background_aerosol.geometric_sigma",
        category="Cloud & background aerosol",
        label="Background size-distribution width",
        value_label="Background geometric σ values [–]",
        default_values="1.2, 1.4, 1.8",
        why="배경 aerosol의 큰 입자 tail과 자연 활성화 스펙트럼을 바꿉니다.",
    ),
    SweepParameterSpec(
        name="microphysics.collision",
        category="Microphysics & numerical robustness",
        label="Collision–coalescence OFF / ON",
        value_label="Collision states",
        default_values="false, true",
        value_type="bool",
        why="응결 성장과 충돌·병합에 의한 rain-size 전이를 분리합니다.",
        placeholder_effective=True,
    ),
    SweepParameterSpec(
        name="environment.timestep",
        category="Microphysics & numerical robustness",
        label="Model timestep",
        value_label="Timestep values [s]",
        default_values="5, 10, 15, 30",
        value_type="int",
        role="numerical",
        why="시간해상도에 결과가 의존하지 않는지 확인하는 수치수렴 변수입니다.",
        placeholder_effective=True,
    ),
    SweepParameterSpec(
        name="background_aerosol.number_superdroplets",
        category="Microphysics & numerical robustness",
        label="Background super-droplet resolution",
        value_label="Background super-droplet counts",
        default_values="50, 100, 200, 400",
        value_type="int",
        role="numerical",
        why="배경 aerosol 스펙트럼의 Monte-Carlo 표현 수렴성을 검사합니다.",
    ),
]


SENSITIVITY_PRESETS: Dict[str, Dict[str, object]] = {
    "Custom": {
        "description": "필요한 parameter를 직접 선택합니다.",
        "parameters": {},
    },
    "Activation & hygroscopicity (48 cases)": {
        "description": "dry radius–κ–분포 폭이 활성화와 성장 경로를 어떻게 바꾸는지 검사합니다.",
        "parameters": {
            "seeding.dry_radius": "0.3, 0.5, 1.0, 2.0",
            "seeding.kappa": "0.3, 0.6, 0.9, 1.2",
            "seeding.geometric_sigma": "1.1, 1.2, 1.4",
        },
    },
    "Dose response (27 cases)": {
        "description": "입자 크기·농도·투입 지속시간에 대한 시딩량 반응을 검사합니다.",
        "parameters": {
            "seeding.dry_radius": "0.5, 1.0, 2.0",
            "seeding.number_concentration": "1, 10, 100",
            "seeding.injection_duration": "120, 300, 600",
        },
    },
    "Timing & updraft (27 cases)": {
        "description": "구름 발달 시간척도와 시딩 시점의 정합성을 검사합니다.",
        "parameters": {
            "seeding.injection_start": "600, 900, 1200",
            "seeding.injection_duration": "120, 240, 300",
            "environment.updraft_velocity": "0.5, 1.0, 1.5",
        },
    },
    "Background CCN competition (36 cases)": {
        "description": "clean/polluted cloud와 배경 aerosol 크기·흡습성 경쟁을 검사합니다.",
        "parameters": {
            "background_aerosol.number_concentration": "50, 100, 300, 1000",
            "background_aerosol.dry_radius": "0.03, 0.075, 0.15",
            "background_aerosol.kappa": "0.1, 0.5, 0.9",
        },
    },
    "Thermodynamic regime (27 cases)": {
        "description": "초기 온도·수증기·상승류가 시딩 반응을 허용하는 영역을 찾습니다.",
        "parameters": {
            "environment.temperature": "283, 293, 300",
            "environment.water_vapour_mixing_ratio": "0.012, 0.018, 0.0222",
            "environment.updraft_velocity": "0.5, 1.0, 1.5",
        },
    },
    "Collision transition (18 cases)": {
        "description": "시딩 입자 크기·농도별 반응이 collision–coalescence에 의존하는지 분리합니다.",
        "parameters": {
            "seeding.dry_radius": "0.5, 1.0, 2.0",
            "seeding.number_concentration": "1, 10, 100",
            "microphysics.collision": "false, true",
        },
    },
    "Numerical convergence (64 cases)": {
        "description": "물리 결론 전에 timestep과 super-droplet 수에 대한 수렴성을 검사합니다.",
        "parameters": {
            "environment.timestep": "5, 10, 15, 30",
            "seeding.number_superdroplets": "50, 100, 200, 400",
            "background_aerosol.number_superdroplets": "50, 100, 200, 400",
        },
    },
}


def parameter_specs_by_category() -> Dict[str, List[SweepParameterSpec]]:
    grouped = {category: [] for category in CATEGORY_DESCRIPTIONS}
    for spec in COMMON_SWEEP_PARAMETERS:
        grouped.setdefault(spec.category, []).append(spec)
    return grouped


def parameter_spec_lookup() -> Dict[str, SweepParameterSpec]:
    return {spec.name: spec for spec in COMMON_SWEEP_PARAMETERS}


def preset_parameters(name: str) -> Mapping[str, str]:
    preset = SENSITIVITY_PRESETS.get(name, SENSITIVITY_PRESETS["Custom"])
    return preset.get("parameters", {})  # type: ignore[return-value]

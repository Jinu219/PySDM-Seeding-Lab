from __future__ import annotations

from typing import Any, Dict, List


# Single source of truth for "what is this file for" so that runner.py (writer)
# and dashboard.py / pages (reader) never drift apart. Keys match the filenames
# actually written by simulation/runner.py.
RESULT_FILE_ROLES: Dict[str, Dict[str, str]] = {
    "config.yaml": {
        "when": "실행 직전",
        "answers": "이 run을 만든 정확한 설정은 무엇인가",
        "description": (
            "이 run을 생성한 config의 스냅샷. 재현(reproduce)을 위한 원본이며, "
            "실행 결과와 무관하게 '입력'만 담는다."
        ),
    },
    "validation_report.json": {
        "when": "실행 직전 (모델 실행 전)",
        "answers": "이 config 자체가 타당한가",
        "description": (
            "시뮬레이션을 실행하기 전에 config의 스키마/범위/논리적 정합성을 검사한 결과. "
            "severity(error/warning/info) 목록이며, 시뮬레이션 결과 값과는 무관하다. "
            "즉 '모델이 잘 돌았는가'가 아니라 '설정이 말이 되는가'에 대한 답."
        ),
    },
    "summary.json": {
        "when": "실행 완료 직후",
        "answers": "결과적으로 무엇이 나왔는가",
        "description": (
            "실행 후 계산된 요약. adapter가 반환한 요약 통계, timeseries metrics, "
            "(가능한 경우) growth pathway diagnostic provenance, timing 정보, "
            "그리고 validation 결과의 badge 형태 요약을 담는다. "
            "'모델 실행의 산출물'에 대한 답이며 validation_report.json과는 목적이 다르다."
        ),
    },
    "metadata.json": {
        "when": "실행 완료 직후",
        "answers": "이 결과가 언제, 어떻게, 무엇으로 만들어졌는가",
        "description": (
            "run_id, 생성 시각, adapter 이름, experiment mode, 파일 경로 맵 등 "
            "run 자체에 대한 book-keeping 정보. 결과 값 자체(summary.json)나 "
            "config 타당성(validation_report.json)과는 구분되는, 이 결과 폴더를 "
            "다른 도구/스크립트가 기계적으로 다룰 때 필요한 색인 정보에 가깝다."
        ),
    },
    "diagnostic_health.json": {
        "when": "실행 완료 직후",
        "answers": "각 진단 변수의 데이터 품질은 어떤가",
        "description": (
            "Growth Pathway 진단 변수별 finite fraction(NaN이 아닌 비율) 등 "
            "데이터 품질 지표. 값이 '있는지'를 보는 것이지 '직접 측정치인지 근사치인지'는 "
            "diagnostic_provenance.json에서 확인한다."
        ),
    },
    "diagnostic_provenance.json": {
        "when": "실행 완료 직후",
        "answers": "각 진단 변수는 실측값인가 근사값인가",
        "description": (
            "Growth Pathway 진단 변수별로 adapter가 직접 제공한 값(native)인지, "
            "native 값으로부터 계산된 값(derived)인지, adapter가 제공하지 않아 "
            "휴리스틱으로 근사한 값(proxy)인지를 분류한다. 논문/보고서 작성 시 "
            "'이 수치가 PySDM 직접 출력인지 근사치인지' 확인하는 용도."
        ),
    },
    "timeseries.csv": {
        "when": "실행 완료 직후",
        "answers": "시간에 따라 무엇이 변했는가",
        "description": "단일 run의 시계열 원자료 (Growth Pathway 진단 컬럼 포함).",
    },
    "wet_radius_spectrum.csv": {
        "when": "PySDM run checkpoint",
        "answers": "How is droplet number and liquid volume distributed by wet radius?",
        "description": (
            "Tidy checkpoint table of bin-integrated number concentration and liquid-volume "
            "fraction per wet-radius logarithm. Bin edges include every tested threshold."
        ),
    },
    "threshold_robustness.csv": {
        "when": "After wet-radius spectrum extraction",
        "answers": "Does the cloud/rain conclusion change when diagnostic thresholds move?",
        "description": (
            "Repartitions each checkpoint spectrum over configured activation/rain threshold "
            "factors without rerunning PySDM."
        ),
    },
    "comparison.csv": {
        "when": "실행 완료 직후",
        "answers": "control 대비 seeding이 무엇을 바꿨는가",
        "description": "control/seeding 쌍에 대한 <var>_control/_seeding/_diff/_relative_change_percent 컬럼.",
    },
    "sweep_summary.csv": {
        "when": "sweep 종료 직후",
        "answers": "어떤 parameter 조합이 가장 효과적이었는가",
        "description": "sweep의 각 case에 대한 요약 및 ranking_metric 기준 순위.",
    },
    "ensemble_statistics.csv": {
        "when": "ensemble 종료 직후",
        "answers": "seed에 따른 불확실성은 얼마나 되는가",
        "description": "ensemble member들에 대한 mean/std/median/q25/q75/finite_fraction 등.",
    },
    "member_summary.csv": {
        "when": "ensemble 종료 직후",
        "answers": "개별 ensemble member는 각각 어땠는가",
        "description": "ensemble의 각 member별 개별 요약 (seed 포함).",
    },
}


def describe_result_files(present_keys: List[str] | None = None) -> List[Dict[str, str]]:
    """
    Return role descriptions as table rows, optionally filtered to files that
    actually exist for a given result (present_keys, e.g. ["summary.json", ...]).
    """
    if present_keys is None:
        keys = list(RESULT_FILE_ROLES.keys())
    else:
        present = set(present_keys)
        keys = [key for key in RESULT_FILE_ROLES if key in present]

    rows: List[Dict[str, Any]] = []
    for key in keys:
        role = RESULT_FILE_ROLES[key]
        rows.append(
            {
                "file": key,
                "생성 시점": role["when"],
                "무엇에 대한 답인가": role["answers"],
                "설명": role["description"],
            }
        )
    return rows

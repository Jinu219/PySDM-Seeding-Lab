# Project Status

Last updated: 2026-07-14

Active branch: `develop`

Current milestone: Step 14 physical robustness + Step 16 wet-radius spectrum, first implementation

이 문서는 프로젝트의 현재 상태를 한 화면에서 확인하는 운영 문서다. 세부 변경 이력은
`DEVELOPMENT.md`, 우선순위와 완료 조건은 `ROADMAP.md`, 설치와 사용법은 `README.md`를
기준으로 한다.

## 한눈에 보는 진행 상황

| 단계 | 상태 | 현재 결과 | 다음 완료 조건 |
|---|---|---|---|
| Step 0-12 | 완료 | 앱 골격, 설정/검증, PySDM adapter, control vs seeding, sweep, ensemble, Growth Pathway | 회귀 테스트 유지 |
| Step 13 | 완료 | PySDM 2.131 native scalar diagnostics, native 11 / derived 2 / proxy 0 | PySDM 버전 변경 시 product API 재검증 |
| Step 14 | 진행 중 | liquid-water partition closure와 wet-radius threshold robustness 구현 | control/seeding 보존성 검사와 수치 수렴 기준 확정 |
| Step 15 | 1차 완료 | Growth Pathway, OFAT, collision, ensemble publication panels | PDF/SVG export와 journal style preset |
| Step 16 | 1차 완료 | wet-radius number/volume spectrum, cloud/rain bin 재분할, Results UI | spectrum 기반 seeding-minus-control 정량 지표 확정 |
| Step 17 | 대기 | large ensemble 성능 최적화 | Step 14/16 검증 후 착수 |
| Step 18 | 대기 | 자동 report export | Step 17 이후 |
| Step 19 | 대기 | old/new result 호환성 강화 | schema migration 정책과 함께 진행 |

## 현재 동작하는 연구 흐름

1. Welcome 페이지에서 연구 질문과 권장 sweep preset을 선택한다.
2. Environment, aerosol, seeding, dynamics, microphysics를 설정하고 validation을 확인한다.
3. `pysdm_parcel`로 single, control vs seeding, parameter sweep 또는 ensemble을 실행한다.
4. 각 실행은 재현 가능한 config, validation, metadata, summary, timeseries를 저장한다.
5. Results Dashboard에서 Growth Pathway, publication panels, spectrum과 threshold robustness를 확인한다.

`placeholder_warm_cloud`는 UI와 workflow 점검용 합성 adapter다. 물리 해석에는
`pysdm_parcel` 결과만 사용하고 diagnostic provenance를 함께 확인해야 한다.

## 이번 개발에서 추가된 것

- PySDM native `NumberSizeSpectrum`과
  `ParticleVolumeVersusRadiusLogarithmSpectrum` product를 프로젝트 builder에 연결했다.
- 기본 체크포인트는 시작, 주입 시작, 주입 종료, 모의실험 종료이며 설정에서 직접 바꿀 수 있다.
- 기본 32개 logarithmic bin에 activation/rain threshold와 각 threshold factor를 정확한
  bin edge로 추가한다.
- 기본 threshold factors `0.8, 1.0, 1.2`로 동일 spectrum을 재분할한다. 따라서 threshold
  민감도 계산을 위해 PySDM을 다시 실행하지 않는다.
- single run은 결과 루트, control vs seeding은 각 case 하위 폴더에 다음 파일을 저장한다.

| 파일 | 내용 |
|---|---|
| `wet_radius_spectrum.csv` | checkpoint별 wet-radius bin, number concentration, liquid-volume fraction, regime |
| `threshold_robustness.csv` | activation/rain threshold 조합별 unactivated/cloud/rain partition과 비율 |

## 현재 해석 범위

- `unactivated`, `cloud`, `rain`은 입자의 과거 activation event가 아니라 설정된 시점의
  **wet-radius 구간 정의**다.
- `NumberSizeSpectrum`은 각 bin에 적분된 농도이며 결과 파일은 `m^-3`와 `cm^-3`를 함께 저장한다.
- volume spectrum은 `dV_liquid / V_air / dln(r)`이고, 결과 파일은 bin 적분값도 함께 저장한다.
- threshold robustness는 진단 정의의 안정성을 검사한다. 모델 입력 민감도나 관측 불확실성을
  대신하지 않는다.

## 다음 개발 우선순위

1. Step 14 완료: control/seeding 각각의 water partition closure와 총수분 변화 검사를 자동 판정한다.
2. Step 14 완료: background/seed super-droplet 수에 대한 numerical convergence 기준과 경고를 만든다.
3. Step 16 강화: spectrum 기반 seeding-minus-control difference와 onset/transition 지표를 추가한다.
4. Step 17 착수: checkpoint 결과를 유지하면서 sweep/ensemble 메모리와 실행 시간을 줄인다.

## 검증 명령

```powershell
& 'C:\Users\PC\anaconda3\envs\PySDM\python.exe' -m unittest -v tests.test_native_diagnostics
& 'C:\Users\PC\anaconda3\envs\PySDM\python.exe' scripts\check_project_integrity.py
```

Streamlit 화면 회귀 검사는 `pages/02_aerosol.py`, `pages/06_run.py`,
`pages/07_results.py`를 대상으로 수행한다.

## 문서 관리 규칙

- `PROJECT_STATUS.md`: 지금 무엇이 되고 있고 바로 다음에 무엇을 하는지 갱신한다.
- `ROADMAP.md`: 단계 순서, 연구 리스크, 완료 조건이 바뀔 때 갱신한다.
- `DEVELOPMENT.md`: 완료된 구현과 검증 결과를 append-only changelog로 남긴다.
- `README.md`: 신규 사용자가 설치하고 실행하는 데 필요한 안정된 사용법만 유지한다.

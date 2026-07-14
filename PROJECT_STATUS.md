# Project Status

Last updated: 2026-07-14

Active branch: `develop`

Current milestone: Full PySDM qualification and large-ensemble evidence completed

## Latest research-evidence update

Completed:
- A 27-case `pysdm_parcel` standard qualification completed 54 physical model
  executions without failure. All 12 non-zero next-finest checks passed the 5%
  tolerance; the median, P95, and maximum relative differences were 0.187%,
  1.140%, and 1.731%. This supports 5% for the tested marine, collision-OFF
  profile, but does not yet support rain-producing or collision-ON claims.
- The spectrum-transition diagnostic now audits 20/25/30 micrometre radius
  boundaries and 0.5/1/2% activated-liquid fractions. The 25 micrometre boundary
  is literature-bounded; 1% remains an explicit project-owned operational floor.
  Automatic checkpoints target 10 seconds, snap to model timesteps, and preserve
  injection boundaries and endpoints.
- A 24-member large real-PySDM ensemble benchmark measured the complete process
  and the streaming aggregation phase separately. Peak RSS rose by 999.64 MiB
  over baseline, while aggregation itself added only 0.27 MiB RSS and took 3.772 s.
  Repeated PySDM/JIT/object lifetime is therefore the next memory-profiling target.
- Results can prepare an on-demand PDF containing the publication figure currently
  selected in the dashboard, in addition to the automatic report artifacts.
- A preserved pre-manifest sweep fixture and a schema-v1 alias fixture now exercise
  legacy inference and in-memory manifest migration regression paths.

Evidence:
- [`docs/evidence/NUMERICAL_QUALIFICATION_20260714.md`](docs/evidence/NUMERICAL_QUALIFICATION_20260714.md)
- [`docs/evidence/ENSEMBLE_BENCHMARK_20260714.md`](docs/evidence/ENSEMBLE_BENCHMARK_20260714.md)
- [`docs/SPECTRUM_TRANSITION_BASIS.md`](docs/SPECTRUM_TRANSITION_BASIS.md)

Next scientific and performance priorities:
1. Repeat qualification with collision enabled and a rain-producing configuration.
2. Profile retained RSS ownership across ensemble members and backend/JIT lifetimes.
3. Compare a columnar internal cache with CSV using numerical-equality regressions.
4. Validate the operational 1% transition floor against an observational dataset.

## Latest execution-robustness update

Completed:
- Nested sweep and ensemble outputs now use compact stable directories such as
  `cases/case_001/members/member_001/comparison`, while full experiment and
  parameter metadata remain in the saved configuration and summary files.
- Filesystem components are sanitized and length-bounded, preventing the Windows
  legacy path-limit failure reproduced by the 281-character member output path.
- Ensemble and sweep summaries now distinguish `success`, `partial`, and `failed`.
  Complete failure is raised only after durable member/case error artifacts are saved.
- Results Dashboard diagnoses both new and older failed sweeps. The reproduced
  `20260714_190022_727349_0714_18_58_parameter_sweep` result is now identified as
  24 failed cases and 240 failed members instead of being described as an empty or
  incorrectly configured sensitivity experiment.
- Ensemble sweeps retain member-level scalar metrics and can rank successful cases
  from ensemble means when a direct comparison summary is not present.

Operational note: the reproduced result contains no successful physical time series,
so it cannot be repaired in place and must be rerun with the updated runner. Its
configuration and failure evidence remain useful for audit and regression testing.

## Latest portable report and qualification update

Completed:
- Every new result writes `report.pdf`. Single runs embed a water-budget figure,
  comparisons embed spectrum transition, and numerical sweeps embed convergence
  when those diagnostics are available.
- Results Dashboard downloads Markdown, HTML, and PDF reports.
- Ensemble aggregation separates tracemalloc-visible allocation from sampled
  whole-process RSS.
- `scripts/run_numerical_qualification.py` provides dry-run, `pilot`, and
  `standard` profiles and stores `qualification_plan.json`.
- Generated run IDs use microsecond resolution, preventing rapid sweep collisions.

Next scientific priority:
1. Run `standard` qualification with `pysdm_parcel` and justify or revise the
   default 5% tolerance.
2. Benchmark sampled RSS and streaming CSV I/O on a genuinely large PySDM ensemble.
3. Add migration fixtures when the result schema first changes beyond version 2.

The completed placeholder pilot validates software orchestration only; it is not
physical cloud-seeding evidence.

이 문서는 프로젝트의 현재 상태를 한 화면에서 확인하는 운영 문서다. 세부 변경 이력은
`DEVELOPMENT.md`, 우선순위와 완료 조건은 `ROADMAP.md`, 설치와 사용법은 `README.md`를
기준으로 한다.

## 한눈에 보는 진행 상황

| 단계 | 상태 | 현재 결과 | 다음 완료 조건 |
|---|---|---|---|
| Step 0-12 | 완료 | 앱 골격, 설정/검증, PySDM adapter, control vs seeding, sweep, ensemble, Growth Pathway | 회귀 테스트 유지 |
| Step 13 | 완료 | PySDM 2.131 native scalar diagnostics, native 11 / derived 2 / proxy 0 | PySDM 버전 변경 시 product API 재검증 |
| Step 14 | 1차 완료 | source-aware water budget, threshold robustness, numerical convergence gate | 장기/고해상도 실험으로 tolerance 근거 축적 |
| Step 15 | 1차 완료 | publication panels, PNG/SVG/PDF export, journal width presets | 저널별 세부 typography preset은 실제 투고 시 확장 |
| Step 16 | 2차 완료 | spectrum transition onset, checkpoint interpolation, threshold-pair audit | 1% 기본 threshold의 관측·문헌 근거 확정 |
| Step 17 | 2차 완료 | streaming aggregation과 input/time/tracemalloc benchmark JSON | 대형 PySDM 실행의 RSS·I/O benchmark |
| Step 18 | 2차 완료 | 모든 result type의 Markdown + self-contained HTML report | 향후 PDF report 및 figure embedding |
| Step 19 | 1차 완료 | versioned `result_manifest.json`, legacy inference, Results compatibility status | 실제 schema 변경 시 migration fixture 추가 |

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

이번 연구 품질 묶음에서 다음 산출물이 추가됐다.

| 파일 | 내용 |
|---|---|
| `water_budget.csv` | vapour/liquid/total water와 closed-window 보존성 drift |
| `water_budget_comparison.csv` | control–seeding 수분 예산 정렬 비교 |
| `wet_radius_spectrum_comparison.csv` | wet-radius bin별 seeding-minus-control number/volume 차이 |
| `threshold_robustness_comparison.csv` | threshold 조합별 seeding response 차이 |
| `numerical_convergence.csv` | finest reference 대비 timestep/NSD OFAT 수렴 오차 |
| `report.md` | 품질 판정, 핵심 지표, validation, artifact, 재현 절차 자동 요약 |
| `report.html` | 브라우저 열람과 인쇄가 가능한 self-contained 연구 보고서 |
| `result_manifest.json` | result schema version, result type, primary data, artifact map |
| `spectrum_transition.csv` | baseline threshold의 control/seeding rain-size liquid fraction과 차이 |
| `spectrum_transition_onset_robustness.csv` | radius threshold 조합별 보간 onset과 onset shift |
| `ensemble_aggregation_diagnostics.json` | streaming input bytes, elapsed time, traced peak allocation |

## 현재 해석 범위

- `unactivated`, `cloud`, `rain`은 입자의 과거 activation event가 아니라 설정된 시점의
  **wet-radius 구간 정의**다.
- `NumberSizeSpectrum`은 각 bin에 적분된 농도이며 결과 파일은 `m^-3`와 `cm^-3`를 함께 저장한다.
- volume spectrum은 `dV_liquid / V_air / dln(r)`이고, 결과 파일은 bin 적분값도 함께 저장한다.
- threshold robustness는 진단 정의의 안정성을 검사한다. 모델 입력 민감도나 관측 불확실성을
  대신하지 않는다.
- water-budget pass/fail은 injection source window를 제외한 닫힌 구간에만 적용한다.
- numerical convergence 기본 판정은 rank 1과 finest rank 0의 상대 차이 5%다. 기준 metric이
  0에 매우 가까우면 상대오차가 과대해질 수 있으므로 absolute difference도 함께 확인한다.
- spectrum transition onset은 activated liquid 중 rain-size bin liquid 비율이 기본 1%를
  처음 넘는 시각이다. 저장된 checkpoint 사이를 선형 보간하며 particle-history event가 아니다.
- aggregation peak는 `tracemalloc`이 관측한 Python/NumPy allocation이며 whole-process RSS가 아니다.

## 다음 개발 우선순위

1. numerical convergence preset을 full PySDM으로 실행해 5% 기본 tolerance의 경험적 근거를 축적한다.
2. spectrum transition 1% threshold와 checkpoint 간격을 관측 또는 문헌 기준으로 보정한다.
3. 대형 PySDM ensemble에서 whole-process RSS와 streaming CSV I/O 시간을 benchmark한다.
4. Step 18 report를 PDF로 확장하고 선택한 publication figure를 포함한다.
5. 실제 구버전 결과 fixture를 보존하고 schema 변경 때 migration 회귀 테스트를 추가한다.

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

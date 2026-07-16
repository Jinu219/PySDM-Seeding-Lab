# Project Status

Last updated: 2026-07-16

Active branch: `develop`

Current milestone: Targeted high-resolution rain-response plan completed

## Targeted high-resolution response-plan update

Completed on 2026-07-16:
- Added `rain_response_targeted`, using only finest and next-finest timestep,
  seeding-super-droplet, and background-super-droplet levels.
- The resulting OFAT plan is exactly 4 cases, 5 common seeds, 20 case-seed pairs,
  and 40 control/seeding model executions instead of the 70-execution standard.
- Qualification plans now include local runtime-estimate provenance, estimated
  serial duration, case-seed count, and execution-confirmation metadata.
- The profile is dry-run-first, forces one case worker, and rejects physical
  execution unless `--confirm-targeted-run` is explicitly supplied.
- The dry-run and rejection paths were exercised without starting PySDM.
- All 37 unit/integration tests and project integrity passed after the change.

Decision: preserve this as a reviewed execution plan only. Existing physical
interpretation does not change until the 40 runs are explicitly authorized and
completed.

Plan: [`docs/TARGETED_RESPONSE_PLAN.md`](docs/TARGETED_RESPONSE_PLAN.md)

## Lab-server and bounded parallel execution update

Completed on 2026-07-15:
- Added a Linux `nohup` service script with start, stop, restart, status, PID,
  private log, headless Streamlit, configurable interpreter/host/port, and a
  secure loopback-plus-SSH-tunnel default.
- Added detached experiment jobs. Each job preserves an immutable YAML snapshot,
  PID, state, progress, error, log, and result path under `.runtime/jobs/`; it is
  independent of browser and Streamlit page lifetimes.
- Added the Server Jobs page for persistent monitoring and diagnostics.
- Added bounded process-pool execution for independent sweep cases through
  `execution.max_workers`. Ensemble members remain sequential inside each worker,
  preventing nested oversubscription.
- Process workers use spawn semantics and are reused across cases until the sweep
  ends. Timing-history writes are now inter-process locked and atomically replaced.
- The marine showcase scenario starts at four workers. Its 10 cases can use at
  most 10 workers; a 20-worker setting only becomes effective for 20 or more cases.
- Added server deployment, SSH tunnel, RAM sizing, and rollout guidance under
  `docs/SERVER_DEPLOYMENT.md`.
- All 37 unit/integration tests and project integrity passed. Parameter Sweep,
  Run, and Server Jobs AppTests rendered with zero exceptions and zero errors.

Decision: server use is supported, but worker count remains opt-in and defaults to
one. Recent PySDM evidence reached about 1.03 GiB per active isolated child, so the
first lab-server run should use four workers and scale only after measuring RAM.

## Process-isolated ensemble backend update

Completed on 2026-07-15:
- Added opt-in `ensemble.execution_backend: subprocess`. Every member runs in a
  fresh Python process and preserves its normalized config, status, stdout, stderr,
  return code, elapsed time, and sampled child process-tree peak RSS.
- Kept `in_process` as the compatibility and speed default. Invalid backend values
  are blocking validation errors, and the Parameter Sweep page explains the choice.
- Ensemble summaries and Results now separate parent/member-boundary RSS from child
  peak RSS. The benchmark samples the fair parent-plus-live-children process tree.
- Matched real-PySDM 3-member pilots both succeeded. Subprocess reduced first-to-last
  parent RSS from 37.797 MiB to 0.125 MiB (99.669%), confirming process-lifetime
  ownership of the retained memory.
- The tradeoff was unfavorable for a default: wall time increased from 248.725 s
  to 530.714 s (+113.374%), and process-tree peak increase rose from 879.238 MiB
  to 998.867 MiB (+13.606%).
- All 32 unit/integration tests and project integrity passed. Parameter Sweep and
  Results AppTests rendered with zero exceptions and zero error elements.

Decision: keep subprocess opt-in. It controls cross-member retention but does not
lower instantaneous memory or runtime for the tested pilot. The next performance
prototype should use bounded-lifetime warm workers or batches before attempting the
70-execution common-seed standard qualification.

Evidence: [`docs/evidence/ENSEMBLE_EXECUTION_BACKEND_AB_20260715.md`](docs/evidence/ENSEMBLE_EXECUTION_BACKEND_AB_20260715.md)

## Higher-resolution common-seed rain-response update

Completed on 2026-07-15:
- Added `rain_response_pilot` and `rain_response_standard` profiles. The pilot uses
  a 5 s / 800-super-droplet reference and three paired common random seeds; the
  standard plan reaches 2.5 s / 1600 super-droplets and five seeds.
- Ensemble member summaries now preserve every convergence scalar. Sweep results
  store `paired_seed_metrics.csv`, and identical seeds are compared across OFAT
  resolution cases before evidence is pooled.
- Coverage requires every configured seed in every case. Rain-signal gates are also
  evaluated per seed instead of accepting the maximum from any seed.
- The full pilot completed 4 cases, 12 case-seed pairs, and 24/24 physical PySDM
  executions in 956.4 s. All three seeds produced rain.
- Absolute rain state passed 36/36 checks (maximum 2.366%). Seeding response passed
  only 4/63 checks (median 39.093%, maximum 526.314%), so quantitative response
  remains unsupported.
- All 29 tests, project integrity, and an actual-result Results AppTest passed;
  the dashboard rendered the paired-seed evidence with zero errors or exceptions.

Decision: preserve the common-seed workflow, but gate the planned 70-execution
standard run behind process isolation and a targeted high-resolution plan.

Evidence: [`docs/evidence/RAIN_RESPONSE_COMMON_SEED_20260715.md`](docs/evidence/RAIN_RESPONSE_COMMON_SEED_20260715.md)

## Ensemble retained-memory ownership update

Completed on 2026-07-15:
- Added member/stage RSS, USS, GC-object, thread, and open-figure checkpoints to
  reproducible PySDM ensemble benchmarks.
- Added opt-in `gc.collect()` between members and a matched-workload A/B comparison
  CLI. Normal ensemble execution keeps the option disabled.
- Ran two 12-member standard real-PySDM ensembles. Explicit GC reclaimed objects and
  produced 198.676 MiB of cumulative per-event RSS drops, but peak RSS was 0.310%
  worse, first-to-last retained RSS was 1.515% worse, and wall time was 3.772% higher.
- No Matplotlib figures accumulated. Streaming aggregation remained about 0.26 MiB
  incremental RSS in both runs.
- Results Dashboard now exposes raw stage checkpoints and member-boundary RSS/USS
  trends. Machine-readable A/B evidence is preserved with the interpretation rule.

Decision: keep member-boundary GC disabled by default. The result does not support
GC-reclaimable Python cycles as the dominant retained-RSS explanation; the next
performance experiment should isolate PySDM/Numba/backend lifetime at process exit.

Evidence: [`docs/evidence/ENSEMBLE_MEMORY_OWNERSHIP_20260715.md`](docs/evidence/ENSEMBLE_MEMORY_OWNERSHIP_20260715.md)

## Collision-ON rain qualification update

Completed on 2026-07-15:
- Added `rain_pilot` and `rain_standard` qualification profiles that force real
  PySDM collision/coalescence and require non-zero rain-water in both control and
  seeding reference cases.
- Replaced qualification-only 3-axis Cartesian execution with a one-factor-at-
  reference design. A three-level qualification now uses 7 cases / 14 model
  executions instead of 27 cases / 54 executions without removing any comparison
  used by the OFAT convergence decision.
- The full collision-ON run completed all 7 cases in 699 seconds. The finest
  reference produced 0.002558 kg/kg control and 0.002634 kg/kg seeding rain water.
- All 12 absolute rain-state checks passed 5% (maximum 3.285%). Only 2 of 21
  seeding-response checks passed, so the overall result correctly remains
  `not_supported_for_profile` for quantitative seeding-effect claims.
- Results and reports now separate absolute-state convergence from the more
  sensitive seeding-minus-control response and display the required rain-signal gate.

Evidence: [`docs/evidence/RAIN_QUALIFICATION_20260715.md`](docs/evidence/RAIN_QUALIFICATION_20260715.md)

Next priority: prototype bounded-lifetime warm worker batches, then use the measured
resource bounds to target—not blindly launch—the 1600-super-droplet response plan.

## Portable path-budget hardening

The historical `20260714_190022_727349_0714_18_58_parameter_sweep` failure was
caused by every nested ensemble member exceeding the Windows path limit before a
time series could be written. The original compact `case_###/member_###` fix is now
reinforced by an absolute-path budget:

- all result modes reserve space for their deepest known artifact;
- result/scenario names are shortened with a stable hash only when required;
- generated paths target a 240-character portable ceiling rather than relying on
  the 260-character legacy boundary;
- an output root that is already too deep fails before model execution with a clear
  suggestion to choose a shorter result root;
- full run IDs and scientific parameter labels remain in metadata and configuration.

The original failed result contains no recoverable member time series and must be
rerun. Ensemble execution remains supported.

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
1. Test process-per-member isolation for backend/JIT retained memory.
2. Target a bounded 1600-super-droplet common-seed response qualification.
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

1. ensemble member를 child process로 격리해 PySDM/Numba backend RSS가 process 종료 시 회수되는지 측정한다.
2. 격리 benchmark의 자원 한도 안에서 1600-super-droplet common-seed response run을 설계한다.
3. CSV와 수치적으로 동일한 columnar internal cache prototype을 benchmark한다.
4. spectrum transition 1% threshold와 checkpoint 간격을 관측 자료로 보정한다.

## 검증 명령

```powershell
& .\.conda\python.exe -m unittest -v tests.test_native_diagnostics
& .\.conda\python.exe scripts\check_project_integrity.py
```

Streamlit 화면 회귀 검사는 `pages/02_aerosol.py`, `pages/06_run.py`,
`pages/07_results.py`를 대상으로 수행한다.

## 문서 관리 규칙

- `PROJECT_STATUS.md`: 지금 무엇이 되고 있고 바로 다음에 무엇을 하는지 갱신한다.
- `ROADMAP.md`: 단계 순서, 연구 리스크, 완료 조건이 바뀔 때 갱신한다.
- `DEVELOPMENT.md`: 완료된 구현과 검증 결과를 append-only changelog로 남긴다.
- `README.md`: 신규 사용자가 설치하고 실행하는 데 필요한 안정된 사용법만 유지한다.

# Roadmap

## Current milestone snapshot (2026-07-14)

Portable-report and qualification status:
- Every new result writes `report.pdf`, with water-budget, spectrum-transition,
  or numerical-convergence figures embedded when available.
- Ensemble aggregation records both tracemalloc allocation and sampled process RSS.
- The numerical-qualification CLI provides dry-run, `pilot`, and `standard` profiles
  plus a stored `qualification_plan.json`.
- The placeholder pilot is complete. The next scientific gate is a standard
  `pysdm_parcel` qualification and evidence-based tolerance review.

The canonical current-state view is [`PROJECT_STATUS.md`](PROJECT_STATUS.md).
Step 13 native scalar diagnostics, the first Step 14–16 research-quality
bundle, Step 17 instrumented streaming aggregation, Step 18 Markdown/HTML
reporting, and Step 19 result manifests are complete.
Source-aware conservation, numerical convergence, control–seeding spectrum
differences, vector publication export, and legacy-result inference are now
implemented. Spectrum transition onset and threshold-pair timing audits are also
connected to real comparison results. The next priority is full PySDM convergence
evidence and large-ensemble RSS/I/O benchmarking.

`DEVELOPMENT.md`가 "무엇을 했는가"의 기록(changelog)이라면, 이 문서는 "다음에 무엇을,
어떤 순서로 할 것인가"를 관리한다. README.md의 Development Roadmap 섹션은 Step 10까지만
반영된 예전 버전이므로, 최신 우선순위는 항상 이 문서를 기준으로 한다.

## 완료된 단계 (요약)

`DEVELOPMENT.md` Step 0~12에서 스캐폴딩, config schema, validation, 첫 PySDM 연결,
control vs seeding, efficiency metric, parameter sweep, Growth Pathway Diagnostics,
ensemble statistics까지 구축되었다. Step 13 native scalar diagnostic의 첫 구현도 완료되었다.

## 우선순위를 재정렬한 이유

기존에 후보로 나열되어 있던 다음 목록은 순서상 문제가 있었다.

```text
1. Dashboard를 더 논문/발표용으로 정리          <- 먼저 하면 재작업 위험
2. four-panel plot 추가
3. collision OFF / ON 분리 panel 추가
4. Growth Pathway Diagnostics를 더 물리적으로 정교화
5. PySDM native diagnostic extraction 개선      <- 이게 먼저 되어야 함
6. wet radius distribution output 추가
7. cloud-size / rain-size bin diagnostic 추가
8. ensemble large-run 성능 최적화
9. 자동 report export 기능 추가
10. result dashboard에서 old result / new result 호환성 강화
```

문제: 1~3(발표/논문용 plot)을 5(native diagnostic extraction 개선)보다 먼저 하면,
5를 나중에 하면서 diagnostic 계산 방식이 바뀔 때마다 1~3에서 만든 plot을 다시 만들어야
하는 이중작업이 생긴다. 특히 현재 `pysdm_parcel` adapter는 `cloud_water_mixing_ratio`,
`temperature_K`, `rain_droplet_concentration` 등 다수의 pathway 변수를 **PySDM이 직접
출력하지 않아 proxy(근사값)로 채우고 있다** — 이번 업데이트에서 추가된
`diagnostic_provenance.json` / Results Dashboard의 "Growth Pathway Diagnostic
Provenance" 표에서 이를 변수별로 바로 확인할 수 있다. proxy 변수가 남아 있는 상태로
발표용 4-panel plot을 먼저 완성하면, 그 plot에 들어간 곡선 중 상당수가 근사값이라는
것을 재검토해야 한다.

## 재정렬된 순서

```text
Step 13. PySDM native diagnostic extraction 개선          (구 5번, 최우선)
Step 14. Growth Pathway Diagnostics를 더 물리적으로 정교화  (구 4번)
Step 15. Publication-style diagnostic plots                (구 1~3번, 구 Step 13)
Step 16. wet radius / cloud-size / rain-size bin diagnostic (구 6~7번)
Step 17. ensemble large-run 성능 최적화                     (구 8번)
Step 18. 자동 report export 기능 추가                       (구 9번)
Step 19. result dashboard old/new result 호환성 강화        (구 10번)
```

### Step 13. PySDM native diagnostic extraction 개선 (최우선)

**Status: first native scalar-product implementation completed (PySDM 2.131).**

프로젝트 내부 `simulation/native_parcel_simulation.py`가 PySDM parcel builder와
product collection을 소유한다. 설치된 `PySDM_examples` 파일을 수정하지 않고 다음을
직접 출력한다.

- ambient temperature, pressure, water-vapour mixing ratio, relative humidity
- wet-radius 구간별 unactivated/cloud/rain/total liquid-water mixing ratio
- cloud/rain particle concentration
- cloud/rain/all-activated effective radius

기본 wet-radius 구간은 `[0, 0.5 µm)`, `[0.5, 25 µm)`, `[25 µm, ∞)`이며 config와
result metadata에 경계와 half-open convention을 기록한다. 현재 Growth Pathway
contract는 실제 smoke run에서 native 11 / derived 2 / proxy 0이다. 여기서 cloud/rain은
activation history가 아니라 **설정된 wet-radius bin 정의**라는 점을 유지해야 한다.

목표: `diagnostic_provenance.json`에서 `proxy`로 분류되는 변수를 하나씩 `native`로
옮긴다. 마련된 기반:

- `analysis/growth_pathway_diagnostics.classify_diagnostic_provenance()` —
  현재 proxy로 분류되는 변수와 그 이유를 코드 차원에서 명시.
- Results Dashboard → Files & Metadata 탭 → "Growth Pathway Diagnostic Provenance"
  표에서 native/derived/proxy 개수를 바로 확인 가능.

Step 13 대상 변수의 현재 구현 상태:

| 변수 | 현재 상태 | 구현 |
|---|---|---|
| `cloud_water_mixing_ratio` | native | radius-filtered `WaterMixingRatio` |
| `temperature_K` | native | `AmbientTemperature` |
| `water_vapour_mixing_ratio` | native | `AmbientWaterVapourMixingRatio` |
| `rain_droplet_concentration` | native | radius-filtered `ParticleConcentration` |
| `effective_radius_cloud_um` / `effective_radius_rain_um` | native | 구간별 `EffectiveRadius` |

`scripts/diagnose_pysdm_api.py`와 설치된 PySDM 2.131 소스를 확인해 product API를
확정했다. 버전 변경 시 이 진단과 native integration test를 먼저 다시 실행한다.

### Step 14. Growth Pathway Diagnostics 물리적 정교화

**Status: first implementation completed.** 설정 threshold의 0.8/1.0/1.2 배수에 대한
재분할, seeding source window를 분리한 control/seeding total-water 보존성 판정,
finest timestep/NSD reference 기반 OFAT numerical convergence audit을 저장한다.
향후 과제는 장기·고해상도 PySDM 실험으로 기본 tolerance의 경험적 근거를 축적하는 것이다.

### Step 15. Publication-style diagnostic plots (구 Step 13)

**Status: first implementation completed.** 원래는 Step 13~14 이후에 진행할
계획이었지만, 현재도 proxy를 숨기지 않고 각 panel 제목과 footer에 provenance를
표시하는 조건으로 먼저 구현했다. 향후 native extraction이 개선되어도 plot API와
레이아웃은 그대로 두고 provenance 분류만 자연스럽게 갱신된다.

- [x] mean ± std panel
- [x] median + IQR panel
- [x] collision OFF vs ON matched-condition panel
- [x] dry radius / κ / injection time별 OFAT separated plot
- [x] Growth Pathway four-panel plot
- [x] vector export(PDF/SVG)
- [x] screen / journal single-column / double-column style preset

각 plot 하단에 `diagnostic_provenance.json` 기반으로 "이 변수는 native/proxy입니다"
배지를 함께 표시하는 것을 권장 (완전히 native가 아닌 상태에서 발표해야 한다면, 최소한
proxy임을 명시).

### Step 16. wet radius / cloud-size / rain-size bin diagnostic

**Status: second implementation completed.** native wet-radius number spectrum과 liquid-volume
spectrum을 start/injection start/injection end/run end checkpoint에 저장한다. Results
Dashboard에서 single 및 control/seeding case를 확인할 수 있다. seeding-minus-control
spectrum/threshold difference와 activated liquid 중 rain-size liquid fraction 기반 onset을
저장하며, 모든 threshold pair에서 onset shift 방향이 유지되는지도 audit한다. 다음 단계는
1% 기본 threshold와 checkpoint 해상도의 관측·문헌 근거 확정이다.

### Step 17~19

- Step 17 large ensemble 최적화: member dataframe 전체를 동시에 보관하지 않고 member
  CSV를 변수별로 streaming aggregation하는 첫 구현 완료. 통계 결과는 기존 방식과 동일하며,
  peak aggregation memory는 members x timesteps x variables에서 members x timesteps로 줄었다.
  이제 입력 bytes, elapsed time, tracemalloc peak를 자동 저장한다. 다음은 실제 대형 PySDM
  ensemble의 whole-process RSS와 추가 CSV I/O 시간을 benchmark하는 것이다.
- Step 18 자동 report export: Markdown과 self-contained print-friendly HTML 구현 완료.
  다음은 PDF와 publication figure embedding.
- Step 19 old/new result 호환성 강화: versioned `result_manifest.json`, current/legacy/future
  compatibility inspection, legacy type inference, Results 상태 표시까지 첫 구현 완료.
  다음은 실제 schema 변경 시 migration fixture와 변환기를 추가하는 것이다.

## 이번 업데이트에서 추가로 반영된 항목 (참고)

Step 13 착수를 준비하는 과정에서, 리뷰에서 지적된 다른 세 가지도 함께 반영했다.
자세한 내용은 `DEVELOPMENT.md` Step 13 항목과 `analysis/result_files.py`,
`simulation/run_timing.py`를 참고.

- Growth Pathway 변수별 native/derived/proxy 분류 및 표시 (`diagnostic_provenance.json`)
- sweep/ensemble 실행 전 예상 소요 시간 추정 및 대량 실행 경고 (`simulation/run_timing.py`)
- `config.yaml` / `validation_report.json` / `summary.json` / `metadata.json` /
  `diagnostic_health.json` / `diagnostic_provenance.json` 각 파일의 역할을
  코드와 UI에서 함께 설명 (`analysis/result_files.py`)

# Roadmap

`DEVELOPMENT.md`가 "무엇을 했는가"의 기록(changelog)이라면, 이 문서는 "다음에 무엇을,
어떤 순서로 할 것인가"를 관리한다. README.md의 Development Roadmap 섹션은 Step 10까지만
반영된 예전 버전이므로, 최신 우선순위는 항상 이 문서를 기준으로 한다.

## 완료된 단계 (요약)

`DEVELOPMENT.md` Step 0~12에서 스캐폴딩, config schema, validation, 첫 PySDM 연결,
control vs seeding, efficiency metric, parameter sweep, Growth Pathway Diagnostics,
ensemble statistics까지 구축되었다. Step 13은 이 문서에서 정의한다.

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

목표: `diagnostic_provenance.json`에서 `proxy`로 분류되는 변수를 하나씩 `native`로
옮긴다. 이번 업데이트로 마련된 기반:

- `analysis/growth_pathway_diagnostics.classify_diagnostic_provenance()` —
  현재 proxy로 분류되는 변수와 그 이유를 코드 차원에서 명시.
- Results Dashboard → Files & Metadata 탭 → "Growth Pathway Diagnostic Provenance"
  표에서 native/derived/proxy 개수를 바로 확인 가능.

현재 proxy로 분류되는 항목과 필요한 작업 (`simulation/pysdm_parcel_adapter.py`
`_output_to_dataframe()` / `product_mapping` 확장 필요):

| 변수 | 현재 상태 | 필요한 작업 |
|---|---|---|
| `cloud_water_mixing_ratio` | proxy (0으로 기본값) | PySDM 쪽 product 이름 확인 후 `product_mapping`에 추가 |
| `temperature_K` | proxy (liquid water 비례 휴리스틱) | PySDM_examples seeding Simulation의 온도 product 확인 |
| `water_vapour_mixing_ratio` | proxy (qv0 - liquid 역산) | PySDM 쪽 수증기 혼합비 product 확인 |
| `rain_droplet_concentration` | proxy (0/1 지시값) | 강우 방울 수농도 product 확인 |
| `effective_radius_cloud_um` / `effective_radius_rain_um` | proxy/derived (전체 유효반경 재사용) | cloud-only / rain-only 유효반경 product 분리 |

`scripts/diagnose_pysdm_api.py`로 현재 설치된 PySDM/PySDM_examples 버전에서
실제로 사용 가능한 product 이름 목록을 먼저 확인하고 진행할 것.

### Step 14. Growth Pathway Diagnostics 물리적 정교화

Step 13에서 native 데이터가 늘어난 뒤에 진행한다. proxy 근사 공식(예: 온도 추정,
rain 유효반경 재사용)을 실제 물리 계산으로 교체.

### Step 15. Publication-style diagnostic plots (구 Step 13)

Step 13~14 이후에 진행한다. 이 시점에는 대부분의 pathway 변수가 native/derived이므로
발표/논문용 plot을 한 번만 만들면 된다.

- mean ± std panel
- median + IQR panel
- collision OFF vs ON panel
- dry radius / κ / injection time별 separated plot
- Growth Pathway four-panel plot

각 plot 하단에 `diagnostic_provenance.json` 기반으로 "이 변수는 native/proxy입니다"
배지를 함께 표시하는 것을 권장 (완전히 native가 아닌 상태에서 발표해야 한다면, 최소한
proxy임을 명시).

### Step 16~19

기존 문서의 6~10번과 동일. 상세 내용은 실행 시점에 이 문서를 갱신한다.

## 이번 업데이트에서 추가로 반영된 항목 (참고)

Step 13 착수를 준비하는 과정에서, 리뷰에서 지적된 다른 세 가지도 함께 반영했다.
자세한 내용은 `DEVELOPMENT.md` Step 13 항목과 `analysis/result_files.py`,
`simulation/run_timing.py`를 참고.

- Growth Pathway 변수별 native/derived/proxy 분류 및 표시 (`diagnostic_provenance.json`)
- sweep/ensemble 실행 전 예상 소요 시간 추정 및 대량 실행 경고 (`simulation/run_timing.py`)
- `config.yaml` / `validation_report.json` / `summary.json` / `metadata.json` /
  `diagnostic_health.json` / `diagnostic_provenance.json` 각 파일의 역할을
  코드와 UI에서 함께 설명 (`analysis/result_files.py`)

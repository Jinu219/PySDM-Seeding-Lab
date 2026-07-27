# Hygroscopic Response Regime Atlas Refinement v2

## 목적

v1 screen은 162개 격자 조건과 3개 seed로 억제, 부호 전환, 지속 증강
regime의 위치를 빠르게 탐색한다. v2는 같은 물리 질문을 더 긴 적분 시간,
더 작은 timestep, 더 많은 super-droplet과 ensemble로 다시 조사하여
regime 경계와 변수 간 상호작용을 정밀화한다.

이 실험은 이상화된 0-D parcel-model 민감도 실험이다. 현장 강수 증강률이나
운영 효율을 직접 추정하지 않는다.

## v1과 v2 비교

| 항목 | Screen v1 | Refinement v2 |
|---|---:|---:|
| 설계 | 5축 Cartesian | 8축 Latin Hypercube |
| sweep cases | 162 | 512 |
| ensemble seeds | 3 | 10 |
| control/seeding factor | 2 | 2 |
| 총 model runs | 972 | 10,240 |
| 물리시간 | 1,500 s | 2,400 s |
| timestep | 10 s | 5 s |
| background super-droplets | 400 | 800 |
| seed super-droplets | 400 | 800 |
| case workers | 12 | 12 |

v2의 512개 조건은 `sweep.random_seed: 64001`로 결정된다. 같은 시나리오
파일과 코드에서는 동일한 조건과 case index가 다시 생성된다.

## 표본화 변수

| 변수 | 범위 | 표본 척도 |
|---|---:|---|
| updraft velocity | 0.25–1.4 m s⁻¹ | linear |
| background aerosol | 20–1,280 cm⁻³ | log |
| seed number concentration | 1–100 cm⁻³ | log |
| injection start | 60–1,200 s | integer, linear |
| injection duration | 60–300 s | integer, linear |
| seed dry radius | 0.5–2.0 μm | log |
| seed κ | 0.4–1.2 | linear |
| collision–coalescence | OFF/ON | balanced categorical |

Latin Hypercube는 각 연속 변수의 범위를 512개 층으로 나누어 전체 범위를
고르게 덮는다. 따라서 8개 변수의 모든 격자 조합을 계산하지 않고도
다변수 상호작용과 response boundary를 탐색할 수 있다.

## 서버 실행

1. v1 작업이 `succeeded`인지 확인한다.
2. 최신 `develop`을 cloud7에 배포한다.
3. **06. Run Simulation**에서
   `Hygroscopic Response Regime Atlas Refinement v2`를 선택한다.
4. Run Plan에서 다음 값을 확인한다.
   - 512 sweep cases
   - 10 ensemble members
   - control/seeding factor 2
   - 10,240 model runs
   - 12/12 workers
   - blocking error 0
5. detached background job으로 제출한다.
6. **08. Server Jobs**에서 progress, remaining time, worker log를 확인한다.

먼저 전체 v2를 제출하기보다 서버에 기록된 실제 ETA와 메모리 사용량을
확인한다. 12 workers의 메모리가 안정적이면 그대로 overnight run을
진행한다.

## 완료 후 비교 순서

1. v1과 v2 모두 case/member 실패가 없는지 확인한다.
2. water-budget 검사를 통과하지 못한 case를 물리 해석에서 제외한다.
3. suppression, sign reversal, persistent enhancement의 비율을 비교한다.
4. collision OFF/ON에 따라 response boundary가 이동하는지 비교한다.
5. v2에서 updraft, aerosol, seed dose, timing, size, κ의 주효과와
   상호작용을 분석한다.
6. v1의 대표 regime 조건과 가장 가까운 v2 표본을 연결하여 trajectory와
   최종값, signed integral, crossover time을 비교한다.
7. 경계에 가까우며 ensemble 부호 일관성이 낮은 조건을 다음 수치수렴
   실험 후보로 선정한다.

v1과 v2의 case grid는 서로 동일하지 않으므로 case index를 직접 대응시키지
않는다. 물리 변수 공간의 최근접 조건과 regime classification을 기준으로
비교한다.

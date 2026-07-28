# Hygroscopic Collision Response v3

## 결정

v2 refinement는 collision OFF 256개를 모두 완료했지만 collision ON은 256개
중 46개만 완전 성공했고 41개는 부분 성공, 169개는 실패했다. 실패는 약
6 mm wet radius에서 Rogers–Yau terminal-velocity 보간 범위를 넘은
조건이었다. 특히 강한 상승류가 선택적으로 탈락했으므로 결과 누락은
무작위가 아니다.

v3는 collision ON을 본 실험으로 사용한다. Collision OFF는 본 atlas의
절반을 차지하지 않으며, 결과가 나온 뒤 선택한 소수 조건에서만 정확히
짝지은 mechanism ablation으로 사용한다.

현재 `pysdm_parcel` adapter는 `microphysics.collision`을 PySDM의
`enable_collisions`에 연결하지만 `microphysics.sedimentation`은 실제
모델 설정에 연결하지 않는다. 따라서 YAML에서 sedimentation을 `true`로
바꾸는 것만으로 fallout이 생기지 않는다. 본 atlas 전에 giant-drop
domain과 retained-parcel 동역학을 별도로 통과시켜야 한다.

## Gate 0: Collision Safety Pilot v3

저장된 시나리오는 `Hygroscopic Collision Safety Pilot v3`이다.

| 항목 | 설정 |
|---|---:|
| collision | 전 case ON |
| updraft | 0.3, 0.6, 0.9, 1.2 m s⁻¹ |
| background aerosol | 40, 640 cm⁻³ |
| seed dry radius | 0.7, 1.7 µm |
| seed number concentration | 10 cm⁻³ 고정 |
| κ | 0.8 고정 |
| injection | 300–420 s |
| duration / timestep | 1,500 s / 5 s |
| super-droplets | background 800 + seed capacity 800 |
| ensemble | common seeds 3개 |
| 총 실행 | 16 cases × 3 seeds × control/seeding = 96 |

이 pilot은 시딩 효과를 주장하는 실험이 아니다. 목적은 다음 세 가지다.

1. updraft와 background에 따른 failure/partial-success 경계를 찾는다.
2. 1–6 mm 방향으로 spectrum이 이동하는 시점과 조건을 확인한다.
3. 전체 v3 atlas를 실행해도 되는지 결정한다.

### 실행 절차

1. 최신 `develop`을 서버에 배포한다.
2. **06. Run Simulation**에서
   `Hygroscopic Collision Safety Pilot v3`를 선택한다.
3. 16 cases, 3 members, control factor 2, 총 96 model runs인지 확인한다.
4. detached job으로 제출한다.
5. 성공 수만 보지 말고 모든 partial/failed member의 첫 오류와 updraft를
   기록한다.
6. Results에서 rain-water response와 함께 wet-radius spectrum,
   water budget, transition status를 확인한다.

### 통과 조건

- 일반적인 설정·I/O·memory 오류 0개
- pre-injection control/seeding difference 0
- water-budget failure 0
- 각 case 3/3 valid members
- 6 mm Rogers–Yau 오류 0
- 2–3 mm 이상 giant-drop 상태가 나타나면 성공으로 세지 않고
  `model-domain review`로 분류

한 member라도 terminal-velocity 범위를 넘으면 그 조건을 제외하고 큰
atlas를 진행하지 않는다. 실패율이 낮더라도 강한 updraft에 몰려 있으면
missing-at-random으로 취급하지 않는다.

## Gate 1: Collision-ON Atlas v3

Gate 0를 통과하고 fallout/domain 처리가 검토된 뒤에만 생성·실행한다.

- 192-point stratified Latin Hypercube
- collision ON 고정
- 10 common seeds
- paired control/seeding
- 3,840 physical model runs
- 변화축:
  - updraft 0.25–1.4 m s⁻¹
  - background aerosol 20–1,280 cm⁻³, log
  - seed number concentration 1–100 cm⁻³, log
  - seed dry radius 0.5–2.0 µm, log
  - injection stage: pre-transition / near-transition / post-transition
- κ=0.8 및 injection duration=120 s 고정

절대 injection time은 다른 updraft에서 동일한 cloud stage를 뜻하지
않는다. 각 control trajectory에서 transition 상태를 먼저 계산하고
case별 injection time을 고정하거나, adapter가 지원되면 state-based
injection을 사용한다.

주요 분석창은 injection 후 0–900 s이다. 2,400 s 최종값 하나로 순위를
정하지 않는다.

## Gate 2: Exact-paired collision ablation

Atlas 결과에서 다음 24개 조건을 선택한다.

- suppression 중심 8개
- sign-reversal 또는 regime boundary 8개
- enhancement 중심 8개

각 조건은 continuous parameter, injection, ensemble seed를 동일하게
유지하고 collision만 ON/OFF로 바꾼다. 추가 실행은
24 × 10 × control/seeding = 480 model runs이다.

이 단계에서만 `collision이 추가한 response`를 인과적으로 비교한다.

## Gate 3: Numerical qualification

대표·경계 12개 조건에서 다음을 검사한다.

- timestep: 5 s → 2.5 s
- super-droplets: 800+800 → 1,600+1,600
- 가능하면 20 common seeds

Sign reversal은 최종값이 단순히 양수라는 이유로 확정하지 않는다.
ensemble uncertainty, timestep/representation 변화, numerical floor,
crossover-time 재현성을 모두 통과해야 한다.

## Primary estimands

1. injection 후 0–900 s rain-water difference signed integral
2. post-injection minimum과 window-final difference
3. negative-to-positive 및 positive-to-negative crossover time
4. rain-size onset shift
5. 20/25/30 µm threshold robustness
6. maximum wet radius와 1/2/3/6 mm bin 질량분율
7. water budget 및, 구현되는 경우, fallout mass flux
8. exact-paired collision ON−OFF contribution

Trajectory는 다음으로 분류한다.

- sustained suppression
- suppression → recovery
- transient enhancement → late suppression
- persistent enhancement
- neutral/unresolved
- out of model domain

최종 목적은 가장 큰 양의 값을 찾는 것이 아니라, collision ON warm-rain
parcel에서 response 부호와 시간경로가 바뀌는 경계를 찾는 것이다.

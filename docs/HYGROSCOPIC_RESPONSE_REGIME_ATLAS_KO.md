# 심화 실험: Hygroscopic Response Regime Atlas

## 기존 실험과 다른 질문

이전 실험은 다음 질문들을 이미 다뤘다.

- super-droplet 수에 따른 numerical representation sensitivity
- seed dry radius, κ, injection timing의 개별 민감도
- vapour → activation → cloud/rain water growth pathway
- clean/polluted/orographic background와 fixed-number/fixed-mass 비교
- κ × dry radius × injection timing의 고밀도 response-surface 최적화

새 실험은 또 다른 최댓값을 찾지 않는다. 랩미팅용 실험에서 관측된
`초기 rain-water 억제 → 후기 증강`의 부호 전환을 연구 대상으로 삼는다.

> 어떤 updraft, background CCN, seed dose, injection stage에서 hygroscopic
> seeding response가 competition-dominated suppression에서
> collision-assisted enhancement로 전환되는가?

## 가설

### H1. Competition-dominated regime

낮은 updraft, 높은 background aerosol concentration, 높은 seed dose에서는
활성 입자 사이의 수증기 경쟁이 강해져 supersaturation이 빠르게 소모되고,
rain-water response가 음수로 유지될 수 있다.

### H2. Sign-reversal regime

중간 조건에서는 주입 직후 rain water가 감소하지만, 추가된 activated water가
collision-coalescence를 거쳐 rain-size reservoir로 이동하면서 후기에는 양수로
전환될 수 있다.

### H3. Persistent-enhancement regime

충분한 updraft 공급, 낮거나 중간인 background competition, 적절한 seed
dose가 collision ON과 결합되면 주입 후 양의 rain-water response가 지속될 수
있다.

Collision OFF는 rain response를 최적화하는 별도 조건이 아니라, condensation
pathway와 collision-assisted pathway를 분리하기 위한 mechanism control이다.

## 실험 설계

시나리오 이름은 `Hygroscopic Response Regime Atlas Screen v1`이다.

| 축 | 값 | 의미 |
|---|---|---|
| updraft velocity | 0.4, 0.8, 1.2 m s⁻¹ | 수증기 공급 및 cloud growth rate |
| background aerosol | 40, 160, 640 cm⁻³ | clean-to-polluted CCN competition |
| seed number concentration | 2.5, 10, 40 cm⁻³ | low/reference/high seed dose |
| injection start | 60, 300, 900 s | early/developing/mature absolute time |
| injection duration | 120 s | pulse duration 고정 |
| collision | OFF, ON | condensation-only / collision-assisted |

Seed dry radius는 1 µm, κ는 0.8로 고정한다. 기존 κ–radius optimization과
질문을 분리하기 위해 activation-strength 축을 다시 sweep하지 않는다.

- Cartesian cases: 3 × 3 × 3 × 3 × 1 × 2 = 162
- common random seeds: 3
- paired control/seeding: 2
- 총 물리 실행: 162 × 3 × 2 = 972
- case workers: 최대 12
- super-droplets: background 400 + inactive/seed capacity 400

이 실험은 boundary discovery용 screen이다. 세 seed의 평균이나 순위를 최종
근거로 사용하지 않는다.

## 핵심 estimand

단순 `final rain-water difference`만 보면 초기 억제를 놓친다. 각 case와 seed에
대해 다음을 함께 본다.

1. 주입 후 minimum `rain_water_mixing_ratio_diff`
2. final `rain_water_mixing_ratio_diff`
3. signed time integral
4. 음수에서 양수로 바뀐 뒤 다시 음수가 되지 않는 persistent-positive time
5. seed별 final sign consistency
6. `supersaturation`, activated concentration, effective radius의 동반 변화
7. 주입 시점 control의 rain-volume fraction과 transition status

세 가지 trajectory class의 운영 정의는 다음과 같다.

- `suppression`: post-injection final과 signed integral이 모두 음수
- `persistent enhancement`: 유의한 초기 음수 구간 없이 final과 integral이 양수
- `sign reversal`: post-injection minimum은 음수이고 final은 양수

Near-zero case는 별도 `neutral/unresolved`로 남긴다. 수치 noise floor는 이
screening 결과만으로 정하지 않고 후속 numerical qualification에서 결정한다.

## 웹 실행 절차

1. 서버를 시나리오가 포함된 최신 `develop` commit으로 갱신한다.
2. **06. Run Simulation**에서
   `Hygroscopic Response Regime Atlas Screen v1`을 선택한다.
3. run plan을 확인한다.
   - 162 cases
   - 3 ensemble members
   - 972 total model runs
   - 12/12 effective case workers
   - blocking error 0
4. **Run as a detached background job**을 켜고 제출한다.
5. **08. Server Jobs**에서 completed/failed case 수를 확인한다.
6. 실행 중에는 같은 결과 폴더를 복사하거나 Streamlit process를 종료하지 않는다.

## Results에서 보는 순서

### 1. 실행 및 품질

- 162/162 case success
- 각 case 3/3 member success
- pre-injection physical diff = 0
- water-budget status = pass

### 2. Regime slice

한 번에 5차원을 해석하지 않는다. **Case filter**에서 세 축을 고정하고 두 축만
비교한다.

- `background aerosol × seed dose`, updraft/timing/collision 고정
- `updraft × seed dose`, background/timing/collision 고정
- `injection start × background aerosol`, updraft/dose/collision 고정

Collision OFF와 ON은 같은 설정끼리 pairing하여 별도 panel에서 비교한다.

### 3. Time series

대표 suppression, sign-reversal, enhancement case를 각각 하나씩 선택한다.

- `rain_water_mixing_ratio_diff`
- `supersaturation_percent_diff`
- `all_activated_concentration_diff`
- `effective_radius_all_um_diff`

주입 시점에 맞춘 relative time axis로 세 trajectory를 비교한다.

## 해석 제한

- injection start는 절대시간이다. 서로 다른 updraft/background case에서 같은
  300 s가 같은 cloud lifecycle stage라는 보장은 없다.
- 따라서 control의 spectrum-transition 상태를 사용해 주입 당시 parcel을
  post hoc로 분류해야 한다.
- entrainment, sedimentation, spatial dispersion을 포함하지 않는 0-D parcel
  sensitivity이다.
- 세 seed는 regime 후보를 찾기 위한 최소 screen이며 불확실성 확정이 아니다.
- field precipitation enhancement나 operational efficacy로 해석하지 않는다.

## 2단계 확인 실험

Screening이 끝나면 전체 162 case를 더 높은 해상도로 반복하지 않는다.

1. 각 trajectory class의 중심 case 2개씩 선택
2. class boundary에 가까운 case 6개 선택
3. 약 12개 case를 10–20 common seeds로 재실행
4. super-droplet/timestep next-finest numerical qualification 수행
5. response sign과 crossover time의 재현성을 평가

최종 연구 산출물은 “최적 조건 표”가 아니라 cloud regime에 따른 response
trajectory phase map과 확인된 경계 조건이다.

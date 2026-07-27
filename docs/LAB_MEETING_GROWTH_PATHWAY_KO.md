# 랩미팅 실험: 흡습성 시딩의 성장 경로

## 발표의 한 문장

PySDM Seeding Lab은 같은 초기조건과 난수 seed를 공유하는 control/seeding
parcel simulation을 반복 실행하고, 시딩 입자가 활성화·응결 성장·충돌 병합을
거쳐 rain-size 물방울로 전이하는 과정을 재현 가능한 실험 묶음과 plot으로
비교하는 연구 workflow이다.

이 발표에서 답할 질문은 다음과 같다.

> 같은 수농도로 주입한 흡습성 입자의 초기 건조 반경이 달라질 때,
> collision-coalescence의 유무는 활성화 이후 유효반경과 rain water response를
> 어떻게 바꾸는가?

## 실험 설계

- 시나리오: `Lab Meeting Growth Pathway v1`
- 실제 계산기: `pysdm_parcel`
- seed dry radius: 0.5, 1.0, 2.0 µm
- collision-coalescence: OFF, ON
- 설계: 3 × 2 Cartesian sweep, 총 6 cases
- 불확실성: case마다 동일한 5개 random seed를 control/seeding에 공통 적용
- 물리 실행 수: 6 cases × 5 members × control/seeding = 60 runs
- 병렬화: 독립 case 6개를 최대 6 workers로 실행
- 시딩 시간: 900–1200 s
- 전체 시간: 0–1500 s, timestep 10 s

건조 반경만 바꾸되 수농도는 10 cm⁻³로 고정했다. 따라서 반경이 커질수록
주입되는 건조 질량도 함께 증가한다. 이 결과는 순수한 크기 효과가 아니라
`size–dose coupled sensitivity`로 설명해야 한다.

## 웹에서 실행

1. 서버의 저장소를 paired-control 수정이 포함된 최신 commit으로 갱신한다.
2. Streamlit을 시작하고 SSH tunnel로 웹에 접속한다.
3. **06. Run Simulation**으로 이동한다.
4. **Scenario to run**에서 `Lab Meeting Growth Pathway v1`을 선택한다.
5. run plan이 `6 cases`, `5 ensemble members`, `60 total model runs`,
   `6/6 workers`인지 확인한다.
6. blocking validation error가 0인지 확인한다.
7. **Run as a detached background job**을 켠 뒤 **Submit Background Job**을 누른다.
8. **08. Server Jobs**에서 완료 여부와 실패 case 수를 확인한다.
9. **07. Results**에서 `lab_meeting_growth_pathway_v1` 결과를 선택한다.

기존 pilot 결과는 paired-control 수정 전 결과이므로 발표 그림으로 재사용하지
않는다. 반드시 이 시나리오를 최신 코드에서 다시 실행한다.

## plot을 읽는 순서

모든 `*_diff`는 다음 정의를 사용한다.

```text
diff = seeding - paired control
```

곡선 번호의 물리 설정은 plot 아래 case legend table에서 확인한다. 선 하나만
보고 반경이나 collision 설정을 추측하지 않는다.

### 1. 주입 전 동등성: 0–900 s

먼저 모든 물리 `diff`가 0인지 확인한다. 이것은 과학적 결론이 아니라
paired-control 품질검사이다. 주입 전 차이가 보이면 시딩 효과로 해석하지 말고
실행 commit과 결과를 점검한다.

### 2. 활성화와 수증기 경쟁: 900–1200 s

- `all_activated_concentration_diff`: 새로 활성화된 물방울 수의 변화
- `cloud_droplet_concentration_diff`: cloud-size population의 변화
- `supersaturation_percent_diff`: 추가 입자가 수증기를 소비하면서 생기는
  supersaturation response
- `water_vapour_mixing_ratio_diff`: 기체상 물의 변화
- `cloud_water_mixing_ratio_diff`: 응결로 cloud-size 물에 배분된 변화

발표에서는 한 plot의 부호만 결론으로 삼지 않고, 농도 증가 → supersaturation
및 수증기 변화 → cloud water 변화가 시간적으로 연결되는지 본다.

### 3. 성장과 rain-size 전이: 1200–1500 s

- `effective_radius_all_um_diff`: 활성 물방울 집단의 대표 크기 변화
- `rain_water_mixing_ratio_diff`: 25 µm threshold 이상의 액체 물 변화
- `all_activated_water_mixing_ratio_diff`: 활성화된 전체 액체 물 변화

`effective_radius`와 `rain water`가 같은 방향으로 움직인다고 가정하지 않는다.
작은 물방울 수가 늘면 활성화 농도는 증가하면서 대표 반경은 감소할 수 있다.
반대로 collision ON에서 큰 물방울 꼬리가 형성되면 rain water가 민감하게
반응할 수 있다.

### 4. collision OFF/ON 비교

**Publication Plots → Collision OFF / ON Panel**에서 같은 dry radius끼리
짝지어진 결과를 비교한다.

- OFF: 활성화와 응결 성장 중심의 경로
- ON: 위 경로에 stochastic collision-coalescence를 추가
- ON−OFF의 차이: 이 parcel 설정에서 충돌 병합 경로가 결과에 기여한 정도

이는 실제 구름에서의 강수 증가율이나 살포 성공률이 아니다. 0-D parcel,
이상화된 균일 주입, entrainment·sedimentation 미사용이라는 범위 안의
mechanism sensitivity이다.

## 발표용 figure 네 장

1. **Dashboard / Sweep overlay**  
   `supersaturation_percent_diff`, `all_activated_concentration_diff`,
   `effective_radius_all_um_diff`, `rain_water_mixing_ratio_diff`를 선택한다.
   발표의 시간 순서를 한 화면에서 보여준다.
2. **Publication Plots / Selected-case Growth Pathway Four-panel**  
   1.0 µm, collision ON case를 대표 case로 사용한다.
3. **Publication Plots / Collision OFF / ON Panel**  
   세 반경에서 collision 경로가 response를 어떻게 바꾸는지 비교한다.
4. **Publication Plots / Ensemble Uncertainty Four-panel**  
   mean ± std 또는 median/IQR을 함께 보여 단일 난수 실현을 일반화하지 않는다.

가능하면 마지막 보조자료에 **Wet-radius Spectrum**의 900, 1050, 1200,
1500 s checkpoint를 넣어 분포의 큰 반경 꼬리가 실제로 이동했는지 확인한다.

## 7분 발표 흐름

1. **문제 제기 (40초)**  
   “시딩 입자를 넣었다”에서 끝나지 않고 활성화부터 rain-size 전이까지 어느
   microphysical pathway가 달라졌는지 추적하겠다고 설명한다.
2. **Lab 소개 (60초)**  
   scenario 저장, paired control, parameter sweep, common-seed ensemble,
   server job, diagnostics/report까지 하나의 재현 가능한 workflow라고 설명한다.
3. **실험 설계 (60초)**  
   3 radii × collision OFF/ON × 5 seeds와 60 runs를 제시한다.
4. **시간 경로 plot (120초)**  
   0–900 s 품질검사, 900–1200 s 활성화, 1200–1500 s 성장 순서로 읽는다.
5. **collision panel과 uncertainty (120초)**  
   collision 경로의 기여와 ensemble spread를 함께 설명한다.
6. **한계와 다음 실험 (60초)**  
   size–dose 결합, 작은 ensemble, 0-D parcel, 외부 관측 미보정을 명시한다.

## 결론 문장 템플릿

> 이 실험은 특정 조건에서 hygroscopic seed size와 collision-coalescence가
> activation-to-growth pathway에 어떤 sensitivity를 만드는지 보여준다.
> 결과는 paired control과 common-seed ensemble에 기반한 model response이며,
> 정량적 cloud-seeding efficacy나 현장 강수 증대의 증거로 해석하지 않는다.

다음 연구 질문은 수농도 대신 총 건조 질량을 고정한 비교와, ensemble 수 및
super-droplet 해상도를 늘렸을 때 response의 방향과 크기가 유지되는지이다.

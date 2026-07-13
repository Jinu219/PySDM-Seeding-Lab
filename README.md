# PySDM Seeding Lab

PySDM 기반 cloud seeding simulation을 앱처럼 실행하기 위한 연구용 프로젝트 skeleton입니다.

## 목적

- PySDM 내부 코드를 직접 계속 수정하지 않고, YAML configuration으로 실험 조건을 관리합니다.
- Streamlit 화면에서 환경 조건, aerosol 조건, seeding 조건, dynamic parameter를 입력합니다.
- Control / Seeding / Sensitivity experiment를 실행하고 결과를 `results/`에 저장합니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 현재 구조

```text
pysdm-seeding-lab/
├── app.py
├── pages/
├── configs/
├── simulation/
├── analysis/
├── experiments/
└── results/
```

## 개발 순서

1. `configs/default.yaml`에서 기본 실험 조건 정의
2. `simulation/config.py`에서 설정 파일 로드
3. `simulation/validation.py`에서 입력값 검증
4. `simulation/pysdm_adapter.py`에서 PySDM 실행 코드 연결
5. `analysis/metrics.py`에서 결과 지표 계산
6. `pages/06_results.py`에서 결과 시각화

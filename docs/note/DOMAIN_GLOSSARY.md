# 도메인 용어 정리

## 설비 구성

이 프로젝트는 **롤러(회전체) 기반 연속공정 라인**의 설비 모니터링 시스템.
제철/제지/필름 등 롤러가 연속 회전하면서 제품을 이송하는 산업에서 사용.

```
[제품 이송 방향 →]

  ──────────────────────────────────
        R1          R2          R3          R4
       (롤러)      (롤러)      (롤러)      (롤러)
       ┌──┐        ┌──┐        ┌──┐        ┌──┐
       │  │        │  │        │  │        │  │
       └──┘        └──┘        └──┘        └──┘
     PULSE+VIB   PULSE+VIB   PULSE+VIB   PULSE+VIB
      센서         센서         센서         센서
```

- **R1~R4**: 4개 롤러에 각각 센서가 부착됨
- 각 센서는 **PULSE 데이터**와 **VIB 데이터**를 동시에 수집

---

## 센서 데이터

### PULSE (펄스)

롤러 표면에 새겨진 패턴을 센서가 감지할 때마다 발생하는 **신호 간격(마이크로초)**.

```
롤러 표면:  ──▮──────▮──────▮──────▮──  (▮ = 패턴)
센서 감지:    ↑        ↑        ↑        ↑
간격(μs):     5507     6228     5028     7887
```

- **간격이 짧으면** → 빨리 회전 (RPM 높음)
- **간격이 길면** → 느리게 회전 (RPM 낮음)
- 이 간격 데이터로 **RPM**, **MPM**을 계산

#### CSV 포맷
```
timestamp, [{'pulse': 5507, 'accel_x': 0.08, 'accel_y': 0.98, 'accel_z': 0.02}, ...]
```
- 한 줄 = 1 사이클 (약 5초 측정 구간)
- 사이클당 5~15개 펄스 + 가속도 데이터

### VIB (Vibration, 진동)

롤러에 부착된 **가속도계(ADXL355)**가 측정하는 진동 가속도 데이터.

```
정상 상태:   ~~~~ (±0.1g 이내, 잔잔한 파형)
이상 상태:   ∿∿∿∿ (0.3g 초과, 큰 진폭) → 고진동 이벤트
```

- **고진동(>0.3g)**: 베어링 마모, 편심, 정렬 불량 등 설비 이상 징후
- 샘플링: **1000Hz** (초당 1000회 측정)
- 사이클당 약 **5,000개** 데이터 포인트

#### CSV 포맷
```
timestamp, [{'accel_x': 0.07, 'accel_z': 0.02}, {'accel_x': 0.08, 'accel_z': 0.03}, ...]
```
- 한 줄 = 1 사이클
- X축(수평), Z축(수직) 가속도만 기록 (Y축 없음)

---

## 계산 지표

### RPM (Revolutions Per Minute, 분당 회전수)

펄스 간격으로 계산하는 롤러 회전 속도.

```
RPM = (60 / 2π) × (pattern_width / (radius × pulse_duration/1000)) × 1000
```

- `shaft_dia`: 샤프트 직경 (기본 50mm)
- `pattern_width`: 패턴 간격 (기본 10mm)
- `target_rpm`: 목표 RPM (기본 100)

### MPM (Meters Per Minute, 분당 미터)

롤러 표면 속도. RPM에서 변환.

```
MPM = RPM × π × roll_diameter / 1000
```

- `roll_diameter`: 롤러 직경 (140mm, shaft_dia와 다름)

### Expected Pulse Count (예상 펄스 수)

5초 샘플링 구간에서 예상되는 펄스 수.
실제 펄스 수가 예상 대비 **±10%** 이내면 유효(valid)로 판정.

```
유효:   실제 5개, 예상 5개 → 오차 0% → ✓ valid
무효:   실제 2개, 예상 5개 → 오차 60% → ✗ invalid (스킵)
```

무효 사이클은 센서 오작동, 설비 정지 등의 이유로 발생.

---

## 설비 상태 판정

| 지표 | 정상 | 주의 | 경고 |
|------|------|------|------|
| RPM 편차 | ±10% 이내 | ±20% 이내 | ±30% 초과 |
| 진동 (g) | <0.1g | 0.1~0.3g | >0.3g |

---

## 디바이스 매핑

| MAC 주소 | 세션명 | 설명 |
|----------|--------|------|
| `0013A20041F71B01` | R1 | 롤러 1 |
| `0013A20041F9D466` | R2 | 롤러 2 |
| `0013A20041F98275` | R3 | 롤러 3 |
| `0013A20041F9D4F8` | R4 | 롤러 4 |

---

## 데이터 저장 구조

DB와 CSV 파일이 역할을 분리하여 데이터를 관리한다.

### DB 저장 (t_cycle 테이블) — 집계값만

| 구분 | 컬럼 | 설명 |
|------|------|------|
| RPM/MPM | rpm_mean, rpm_min, rpm_max, mpm_mean, mpm_min, mpm_max | 사이클별 통계 |
| 진동 | max_vib_x, max_vib_z | X/Z축 가속도 최대 절대값 |
| 진동 | high_vib_event | 0.3g 초과 여부 (0 또는 1) |
| 메타 | duration_ms, set_count, expected_count, is_valid | 사이클 유효성 |
| 추적 | source_path | 원본 CSV 파일 경로 |

- 전체 배열 데이터(수천 포인트)는 DB에 저장하지 않음
- 목록 조회, KPI 통계 등에 사용

### CSV 파일 — raw 배열 데이터

| 파일 | 배열 데이터 | 용도 |
|------|------------|------|
| PULSE_*.csv | pulse_timeline, accel_x/y/z, rpm_data | RPM 차트, 펄스 가속도 차트 |
| VIB_*.csv | accel_x, accel_z (사이클당 ~5000개) | Vibration 파형 차트 |

- API 조회 시 `source_path` 기반으로 원본 CSV에서 on-demand 로드
- **CSV 원본 파일이 없으면 차트 배열 데이터를 볼 수 없음**

### 조회 흐름

```
프론트 → GET /cycles/daily?month=2603&date=260301
  ↓
DB에서 사이클 목록 + 집계값 조회
  ↓
각 사이클의 source_path로 원본 CSV 참조
  ↓
PULSE CSV → rpm_timeline, rpm_data, pulse_accel_x/y/z
VIB CSV   → vib_accel_x, vib_accel_z
  ↓
집계값 + raw 배열을 합쳐서 DailyDataResponse로 응답
```

---

## 데이터 흐름 요약

```
센서 (R1~R4)
  ↓ 5초마다 측정
CSV 파일 (PULSE_YYMMDD.csv, VIB_YYMMDD.csv)
  ↓ 프론트에서 업로드 / 경로 지정
CSV 파싱 + RPM/MPM 계산 + 유효성 검증
  ↓
SQLite DB (집계값: rpm_mean, mpm_mean, duration, 진동 이벤트)
  ↓
통계 조회 (가동시간, 이벤트 횟수 등)
차트 렌더링 (RPM 타임라인, VIB 파형 — 원본 CSV에서 직접 읽기)
```

### 분포 통계

| 항목 | 계산 | 설명 |
| --- | --- | --- |
| **rms** | √(평균(x²)) | 전체 에너지 크기 (진동 강도 대표값) |
| **peak** | max(|x|) | 절대 최대값 |
| **min** | min(x) | 최소값 (방향 포함) |
| **max** | max(x) | 최대값 (방향 포함) |
| **q1** | 25th percentile of |x| | 하위 25% 경계 |
| **median** | 50th percentile of |x| | 중앙값 |
| **q3** | 75th percentile of |x| | 상위 25% 경계 |

### Threshold 초과 분석 (기본 0.1g)

| 항목 | 계산 | 설명 |
| --- | --- | --- |
| **exceed_count** | |x| > 0.1g인 샘플 수 | 고진동 발생 횟수 |
| **exceed_ratio** | exceed_count / 전체 샘플 수 | 고진동 비율 (0~1) |
| **exceed_duration_ms** | exceed_count / 1000Hz × 1000 | 고진동 총 시간 (ms) |

### 이벤트 분류 (Burst vs Peak Impact)

threshold 초과 **연속 구간**을 찾아서:

| 항목 | 기준 | 의미 |
| --- | --- | --- |
| **burst_count** | 연속 ≥ 500ms | 지속 진동 (설비 이상 의심) |
| **peak_impact_count** | 연속 < 500ms | 순간 충격 (충돌, 이물질 등) |
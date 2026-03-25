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

롤러 표면에 새겨진 패턴을 **광학 센서(포토센서)**가 감지할 때마다 발생하는 **신호 간격(마이크로초)**.

```
롤러 표면:  ████    ████    ████    ████   (████ = 반사 패턴, pattern_width=10mm)
            ────────────────────────────
                     ↑
              광학 센서 (고정 위치)
              반사/비반사 감지 → 펄스 신호 생성
```

```
센서 감지:    ↑        ↑        ↑        ↑
간격(μs):     5507     6228     5028     7887
```

- 패턴이 센서 앞을 지나감 → **반사** → 펄스 ON
- 패턴 사이 빈 공간 → **비반사** → 펄스 OFF
- **간격이 짧으면** → 빨리 회전 (RPM 높음)
- **간격이 길면** → 느리게 회전 (RPM 낮음)
- 이 간격 데이터로 **RPM**, **MPM**을 계산
- `shaft_dia`(축 지름)와 `pattern_width`(패턴 폭)를 알아야 펄스 간격 → RPM 변환 가능

#### 측정 주기
- **10분 간격**으로 센서가 동작
- 1회 측정 시 **5초간** 데이터 수집 → CSV에 1줄(1사이클)로 기록
- 5초는 **센서 펌웨어에서 정해진 값** (소프트웨어에서 변경 불가)

#### CSV 포맷
```
timestamp, [{'pulse': 5507, 'accel_x': 0.08, 'accel_y': 0.98, 'accel_z': 0.02}, ...]
```
- 한 줄 = 1 사이클 (5초 측정 구간)
- 사이클당 5~15개 펄스 + 가속도 데이터

### VIB (Vibration, 진동)

롤러에 부착된 **가속도계(ADXL355)**가 측정하는 진동 가속도 데이터.

```
정상 상태:   ~~~~ (±0.1g 이내, 잔잔한 파형)
이상 상태:   ∿∿∿∿ (0.3g 초과, 큰 진폭) → 고진동 이벤트
```

- **고진동(>0.3g)**: 베어링 마모, 편심, 정렬 불량 등 설비 이상 징후
- 샘플링: **1000Hz** (초당 1000회 측정)
- 사이클당 약 **5,000개** 샘플 포인트 (1000Hz × 5초)
- "포인트" = 1개 측정 시점의 가속도 값 (샘플 포인트)

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
- `pulse_duration`: purse간 시간간격

### MPM (Meters Per Minute, 분당 미터)

롤러 표면 속도. RPM에서 변환.

```
MPM = RPM × π × roll_diameter / 1000
```

- `roll_diameter`: 롤러 직경 (140mm, shaft_dia와 다름)

### Expected Pulse Count (예상 펄스 수)

RPM 평균값으로 계산한 **이론적 펄스 수**. DB에 `expected_count`로 저장 (참고용).

```
pulse_width = pattern_width / (rpm_mean / 9.549 / 1000) / (shaft_dia / 2) × 1000  (μs)
expected_count = ceil(5,000,000 / pulse_width)
```

예: RPM=100, shaft_dia=50, pattern_width=10 → "이 속도로 5초간 돌리면 펄스 N개"

실측값 `set_count`와 비교하면 데이터 품질 판단 가능.
(이전에는 `is_valid` 플래그로 DB에 저장했으나, tolerance가 유동적이므로 제거됨. 필요 시 조회 시점에 동적 계산.)

---

## 설비 상태 판정

| 지표 | 정상 | 주의 | 경고 |
|------|------|------|------|
| RPM 편차 | ±10% 이내 | ±20% 이내 | ±30% 초과 |
| 진동 (g) | <0.1g | 0.1~0.3g | >0.3g |

---

## 디바이스 매핑

| MAC 주소 (device) | 디바이스명 (device_name) | 설명 |
|--------------------|--------------------------|------|
| `0013A20041F71B01` | R1 | 롤러 1 |
| `0013A20041F9D466` | R2 | 롤러 2 |
| `0013A20041F98275` | R3 | 롤러 3 |
| `0013A20041F9D4F8` | R4 | 롤러 4 |

- `device`: 센서 MAC 주소 (하드웨어 식별자)
- `device_name`: 사람이 읽기 쉬운 별칭 (R1/R2/R3/R4)
- 설정 키: `device_name_map` (이전: `device_session_map`)

---

## 데이터 저장 구조

PostgreSQL에 집계값 + 원시 파형을 모두 저장. CSV 파일 의존성 없음.

### t_cycle — 사이클별 집계값

| 구분 | 컬럼 | 설명 |
|------|------|------|
| 메타 | timestamp, date, month, device, device_name, cycle_index | 사이클 식별 |
| RPM/MPM | rpm_mean, rpm_min, rpm_max, mpm_mean, mpm_min, mpm_max | 사이클별 통계 |
| 진동 피크 | max_vib_x, max_vib_z | X/Z축 가속도 최대 절대값 |
| 메타 | duration_ms, set_count, expected_count | 사이클 메타데이터 |
| 통계 | pulse_x_rms, vib_z_peak, burst_count 등 | 축별 진동 통계 (50개 컬럼) |

- `high_vib_event` 컬럼은 제거됨 → 조회 시 `max_vib_x > vib_threshold`로 동적 계산
- `is_valid` 컬럼은 제거됨 → tolerance가 유동적이므로 필요 시 동적 계산

### t_vib_waveform — VIB 원시 파형 (BYTEA)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| cycle_id | INTEGER FK | t_cycle 참조 |
| accel_x | BYTEA | X축 가속도 배열 (float → 바이너리) |
| accel_z | BYTEA | Z축 가속도 배열 (float → 바이너리) |
| sample_count | INTEGER | 샘플 수 (보통 5,000) |

- TOAST 자동 압축: 40KB 원본 → ~15-20KB 저장
- 메인 테이블 조회 시 파형 컬럼을 SELECT하지 않으면 I/O 없음

### 조회 흐름

```
프론트 → GET /cycles/daily?month=2603&date=260301
  ↓
t_cycle에서 사이클 목록 + 집계값 조회
  ↓
t_vib_waveform에서 파형 배열 조회 (필요 시)
  ↓
DailyDataResponse로 응답 (CSV 파일 참조 없음)
```

---

## 데이터 흐름 요약

```
센서 (R1~R4)
  ↓ 10분 간격, 5초간 측정
CSV 파일 (PULSE_YYMMDD.csv, VIB_YYMMDD.csv)
  ↓ 프론트에서 업로드 / 경로 지정
CSV 파싱 + RPM/MPM 계산 + 진동 통계 계산
  ↓
PostgreSQL DB
  ├── t_cycle: 집계값 (rpm_mean, mpm_mean, 진동 stats)
  └── t_vib_waveform: VIB 원시 파형 (BYTEA)
  ↓
통계 조회 (가동시간, 고진동 이벤트 등 — 동적 계산)
차트 렌더링 (RPM 타임라인, VIB 파형 — DB에서 조회)
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
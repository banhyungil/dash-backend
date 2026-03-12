# Day Viewer - Daily Roll Data Viewer

하루 단위 롤 데이터 뷰어 (Expected 필터링 적용)

## 주요 기능

- **Expected 필터링**: RPM mean 기반 expected pulse count 계산 후 10% tolerance 내의 사이클만 표시
- **세션 통합**: r1~r4 세션을 timestamp 순서로 병합하여 연속된 타임라인으로 표시
- **RPM Timeline**: 연속된 RPM 데이터 시각화
- **Vibration View**: Pulse accelerometer + VIB accelerometer 연속 표시
- **캐시 재사용**: 기존 viewer의 캐시 및 데이터 폴더 재사용

## 프로젝트 구조

```
day_viewer/
├── backend/
│   ├── main.py                      # FastAPI app (port 8001)
│   ├── config.py                    # 설정 (DATA_DIR, CACHE_DIR)
│   ├── routers/
│   │   └── data_router.py          # API endpoints
│   └── services/
│       ├── expected_filter.py      # Expected 계산 로직
│       └── session_merger.py       # 세션 병합 로직
└── frontend/
    ├── package.json
    ├── src/
    │   ├── App.tsx                 # 메인 앱
    │   ├── pages/
    │   │   └── DateSelector.tsx   # 날짜 선택 페이지
    │   ├── components/
    │   │   ├── RpmChart.tsx        # RPM 타임라인 차트
    │   │   └── VibrationChart.tsx  # 진동 차트
    │   └── api/
    │       └── client.ts           # API 클라이언트
```

## Expected 필터링 로직

```python
# Expected pulse count 계산
expected_count = CEILING(SAMPLING_TIME_US / pulse_width)

# 10% tolerance 검증
deviation = abs(set_count - expected_count) / expected_count
is_valid = deviation <= 0.1
```

## 시간 계산

### 세션 병합
- r1~r4 세션의 모든 사이클을 timestamp 기준으로 정렬
- 연속된 타임라인 생성 (cycle 간 0.1초 gap)

### Pulse + VIB 병합
- Pulse accelerometer: 먼저 측정 (pulse_timeline 사용)
- VIB accelerometer: Pulse 이후 측정 (1000Hz sampling rate)
- VIB offset = pulse_duration + vib_time

## 실행 방법

### 1. Backend 실행

```bash
cd /home/jsw/code/day_viewer/backend
python main.py
```

Backend: http://localhost:8001
API Docs: http://localhost:8001/docs

### 2. Frontend 실행

```bash
cd /home/jsw/code/day_viewer/frontend
npm install
npm run dev
```

Frontend: http://localhost:3001

## API Endpoints

### GET /api/months
사용 가능한 월 목록

### GET /api/devices?month={month}
특정 월의 디바이스 목록

### GET /api/dates?month={month}&device={device}
특정 월/디바이스의 날짜 목록

### GET /api/daily-data?month={month}&date={date}&device={device}
일일 데이터 (Expected 필터링 적용)

**응답 예시:**
```json
{
  "date": "2601-01",
  "device": "AA:BB:CC:DD:EE:FF",
  "settings": {
    "shaft_dia": 50.0,
    "pattern_width": 10.0,
    "target_rpm": 100.0
  },
  "cycles": [
    {
      "timestamp": "2026-01-01 10:00:00",
      "session": "r1",
      "cycle_index": 0,
      "rpm_mean": 98.5,
      "rpm_timeline": [...],
      "rpm_data": [...],
      "set_count": 95,
      "expected_count": 100,
      "timeline_offset": 0.0,
      "pulse_accel_x": [...],
      "vib_accel_x": [...],
      ...
    }
  ],
  "total_cycles": 42
}
```

## 모듈 설명

### Backend

#### `services/expected_filter.py`
- `calculate_expected_pulse_count()`: Expected pulse count 계산
- `is_expected_valid()`: 10% tolerance 검증

#### `services/session_merger.py`
- `merge_sessions_by_timestamp()`: 세션 병합
- `calculate_continuous_timeline()`: 연속 타임라인 오프셋 계산

#### `routers/data_router.py`
- `/api/daily-data`: 메인 API - expected 필터링 및 세션 병합

### Frontend

#### `components/RpmChart.tsx`
- RPM timeline 시각화
- Target RPM 대시라인
- 색상 코딩 (deviation 기준)

#### `components/VibrationChart.tsx`
- Pulse accelerometer (X, Y, Z)
- VIB accelerometer (X, Z)
- 시간 순서대로 연속 표시

## 데이터 흐름

1. 날짜 선택 (DateSelector)
2. API 호출: `/api/daily-data`
3. Backend:
   - CSV 파싱 (캐시 사용)
   - RPM 계산
   - Expected 검증 (10% tolerance)
   - 세션 병합 (timestamp 정렬)
   - 연속 타임라인 계산
4. Frontend:
   - 탭별 차트 렌더링
   - RPM: 연속 RPM 타임라인
   - Vibration: Pulse + VIB 연속 표시

## 향후 확장

프로토타입이므로 다음 기능들을 추가할 수 있습니다:

- [ ] 다양한 그래프 디자인 (산점도, 히트맵, 등)
- [ ] FFT/Spectrogram 옵션 추가
- [ ] Expected tolerance 조정 UI
- [ ] 데이터 필터링 옵션 (날짜 범위, 세션 선택)
- [ ] 데이터 export 기능 (CSV, Excel)
- [ ] 실시간 업데이트 기능
- [ ] 다중 디바이스 비교

# daily API 파형 데이터 분리

## Context
`/api/cycles/daily`가 모든 사이클의 원시 파형(수천 포인트 × N개)을 한 번에 반환.
실제로 파형을 쓰는 건 VibrationChart 1개뿐이고, 나머지 5개 컴포넌트는 stats만 사용.
파형을 별도 API로 분리하여 응답 크기 감소 + 필요 시만 로딩(lazy loading).

## 현재 파형 사용 현황

| 컴포넌트 | 파형 데이터 | stats |
|----------|:---------:|:-----:|
| VibrationChart | O (pulse_timeline, pulse_accel_*, vib_accel_*) | - |
| CycleDetailModal | O (별도 detail API로 이미 분리됨) | - |
| RpmChart | - | O |
| RpmChart3Panel | - | O |
| VibrationChart3Panel | - | O |
| KpiCards | - | O |

## 변경

### 백엔드: `services/daily_data_service.py`
- `build_daily_data()`에서 `_load_pulse_arrays()`, `_load_vib_arrays()`, `_apply_gravity_correction()` 제거
- `_EMPTY_ARRAYS` 상수 제거
- `find_by_date()` 결과를 직접 사용 (stats + 집계값만)
- `_attach_stats()`, `calculate_continuous_timeline()`은 유지
- 미사용 import 제거: `find_pulse_waveform`, `find_vib_waveform`, `process_pulse_compact_to_rpm`

### 백엔드: 새 API `/api/cycles/daily/waveforms`
- `routers/cycles.py`에 엔드포인트 추가
- `daily_data_service.py`에 `build_daily_waveforms(month, date)` 함수 추가
- 기존 `_load_pulse_arrays()` + `_load_vib_arrays()` + `_apply_gravity_correction()` 로직 이동
- 반환: `{ cycles: [{ id, device_name, cycle_index, rpm_timeline, rpm_data, mpm_data, pulse_timeline, pulse_accel_*, vib_accel_* }] }`

### 프론트: `api/cycles.ts`
- `fetchDailyWaveforms(month, date)` 추가

### 프론트: `api/types.ts`
- `CycleData`에서 파형 필드를 optional로 변경 또는 별도 `WaveformData` 타입 분리

### 프론트: `pages/ChartsPage.tsx`
- VibrationChart 탭 선택 시에만 waveforms API 호출 (useQuery + enabled)

### 프론트: `components/VibrationChart.tsx`
- props로 waveform 데이터를 별도로 받거나, 내부에서 useQuery로 조회

## 변경 파일
| 파일 | 변경 |
|------|------|
| `services/daily_data_service.py` | build_daily_data 경량화, build_daily_waveforms 추가 |
| `routers/cycles.py` | `/api/cycles/daily/waveforms` 엔드포인트 추가 |
| `src/api/cycles.ts` | fetchDailyWaveforms 추가 |
| `src/api/types.ts` | WaveformData 타입 추가, CycleData에서 파형 필드 분리 |
| `src/pages/ChartsPage.tsx` | VibrationChart에 waveform 별도 전달 |
| `src/components/VibrationChart.tsx` | waveform props 수정 |

## 검증
1. `npx pyright` — 0 errors
2. `npx tsc --noEmit` — 0 errors
3. `pytest` — 통과
4. 브라우저: RpmChart, RpmChart3Panel, VibrationChart3Panel, KpiCards — 정상 (파형 없이 동작)
5. 브라우저: VibrationChart 탭 선택 시 파형 로딩 후 차트 정상 렌더링
6. 브라우저: CycleDetailModal — 기존대로 정상 (별도 API라 영향 없음)

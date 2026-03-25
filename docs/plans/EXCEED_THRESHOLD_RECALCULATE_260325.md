# exceed threshold 설정화 + 배치 재계산

## Context
현재 `vibration_analyzer.py`의 `analyze_axis()`가 threshold=0.1로 하드코딩되어 있고,
DB 설정의 `vib_threshold`(0.3)는 exceed 계산에 사용되지 않아 **기준 불일치** 발생.

threshold 변경 시 재적재 없이 **배치 재계산**으로 처리하는 구조로 변경.

## 현재 문제
- `analyze_axis(threshold=0.1)` — 하드코딩, 설정 미반영
- `get_dates()`: `max_vib_x > 0.3` — DB 설정 사용
- exceed 계산(0.1)과 고진동 판정(0.3) 기준 불일치

## 구현 단계

### Step 1: 적재 시 threshold를 설정에서 읽기
**`services/ingest_service.py`**
- `_process_pulse_file()`, `_process_vib_file()`에서 `get_setting("vib_threshold")` 값을 `analyze_axis(threshold=...)` 에 전달

### Step 2: 배치 재계산 API 추가
**`routers/settings.py`**
- `PUT /api/settings/{key}` — `vib_threshold` 변경 시 재계산 트리거 (또는 별도 엔드포인트)
- 또는 `POST /api/settings/recalculate-exceed` — 명시적 재계산 API

**`services/recalculate_service.py`** (신규)
- `recalculate_exceed(threshold: float)`
  1. `t_pulse_waveform`, `t_vib_waveform`에서 원시 파형 조회
  2. `analyze_axis(samples, threshold=new_threshold)` 재계산
  3. `t_cycle`의 exceed 컬럼들 UPDATE (배치)

### Step 3: 재계산 범위 선택
- 전체 재계산 (전 사이클)
- 또는 월별/일별 범위 지정 가능하게 파라미터 추가

### Step 4: 프론트 연동
**`dash-front`**
- 설정 패널에서 `vib_threshold` 변경 시 "재계산" 버튼 또는 자동 트리거
- 재계산 진행 상태 표시 (선택)

## 변경 파일 요약
| 파일 | 변경 |
|------|------|
| `services/ingest_service.py` | `analyze_axis()` 호출 시 threshold 전달 |
| `services/vibration_analyzer.py` | 기존 유지 (이미 파라미터 있음) |
| `services/recalculate_service.py` | **신규** — 배치 재계산 로직 |
| `routers/settings.py` | 재계산 API 추가 |
| `repos/cycles_repo.py` | exceed 컬럼 배치 UPDATE 함수 추가 |

## 검증
1. `vib_threshold` 변경 → 재계산 API 호출 → exceed 값 변경 확인
2. 새 적재 시 현재 threshold로 계산되는지 확인
3. `npx pyright` — 0 errors
4. `pytest` — 전체 통과

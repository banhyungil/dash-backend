# high_vib_event 컬럼 제거 — 조회 시 계산으로 전환

## Context
`high_vib_event`는 적재 시 `abs(v) > 0.3` 하드코딩 임계값으로 판정하여 DB에 저장하는 플래그.
임계값이 바뀌면 재적재가 필요하므로 `is_valid` 제거와 같은 이유로 컬럼을 제거한다.
`max_vib_x`, `max_vib_z`가 이미 DB에 있으므로, 조회 시 설정값과 비교하여 계산한다.

## 새 설정 추가
- `vib_threshold`: 고진동 임계값 (기본 0.3g)
- `services/database.py`의 `_DEFAULT_SETTINGS`에 추가
- `services/settings_service.py`의 `_FALLBACK`에 추가

## 변경 파일

### 1. `services/database.py`
- DDL에서 `high_vib_event INTEGER DEFAULT 0` 컬럼 삭제
- `_DEFAULT_SETTINGS`에 `("vib_threshold", "0.3", "number", "고진동 임계값(g)", "vibration")` 추가

### 2. `services/settings_service.py`
- `_FALLBACK`에 `"vib_threshold": 0.3` 추가

### 3. `services/ingest_service.py`
- 205행: `"high_vib_event": 1 if any(...) else 0` 삭제

### 4. `repos/cycles_repo.py`
- INSERT 컬럼에서 `high_vib_event` 제거
- `get_dates` (78행): SQL 집계를 `max_vib_x`, `max_vib_z` 비교로 변경
  ```sql
  SUM(CASE WHEN max_vib_x > ? OR max_vib_z > ? THEN 1 ELSE 0 END) AS high_vib_events
  ```
  - `vib_threshold` 설정값을 파라미터로 전달
- `get_monthly_summary` (139행): 동일하게 변경
- `find_by_date`, `find_one`: SELECT에서 `high_vib_event` 제거

### 5. `docs/ddl.md`
- DDL 문서에서 `high_vib_event` 컬럼 삭제

### 6. `tests/test_cycles_repo.py`
- `_make_cycle()`에서 `high_vib_event` 필드 제거
- `high_vib_event=1` 사용하던 테스트를 `max_vib_x` 값으로 대체

### 7. 프론트엔드 — 변경 없음
- `high_vib_events` 필드명은 API 응답에서 그대로 유지 (값만 조회 시 계산으로 변경)
- UI 코드(`DateCalendar.tsx`, `IngestStatus.tsx`) 변경 불필요

## 검증
1. `npx pyright` — 0 errors
2. `pytest` — 테스트 통과

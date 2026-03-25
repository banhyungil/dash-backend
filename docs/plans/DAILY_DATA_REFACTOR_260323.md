# daily-data API 리팩토링 — DB 기반 조회로 전환

## Context

현재 `/api/daily-data`는 `folder_scanner`로 data/ 폴더를 직접 스캔하고, 매 요청마다 CSV를 파싱합니다.
적재(ingest) 시스템이 도입되었으므로, DB에 저장된 데이터를 활용하도록 전환합니다.

---

## 현재 구조 (문제점)

```
GET /api/daily-data?month=2603&date=260311
  ↓
folder_scanner.py — data/ 폴더 구조 스캔 (Measured_YYMM/...)
  ↓
csv_parser.py — CSV 파싱 (매 요청마다 반복)
  ↓
rpm_service.py — RPM/MPM 계산 (매 요청마다 반복)
  ↓
expected_filter.py — 유효성 검증 (매 요청마다 반복)
  ↓
session_merger.py — 병합 + 타임라인 오프셋
  ↓
응답: cycles 배열 (집계값 + 배열 데이터)
```

**문제:**
- `data/Measured_YYMM/Measured/세션/measure/MAC/` 폴더 구조에 강하게 의존
- 매 요청마다 CSV 파싱 + RPM 계산 반복 (캐시로 완화하지만 근본적 비효율)
- 적재(ingest)로 이미 계산된 집계값이 DB에 있는데 활용 안 함

---

## 변경 후 구조

```
GET /api/daily-data?month=2603&date=260311
  ↓
[1] cycle_repo.py — DB에서 해당 날짜 cycles 조회
    SELECT * FROM t_cycles WHERE month='2603' AND date='260311'
    → 집계값 (rpm_mean, mpm_mean, duration_ms, is_valid 등)
    → source_path (원본 CSV 경로)
  ↓
[2] 차트 배열 데이터 필요 시 → source_path에서 CSV 읽기
    csv_parser.py + rpm_service.py로 배열 생성
    (rpm_timeline, rpm_data, pulse_accel_x/y/z, vib_accel_x/z)
  ↓
[3] 집계값(DB) + 배열 데이터(CSV) 합쳐서 응답
```

---

## 상세 설계

### 1단계: cycle_repo에 조회 함수 추가

```python
# repos/cycle_repo.py

def get_cycles_by_date(month: str, date: str) -> list[dict]:
    """DB에서 해당 날짜의 유효 사이클 조회."""
    SELECT timestamp, date, month, device, session, cycle_index,
           rpm_mean, rpm_min, rpm_max,
           mpm_mean, mpm_min, mpm_max,
           duration_ms, set_count, expected_count, is_valid,
           source_path
    FROM t_cycles
    WHERE month = ? AND date = ?
    ORDER BY timestamp
```

### 2단계: 배열 데이터 로더 추가

```python
# services/chart_data_loader.py (신규)

def load_chart_arrays(cycle: dict) -> dict:
    """DB의 cycle 정보 + source_path로 차트용 배열 데이터를 로드."""

    source_path = cycle["source_path"]
    cycle_index = cycle["cycle_index"]

    # 1. source_path에서 CSV 파싱 (캐시 활용)
    parsed = parse_pulse_cached(source_path)

    # 2. 해당 cycle_index의 원본 데이터 추출
    raw_cycle = parsed["cycles"][cycle_index]

    # 3. RPM 계산 → 배열 데이터 생성
    rpm_result = process_pulse_compact_to_rpm(...)

    # 4. 배열 데이터 반환
    return {
        "rpm_timeline": rpm_result["timeLine"],
        "rpm_data": rpm_result["dataRPM"],
        "mpm_data": [...],
        "pulse_timeline": rpm_result["rawTimeLine"],
        "pulse_accel_x": rpm_result["rawAccelX"],
        ...
    }
```

### 3단계: data_router 변경

```python
# routers/data_router.py

@router.get("/daily-data")
def api_daily_data(month, date):
    # [1] DB에서 집계값 조회
    db_cycles = cycle_repo.get_cycles_by_date(month, date)

    # [2] 각 사이클에 배열 데이터 붙이기
    result_cycles = []
    for cycle in db_cycles:
        arrays = load_chart_arrays(cycle)
        result_cycles.append({**cycle, **arrays})

    # [3] VIB 데이터 매칭 (기존 로직 유지)
    # [4] 타임라인 오프셋 계산 (기존 로직 유지)

    return { "cycles": result_cycles, ... }
```

---

## 제거 가능한 파일/코드

| 대상 | 현재 역할 | 변경 후 |
|------|----------|---------|
| `folder_scanner.py` | data/ 폴더 구조 스캔 | **제거 가능** (DB가 대체) |
| `data_router.py` 기존 로직 | CSV 스캔→파싱→계산→필터→병합 | DB 조회 + 배열 로드로 대체 |
| `DEVICE_SESSION_MAP` 의존 | 폴더 경로에서 디바이스 판별 | DB에 session 저장되어 있음 |

### 유지하는 것
| 대상 | 이유 |
|------|------|
| `csv_parser.py` | 배열 데이터 로드에 여전히 필요 |
| `cached_csv_parser.py` | 배열 데이터 캐싱 |
| `rpm_service.py` | 배열 데이터 계산 (rpm_timeline 등) |
| `session_merger.py` | 타임라인 오프셋 계산 |

---

## 기존 API 유지 (하위 호환)

프론트엔드 `CycleData` 인터페이스는 변경 없음.
응답 구조가 동일하므로 프론트 수정 불필요.

```typescript
// 기존과 동일한 응답
interface CycleData {
  timestamp, session, cycle_index, date,
  rpm_mean, rpm_min, rpm_max, rpm_timeline, rpm_data,
  mpm_mean, mpm_min, mpm_max, mpm_data,
  duration_ms, set_count, expected_count, timeline_offset,
  pulse_timeline, pulse_accel_x, pulse_accel_y, pulse_accel_z,
  vib_accel_x, vib_accel_z,
}
```

---

## 마이그레이션 순서

1. **cycle_repo에 `get_cycles_by_date` 추가**
2. **chart_data_loader.py 신규 작성** — source_path → 배열 데이터 로드
3. **data_router.py 수정** — DB 조회 기반으로 전환
4. **기존 API 테스트** — 프론트에서 차트 동일하게 나오는지 확인
5. **folder_scanner 의존 제거** — data_router에서 import 삭제

### 전제 조건
- 차트로 볼 데이터는 **먼저 적재(ingest)가 되어 있어야** 함
- 적재 안 된 날짜는 조회 불가 → 프론트에서 안내 필요

---

## 검증 방법

1. 테스트 데이터 적재: `POST /api/ingest` 로 260311 데이터 적재
2. `GET /api/daily-data?month=2603&date=260311` 호출
3. 기존 응답과 동일한 구조인지 비교
4. 프론트 차트가 정상 렌더링되는지 확인
5. pytest: `test_data_router.py` 추가

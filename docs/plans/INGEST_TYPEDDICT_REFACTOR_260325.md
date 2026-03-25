# ingest_service 리팩터링: PULSE/VIB 분리 + TypedDict

## Context
1. PULSE/VIB 처리가 혼재 — `_process_pulse_file()` 안에서 VIB 병합(`_enrich_vib_stats`)
2. 내부 dict에 타입 없음 — 키 오타를 pyright가 잡지 못함
3. naming 모호 — `db_rows`, `_raw_pulses`, `pulse_result` 등

## 현재 흐름 (문제)
```
_process_pulse_file()
    → RPM 계산 + PULSE stats
    → _enrich_vib_stats()  ← PULSE 안에서 VIB 처리 (혼재)
    → db_rows에 VIB stats 병합
_write_result_to_db()
    → raw 배열 pop → waveform 저장 → t_cycle INSERT
```

## 변경 후 흐름
```
_process_pulse(path) → PulseResult (RPM + PULSE stats + 원시 파형)
_process_vib(path)   → VibResult (VIB stats + 원시 파형)
    ↓
_merge_pulse_vib(pulse, vib) → cycle_index로 매칭, stats/파형 합침
    ↓
_write_to_db() → t_cycle INSERT + waveform INSERT
```

## TypedDict 정의

```python
# --- 축별 stats는 AxisStats로 중첩 저장, _write_to_db()에서 flatten하여 DB INSERT ---

class AxisStats(TypedDict):
    """축별 통계 — analyze_axis() 반환값. PULSE/VIB 공통."""
    rms: float
    peak: float
    min: float
    max: float
    q1: float
    median: float
    q3: float
    exceed_count: float
    exceed_ratio: float
    exceed_duration_ms: float

class PulseRawCycle(TypedDict):
    """PULSE CSV 사이클 1개 — RPM/MPM + PULSE 3축 stats + 원시 파형."""
    timestamp: str
    date: str
    month: str
    device: str | None
    device_name: str
    cycle_index: int
    rpm_mean: float
    rpm_min: float
    rpm_max: float
    mpm_mean: float
    mpm_min: float
    mpm_max: float
    duration_ms: float
    set_count: int
    expected_count: int
    pulse_x_stats: AxisStats
    pulse_y_stats: AxisStats
    pulse_z_stats: AxisStats
    burst_count: int            # 3축 합산
    peak_impact_count: int      # 3축 합산
    _raw_pulses: list
    _raw_accel_x: list[float]
    _raw_accel_y: list[float]
    _raw_accel_z: list[float]

class PulseResult(TypedDict):
    filename: str
    source: str
    cycles: list[PulseRawCycle]
    skipped: int
    errors: list[str]

class VibRawCycle(TypedDict):
    """VIB CSV 사이클 1개 — VIB 2축 stats + 원시 파형."""
    cycle_index: int
    accel_x: list[float]
    accel_z: list[float]
    vib_x_stats: AxisStats
    vib_z_stats: AxisStats

class VibResult(TypedDict):
    filename: str
    source: str
    cycles: list[VibRawCycle]
    skipped: int
    errors: list[str]

class MergedCycle(TypedDict):
    """_merge_pulse_vib() 결과 — PULSE + VIB 합산. _write_to_db() 입력."""
    # PulseRawCycle 전체 키 포함 +
    max_vib_x: float
    max_vib_z: float
    vib_x_stats: AxisStats
    vib_z_stats: AxisStats
    # burst_count, peak_impact_count는 PULSE + VIB 합산으로 갱신

class IngestDetail(TypedDict):
    filename: str
    cycles_ingested: int
    cycles_skipped: int
    errors: list[str]

class IngestBatchResult(TypedDict):
    total_files: int
    success_cycles: int
    skipped_cycles: int
    failed_lines: int
    details: list[IngestDetail]
```

## naming 변경 요약

| 현재 | 변경 후 | 이유 |
|------|---------|------|
| `_process_pulse_file()` | `_process_pulse()` | 간결화 |
| `_process_vib_file()` | `_process_vib()` | 간결화 |
| `_enrich_vib_stats()` | `_merge_pulse_vib()` | 독립 함수로 분리, 역할 명확화 |
| `db_rows` | `cycles` | 원시 파형도 포함하므로 "DB row"가 부정확 |
| `_raw_pulses` | `raw_pulses` | 언더스코어 제거 |
| `_vib_accel_x` | `vib_accel_x` | 동일 |
| `_inserted` | `inserted_count` | 의미 명확화 |
| `_write_result_to_db` | `_write_to_db` | 간결화 |

## 구현 단계

### Step 1: TypedDict 정의
**`services/ingest_service.py`** 상단에 TypedDict 클래스 추가

### Step 2: PULSE/VIB 처리 분리
- `_process_pulse()`: RPM + PULSE stats만 처리. VIB 관련 로직 제거
- `_process_vib()`: VIB stats만 처리 (기존과 유사)
- `_merge_pulse_vib(pulse_result, vib_result)`: cycle_index로 매칭 → MergedCycle 리스트 반환
- `_process_file()`: PULSE면 VIB 파일도 찾아서 각각 처리 후 merge

### Step 3: naming + 타입 어노테이션 적용
- 함수 반환 타입 추가
- 내부 변수명/키명 일괄 변경

### Step 4: pyright + pytest 검증

## 변경 파일
| 파일 | 변경 |
|------|------|
| `services/ingest_service.py` | PULSE/VIB 분리, TypedDict, naming |

## 검증
1. `npx pyright` — 0 errors
2. `pytest` — 전체 통과
3. 적재 후 t_cycle + waveform 데이터 정상 확인

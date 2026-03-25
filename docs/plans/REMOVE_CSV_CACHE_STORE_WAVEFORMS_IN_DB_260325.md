# CSV 캐시 제거 — 원시 파형 DB 저장으로 전환

## Context
현재 CSV 파싱 결과를 msgpack 캐시로 저장하고, 조회 시 캐시에서 읽는 구조.
PostgreSQL 전환과 함께 원시 파형을 DB(BYTEA)에 저장하면:
- CSV 파일 의존성 완전 제거 (파일 삭제/이동해도 데이터 유지)
- msgpack 캐시 계층 삭제 (코드 단순화)
- source_path 컬럼도 불필요해짐

## 현재 구조

### DB에 저장되는 것 (t_cycle)
- 메타: timestamp, date, month, device, device_name, cycle_index
- 집계값: rpm_mean/min/max, mpm_mean/min/max, duration_ms
- 통계: rms, peak, q1, median, q3, exceed, burst 등
- source_path (CSV 원본 경로 참조)

### CSV에서만 읽는 것 (캐시 경유)
- **PULSE 원시 배열**: pulses(펄스 간격 μs), accel_x, accel_y, accel_z
  - 사이클당 ~5개 포인트 (set_count), 포인트당 4개 값
  - 용도: RPM 타임라인 차트, 가속도 파형 차트
- **VIB 원시 배열**: accel_x, accel_z
  - 사이클당 5,000+ 포인트
  - 용도: 진동 파형 차트

## 변경 계획

### 1. 새 테이블: `t_pulse_waveform` (PULSE 원시 배열)
```sql
CREATE TABLE IF NOT EXISTS t_pulse_waveform (
    id           SERIAL PRIMARY KEY,
    cycle_id     INTEGER NOT NULL REFERENCES t_cycle(id) ON DELETE CASCADE,
    pulses       BYTEA,       -- 펄스 간격 배열 (int, μs)
    accel_x      BYTEA,       -- X축 가속도 배열 (float, g)
    accel_y      BYTEA,       -- Y축 가속도 배열 (float, g)
    accel_z      BYTEA,       -- Z축 가속도 배열 (float, g)
    sample_count INTEGER,
    UNIQUE(cycle_id)
);
```
- PULSE는 사이클당 ~5개 포인트라 매우 작음 (~100 bytes)

### 2. 기존 테이블: `t_vib_waveform` (이미 생성됨)
```sql
CREATE TABLE IF NOT EXISTS t_vib_waveform (
    id           SERIAL PRIMARY KEY,
    cycle_id     INTEGER NOT NULL REFERENCES t_cycle(id) ON DELETE CASCADE,
    accel_x      BYTEA,
    accel_z      BYTEA,
    sample_count INTEGER,
    UNIQUE(cycle_id)
);
```
- VIB는 사이클당 5,000+ 포인트 → TOAST 자동 압축 (~15-20KB)

### 3. 적재 시 변경 — `services/ingest_service.py`
- `_process_pulse_file`: PULSE 원시 배열(pulses, accel_x/y/z)을 반환값에 포함
- `_process_vib_file`: VIB 원시 배열(accel_x, accel_z)을 반환값에 포함
- `_write_result_to_db`: cycle INSERT 후 cycle_id를 받아 파형 테이블에 저장

### 4. 조회 시 변경 — `services/daily_data_service.py`
- `_load_pulse_arrays`: `parse_pulse_cached()` 대신 DB에서 파형 조회
- `_load_vib_arrays`: `parse_vib_cached()` 대신 DB에서 파형 조회
- `build_cycle_detail`: 동일하게 DB 조회로 전환

### 5. 삭제 대상
| 파일 | 이유 |
|------|------|
| `services/cached_csv_parser.py` | 캐시 파싱 계층 전체 삭제 |
| `services/cache_manager.py` | msgpack 캐시 관리 전체 삭제 |
| `config.py`의 `CACHE_DIR`, `CACHE_VERSION` | 캐시 디렉토리 불필요 |
| `t_cycle.source_path` 컬럼 | CSV 경로 참조 불필요 |
| `.cache/` 디렉토리 | 물리적 캐시 파일 삭제 |

### 6. 영향받는 파일
| 파일 | 변경 |
|------|------|
| `services/database.py` | `t_pulse_waveform` DDL 추가, `source_path` 컬럼 삭제 |
| `repos/cycles_repo.py` | INSERT/SELECT에서 `source_path` 제거 |
| `repos/pulse_waveform_repo.py` | **신규** — PULSE 파형 CRUD |
| `repos/vib_waveform_repo.py` | 이미 생성됨 |
| `services/ingest_service.py` | 파형 DB 저장, source_path 제거 |
| `services/daily_data_service.py` | CSV 파싱 → DB 조회로 전환 |
| `services/test_export.py` | `parse_pulse_cached` → DB 조회 |
| `tests/test_cycles_repo.py` | source_path 필드 제거 |

### 7. 유지되는 것
- `services/csv_parser.py` — 최초 적재 시 CSV 파싱은 여전히 필요
- `services/folder_scanner.py` — 적재할 CSV 파일 탐색
- `repos/ingested_files_repo.py` — 적재 이력 관리 (source_path는 여기서 관리)

## 검증
1. `npx pyright` — 0 errors
2. `pytest` — 전체 통과
3. 적재 → DB에서 파형 조회 → 차트 표시 확인
4. `.cache/` 디렉토리 없이 동작 확인

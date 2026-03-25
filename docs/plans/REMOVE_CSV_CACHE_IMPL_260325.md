# CSV 캐시 제거 + 원시 파형 DB 저장

## Context
CSV 파싱 결과를 msgpack 캐시로 관리하는 구조를 제거하고, 원시 파형을 PostgreSQL BYTEA로 저장.
CSV 파일 의존성 완전 제거. 상세 배경: `docs/plans/REMOVE_CSV_CACHE_STORE_WAVEFORMS_IN_DB_260325.md`

## 구현 단계

### Step 1: DDL — `t_pulse_waveform` 추가 + `source_path` 제거
**`services/database.py`**
- `t_pulse_waveform` 테이블 추가 (pulses BYTEA, accel_x/y/z BYTEA, sample_count)
- `t_cycle`에서 `source_path TEXT` 컬럼 삭제
- `idx_t_cycle_source` 인덱스 삭제
- `config.py`에서 `CACHE_DIR`, `CACHE_VERSION` 삭제

### Step 2: `repos/pulse_waveform_repo.py` 신규
- `vib_waveform_repo.py`와 동일 패턴
- `insert(cycle_id, pulses, accel_x, accel_y, accel_z, conn)` — int 배열은 `struct.pack('i'...)`, float은 `'d'...`
- `find_by_cycle_id(cycle_id)` — bytes → 배열 디코딩

### Step 3: `repos/cycles_repo.py` — source_path 제거
- INSERT SQL에서 `source_path` 제거
- `find_by_date`, `find_one` SELECT에서 `source_path` 제거
- `insert_many`가 삽입된 cycle의 id를 반환하도록 변경 (파형 저장에 필요)

### Step 4: `services/ingest_service.py` — 적재 시 파형 DB 저장
- `_process_pulse_file`: 반환 dict에 원시 배열 포함 (`raw_pulses`, `raw_accel_x/y/z` per cycle)
- `_process_vib_file`: VIB 원시 배열도 반환 (`vib_accel_x`, `vib_accel_z` per cycle)
- `_write_result_to_db`:
  - t_cycle INSERT 후 id 획득
  - `pulse_waveform_repo.insert(cycle_id, ...)` 호출
  - VIB 파형이 있으면 `vib_waveform_repo.insert(cycle_id, ...)` 호출
- `source_path` dict 키 제거
- `_enrich_vib_stats`: source_path 기반 VIB 경로 변환 → 이미 파싱된 vib_cycles 직접 전달로 변경

### Step 5: `services/daily_data_service.py` — 조회를 DB에서
- `_load_pulse_arrays`: `parse_pulse_cached(source_path)` → `pulse_waveform_repo.find_by_cycle_id(cycle_id)` + RPM 재계산
- `_load_vib_arrays`: `parse_vib_cached(vib_path)` → `vib_waveform_repo.find_by_cycle_id(cycle_id)`
- `build_cycle_detail`: 동일하게 DB 조회로 전환
- import에서 `cached_csv_parser` 제거

### Step 6: `services/test_export.py` — CSV 파싱 → DB 조회
- `parse_pulse_cached`, `parse_vib_cached` import 제거
- DB에서 파형 조회하도록 변경

### Step 7: 삭제
- `services/cached_csv_parser.py` — 파일 삭제
- `services/cache_manager.py` — 파일 삭제
- `services/folder_scanner.py` — `cache_manager` import 제거
- `config.py` — `CACHE_DIR`, `CACHE_VERSION` 삭제

### Step 8: 테스트 수정
- `tests/test_cycles_repo.py` — `source_path` 필드 제거
- `tests/test_ingest_service.py` — source_path 관련 assertion 수정

### Step 9: docs
- `docs/ddl.md` — `t_pulse_waveform` 추가, `source_path` 제거
- `docs/plans/`에 플랜 복사

## 변경 파일 요약
| 파일 | 변경 |
|------|------|
| `config.py` | CACHE_DIR, CACHE_VERSION 삭제 |
| `services/database.py` | t_pulse_waveform DDL 추가, source_path 삭제 |
| `repos/pulse_waveform_repo.py` | **신규** |
| `repos/vib_waveform_repo.py` | 기존 유지 |
| `repos/cycles_repo.py` | source_path 제거, id 반환 |
| `services/ingest_service.py` | 파형 DB 저장, source_path 제거 |
| `services/daily_data_service.py` | CSV → DB 조회 |
| `services/test_export.py` | CSV → DB 조회 |
| `services/folder_scanner.py` | cache import 제거 |
| `services/cached_csv_parser.py` | **삭제** |
| `services/cache_manager.py` | **삭제** |
| `tests/test_cycles_repo.py` | source_path 제거 |
| `tests/test_ingest_service.py` | source_path 수정 |
| `docs/ddl.md` | DDL 업데이트 |

## 검증
1. `npx pyright` — 0 errors
2. `pytest` — 전체 통과
3. 적재 → DB에서 파형 조회 확인

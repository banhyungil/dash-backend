# is_valid 컬럼 완전 제거

## Context
`is_valid`는 적재 시 `tolerance` 기반으로 판정해서 DB에 저장하는 플래그인데,
`tolerance`가 바뀌면 기존 데이터를 전부 재적재해야 하므로 유지 가치가 없다.
`set_count`와 `expected_count`는 DB에 남아있으므로, 필요 시 조회 시점에 계산 가능.

## 변경 파일

### 1. `services/expected_filter.py`
- `is_expected_valid()` 함수 삭제
- `calculate_expected_pulse_count()`는 유지 (`expected_count` 컬럼 계산에 사용)

### 2. `services/ingest_service.py`
- import에서 `is_expected_valid` 제거
- 170행: `valid = is_expected_valid(...)` 삭제
- 203행: `"is_valid": 1 if valid else 0` 삭제

### 3. `services/database.py`
- DDL에서 `is_valid INTEGER DEFAULT 1` 컬럼 삭제

### 4. `repos/cycles_repo.py`
- `insert_many`: INSERT 컬럼 목록에서 `is_valid` 제거
- `get_dates` (78행): `SUM(CASE WHEN is_valid = 1 ...)` 집계 삭제
- `get_monthly_summary` (140행): 동일 집계 삭제
- `find_by_date`, `find_one`: SELECT 목록에서 `is_valid` 제거

### 5. `dash-front/src/api/types.ts`
- `CycleData`에서 `is_valid: number` 제거 (직전에 추가한 것)

### 6. `tests/test_expected_filter.py`
- `is_expected_valid` 관련 테스트 케이스 삭제
- `calculate_expected_pulse_count` 테스트는 유지

### 7. `tests/test_cycles_repo.py`
- 테스트 데이터에서 `is_valid` 필드 제거

### 8. `docs/ddl.md`
- DDL 문서에서 `is_valid` 컬럼 삭제

## 변경하지 않는 항목
| 항목 | 이유 |
|------|------|
| `expected_count` 컬럼 | RPM 기반 이론값, 참고 정보로 유지 |
| `calculate_expected_pulse_count()` | `expected_count` 계산에 사용 |
| `daily_data_service.py` | 이전 단계에서 이미 필터링 제거 완료 |

## 검증
1. `npx pyright` — 0 errors
2. `pytest` — 테스트 통과

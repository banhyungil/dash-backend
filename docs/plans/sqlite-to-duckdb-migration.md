# SQLite → DuckDB 전환 방안

> 작성일: 2026-03-24
> 상태: 검토 대기

---

## 1. 전환 이유

현재 워크로드가 OLAP 성격:
- 읽기: 날짜별 수백~수천 행 풀스캔, GROUP BY 집계, 분위수 계산
- 쓰기: 적재 시점에만 배치 INSERT

DuckDB의 이점:
- 컬럼 기반 → 특정 컬럼 집계 시 불필요한 컬럼 읽지 않음
- 벡터화 실행 → 대량 행 처리 성능 우수
- CSV/Parquet 직접 쿼리 가능
- SQL 호환성 높음 (SQLite와 문법 거의 동일)
- 임베디드 (별도 서버 불필요, `pip install duckdb`)

---

## 2. 영향 범위 분석

### DB 접근 계층 (변경 대상)

| 파일 | 역할 | 변경 범위 |
|------|------|-----------|
| `services/database.py` | 커넥션 + DDL | **핵심** — duckdb로 교체 |
| `repos/cycles_repo.py` | t_cycle CRUD | SQL 호환 확인, row_factory 대응 |
| `repos/settings_repo.py` | t_settings CRUD | SQL 호환 확인 |
| `repos/ingested_files_repo.py` | h_ingested_file CRUD | SQL 호환 확인 |
| `tests/conftest.py` | 테스트 DB fixture | duckdb로 교체 |

### SQL 호환성 체크

| SQLite 문법 | DuckDB 지원 | 비고 |
|-------------|-------------|------|
| `CREATE TABLE IF NOT EXISTS` | O | |
| `INSERT OR REPLACE` | X | → `INSERT OR REPLACE` 미지원, `INSERT ... ON CONFLICT ... DO UPDATE` 사용 |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | X | → `INTEGER PRIMARY KEY` + `DEFAULT nextval('seq')` 또는 제거 |
| `PRAGMA journal_mode=WAL` | X | → 삭제 (DuckDB 자체 WAL) |
| `PRAGMA foreign_keys=ON` | X | → 삭제 |
| `datetime('now')` | X | → `current_timestamp` |
| `sqlite3.Row` (row_factory) | X | → DuckDB는 `.fetchdf()` 또는 `.fetchall()` + 수동 dict 변환 |
| Named parameter (`:key`) | O | |
| `?` placeholder | O | |

### 주요 변경 포인트

1. **AUTOINCREMENT 제거** — DuckDB는 `GENERATED ALWAYS AS IDENTITY` 또는 시퀀스 사용
2. **INSERT OR REPLACE** → `INSERT ... ON CONFLICT DO UPDATE`
3. **Row 접근 방식** — `sqlite3.Row`(dict-like) → DuckDB `fetchall()`은 tuple 반환, dict 변환 필요
4. **날짜 함수** — `datetime('now')` → `current_timestamp`

---

## 3. 구현 계획

### Step 1. 의존성 추가 + database.py 교체

```bash
pip install duckdb
```

```python
# services/database.py
import duckdb
from config import DB_PATH

def get_connection():
    conn = duckdb.connect(str(DB_PATH))
    return conn
```

### Step 2. DDL 변환

```sql
-- SQLite
CREATE TABLE IF NOT EXISTS t_cycle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
    UNIQUE(device, date, cycle_index)
);

-- DuckDB
CREATE TABLE IF NOT EXISTS t_cycle (
    id INTEGER PRIMARY KEY DEFAULT nextval('t_cycle_seq'),
    ...
    UNIQUE(device, date, cycle_index)
);
CREATE SEQUENCE IF NOT EXISTS t_cycle_seq;
```

또는 `id` 컬럼을 없애고 `(device, date, cycle_index)` 복합 PK로 단순화.

### Step 3. INSERT OR REPLACE 변환

```sql
-- SQLite
INSERT OR REPLACE INTO t_cycle (...) VALUES (...)

-- DuckDB
INSERT INTO t_cycle (...) VALUES (...)
ON CONFLICT (device, date, cycle_index) DO UPDATE SET
    rpm_mean = EXCLUDED.rpm_mean,
    ...
```

또는 적재 전 DELETE + INSERT 패턴 (현재 재적재 시 DB 삭제하므로 단순 INSERT로 충분할 수 있음).

### Step 4. Row 반환 형식 대응

```python
# SQLite — sqlite3.Row는 dict-like
conn.row_factory = sqlite3.Row
row["column_name"]  # OK

# DuckDB — tuple 반환, 수동 변환 필요
def fetchall_dict(cursor):
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

`database.py`에 헬퍼 함수로 추가하면 repo 코드 변경 최소화.

### Step 5. Repo 코드 수정

- `conn.execute()` → 결과 dict 변환 적용
- `INSERT OR REPLACE` → `INSERT ... ON CONFLICT` 또는 단순 INSERT
- `conn.commit()` → DuckDB도 지원 (autocommit 기본이지만 트랜잭션 가능)

### Step 6. 테스트 fixture 변경

```python
# tests/conftest.py
import duckdb

@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.duckdb")
    def _get_test_connection():
        return duckdb.connect(test_db)
    monkeypatch.setattr("services.database.get_connection", _get_test_connection)
    from services.database import init_db
    init_db()
```

### Step 7. 파일 확장자 변경

- `dash.db` → `dash.duckdb` (config.py의 DB_PATH)

---

## 4. 단순화 옵션

현재 재적재 시 DB를 삭제하는 패턴이므로:

- **id 컬럼 제거** — AUTOINCREMENT 불필요, 복합 PK 사용
- **INSERT OR REPLACE → 단순 INSERT** — 중복 없는 전제
- **UPSERT는 settings/ingested_files만** — 이 2개만 ON CONFLICT 처리

---

## 5. 마이그레이션 후 추가 기회

DuckDB 전환 후 활용 가능한 기능:

| 기능 | 설명 |
|------|------|
| CSV 직접 쿼리 | 적재 없이 `read_csv()` 로 CSV 분석 |
| Parquet 내보내기 | 장기 보관용 압축 포맷 |
| 윈도우 함수 | `PERCENTILE_CONT`, `LAG`, `LEAD` — stats 계산 DB 레벨에서 |
| COPY TO | 대량 데이터 빠른 내보내기 |

---

## 6. 구현 순서

```
Step 1. pip install duckdb + database.py 교체
Step 2. DDL 변환 (id 제거, 복합 PK)
Step 3. INSERT 문 변환
Step 4. Row dict 변환 헬퍼
Step 5. Repo 코드 수정
Step 6. 테스트 fixture 변경
Step 7. 전체 테스트 통과 확인
Step 8. DB 삭제 + 재적재
```

예상 소요: database.py + 3개 repo + conftest = 5개 파일 수정

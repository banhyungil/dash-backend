# SQLite → PostgreSQL 전환 플랜

## Context
현재 SQLite를 사용 중이나, 향후 실시간 센서 데이터 삽입이 예정되어 있음.
SQLite는 동시 쓰기/읽기에 제한이 있어, 센서 INSERT 중 대시보드 조회 시 락 충돌 위험.
프로토타입 단계에서 전환하는 것이 데이터 쌓인 후보다 비용이 적음.

## 전환 이점
- **동시성**: MVCC로 읽기/쓰기 완전 병렬 (센서 삽입 중 조회 가능)
- **VIB 파형 저장**: TOAST 자동 압축으로 BYTEA 컬럼에 대용량 배열 저장
- **확장성**: TimescaleDB 확장 추가 시 시계열 자동 파티셔닝/다운샘플링
- **서버 배포**: 원격 센서 → DB 직접 삽입 구조 가능

## 전환 범위

### 1. 의존성
```
pip install psycopg[binary]   # PostgreSQL 드라이버 (psycopg3)
```
- `sqlite3` (stdlib) → `psycopg` (pip)
- psycopg3는 dict row 지원, 커넥션 풀 내장

### 2. config.py
```python
# 변경 전
DB_PATH = Path(os.environ.get("DB_PATH", backend_dir / "dash.db"))

# 변경 후
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/dash")
```

### 3. services/database.py (핵심)

| 항목 | SQLite (현재) | PostgreSQL (변경 후) |
|------|--------------|---------------------|
| 드라이버 | `sqlite3` | `psycopg` |
| 커넥션 | `sqlite3.connect(path)` | `psycopg.connect(url)` |
| Row 접근 | `sqlite3.Row` (dict-like) | `psycopg.rows.dict_row` |
| PRAGMA | `journal_mode=WAL` 등 | 삭제 (불필요) |
| AUTOINCREMENT | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` 또는 `GENERATED ALWAYS AS IDENTITY` |
| executescript | `conn.executescript(sql)` | `conn.execute(sql)` (psycopg3는 멀티문 지원) |
| 파라미터 | `?` (qmark) | `%s` 또는 `%(name)s` |
| upsert | `INSERT OR REPLACE` | `INSERT ... ON CONFLICT DO UPDATE` |

### 4. DDL 변경점

```sql
-- SQLite
CREATE TABLE IF NOT EXISTS t_cycle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
    UNIQUE(device, date, cycle_index)
);

-- PostgreSQL
CREATE TABLE IF NOT EXISTS t_cycle (
    id SERIAL PRIMARY KEY,
    ...
    UNIQUE(device, date, cycle_index)
);
```

- `REAL` → `DOUBLE PRECISION` (또는 그대로 사용 가능, PG도 REAL 지원)
- `TEXT` → `TEXT` (동일)
- `INTEGER` → `INTEGER` (동일)
- `datetime('now')` → `NOW()`

### 5. VIB 파형 테이블 추가 (신규)
PostgreSQL 전환과 함께 VIB 파형 데이터를 DB에 저장:
```sql
CREATE TABLE IF NOT EXISTS t_vib_waveform (
    id SERIAL PRIMARY KEY,
    cycle_id INTEGER NOT NULL REFERENCES t_cycle(id) ON DELETE CASCADE,
    accel_x BYTEA,        -- TOAST 자동 압축
    accel_z BYTEA,        -- TOAST 자동 압축
    sample_count INTEGER,
    UNIQUE(cycle_id)
);
```
- `accel_x`, `accel_z`: float 배열을 `struct.pack`으로 직렬화 → BYTEA 저장
- TOAST가 자동으로 압축/외부 저장 처리 (별도 설정 불필요)
- 조회 시 CSV 파싱 불필요, 파일 의존성 제거

### 6. 파라미터 스타일 변경
모든 repo 파일에서:
```python
# SQLite (qmark)
conn.execute("SELECT * FROM t_cycle WHERE month = ?", (month,))
conn.execute("... VALUES (?, ?, ?)", (a, b, c))

# PostgreSQL (pyformat) — psycopg3 기본
conn.execute("SELECT * FROM t_cycle WHERE month = %s", (month,))
conn.execute("... VALUES (%s, %s, %s)", (a, b, c))
```

named parameter:
```python
# SQLite
conn.execute("... VALUES (:timestamp, :date)", row_dict)

# PostgreSQL (psycopg3)
conn.execute("... VALUES (%(timestamp)s, %(date)s)", row_dict)
```

### 7. 변경 대상 파일

| 파일 | 변경 내용 |
|------|-----------|
| `config.py` | `DB_PATH` → `DATABASE_URL` |
| `services/database.py` | 드라이버, DDL, get_connection 전면 교체 |
| `repos/cycles_repo.py` | `?` → `%s`, `:name` → `%(name)s`, INSERT OR REPLACE → ON CONFLICT |
| `repos/settings_repo.py` | 동일 파라미터 변경, INSERT OR IGNORE → ON CONFLICT DO NOTHING |
| `repos/ingested_files_repo.py` | 동일 파라미터 변경 |
| `tests/conftest.py` | 테스트 DB fixture를 PostgreSQL 또는 SQLite 호환 레이어로 변경 |
| `services/daily_data_service.py` | VIB 파형 조회를 DB에서 읽도록 변경 (CSV 파싱 제거) |
| `services/ingest_service.py` | VIB 파형 DB 저장 로직 추가 |

### 8. 테스트 전략
- **로컬 개발**: Docker로 PostgreSQL 실행 (`docker run -p 5432:5432 postgres:16`)
- **테스트**: `pytest-postgresql` 또는 테스트용 별도 DB
- 또는: `testing.postgresql` 패키지로 임시 PG 인스턴스 자동 생성

### 9. 마이그레이션 순서
1. PostgreSQL 설치 + DB 생성
2. `config.py` + `database.py` 교체
3. repo 파일 파라미터 스타일 변경 (3개 파일)
4. `t_vib_waveform` 테이블 추가 + VIB 적재 로직
5. 테스트 fixture 교체
6. 기존 SQLite 데이터 마이그레이션 (필요 시)

## 검증
1. `npx pyright` — 0 errors
2. `pytest` — 전체 통과
3. 적재 → 조회 → VIB 파형 차트 표시 확인


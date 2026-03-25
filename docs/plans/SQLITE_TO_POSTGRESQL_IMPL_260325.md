# SQLite → PostgreSQL 전환 구현 플랜

## Context
향후 실시간 센서 데이터 삽입 예정. SQLite는 동시 쓰기/읽기 제한이 있어 PostgreSQL로 전환.
VIB 파형 데이터도 DB에 저장하여 CSV 파일 의존성 제거.
상세 배경은 `docs/plans/sqlite-to-postgresql-migration.md` 참조.

## 사전 준비
- Docker로 PostgreSQL 실행:
  ```bash
  docker run -d --name dash-pg -p 5432:5432 \
    -e POSTGRES_DB=dash -e POSTGRES_PASSWORD=dash \
    postgres:16
  ```
- 테스트 DB 생성:
  ```bash
  docker exec dash-pg psql -U postgres -c "CREATE DATABASE dash_test;"
  ```
- `pip install "psycopg[binary]"`
- `pip install pytest-postgresql` (테스트용)

## docker-compose.yml (프로젝트 루트에 추가)
```yaml
services:
  db:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: dash
      POSTGRES_PASSWORD: dash
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

## 구현 단계

### Step 1: config.py
- `DB_PATH` → `DATABASE_URL` 환경변수
```python
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/dash")
```
- `DB_PATH` 변수 삭제 (sqlite 파일 경로 불필요)

### Step 2: services/database.py (핵심)
전면 교체:
- `import sqlite3` → `import psycopg`
- `get_connection()`: `psycopg.connect(DATABASE_URL, row_factory=dict_row)`
- PRAGMA 삭제
- DDL 변경:
  - `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
  - `datetime('now')` → `NOW()`
  - `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING`
- `executescript()` → `execute()` (psycopg3는 멀티문 지원)
- `t_vib_waveform` 테이블 추가 (BYTEA)

### Step 3: repos/cycles_repo.py
- 파라미터 스타일: `:name` → `%(name)s`
- `INSERT OR REPLACE` → `INSERT ... ON CONFLICT (device, date, cycle_index) DO UPDATE SET ...`
- `?` → `%s` (get_dates, get_monthly_summary의 threshold 파라미터)
- `executemany` → `executemany` (psycopg3도 지원)

### Step 4: repos/settings_repo.py
- `?` → `%s`
- `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING`
- `executemany` 파라미터를 tuple 리스트로 유지 (psycopg3 호환)

### Step 5: repos/ingested_files_repo.py
- `?` → `%s`
- `INSERT OR REPLACE` → `INSERT ... ON CONFLICT (source_path) DO UPDATE SET ...`

### Step 6: VIB 파형 저장 (신규)
- `repos/vib_waveform_repo.py` 신규 생성
  - `insert(cycle_id, accel_x_bytes, accel_z_bytes, sample_count)`
  - `find_by_cycle_id(cycle_id) -> dict | None`
- `services/ingest_service.py` 수정:
  - `_process_vib_file`: 파형 데이터를 bytes로 변환하여 반환
  - `_write_result_to_db`: VIB 파형 DB 저장
- `services/daily_data_service.py` 수정:
  - VIB 조회를 CSV 파싱 대신 DB에서 읽도록 변경

### Step 7: tests/conftest.py
- SQLite fixture → PostgreSQL fixture
```python
import psycopg
from psycopg.rows import dict_row

@pytest.fixture(autouse=True)
def _use_test_db(monkeypatch):
    conn = psycopg.connect("postgresql://localhost:5432/dash_test", row_factory=dict_row)
    conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    monkeypatch.setattr("services.database.get_connection", lambda: conn)
    from services.database import init_db
    init_db()
    yield
    conn.close()
```

### Step 8: docs 업데이트
- `docs/ddl.md`: PostgreSQL DDL로 변경
- `docs/architecture.md`: DB 섹션 업데이트

## 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `config.py` | DB_PATH → DATABASE_URL |
| `services/database.py` | 전면 교체 (psycopg + PG DDL) |
| `repos/cycles_repo.py` | 파라미터 + upsert 문법 |
| `repos/settings_repo.py` | 파라미터 + upsert 문법 |
| `repos/ingested_files_repo.py` | 파라미터 + upsert 문법 |
| `repos/vib_waveform_repo.py` | **신규** — VIB 파형 CRUD |
| `services/ingest_service.py` | VIB 파형 bytes 변환 + DB 저장 |
| `services/daily_data_service.py` | VIB 조회를 DB에서 읽기 |
| `tests/conftest.py` | PG 테스트 fixture |
| `docs/ddl.md` | PG DDL |

## 검증
1. `npx pyright` — 0 errors
2. `pytest` — 전체 통과 (PostgreSQL 테스트 DB 필요)
3. 적재 → 조회 → VIB 파형 차트 표시 확인

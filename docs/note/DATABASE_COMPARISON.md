# 임베디드 DB 비교: SQLite vs DuckDB vs 시계열 DB

## 1. SQLite

**특징**: 트랜잭션/CRUD에 강한 범용 임베디드 DB

| 항목 | 설명 |
|------|------|
| 저장 방식 | Row 기반 |
| 강점 | CRUD, 트랜잭션, 동시 읽기 |
| 약점 | 대량 집계 느림 (전체 row 스캔) |
| 배포 | 파이썬 내장 (import sqlite3) |
| 동시 쓰기 | WAL 모드로 읽기/쓰기 동시 가능 |
| 적합한 경우 | 설정, 메타데이터, 소규모 데이터 CRUD |

```sql
-- 일반적인 CRUD 쿼리에 최적
SELECT * FROM t_cycle WHERE date = '250920' AND session = 'R1'
INSERT INTO t_settings (key, value) VALUES ('shaft_dia', '50')
```

---

## 2. DuckDB

**특징**: 분석(OLAP)에 특화된 컬럼 기반 임베디드 DB

| 항목 | 설명 |
|------|------|
| 저장 방식 | Column 기반 (압축 효율 높음) |
| 강점 | 집계, 윈도우 함수, CSV/Parquet 직접 쿼리 |
| 약점 | 동시 쓰기 단일 writer, 빈번한 단건 INSERT 비효율 |
| 배포 | `pip install duckdb` |
| 적합한 경우 | 대량 데이터 분석, CSV 직접 조회 |

```sql
-- CSV를 DB에 적재 없이 직접 쿼리
SELECT avg(rpm_mean), percentile_cont(0.5) WITHIN GROUP (ORDER BY rpm_mean)
FROM read_csv('PULSE_250920.csv');

-- Parquet 지원
COPY t_cycle TO 'cycles.parquet' (FORMAT PARQUET);
SELECT * FROM 'cycles.parquet' WHERE month = '2509';
```

### SQLite와 성능 비교 (집계 쿼리)

| 데이터 규모 | SQLite | DuckDB |
|-------------|--------|--------|
| 1,000행 | 비슷 | 비슷 |
| 100,000행 | 느려짐 | 빠름 |
| 1,000,000행+ | 매우 느림 | 여전히 빠름 |

컬럼 기반이라 특정 컬럼만 읽으면 되는 집계에서 압도적. 하지만 단건 조회(`WHERE id = ?`)는 SQLite가 빠름.

### CSV 직접 쿼리

DuckDB의 가장 큰 차별점. CSV/JSON/Parquet 파일을 테이블처럼 바로 쿼리 가능.

```sql
-- 여러 CSV를 glob으로 한번에 조회
SELECT * FROM read_csv('data/PULSE_*.csv');

-- CSV 간 JOIN도 가능
SELECT p.*, v.accel_x
FROM read_csv('PULSE_250920.csv') p
JOIN read_csv('VIB_250920.csv') v ON p.cycle_index = v.cycle_index;
```

---

## 3. 시계열 DB (InfluxDB, TimescaleDB)

**특징**: 시간 기반 연속 데이터에 최적화

| 항목 | 설명 |
|------|------|
| 저장 방식 | 시간축 기반 압축 (TSM, Gorilla 등) |
| 강점 | 시간 범위 쿼리, 자동 다운샘플링, 실시간 수집 |
| 약점 | 별도 서버 필요 (InfluxDB) 또는 PostgreSQL 확장 (TimescaleDB) |
| 적합한 경우 | 실시간 센서 수집, 모니터링, IoT |

```sql
-- TimescaleDB: 1분 평균 자동 다운샘플링
SELECT time_bucket('1 minute', timestamp) AS bucket,
       avg(rpm_mean), max(vib_x_rms)
FROM cycles
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY bucket;

-- InfluxDB (Flux 언어)
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "vibration")
  |> aggregateWindow(every: 1m, fn: mean)
```

### 임베디드 vs 서버

| DB | 배포 형태 | 인프라 |
|----|-----------|--------|
| SQLite | 파일 1개 | 없음 |
| DuckDB | 파일 1개 | 없음 |
| InfluxDB | 별도 서버 | Docker 등 필요 |
| TimescaleDB | PostgreSQL 확장 | PG 서버 필요 |

---

## 4. 선택 가이드

```
데이터 수천 건, CRUD 위주           → SQLite ✓
데이터 수만~수백만 건, 분석/집계 위주 → DuckDB
실시간 센서 수집, 스트리밍           → 시계열 DB
CSV를 DB 없이 바로 분석             → DuckDB
```

### 혼합 사용 패턴

SQLite와 DuckDB는 공존 가능:
- **SQLite**: 설정(t_settings), 적재 이력(h_ingested_file) 등 CRUD
- **DuckDB**: 사이클 데이터 집계, CSV 직접 분석

```python
import duckdb
import sqlite3

# DuckDB에서 SQLite 테이블 직접 읽기도 가능
conn = duckdb.connect()
conn.execute("INSTALL sqlite; LOAD sqlite;")
conn.execute("SELECT avg(rpm_mean) FROM sqlite_scan('dash.db', 't_cycle')")
```

---

## 5. 현재 dash 프로젝트 판단

| 기준 | 현재 상황 | 판단 |
|------|-----------|------|
| 데이터 규모 | 수천 행/일 | SQLite 충분 |
| 쿼리 패턴 | 날짜별 전체 조회 | SQLite 충분 |
| CSV 직접 분석 | 미사용 (적재 후 조회) | DuckDB 불필요 |
| 실시간 수집 | 없음 (배치) | 시계열 DB 불필요 |
| 인프라 | 단일 서버 | 임베디드 유리 |

**결론**: PostgreSQL로 전환 완료 (2026-03). 실시간 센서 삽입 대비 + VIB 파형 BYTEA 저장.

---

## 환경변수 분리 패턴

DB 접속 정보 등 환경에 따라 달라지는 값을 코드에서 분리하는 패턴.

### 왜 분리하는가?

| 이유 | 설명 |
|------|------|
| **보안** | DB 비밀번호, API 키를 코드에 넣지 않음. `.env`는 gitignore, 코드만 커밋 |
| **환경별 설정** | 개발/테스트/운영 환경마다 다른 접속 정보. 코드 변경 없이 `.env`만 교체 |
| **팀 협업** | 팀원마다 로컬 포트/비밀번호가 다를 수 있음. `.env.example`을 템플릿으로 공유 |
| **Docker 연동** | docker-compose 포트 변경 시 `.env`만 수정. 코드 재배포 불필요 |

### 파일 구조

```
.env.example   ← git 커밋 (템플릿, 실제 시크릿 없음)
.env           ← gitignore (로컬 설정, 비밀번호 포함)
```

### 사용법 (python-dotenv)

```python
# config.py
from dotenv import load_dotenv
load_dotenv()  # .env 파일의 값을 os.environ에 로드

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/dash")
```

```bash
# .env
DATABASE_URL=postgresql://postgres:dash@localhost:5435/dash
```

`load_dotenv()`는 `.env` 파일을 읽어서 `os.environ`에 주입.
이미 환경변수가 설정되어 있으면 `.env`보다 우선함 (운영 환경에서 직접 설정 가능).

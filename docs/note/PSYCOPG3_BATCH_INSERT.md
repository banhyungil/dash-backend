# psycopg3 배치 INSERT 방법

## 1. 루프 execute (현재 방식)
```python
for cycle in cycles:
    conn.execute(INSERT_SQL, cycle)
conn.commit()
```
- 건건이 서버 왕복 (round-trip)
- `RETURNING id` 사용 가능
- 가장 느림

## 2. executemany
```python
cur = conn.cursor()
cur.executemany(INSERT_SQL, params_list)
conn.commit()
```
- psycopg3가 내부적으로 **파이프라이닝** — 여러 쿼리를 묶어 전송, 서버 왕복 최소화
- `RETURNING` 결과를 개별로 받을 수 없음 (결과 무시)
- 단순 INSERT에 적합

## 3. 멀티 row VALUES + RETURNING
```python
# VALUES 절을 동적으로 조립
from psycopg.sql import SQL, Placeholder

values = SQL(", ").join(
    SQL("({})").format(SQL(", ").join(Placeholder() * col_count))
    for _ in rows
)
query = SQL("INSERT INTO t_cycle (...) VALUES {} RETURNING id").format(values)
ids = conn.execute(query, flat_params).fetchall()
```
- **한 번의 서버 왕복**으로 전체 INSERT + id 반환
- 현재 프로젝트처럼 `RETURNING id` 후 waveform INSERT가 필요한 경우에 적합
- row 수가 매우 많으면 쿼리 문자열이 커질 수 있음 (1,000건 단위 청크 권장)

## 4. COPY (가장 빠름)
```python
with cur.copy("COPY t_cycle (...) FROM STDIN") as copy:
    for row in rows:
        copy.write_row(row)
conn.commit()
```
- PostgreSQL 네이티브 COPY 프로토콜 — 파싱/플래닝 오버헤드 없음
- **대량 적재 시 가장 빠름** (수만 건 이상)
- `RETURNING` 불가, `ON CONFLICT` 불가
- 임시 테이블 + COPY → INSERT ... ON CONFLICT SELECT 패턴으로 우회 가능하나 복잡도 증가

## 성능 비교

성능 차이는 건수보다 **전체 전송 데이터 크기(payload)**에 비례한다.
row당 컬럼이 많거나 BYTEA 같은 큰 데이터가 포함되면 차이가 커진다.

| 방법 | payload 큰 경우 | RETURNING | ON CONFLICT |
|------|----------------|-----------|-------------|
| 루프 execute | 느림 | O | O |
| executemany | 빠름 | X | O |
| 멀티 row VALUES | 빠름 | O | O |
| COPY | 가장 빠름 | X | X |

## 현재 프로젝트 적용 전략

`exists_by_path`로 이미 적재된 파일을 사전 차단하므로, 정상 흐름에서 중복 INSERT가 발생하지 않는다.
따라서 전 테이블 ON CONFLICT 제거 → 단순 INSERT로 통일 가능.

| 테이블 | 방법 | 이유 |
|--------|------|------|
| t_cycle | 멀티 row VALUES + RETURNING | id 반환 필요 (waveform FK) |
| t_pulse_waveform | COPY | BYTEA 대량 데이터, conflict 없음 |
| t_vib_waveform | COPY | 동일 |

### 흐름
```
1. t_cycle: 멀티 row VALUES + RETURNING id → id 목록 확보
2. t_pulse_waveform: COPY (단순 INSERT)
3. t_vib_waveform: COPY (단순 INSERT)
4. conn.commit() — 일괄 커밋
```

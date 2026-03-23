# CSV 포맷 변경 대응 및 데이터 신뢰성 개선 플랜

## Context

2026년 3월 11일경부터 센서 장비의 CSV 저장 포맷이 변경됨.
기존 `DATETIME, [JSON]` 형식에서 `DATETIME, UNIX_TIMESTAMP, [JSON]` 형식으로 바뀌면서,
현재 파서가 timestamp에 unix timestamp까지 포함시켜 저장하는 문제 발생.
또한 파싱/필터링 과정에서 데이터가 조용히 누락되어 디버깅이 어려운 상태.

---

## 1. 포맷 변경 내용

```
# 구 포맷 (~260310 이전)
2025-09-20 08:26:23.212, [{'pulse': 207220, 'accel_x': 0.08, ...}]

# 신 포맷 (260311~ 이후)
2026-03-11 15:05:34.853, 1773205200, [{'pulse': 8751, 'accel_x': 0.08, ...}]
                         ^^^^^^^^^^
                         UNIX_TIMESTAMP 추가됨
```

PULSE, VIB 파일 모두 동일하게 변경됨.

---

## 2. 현재 파서의 문제점

### 2-1. timestamp 오염

`services/csv_parser.py`에서 `", ["` 기준으로 split:

```python
comma_idx = line.index(", [")
timestamp = line[:comma_idx].strip()     # ← 여기서 문제 발생
data_str = line[comma_idx + 2:]          # ← JSON 데이터는 정상
```

신 포맷의 경우:
- **기대값:** `"2026-03-11 15:05:34.853"`
- **실제값:** `"2026-03-11 15:05:34.853, 1773205200"` (unix timestamp 포함)

프론트엔드에서 `new Date(timestamp)` 호출 시 파싱 실패 또는 잘못된 시간 표시.

### 2-2. Silent Data Loss (조용한 데이터 누락)

| 위치 | 조건 | 처리 | 위험도 |
|------|------|------|--------|
| `csv_parser.py:27-28` | PULSE 파싱 실패 | `except: continue` (로그 없음) | **높음** |
| `csv_parser.py:54-55` | VIB 파싱 실패 | `except: continue` (로그 없음) | **높음** |
| `data_router.py:130-131` | RPM 계산 실패 | `continue` (로그 없음) | 중간 |
| `data_router.py:136-137` | expected 검증 실패 | `continue` (로그 없음) | 중간 |

**→ 어떤 데이터가 얼마나 누락됐는지 확인할 방법이 현재 없음**

---

## 3. 수정 사항

### 3-1. `services/csv_parser.py` — 양쪽 포맷 모두 지원

`parse_pulse_csv`, `parse_vib_csv` 두 함수 모두 동일하게 수정:

```python
import logging
logger = logging.getLogger(__name__)

# timestamp 추출 후 unix timestamp 제거
timestamp = line[:comma_idx].strip()
if ", " in timestamp:
    timestamp = timestamp.split(", ")[0].strip()

# except 블록에 로깅 추가
except (ValueError, SyntaxError) as e:
    logger.warning("Skipped line %d in %s: %s", line_num, file_path, e)
    continue
```

| 포맷 | `timestamp` 변수 | 처리 후 |
|------|-------------------|---------|
| 구 포맷 | `"2025-09-20 08:26:23.212"` | 변경 없음 (`, ` 없으므로) |
| 신 포맷 | `"2026-03-11 15:05:34.853, 1773205200"` | `"2026-03-11 15:05:34.853"` |

### 3-2. `config.py` — 캐시 버전 업

```python
CACHE_VERSION = 2  # 1 → 2: 잘못된 timestamp 캐시 무효화
```

기존 캐시에 오염된 timestamp가 저장되어 있으므로 전부 무효화 필요.

### 3-3. `routers/data_router.py` — 스킵 로깅 추가

```python
import logging
logger = logging.getLogger(__name__)

# api_daily_data 함수 내부
skipped_rpm_none = 0
skipped_expected = 0

# RPM 실패 시
if rpm_result is None:
    skipped_rpm_none += 1
    continue

# expected 검증 실패 시
if not is_expected_valid(...):
    skipped_expected += 1
    continue

# 루프 종료 후 요약 로그
logger.info(
    "Date %s: %d cycles OK, skipped %d (rpm_none=%d, expected=%d)",
    date, len(all_pulse_cycles),
    skipped_rpm_none + skipped_expected,
    skipped_rpm_none, skipped_expected
)
```

### 3-4. 프론트엔드 — 변경 불필요

백엔드에서 깨끗한 datetime 문자열을 보내면 `new Date(timestamp)`가 정상 동작.

---

## 4. 수정하지 않는 파일

| 파일 | 이유 |
|------|------|
| `cached_csv_parser.py` | `csv_parser.py`를 호출하므로 자동 반영 |
| `session_merger.py` | timestamp 문자열 정렬이라 정상 동작 |
| `rpm_service.py` | 숫자 데이터만 처리, timestamp 무관 |
| `expected_filter.py` | 동일 |
| `cache_manager.py` | 이미 version 기반 무효화 로직 있음 |
| 프론트엔드 전체 | 백엔드 수정만으로 해결 |

---

## 5. 데이터 흐름

```
CSV 파일 (PULSE_*.csv, VIB_*.csv)
    ↓
csv_parser.py          ← [수정] timestamp 정리 + 로깅
    ↓
cached_csv_parser.py   ← 캐시 버전업으로 자동 재파싱
    ↓
rpm_service.py         → RPM 계산
    ↓
expected_filter.py     → 유효성 검증
    ↓
data_router.py         ← [수정] 스킵 로깅 추가
    ↓
session_merger.py      → 타임스탬프 기준 병합
    ↓
프론트엔드 (차트 렌더링)
```

---

## 6. SQLite 도입 (통계 데이터 산출용)

### 6-1. 목적

근우님 요구사항: "데이터 신뢰성 확보 → 통계 데이터 산출 (일별/월별 가동시간, 이벤트 감지 횟수 등)"

현재 구조에서는 통계 하나 뽑으려면 모든 CSV를 파싱해야 함 → SQLite에 집계값을 저장하여 SQL로 즉시 조회.

### 6-2. 아키텍처

```
[현재]  CSV 수동 반출 → data/ 폴더에 넣기 → 서버가 폴더 스캔+파싱

[변경]  CSV 수동 반출 → 프론트에서 업로드 → 업로드 API → 파싱+검증 → DB 저장
        (나중에 자동 수집 붙으면 → 같은 API 호출)
```

```
방식 1) 로컬 경로 지정 (기본 — 파일 중복 없음)
프론트에서 경로/폴더 입력
    ↓
POST /api/ingest { "paths": [...] } 또는 { "folder": "C:/data/..." }
    ↓
서버가 해당 경로에서 직접 파싱
    ↓
DB에 집계값 + source_path(원본 경로) 저장
    ↓
차트 렌더링 시 source_path에서 직접 읽기

방식 2) 파일 업로드 (원격 배포 시)
프론트에서 CSV 파일 선택
    ↓
POST /api/upload (multipart)
    ↓
서버 uploads/ 폴더에 저장 + 파싱
    ↓
DB에 집계값 + source_path(uploads/ 경로) 저장
```

- **로컬 경로 방식의 장점:**
  - 파일 복사 없음 → 디스크 공간 절약 (VIB 파일이 20~59MB)
  - 기존 data/ 폴더 구조 그대로 사용 가능
  - 폴더 통째로 지정하면 하위 CSV 자동 스캔
- **두 방식 모두 동일한 파싱 파이프라인 사용** (csv_ingester.py)
- 입구가 하나 → 파싱+검증 로직이 한 곳에만 존재
- 업로드 시점에 포맷 체크 → 문제 있으면 즉시 에러 반환
- DB에 들어간 데이터는 이미 검증 완료된 상태
- 나중에 자동 수집 붙어도 같은 파이프라인 호출
- SQLite는 별도 DB 서버 불필요 (파일 하나, Python 기본 내장)
- VIB 배열 데이터(사이클당 5,000+ 포인트)는 DB에 넣지 않음 → source_path에서 조회
- 통계에 필요한 숫자값만 DB에 저장

### 6-3. DB 스키마 (초안)

```sql
-- 사이클별 집계값 (통계 쿼리의 핵심 테이블)
CREATE TABLE cycles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL,          -- "2026-03-11 15:05:34.853"
    date          TEXT NOT NULL,          -- "260311" (YYMMDD)
    month         TEXT NOT NULL,          -- "2601"
    device        TEXT NOT NULL,          -- MAC 주소
    session       TEXT NOT NULL,          -- R1, R2, R3, R4
    cycle_index   INTEGER NOT NULL,       -- 파일 내 사이클 순번

    -- RPM/MPM 집계값
    rpm_mean      REAL,
    rpm_min       REAL,
    rpm_max       REAL,
    mpm_mean      REAL,
    mpm_min       REAL,
    mpm_max       REAL,

    -- 사이클 메타
    duration_ms   REAL,                   -- 사이클 지속시간
    set_count     INTEGER,                -- 실제 펄스 수
    expected_count INTEGER,               -- 예상 펄스 수
    is_valid      BOOLEAN DEFAULT 1,      -- expected 검증 통과 여부

    -- 진동 이벤트
    max_vib_x     REAL,                   -- 해당 사이클 최대 진동 (X축)
    max_vib_z     REAL,                   -- 해당 사이클 최대 진동 (Z축)
    high_vib_event BOOLEAN DEFAULT 0,     -- 0.3g 초과 여부

    -- 원본 파일 추적
    source_path   TEXT,                   -- 원본 CSV 절대경로 (차트 렌더링 시 사용)

    UNIQUE(device, date, cycle_index)
);

-- 통계 쿼리용 인덱스
CREATE INDEX idx_cycles_date ON cycles(date);
CREATE INDEX idx_cycles_month ON cycles(month);
CREATE INDEX idx_cycles_session ON cycles(session);
CREATE INDEX idx_cycles_timestamp ON cycles(timestamp);
```

### 6-4. 통계 쿼리 예시

```sql
-- 일별 가동시간 (초 → 시간)
SELECT date, SUM(duration_ms) / 3600000.0 AS hours
FROM cycles WHERE is_valid = 1
GROUP BY date;

-- 월별 고진동 이벤트 횟수
SELECT month, COUNT(*) AS events
FROM cycles WHERE high_vib_event = 1
GROUP BY month;

-- 세션별 평균 RPM
SELECT session, AVG(rpm_mean) AS avg_rpm
FROM cycles WHERE is_valid = 1 AND month = '2603'
GROUP BY session;

-- 일별 사이클 수 (유효/무효 비교)
SELECT date,
       SUM(CASE WHEN is_valid = 1 THEN 1 ELSE 0 END) AS valid,
       SUM(CASE WHEN is_valid = 0 THEN 1 ELSE 0 END) AS invalid
FROM cycles GROUP BY date;
```

### 6-5. CSV 적재 흐름

```
방식 1) 로컬 경로 지정
1. 프론트에서 경로 입력 (파일 또는 폴더)
    ↓
2. POST /api/ingest { "paths": [...] } 또는 { "folder": "C:/data/..." }
    ↓
3. 서버에서:
   a. 폴더면 하위 PULSE_*.csv / VIB_*.csv 자동 스캔
   b. 파일명으로 타입 판별 (PULSE / VIB)
   c. 포맷 자동 감지 (구 포맷 / 신 포맷)
   d. 파싱 + 검증 → 실패 시 에러 응답 (어떤 줄에서 실패했는지 포함)
   e. RPM/MPM 계산, expected 검증
   f. 집계값 DB INSERT + source_path 저장 (파일 복사 안 함)
    ↓
4. 응답: 적재 결과 (성공 사이클 수, 스킵 수, 에러 상세)

방식 2) 파일 업로드 (원격 배포 시)
1. 프론트에서 CSV 파일 선택 (드래그&드롭)
    ↓
2. POST /api/upload (multipart/form-data)
    ↓
3. 서버에서:
   a~e 동일
   f. uploads/ 폴더에 저장 + DB INSERT (source_path = uploads/ 경로)
    ↓
4. 응답 동일
```

- 이미 적재된 파일 → source_path 기준 중복 체크, 재적재 여부 확인
- 나중에 자동 수집이 붙으면 → 같은 파싱 파이프라인을 내부에서 호출

### 6-6. 구현 파일 계획

| 파일 | 역할 |
|------|------|
| `services/database.py` (신규) | SQLite 연결, 스키마 생성, CRUD |
| `services/csv_ingester.py` (신규) | CSV 파싱 → 검증 → DB INSERT 파이프라인 |
| `routers/ingest_router.py` (신규) | POST /api/ingest (경로), POST /api/upload (파일) |
| `routers/stats_router.py` (신규) | 통계 조회 API |
| `main.py` (수정) | 서버 시작 시 DB 초기화, 라우터 등록 |

### 6-7. 프론트엔드 업로드 UI

| 파일 | 역할 |
|------|------|
| `src/components/FileUpload.tsx` (신규) | CSV 파일 드래그&드롭 / 선택 업로드 |
| `src/api/client.ts` (수정) | 업로드 API 호출 함수 추가 |

---

## 7. 검증 방법

1. 백엔드 서버 재시작 (캐시 무효화 확인)
2. 구 포맷 날짜 (예: `260303`) 선택 → 그래프 정상 표시 확인
3. 신 포맷 날짜 (예: `260312`) 선택 → 그래프 정상 표시 확인
4. 서버 로그에서 스킵된 사이클 수 확인
5. 프론트 RpmChart/VibrationChart에서 시간축 정상 표시 확인
6. SQLite DB 생성 확인 → `sqlite3 dash.db` 접속 후 통계 쿼리 실행

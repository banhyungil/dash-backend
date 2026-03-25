# Config → DB 설정 화면 이관 방안

> 작성일: 2026-03-24
> 상태: 검토 대기

---

## 1. 현황

현재 `config.py`에 하드코딩된 값들이 장비/환경 변경 시 코드 수정 + 서버 재시작을 요구한다.

## 2. 이관 대상

### 이관 O (화면 설정)

| 항목 | 현재 값 | 변경 빈도 | 설명 |
|------|---------|-----------|------|
| `DEFAULT_SHAFT_DIA` | 50mm | 장비 교체 시 | 축 지름 |
| `DEFAULT_PATTERN_WIDTH` | 10mm | 장비 교체 시 | 패턴 폭 |
| `DEFAULT_TARGET_RPM` | 100 | 작업 변경 시 | 목표 RPM |
| `ROLL_DIAMETER_MM` | 140mm | 장비 교체 시 | 롤러 지름 (MPM 계산용) |
| `EXPECTED_TOLERANCE` | 0.1 (10%) | 기준 조정 시 | 유효 사이클 판정 허용 오차 |
| `DEVICE_SESSION_MAP` | 4개 디바이스→R1~R4 | 센서 교체 시 | 디바이스 ID → 세션 매핑 |
| `GRAVITY_OFFSET` | R1/R2: -1.0, R3/R4: 0 | 센서 장착 변경 시 | Z축 중력 보정값 |
| `ALLOW_RPM_ERROR_PER_SET` | 10/20/30 RPM | 기준 조정 시 | RPM 허용 밴드 |

### 이관 X (서버 환경 — config.py 유지)

| 항목 | 이유 |
|------|------|
| `DB_PATH`, `DATA_DIR`, `CACHE_DIR` | 서버 배포 환경에 따라 다름, 환경변수로 관리 |
| `CACHE_VERSION` | 파서 변경 시만 올림, 개발자 영역 |
| `VIB_SAMPLE_RATE` | 센서 하드웨어 스펙 (ADXL355 고정) |
| `RPM_READ_OFFSET` | 알고리즘 파라미터, 튜닝 빈도 극히 낮음 |

---

## 3. 구현 계획

### 3-1. DB 테이블 추가

```sql
CREATE TABLE IF NOT EXISTS t_settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL,
    type    TEXT NOT NULL DEFAULT 'string',  -- string, number, json
    label   TEXT,                            -- 화면 표시용 라벨
    category TEXT                            -- 그룹 (equipment, validation, device)
);
```

초기 데이터:

| key | value | type | label | category |
|-----|-------|------|-------|----------|
| `shaft_dia` | `50` | number | 축 지름 (mm) | equipment |
| `pattern_width` | `10` | number | 패턴 폭 (mm) | equipment |
| `target_rpm` | `100` | number | 목표 RPM | equipment |
| `roll_diameter` | `140` | number | 롤러 지름 (mm) | equipment |
| `expected_tolerance` | `0.1` | number | 유효 판정 허용 오차 | validation |
| `device_session_map` | `{"0013A2...":"R1",...}` | json | 디바이스→세션 매핑 | device |
| `gravity_offset` | `{"R1":{"z":-1.0},...}` | json | 중력 보정값 | device |
| `rpm_error_bands` | `[{"val":10,...},...]` | json | RPM 허용 밴드 | validation |

### 3-2. 백엔드

**settings_repo.py (신규)**
```python
def get_all() -> dict[str, Any]: ...
def get(key: str) -> Any: ...
def set(key: str, value: Any) -> None: ...
```

**routers/settings.py (신규)**
```
GET  /api/settings          — 전체 설정 조회
PUT  /api/settings/:key     — 개별 설정 변경
POST /api/settings/reset    — 초기값으로 리셋
```

**config.py 변경**
- DB에서 값을 읽고, 없으면 현재 하드코딩 값을 fallback으로 사용
- 서버 재시작 없이 설정 반영

```python
def get_setting(key: str, default: Any) -> Any:
    """DB에서 설정값 조회. 없으면 default 반환."""
    ...
```

### 3-3. 프론트엔드

**데이터 관리 페이지에 '설정' 탭 추가**

```
📁 데이터 관리
  [로컬 경로] [파일 업로드] [설정]
```

**설정 화면 구성:**

```
┌─────────────────────────────────────────┐
│  장비 파라미터                            │
│  ┌──────────────┬──────────┐            │
│  │ 축 지름 (mm)  │   [50]   │            │
│  │ 패턴 폭 (mm)  │   [10]   │            │
│  │ 목표 RPM      │  [100]   │            │
│  │ 롤러 지름 (mm) │  [140]   │            │
│  └──────────────┴──────────┘            │
│                                          │
│  유효성 판정                              │
│  ┌──────────────┬──────────┐            │
│  │ 허용 오차 (%)  │   [10]   │            │
│  │ RPM 밴드 1    │   [10]   │            │
│  │ RPM 밴드 2    │   [20]   │            │
│  │ RPM 밴드 3    │   [30]   │            │
│  └──────────────┴──────────┘            │
│                                          │
│  디바이스 매핑                            │
│  ┌──────────────────┬────┬──────┐       │
│  │ 0013A20041F71B01  │ R1 │ Z:-1 │       │
│  │ 0013A20041F9D466  │ R2 │ Z:-1 │       │
│  │ 0013A20041F98275  │ R3 │ Z: 0 │       │
│  │ 0013A20041F9D4F8  │ R4 │ Z: 0 │       │
│  └──────────────────┴────┴──────┘       │
│                                          │
│           [저장]  [초기화]                │
└─────────────────────────────────────────┘
```

### 3-4. 주의사항

- **설정 변경 시 재적재 필요 여부 안내**
  - `shaft_dia`, `pattern_width` 변경 → RPM/MPM 재계산 필요 → "재적재 권장" 경고
  - `target_rpm` 변경 → 차트 기준선만 변경 → 재적재 불필요
  - `expected_tolerance` 변경 → is_valid 재판정 필요 → 재적재 권장
  - `device_session_map` 변경 → 새 데이터부터 적용
- **config.py fallback 유지** — DB에 값이 없으면 현재 하드코딩 값 사용 (초기 기동 시 안전)
- **설정 이력 관리** — 변경 시 이전 값을 로그로 남겨서 추적 가능하게

---

## 4. 구현 순서

```
Step 1. t_settings 테이블 + settings_repo.py + 라우터
Step 2. config.py → get_setting() fallback 패턴 적용
Step 3. 프론트 설정 탭 UI
Step 4. 설정 변경 시 재적재 경고 로직
```

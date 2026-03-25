# Dash Backend - Architecture

## 프로젝트 개요

롤러 설비의 센서 데이터(펄스, 진동)를 적재·분석·시각화하는 대시보드 백엔드.

## 기술 스택

- **런타임**: Python 3.12+
- **프레임워크**: FastAPI
- **DB**: PostgreSQL 17 (Docker)
- **DB 드라이버**: psycopg3 — raw SQL, ORM 없음
- **마이그레이션**: Alembic (raw SQL)
- **환경 설정**: python-dotenv (`.env`)

---

## 프로젝트 구조

```
dash-backend/
├── main.py                  # FastAPI 앱 진입점
├── config.py                # 환경변수 로드, 상수 정의
├── routers/
│   ├── cycles.py            # 사이클 데이터 조회 API
│   ├── ingest.py            # CSV 적재 API
│   └── settings.py          # 설정 CRUD API
├── services/
│   ├── ingest_service.py    # CSV 파싱 → DB 적재 오케스트레이션
│   ├── csv_parser.py        # PULSE/VIB CSV 파싱
│   ├── rpm_service.py       # 펄스 → RPM/MPM 변환
│   ├── daily_data_service.py # 일별 사이클 데이터 조회
│   ├── expected_filter.py   # 이론 펄스 수 계산
│   ├── signal_service.py    # 진동 신호 통계 (RMS, peak 등)
│   ├── vibration_analyzer.py # 진동 분석 (burst, impact)
│   ├── session_merger.py    # 다중 세션 데이터 병합
│   ├── excel_export.py      # Excel 내보내기
│   ├── settings_service.py  # DB 설정 관리
│   └── database.py          # DB 연결, 스키마 초기화
├── repos/
│   ├── cycles_repo.py       # t_cycle CRUD
│   ├── pulse_waveform_repo.py # t_pulse_waveform CRUD
│   ├── vib_waveform_repo.py # t_vib_waveform CRUD
│   ├── ingested_files_repo.py # h_ingested_file CRUD
│   └── settings_repo.py     # t_settings CRUD
├── alembic/                 # DB 마이그레이션
├── tests/                   # pytest 테스트
├── docs/
│   ├── architecture.md      # 이 문서
│   ├── plans/               # 구현 계획
│   └── note/                # 학습 노트
├── docker-compose.yml       # PostgreSQL 컨테이너
├── .env                     # 로컬 환경변수 (gitignore)
└── .env.example             # 환경변수 템플릿
```

---

## 아키텍처

```
Client HTTP Request
    ↓
main.py (CORS, 라우터 마운트)
    ↓
routers/ (HTTP 파라미터 파싱, 응답 포매팅)
    ↓
services/ (비즈니스 로직, CSV 파싱, 계산)
    ↓
repos/ (raw SQL, 데이터 접근)
    ↓
PostgreSQL
```

### 레이어 역할

| 레이어 | 역할 |
|--------|------|
| **routers** | HTTP 입출력, 요청 검증, 응답 코드 결정 |
| **services** | 비즈니스 로직 (파싱, RPM 계산, 통계, 내보내기) |
| **repos** | SQL 실행, DB 행 ↔ dict 변환 |

---

## DB 테이블

| 테이블 | 용도 |
|--------|------|
| `t_cycle` | 사이클별 집계 데이터 (RPM, 진동 통계 등) |
| `t_pulse_waveform` | 펄스 원시 파형 (BYTEA) |
| `t_vib_waveform` | 진동 원시 파형 (BYTEA) |
| `h_ingested_file` | 적재 이력 (중복 방지) |
| `t_settings` | 런타임 설정 (shaft_dia, vib_threshold 등) |

---

## 설정 계층

| 분류 | 위치 | 예시 |
|------|------|------|
| 인프라/환경 | `config.py` + `.env` | DATABASE_URL, PORT |
| 센서 스펙 (불변) | `config.py` 상수 | VIB_SAMPLE_RATE, RPM_READ_OFFSET |
| 비즈니스 (변경 가능) | `t_settings` (DB) | shaft_dia, vib_threshold |

---

## API 엔드포인트

### 사이클 (`/api/cycles`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/months` | 적재된 월 목록 |
| GET | `/dates` | 월별 일자 목록 + 사이클 수 |
| GET | `/daily` | 일별 사이클 상세 데이터 |
| GET | `/monthly-summary` | 월별 적재 현황 요약 |
| GET | `/export/excel` | Excel 내보내기 |

### 적재 (`/api/ingest`)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/scan` | 폴더 스캔 → 적재 대상 CSV 목록 |
| POST | `/files` | CSV 파일 배치 적재 |

### 설정 (`/api/settings`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 전체 설정 조회 |
| PUT | `/{key}` | 설정값 변경 |

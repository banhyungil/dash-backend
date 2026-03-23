# 네이밍 일관화 방안 — 리소스 중심 구조

## Context

프론트 API → 백엔드 라우터 → 서비스 → 리포 → DB 테이블까지
**리소스(resource) 중심**으로 이름을 통일하여 어디서든 같은 이름으로 추적 가능하게 함.

---

## 1. 리소스 정의

현재 프로젝트의 핵심 리소스:

| 리소스 | 설명 | 현재 이름 |
|--------|------|----------|
| **cycle** | 사이클별 측정 집계값 | cycles, CycleData |
| **file** | 적재된 파일 이력 | ingested_files, ScanFile |
| **month** | 월 목록 | MonthInfo |
| **device** | 디바이스(센서) | devices |
| **date** | 날짜별 데이터 | DateInfo |

---

## 2. 레이어별 네이밍 규칙

### 규칙 요약

```
리소스: cycles (복수형)

DB 테이블:     t_cycle (단수)
Repo 파일:     repos/cycles_repo.py (복수)
Repo 함수:     find_by_date(), insert_many()
Service 파일:  services/cycles_service.py (복수)
Service 함수:  get_daily_cycles(), ingest_pulse_file()
Router 파일:   routers/cycles_router.py (복수)
Router 함수:   api_get_daily_cycles()
API 경로:      GET /api/cycles/daily (복수)
Front 함수:    fetchDailyCycles() (복수)
Front 타입:    CycleData
```

### 테이블 접두사

| 접두사 | 유형 | 예시 |
|--------|------|------|
| `t_` | 트랜잭션/데이터 | `t_cycle` |
| `h_` | 히스토리/이력 | `h_ingested_file` |
| `m_` | 마스터/설정 | `m_device` (향후) |

---

## 3. 현재 → 변경 매핑

### DB 테이블

| 현재 | 변경 | 이유 |
|------|------|------|
| `cycles` | `t_cycle` | 접두사 + 단수형 |
| `ingested_files` | `h_ingested_file` | 이력 접두사 + 단수형 |

### Repo 레이어

| 현재 | 변경 |
|------|------|
| `repos/cycle_repo.py` | `repos/cycles_repo.py` |
| `repos/file_repo.py` | `repos/ingested_files_repo.py` |
| `insert_cycles()` | `insert_many()` |
| `get_ingest_status()` | `get_monthly_summary()` |
| `record_ingested_file()` | `upsert()` |
| `is_file_ingested()` | `exists_by_path()` |

### Service 레이어

**리소스 서비스 (복수형):**

| 현재 | 변경 | 이유 |
|------|------|------|
| `services/csv_ingester.py` | `services/ingest_service.py` | 액션 중심 서비스 |
| (신규) | `services/cycles_service.py` | cycles 리소스 서비스 (DAILY_DATA_REFACTOR에서 추가) |
| `ingest_paths()` | `ingest_files()` | |
| `ingest_pulse_file()` | `ingest_pulse_file()` (유지) | |
| `scan_folder()` | `scan_folder()` (유지) | |

**유틸리티 (이름 유지):**

| 파일 | 비고 |
|------|------|
| `services/csv_parser.py` | CSV 파싱 유틸 |
| `services/rpm_service.py` | RPM 계산 유틸 |
| `services/expected_filter.py` | 유효성 검증 유틸 |
| `services/session_merger.py` | 세션 병합 유틸 |
| `services/database.py` | DB 연결/스키마 인프라 |
| `services/folder_scanner.py` | 향후 제거 (DB로 대체) |

### Router 레이어

| 현재 | 변경 | 이유 |
|------|------|------|
| `routers/data_router.py` | `routers/cycles_router.py` | 리소스 = cycles |
| `routers/ingest_router.py` | `routers/ingest_router.py` | 유지 (액션 중심 라우터) |

### API 경로

| 현재 | 변경 | 비고 |
|------|------|------|
| `GET /api/months` | `GET /api/months` | 유지 |
| `GET /api/devices` | `GET /api/devices` | 유지 |
| `GET /api/dates` | `GET /api/dates` | 유지 |
| `GET /api/daily-data` | `GET /api/cycles/daily` | 리소스 중심 |
| `GET /api/test-export` | `GET /api/cycles/export` | 리소스 하위 |
| `POST /api/ingest/scan` | `POST /api/ingest/scan` | 유지 |
| `POST /api/ingest` | `POST /api/ingest` | 유지 |
| `POST /api/upload` | `POST /api/ingest/upload` | ingest 하위로 통일 |
| `GET /api/ingest/status` | `GET /api/ingest/status` | 유지 |

### Frontend API (axios + 리소스별 파일 분리)

**axios 도입** — 공통 base URL, 에러 자동 throw, 제네릭 타입 지원.

**파일 분리:**

| 파일 | 역할 |
|------|------|
| `api/client.ts` | axios 인스턴스 (base URL, 공통 설정) |
| `api/types.ts` | 모든 인터페이스 (CycleData, IngestResult, ...) |
| `api/cycles.ts` | cycles 리소스 API 함수 |
| `api/ingest.ts` | ingest 리소스 API 함수 |

**api/client.ts:**
```typescript
import axios from 'axios';

const client = axios.create({
  baseURL: 'http://localhost:8001/api',
});

export default client;
```

**api/cycles.ts:**
```typescript
import client from './client';
import type { MonthInfo, DateInfo, DailyDataResponse } from './types';

export const fetchMonths = () =>
  client.get<MonthInfo[]>('/months').then(res => res.data);

export const fetchDevices = (month: string) =>
  client.get<string[]>('/devices', { params: { month } }).then(res => res.data);

export const fetchDates = (month: string, device: string) =>
  client.get<DateInfo[]>('/dates', { params: { month, device } }).then(res => res.data);

export const fetchDailyCycles = (month: string, date: string) =>
  client.get<DailyDataResponse>('/cycles/daily', { params: { month, date } }).then(res => res.data);

export const exportCycles = (month: string, date: string) =>
  client.get('/cycles/export', { params: { month, date } }).then(res => res.data);
```

**api/ingest.ts:**
```typescript
import client from './client';
import type { ScanResult, IngestResult, IngestStatus } from './types';

export const scanFolder = (folder: string) =>
  client.post<ScanResult>('/ingest/scan', { folder }).then(res => res.data);

export const ingestFiles = (paths: string[]) =>
  client.post<IngestResult>('/ingest', { paths }).then(res => res.data);

export const uploadFiles = (files: File[]) => {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  return client.post<IngestResult>('/ingest/upload', formData).then(res => res.data);
};

export const getIngestStatus = () =>
  client.get<IngestStatus>('/ingest/status').then(res => res.data);
```

**함수명 매핑:**

| 현재 | 변경 | 파일 | 호출 경로 |
|------|------|------|----------|
| `fetchMonths()` | `fetchMonths()` | `cycles.ts` | `GET /api/months` |
| `fetchDevices()` | `fetchDevices()` | `cycles.ts` | `GET /api/devices` |
| `fetchDates()` | `fetchDates()` | `cycles.ts` | `GET /api/dates` |
| `fetchDailyData()` | `fetchDailyCycles()` | `cycles.ts` | `GET /api/cycles/daily` |
| `testExport()` | `exportCycles()` | `cycles.ts` | `GET /api/cycles/export` |
| `scanFolder()` | `scanFolder()` | `ingest.ts` | `POST /api/ingest/scan` |
| `ingestPaths()` | `ingestFiles()` | `ingest.ts` | `POST /api/ingest` |
| `uploadFiles()` | `uploadFiles()` | `ingest.ts` | `POST /api/ingest/upload` |
| `getIngestStatus()` | `getIngestStatus()` | `ingest.ts` | `GET /api/ingest/status` |

---

## 4. 전체 흐름 예시 (cycles 리소스)

```
[Front]  fetchDailyCycles(month, date)
            ↓
[API]    GET /api/cycles/daily?month=2603&date=260311
            ↓
[Router] cycles_router.py → api_get_daily_cycles()
            ↓
[Service] cycles_service.py → get_daily_cycles()
            ↓
[Repo]   cycles_repo.py → find_by_date()
            ↓
[DB]     SELECT * FROM t_cycle WHERE month=? AND date=?
```

```
[Front]  ingestFiles(paths)
            ↓
[API]    POST /api/ingest
            ↓
[Router] ingest_router.py → api_ingest()
            ↓
[Service] ingest_service.py → ingest_files()
            ↓
[Repo]   cycles_repo.py → insert_many()
         ingested_files_repo.py → upsert()
            ↓
[DB]     INSERT INTO t_cycle ...
         INSERT INTO h_ingested_file ...
```

---

## 5. 파일 구조 (변경 후)

```
dash-backend/
├── routers/
│   ├── cycles_router.py        ← data_router.py에서 rename
│   └── ingest_router.py        ← 유지
├── services/
│   ├── database.py             ← 유지 (DB 연결/스키마)
│   ├── ingest_service.py       ← csv_ingester.py에서 rename
│   ├── csv_parser.py           ← 유지 (CSV 파싱 유틸)
│   ├── rpm_service.py          ← 유지 (RPM 계산 유틸)
│   ├── expected_filter.py      ← 유지
│   ├── session_merger.py       ← 유지
│   └── chart_data_loader.py    ← 신규 (source_path → 배열 데이터)
├── repos/
│   ├── cycles_repo.py          ← cycle_repo.py에서 rename
│   └── ingested_files_repo.py  ← file_repo.py에서 rename
└── tests/
    ├── test_csv_parser.py
    ├── test_cycles_repo.py     ← test_repos.py에서 rename
    ├── test_ingest_service.py  ← test_csv_ingester.py에서 rename
    └── test_expected_filter.py

dash-front/src/
├── api/
│   ├── client.ts               ← axios 인스턴스 (base URL만)
│   ├── types.ts                ← 신규: 모든 인터페이스
│   ├── cycles.ts               ← 신규: cycles 리소스 API
│   └── ingest.ts               ← 신규: ingest 리소스 API
├── pages/
│   ├── DateSelector.tsx
│   ├── DataManager.tsx
│   └── Charts.tsx
└── components/
    ├── ...
```

---

## 6. 구현 순서

1. **DB 테이블명 변경** — `cycles` → `t_cycle`, `ingested_files` → `h_ingested_file`
2. **Repo 파일 rename** — `cycle_repo.py` → `cycles_repo.py`, `file_repo.py` → `ingested_files_repo.py`, 함수명 변경
3. **Service 파일 rename** — `csv_ingester.py` → `ingest_service.py`
4. **Router 파일 rename** — `data_router.py` → `cycles_router.py`, 경로 변경
5. **Frontend API 분리** — axios 설치, client.ts/types.ts/cycles.ts/ingest.ts 분리, 컴포넌트 import 변경
6. **테스트 파일 update** — import 경로, 함수명 반영
7. **E2E 테스트 확인** — 프론트↔백엔드 연동 정상 확인

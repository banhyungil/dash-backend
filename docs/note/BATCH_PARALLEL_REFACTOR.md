# 적재 성능 개선 — 배치 INSERT + 병렬 파싱

## Context

CSV 파일을 대량 적재할 때 느린 문제.
파일 수가 많을수록 체감 속도가 급격히 떨어짐.

---

## 병목 원인 분석

### 1. 파일마다 커넥션/커밋 반복

```
전 (순차):
  파일1 → 커넥션 열기 → INSERT → commit → 닫기
  파일2 → 커넥션 열기 → INSERT → commit → 닫기
  ...반복 100번

→ SQLite에서 commit이 가장 비싼 작업 (디스크 fsync)
→ 100개 파일 = 100번 commit = 심각한 I/O 병목
```

### 2. 파싱+계산이 순차 실행

```
전:
  파일1 파싱(CPU) → 계산(CPU) → 파일2 파싱 → 계산 → ...

→ CPU 작업인데 단일 코어만 사용
→ 파일 간 의존성 없으므로 병렬화 가능
```

---

## 개선 내용

### 1. 배치 INSERT — 커밋 1회로 통합

**변경 파일:** `repos/cycles_repo.py`, `repos/ingested_files_repo.py`, `services/ingest_service.py`

```python
# cycles_repo.py — conn 파라미터 추가
def insert_many(cycles, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = database.get_connection()
    # ... executemany ...
    if own_conn:
        conn.commit()  # 외부 conn이면 커밋 안 함 → 호출자가 관리

# ingest_service.py — 한 트랜잭션으로 묶기
conn = database.get_connection()
for result in results:
    _write_result_to_db(result, conn)  # INSERT만, 커밋 안 함
conn.commit()  # 마지막에 한 번만 커밋
conn.close()
```

**효과:**
```
전: 100개 파일 × commit 1회 = commit 100회
후: 100개 파일 × INSERT만 + commit 1회 = commit 1회
```

### 2. 병렬 파싱 — ProcessPoolExecutor

**변경 파일:** `services/ingest_service.py`

```
처리 흐름:
  1단계: 파싱 + RPM 계산 (CPU 작업)
         → ProcessPoolExecutor로 병렬 실행 (최대 4 workers)
         → DB 쓰기 없음 — 멀티프로세싱에서 안전

  2단계: 결과 모아서 배치 DB INSERT
         → 단일 커넥션, 단일 트랜잭션, commit 1회

  3단계: 응답 집계
```

**구조 분리:**

| 함수 | 역할 | DB 접근 |
|------|------|---------|
| `_process_file()` | 파싱 + 계산 | 없음 (워커 프로세스에서 안전) |
| `_write_result_to_db()` | DB INSERT | 있음 (메인 프로세스에서만 실행) |
| `ingest_files()` | 오케스트레이션 | commit 1회 |

```python
# 2개 이하: 순차 실행 (프로세스 풀 오버헤드 > 이득)
if len(paths) <= 2:
    results = [_process_file(p) for p in paths]

# 3개 이상: 병렬 실행
else:
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_process_file, p): p for p in paths}
        for future in as_completed(futures):
            results.append(future.result())
```

---

## 비동기 적재 (프론트 UX 개선)

**변경 파일:** `routers/ingest.py`, 프론트 `PathIngest.tsx`, `FileUpload.tsx`

### 백엔드

```
POST /api/ingest → 즉시 job_id 반환 (BackgroundTasks로 백그라운드 실행)
GET /api/ingest/job/{job_id} → 진행 상태 조회

응답 예시:
{
  "job_id": "a1b2c3d4",
  "status": "running",      // queued → running → done
  "total_files": 100,
  "completed_files": 42,
  "success_cycles": 1234
}
```

### 프론트

```
[적재 시작] 클릭
  → POST /api/ingest → job_id 받음
  → 1초 간격 폴링 (GET /api/ingest/job/{job_id})
  → 프로그레스 바 실시간 업데이트
  → status === 'done' → 폴링 중단 + 결과 표시
```

---

## 전체 흐름 (최종)

```
프론트: [적재 시작] 클릭
  ↓
백엔드: job_id 즉시 반환 → BackgroundTasks에서 실행
  ↓
1단계: ProcessPoolExecutor로 파싱+계산 병렬 실행
       파일1 파싱 ─┐
       파일2 파싱 ─┼→ (최대 4 워커)
       파일3 파싱 ─┘
  ↓
2단계: 결과 모아서 배치 INSERT → commit 1회
  ↓
3단계: job status = 'done'
  ↓
프론트: 폴링으로 감지 → 결과 카드 표시
```

---

## 관련 파일

| 파일 | 변경 내용 |
|------|----------|
| `repos/cycles_repo.py` | `insert_many(conn=)` 파라미터 추가 |
| `repos/ingested_files_repo.py` | `upsert(conn=)` 파라미터 추가 |
| `services/ingest_service.py` | 병렬 파싱 + 배치 DB 저장 구조로 리팩토링 |
| `routers/ingest.py` | BackgroundTasks 비동기 + job 상태 API |
| `src/api/ingest.ts` | `getJobStatus()` 추가 |
| `src/api/types.ts` | `IngestJob` 타입 추가 |
| `src/components/PathIngest.tsx` | 폴링 + 프로그레스 바 |
| `src/components/FileUpload.tsx` | 동일 |

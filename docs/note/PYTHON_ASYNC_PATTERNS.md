# Python 비동기 처리 3가지 패턴

## 개요

Python에서 비동기/병렬 처리는 상황에 따라 3가지 방식을 사용.

```
CPU 작업 (파싱, 계산)       → ProcessPoolExecutor
I/O 대기 (파일, 네트워크)    → ThreadPoolExecutor
웹서버/대량 I/O             → asyncio (async/await)
```

---

## 1. ProcessPoolExecutor — CPU 작업 병렬화

별도 **프로세스**를 생성하여 CPU 작업을 진짜 병렬로 실행.

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

with ProcessPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(parse_csv, path): path for path in paths}
    for future in as_completed(futures):
        result = future.result()
```

| 항목 | 설명 |
|------|------|
| **용도** | 파싱, 계산, 이미지 처리 등 CPU를 많이 쓰는 작업 |
| **병렬 방식** | OS 프로세스 (각각 독립된 메모리) |
| **GIL** | 영향 없음 (프로세스별 독립 GIL → 진짜 병렬) |
| **오버헤드** | 큼 (프로세스 생성 + 데이터 직렬화) |
| **데이터 공유** | 불가 (반환값으로만 전달) |
| **이 프로젝트** | CSV 파싱 + RPM 계산에 사용 |

### 언제 쓰나?
- `ast.literal_eval`, 수학 계산, numpy 연산 등
- 파일 수가 3개 이상일 때 (이하는 오버헤드 > 이득)

---

## 2. ThreadPoolExecutor — I/O 작업 병렬화

별도 **스레드**를 생성하여 I/O 대기 시간을 겹침.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(fetch_url, url): url for url in urls}
    for future in as_completed(futures):
        result = future.result()
```

| 항목 | 설명 |
|------|------|
| **용도** | API 호출, 파일 다운로드, DB 쿼리 등 대기 시간이 긴 작업 |
| **병렬 방식** | OS 스레드 (같은 메모리 공유) |
| **GIL** | 영향 있음 (CPU 작업은 한 번에 하나만 실행) |
| **오버헤드** | 중간 |
| **데이터 공유** | 가능 (같은 메모리, 락 주의) |

### 언제 쓰나?
- 외부 API 10개 동시 호출
- 파일 100개 동시 다운로드
- CPU 작업에는 쓰지 않음 (GIL 때문에 병렬 안 됨)

### GIL (Global Interpreter Lock)이란?
```
Python 인터프리터가 한 번에 하나의 스레드만 Python 코드를 실행하도록 하는 잠금.

스레드 A: [계산]─────[대기]─────[계산]
스레드 B:       [대기]─────[계산]─────[대기]
                      ↑
                  GIL 때문에 CPU 작업은 교대로만 실행
                  → I/O 대기 중에는 다른 스레드가 실행 가능
                  → CPU 작업은 병렬이 아님
```

---

## 3. asyncio — 비동기 I/O (이벤트 루프)

단일 스레드에서 **이벤트 루프**로 비동기 처리. JS의 async/await와 가장 유사.

```python
import asyncio

async def fetch_data(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

async def main():
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks)  # 전부 동시에 실행

asyncio.run(main())
```

| 항목 | 설명 |
|------|------|
| **용도** | 웹서버(FastAPI), 웹소켓, 대량 API 호출 |
| **병렬 방식** | 단일 스레드 이벤트 루프 (대기 중 다른 작업으로 전환) |
| **GIL** | 무관 (스레드 1개만 사용) |
| **오버헤드** | 가장 작음 |
| **JS 대응** | async/await + Promise.all() |

### 언제 쓰나?
- FastAPI 엔드포인트 (`async def`)
- 웹소켓 실시간 통신
- 수천 개 HTTP 요청 동시 처리

---

## JavaScript 대응 비교

| Python | JavaScript | 설명 |
|--------|-----------|------|
| `Future` | `Promise` | 미래에 완료될 작업 |
| `future.result()` | `await promise` | 결과 꺼내기 |
| `as_completed(futures)` | `Promise.race()` 반복 | 완료 순서대로 |
| `asyncio.gather()` | `Promise.all()` | 전부 동시 실행 |
| `ProcessPoolExecutor` | `Worker Threads` | CPU 병렬 |
| `ThreadPoolExecutor` | — (이벤트 루프로 해결) | I/O 병렬 |
| `async/await` | `async/await` | 동일 문법 |

---

## 이 프로젝트의 하이브리드 구조

```
FastAPI (asyncio 기반)
    ↓
POST /api/ingest → BackgroundTasks (asyncio)
    ↓
ingest_files() → ProcessPoolExecutor (CPU 병렬)
    ↓                ↓              ↓
    파일1 파싱     파일2 파싱     파일3 파싱  (별도 프로세스)
    ↓                ↓              ↓
    결과 모아서 → SQLite INSERT (메인 프로세스, 단일 커밋)
```

| 레이어 | 방식 | 이유 |
|--------|------|------|
| FastAPI 서버 | asyncio | 웹 요청 처리 (I/O) |
| 적재 작업 | BackgroundTasks | 프론트에 즉시 응답 |
| CSV 파싱 + 계산 | ProcessPoolExecutor | CPU 작업 → 진짜 병렬 필요 |
| DB 저장 | 순차 (단일 커넥션) | SQLite는 동시 쓰기 불가 |

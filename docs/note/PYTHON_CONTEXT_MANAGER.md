# Python 컨텍스트 매니저 (with 문)

## 개념

`with` 문은 **자원 획득 → 사용 → 정리**를 자동으로 보장하는 패턴.
`try/finally`를 깔끔하게 쓰는 문법.

```python
# with 사용
with open("a.txt") as f:
    data = f.read()
# 블록 끝나면 f.close() 자동 호출

# 동일한 코드 (with 없이)
f = open("a.txt")
try:
    data = f.read()
finally:
    f.close()  # 에러가 나도 반드시 실행
```

---

## with에 쓸 수 있는 조건

`__enter__`와 `__exit__` 메서드를 정의한 객체만 `with`에 사용 가능.

```python
class MyResource:
    def __enter__(self):
        """with 블록 진입 시 실행. 반환값이 as 뒤의 변수에 바인딩."""
        print("자원 획득")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """with 블록 끝날 때 실행. 에러가 나도 반드시 실행."""
        print("자원 정리")

with MyResource() as r:
    print("사용 중")

# 출력:
# 자원 획득
# 사용 중
# 자원 정리
```

### __exit__의 파라미터

| 파라미터 | 설명 |
|----------|------|
| `exc_type` | 예외 클래스 (정상 종료 시 None) |
| `exc_val` | 예외 인스턴스 (정상 종료 시 None) |
| `exc_tb` | 트레이스백 (정상 종료 시 None) |

```python
def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    if exc_type is not None:
        print(f"에러 발생: {exc_val}")
    # return True 하면 예외를 삼킴 (보통 안 함)
```

---

## 실제 사용 예시

### 파일 I/O
```python
with open("data.csv", "r") as f:
    lines = f.readlines()
# → __exit__에서 f.close() 호출
```

### DB 커넥션
```python
with sqlite3.connect("dash.db") as conn:
    conn.execute("INSERT INTO ...")
# → __exit__에서 conn.close() 호출
```

### 프로세스 풀 (이 프로젝트에서 사용)
```python
with ProcessPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(fn, arg): arg for arg in items}
    for future in as_completed(futures):
        result = future.result()
# → __exit__에서 executor.shutdown() 호출 (워커 프로세스 정리)
```

### 락 (threading)
```python
lock = threading.Lock()
with lock:
    shared_data += 1
# → __exit__에서 lock.release() 호출
```

---

## 간편 생성: @contextmanager 데코레이터

클래스 없이 함수로 컨텍스트 매니저를 만들 수 있음.

```python
from contextlib import contextmanager

@contextmanager
def db_transaction():
    conn = get_connection()
    try:
        yield conn        # yield 전 = __enter__, yield 값 = as 변수
        conn.commit()     # 정상 종료 시
    except Exception:
        conn.rollback()   # 에러 시
        raise
    finally:
        conn.close()      # 항상 실행 = __exit__

# 사용
with db_transaction() as conn:
    conn.execute("INSERT INTO ...")
    conn.execute("INSERT INTO ...")
# → 성공하면 commit, 실패하면 rollback, 항상 close
```

### 이 프로젝트의 FastAPI lifespan도 같은 패턴

```python
# main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()      # 서버 시작 시 (yield 전)
    yield          # 서버 실행 중
    # 서버 종료 시 (yield 후) — 필요하면 정리 코드 작성
```

---

## 요약

| 항목 | 설명 |
|------|------|
| **목적** | 자원 정리를 자동으로 보장 (close, shutdown, release 등) |
| **조건** | `__enter__` + `__exit__` 메서드 필요 |
| **간편 생성** | `@contextmanager` 데코레이터 (yield 기반) |
| **핵심** | 에러가 나도 `__exit__`은 반드시 실행됨 |

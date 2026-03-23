# Python Futures 병렬 처리 패턴

## 이 프로젝트에서 사용하는 코드

```python
with ProcessPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(_process_file, p): p for p in paths}
    for future in as_completed(futures):
        try:
            results.append(future.result())
        except Exception as e:
            p = futures[future]
            results.append({"errors": [str(e)], "source": p})
```

한 줄씩 풀어서 설명.

---

## 1. executor.submit() — 작업 제출

```python
future = executor.submit(_process_file, p)
#        ^^^^^^^^ 함수      ^^^^^^^^^ 인자
```

- `_process_file(p)`를 **워커 프로세스에 던짐**
- 즉시 반환 — `future` 객체를 받음 (아직 결과 없음)
- 워커가 백그라운드에서 실행 중

```python
future = executor.submit(fn, arg1, arg2)
# → 워커에서 fn(arg1, arg2) 실행
# → future.result()로 나중에 결과 꺼냄
```

---

## 2. dict comprehension — future → 원본 매핑

```python
futures = {executor.submit(_process_file, p): p for p in paths}
```

풀어쓰면:
```python
futures = {}
for p in paths:
    future = executor.submit(_process_file, p)
    futures[future] = p

# 결과 딕셔너리:
# {
#   <Future 1>: "C:/.../PULSE_260311.csv",
#   <Future 2>: "C:/.../PULSE_260312.csv",
#   <Future 3>: "C:/.../VIB_260311.csv",
# }
```

| key | value |
|-----|-------|
| future 객체 | 원본 파일 경로 |

**왜 딕셔너리인가?** → 에러 발생 시 어떤 파일에서 에러났는지 역추적하기 위해.

---

## 3. as_completed() — 완료 순서대로 수거

```python
for future in as_completed(futures):
    result = future.result()
```

- **제출 순서가 아니라, 완료된 순서대로** future를 반환
- 빨리 끝난 파일 결과부터 먼저 받을 수 있음

```
제출 순서:  파일1, 파일2, 파일3
완료 순서:  파일3(0.1초) → 파일1(0.3초) → 파일2(0.5초)
                ↑
          as_completed는 이 순서로 반환
```

### 비교: as_completed vs 제출 순서

```python
# 완료 순서 (as_completed) — 빠른 것부터
for future in as_completed(futures):
    result = future.result()

# 제출 순서 — 느린 것 때문에 블로킹
for future in futures:
    result = future.result()  # 첫 번째가 느리면 다 기다림
```

---

## 4. future.result() — 결과 꺼내기

```python
result = future.result()
```

- 워커가 반환한 값을 꺼냄
- 워커에서 예외가 발생했으면 여기서 다시 raise됨

```python
try:
    result = future.result()       # 정상 → 결과 받기
except Exception as e:
    p = futures[future]            # 에러 → 딕셔너리에서 원본 경로 찾기
    print(f"{p}에서 에러: {e}")
```

---

## 5. 전체 흐름 정리

```
paths = ["파일1.csv", "파일2.csv", "파일3.csv"]

┌─ executor.submit(fn, 파일1) → Future1 ─→ 워커1에서 실행 중
├─ executor.submit(fn, 파일2) → Future2 ─→ 워커2에서 실행 중
└─ executor.submit(fn, 파일3) → Future3 ─→ 워커3에서 실행 중

futures = {Future1: "파일1", Future2: "파일2", Future3: "파일3"}

as_completed(futures):
  Future3 완료 → result3 = Future3.result()
  Future1 완료 → result1 = Future1.result()
  Future2 완료 → result2 = Future2.result()

results = [result3, result1, result2]  (완료 순서)
```

---

## dict comprehension 추가 예시

```python
# 기본
{key: value for item in iterable}

# 숫자 → 제곱
{x: x**2 for x in [1, 2, 3]}
# → {1: 1, 2: 4, 3: 9}

# 리스트 → 인덱스 매핑
{v: i for i, v in enumerate(["a", "b", "c"])}
# → {"a": 0, "b": 1, "c": 2}

# 조건 포함
{x: x**2 for x in range(10) if x % 2 == 0}
# → {0: 0, 2: 4, 4: 16, 6: 36, 8: 64}
```

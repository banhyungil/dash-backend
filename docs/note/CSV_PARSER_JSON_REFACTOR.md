# CSV 파서 리팩토링 — ast.literal_eval → json.loads

## Context

CSV 적재 시 파싱이 느린 문제.
특히 VIB 파일은 한 줄에 수천 개 dict가 있어서 `ast.literal_eval`이 심각한 병목.

---

## CSV 데이터 구조

이 프로젝트의 CSV는 **일반 CSV가 아님**. 한 줄에 JSON 배열이 통째로 들어있는 구조.

```
일반 CSV:    col1,col2,col3              → 쉼표/탭으로 split
이 파일:     timestamp, [{...}, {...}]    → 배열 안에도 쉼표가 있어 일반 파서 사용 불가
```

```
# PULSE (한 줄 = 1 사이클, 5~15개 dict)
2026-03-11 15:05:34.853, 1773212400, [{'pulse': 8751, 'accel_x': 0.08}, {'pulse': 6312, 'accel_x': 0.07}]

# VIB (한 줄 = 1 사이클, 5,000+ dict)
2026-03-11 15:06:01.584, 1773212400, [{'accel_x': 0.08, 'accel_z': 0.02}, {'accel_x': 0.07, 'accel_z': 0.03}, ...]
```

파싱 전략: `", ["` 를 기준으로 앞쪽(timestamp)과 뒤쪽(데이터 배열)을 분리.

---

## 병목 원인

```python
# 전: ast.literal_eval (Python 범용 파서)
data = ast.literal_eval(data_str)
# → Python AST를 구성한 뒤 평가 — 범용적이지만 느림
# → VIB 파일 한 줄(5,000개 dict)에 수백ms 소요
```

---

## 개선: json.loads (C 구현 JSON 파서)

CSV 데이터는 Python dict 리터럴 형식(`{'key': val}`)이므로,
작은따옴표 → 큰따옴표 변환 후 JSON으로 파싱.

```python
# 후: json.loads (C로 구현된 JSON 파서)
def _parse_data(data_str: str) -> list[dict]:
    json_str = data_str.replace("'", '"')  # Python dict → JSON 변환
    return json.loads(json_str)            # C 레벨 파싱 — 5~10배 빠름
```

| | `ast.literal_eval` | `json.loads` |
|---|---|---|
| **구현** | Python 인터프리터 | C 확장 모듈 |
| **속도** | 느림 | **5~10배 빠름** |
| **용도** | Python 리터럴 범용 파싱 | JSON 전용 파싱 |
| **전처리** | 불필요 | `'` → `"` 치환 1회 |

---

## 코드 중복 제거

기존에는 `parse_pulse_csv`와 `parse_vib_csv`가 동일한 로직을 중복 구현.
공통 함수 `_parse_csv_lines`로 통합.

```
전:
  parse_pulse_csv() — 파싱 로직 전체
  parse_vib_csv()   — 동일한 파싱 로직 복붙

후:
  _parse_csv_lines()  — 공통 파싱 로직
  _parse_data()       — JSON 변환 + 파싱
  parse_pulse_csv()   — _parse_csv_lines 호출
  parse_vib_csv()     — _parse_csv_lines 호출
```

---

## 캐시 버전

파서가 변경되었으므로 `CACHE_VERSION` 2 → 3으로 업.
기존 캐시(`ast.literal_eval`로 파싱된 데이터)가 자동 무효화되어 새 파서로 재파싱.

---

## 전처리는 불필요

원본 CSV를 다른 포맷으로 변환하는 전처리는 현재 불필요:
- `json.loads`로 충분히 빠름
- 전처리 = 파일을 한 번 더 읽는 것이므로 오히려 느려짐
- 센서 데이터 원본 보존이 중요 (디버깅/추적)
- 필요해지는 시점: 파일 수만 개, 또는 Parquet 등 바이너리 포맷 도입 시

---

## 관련 파일

| 파일 | 변경 |
|------|------|
| `services/csv_parser.py` | `ast.literal_eval` → `json.loads`, 공통 함수 추출 |
| `config.py` | `CACHE_VERSION` 2 → 3 |

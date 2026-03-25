# CSV 파서 버전 관리 방안

> 작성일: 2026-03-24
> 상태: 대기 (다음 포맷 변경 시 착수)

---

## 1. 현황

현재 `csv_parser.py`에서 구/신 포맷을 단일 함수 내 분기로 처리:
- 구 포맷: `timestamp, [data]`
- 신 포맷: `timestamp, unix_ts, [data]`

포맷이 또 변경되면 파서 내부 분기가 계속 늘어남.

## 2. 방안: 버전 감지 + 파서 Registry

### 2-1. 버전 자동 감지

파일 첫 줄을 읽어 포맷 판별:

```python
def detect_version(first_line: str) -> str:
    """첫 줄 구조로 포맷 버전 판별."""
    parts = first_line.split(", [")
    header = parts[0] if parts else ""
    comma_count = header.count(", ")

    if comma_count == 0:
        return "v1"   # timestamp, [data]
    elif comma_count == 1:
        return "v2"   # timestamp, unix_ts, [data]
    else:
        return "unknown"
```

### 2-2. 파서 Registry

```python
# 버전별 파서 함수 등록
PULSE_PARSERS = {
    "v1": parse_pulse_v1,
    "v2": parse_pulse_v2,
}

VIB_PARSERS = {
    "v1": parse_vib_v1,
    "v2": parse_vib_v2,
}

def parse_csv(file_path: Path, file_type: str) -> list[dict]:
    first_line = _read_first_line(file_path)
    version = detect_version(first_line)
    registry = PULSE_PARSERS if file_type == "PULSE" else VIB_PARSERS
    parser = registry.get(version)
    if not parser:
        raise ValueError(f"Unknown CSV format version: {version}")
    return parser(file_path)
```

### 2-3. 새 포맷 추가 시 작업

1. `detect_version()`에 판별 조건 추가
2. `parse_pulse_v3()` / `parse_vib_v3()` 함수 작성
3. Registry에 등록

기존 파서 코드 수정 없음.

## 3. 파일 구조 (리팩토링 후)

```
services/
  csv_parser/
    __init__.py          # parse_csv() 진입점 + detect_version()
    pulse_v1.py          # 구 포맷 PULSE 파서
    pulse_v2.py          # 신 포맷 PULSE 파서
    vib_v1.py            # 구 포맷 VIB 파서
    vib_v2.py            # 신 포맷 VIB 파서
```

또는 단일 파일 유지하되 함수만 분리:
```
services/
  csv_parser.py          # detect_version() + v1/v2 파서 함수 + registry
```

## 4. 착수 시점

다음 조건 중 하나 충족 시:
- 센서 펌웨어 업데이트로 CSV 포맷 변경
- 새로운 센서 타입 추가 (PULSE/VIB 외)
- 기존 분기 로직이 3개 이상으로 늘어날 때

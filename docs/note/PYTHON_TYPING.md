# Python Typing

## TypedDict vs Pydantic

### TypedDict
- **정적 분석 전용** — 런타임에는 그냥 평범한 `dict`
- pyright/mypy가 키 오타, 타입 불일치를 잡아줌
- 런타임 검증 없음 — 잘못된 값이 들어와도 에러 안 남
- 오버헤드 제로 (그냥 dict)

```python
class User(TypedDict):
    name: str
    age: int

u: User = {"name": "Kim", "age": "스물"}  # pyright 경고, 런타임 에러 없음
```

### Pydantic (BaseModel)
- **런타임 검증 + 자동 변환** — 인스턴스 생성 시 실제 타입 체크
- 자동 coercion: `"20"` → `20`
- `.model_dump()`, `.model_json_schema()` 등 직렬화 내장
- 오버헤드 있음 — 객체 생성마다 검증 비용

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

u = User(name="Kim", age="20")   # "20" → 20 자동 변환
u = User(name="Kim", age="스물")  # ValidationError 발생!
```

### 선택 기준

| 기준 | TypedDict | Pydantic |
|------|-----------|----------|
| 외부 입력 (API request, 파일 파싱) | | 적합 — 런타임 검증 필수 |
| 내부 함수 간 데이터 전달 | 적합 — 가볍고 빠름 | 과도할 수 있음 |
| 정적 분석만으로 충분 | 적합 | |
| JSON 직렬화/스키마 생성 필요 | | 적합 |
| 성능 민감한 대량 처리 | 적합 | 병목 가능 |

### 일반적인 패턴
- 내부 데이터 전달: TypedDict
- API 경계 (요청/응답): Pydantic
- 두 계층을 분리하면 내부는 가볍게, 외부는 안전하게 유지 가능

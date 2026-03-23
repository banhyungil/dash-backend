# FastAPI Server - Architecture

## 프로젝트 개요

FastAPI 기반 이미지 처리 서버. OpenCV로 이미지 처리 후 결과를 반환하거나 PostgreSQL에 저장한다.

## 기술 스택

- **런타임**: Python 3.10+
- **프레임워크**: FastAPI 0.133.0
- **이미지 처리**: OpenCV 4.13.0 (headless)
- **DB 드라이버**: psycopg3 (binary) — raw SQL, ORM 없음
- **DB**: PostgreSQL (localhost:5434)
- **패키지 관리**: pip (`requirements.txt`)
- **가상환경**: `.venv/`

---

## 프로젝트 구조

```
fastapi-server/
├── app/
│   ├── main.py                              # FastAPI 앱 진입점
│   ├── api/
│   │   ├── router.py                        # 라우터 집합
│   │   └── endpoints/                       # 엔드포인트 집합
│   ├── core/
│   │   ├── config.py                        # Settings (BaseSettings, .env 로드)
│   │   ├── exception_handlers.py            # 전역 예외 핸들러
│   │   └── logging.py                       # 로깅 설정
│   ├── services/                            # 서비스 집합
│   ├── repos/                               # Repository 집합
│   ├── schemas/                             # 스키마 집합
│   └── utils/                               # Util 집합
├── uploads/                                 # 저장 파일 집합, static 서빙
├── docs/
│   ├── architecture.md                      # 이 문서
│   ├── ddl.md                               # DB 스키마 정의
│   ├── todo                                 # 구현 과제 문서 집합
│   └── note/                                # 개발 노트, 개인 학습용
├── requirements.txt
├── .env.example
└── CLAUDE.md
```

---

## 아키텍처

```
Client HTTP Request
    ↓
main.py (CORS, 라우터, 정적파일 마운트, 예외 핸들러)
    ↓
endpoints/ (HTTP 입출력, 요청 검증, 응답 포매팅)
    ↓
services/ (비즈니스 로직, 오케스트레이션)
    ↓
repos/ (raw SQL, 데이터 접근)
    ↓
PostgreSQL
```

### 레이어 역할

| 레이어 | 역할 | 예시 |
|--------|------|------|
| **endpoints** | HTTP 파라미터 파싱, 응답 코드 결정 | `file` 업로드 수신 → service 호출 → StreamingResponse |
| **services** | 비즈니스 로직 수행 | OpenCV 필터 적용, 배치 처리 체이닝 |
| **repos** | SQL 실행, DB 행 ↔ dict 변환 | `INSERT INTO t_file ...`, 커서 페이지네이션 |
| **schemas** | 요청/응답 데이터 검증 + 직렬화 | Pydantic 모델, CamelModel |

---

## main.py 설정

- **CORS**: 와일드카드 origins, `X-Process-Time-Ms` 헤더 노출
- **라우터**: `/api` 프리픽스로 image_processing, preset, process 라우터 포함
- **정적파일**: `/uploads` → `uploads/` 디렉토리 마운트
- **커스텀 OpenAPI**: 필터 파라미터 모델을 Swagger 스키마에 동적 등록 (중복 방지)

---

## API 엔드포인트

- 요청/응답은 스키마를 통해 명세화한다.
- 스키마 및 모델은 schemas 하위에서 관리한다.


### 프로세스 (`/api/processes`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 프로세스 목록 (선택: `?fileId=` 필터) |
| GET | `/{process_id}` | 프로세스 상세 조회 |
| POST | `/` | 프로세스 생성 (201) |
| PUT | `/{process_id}` | 프로세스 수정 |
| DELETE | `/{process_id}` | 프로세스 삭제 (204) |

---

## 데이터베이스 (상세 DDL은 `ddl.md` 참고)

### 테이블 관계

```
t_file
  ↑ file_id          ↑ final_file_id
  │                   │
t_image_process ←─── t_process_step (parent_id → self, preset_id → t_preset)

t_preset ←────────── t_preset_step (parent_id → self)
```

### 주요 테이블

| 테이블 | 역할 |
|--------|------|
| `t_file` | 물리 파일 메타데이터 (원본명, 서버명, 경로, MIME, 크기) |
| `t_preset` | 재사용 가능한 알고리즘 조합 템플릿 |
| `t_preset_step` | 프리셋의 알고리즘 노드 트리 (parent_id 기반) |
| `t_image_process` | 이미지 편집 세션 (원본 → 최종 결과 연결) |
| `t_process_step` | 실제 적용된 알고리즘 노드 트리 + 실행 이력 |

### 트리 구조

`t_preset_step`과 `t_process_step`은 `parent_id`로 트리 구조를 형성한다:

```
노드A (parent_id: null) → 루트
├── 노드B (parent_id: A)
│   ├── 노드D (parent_id: B)
│   └── 노드E (parent_id: B)
└── 노드C (parent_id: A)     → A와 같은 입력에 다른 알고리즘 (분기/비교)
    └── 노드F (parent_id: C)
```

- `parent_id = NULL`: 루트 노드 (시작점)
- 같은 parent의 siblings: 분기 (동일 입력에 서로 다른 알고리즘 적용 → 비교)
- `t_preset_step`: 순수 트리 (설계도)
- `t_process_step`: 트리 + `is_enabled`, `execution_ms` (실행 기록)

### 커서 페이지네이션

`t_file` 목록 조회 시 `(uploaded_at DESC, id DESC)` 복합키 기준.

---

## 이미지 처리 (image_processing_service.py)

### 지원 필터 (35+)

| 카테고리 | 필터 |
|----------|------|
| **엣지 검출** | sobel, prewitt, laplacian, canny, roberts |
| **블러링** | gaussian, blur, gaussianBlur, medianBlur, bilateralFilter, boxFilter |
| **컨투어** | findContour, convexHull, boundingBox |
| **밝기** | plus, minus, gamma, histogramEqualization |
| **임계값** | binary, inverse, tozero, tozeroInverse, truncate, otsu, adaptive |
| **형태학** | erosion, dilation, opening, closing |

### 파라미터 모델

각 필터별 전용 Pydantic 모델이 `schemas/image_processing.py`에 정의되어 있으며, `PARAM_MODELS` dict로 PrcType과 매핑된다.

### 배치 처리 흐름

```python
# steps: [{ prcType, parameters }, ...]
image = decode(image_bytes)
for step in steps:
    image = OPERATIONS[step.prcType](image, params)
    step.execution_ms = measured_time
return encode(image), steps, total_ms
```

---

## 스키마 설계

### CamelModel

모든 응답 모델의 베이스 클래스. `snake_case` Python 필드를 `camelCase` JSON으로 자동 변환.

```python
class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
```

### PrcType

35+ 필터 타입의 Literal union. 요청 검증과 라우팅에 사용.

---



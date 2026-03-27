# 코딩 컨벤션

- 파일/변수: `snake_case`, 클래스: `PascalCase`, 상수: `UPPER_SNAKE_CASE`
- import: 절대경로 (`app.xxx`), 와일드카드 금지
- 엔드포인트는 얇게 유지 (비즈니스 로직은 service로 위임)
- 각 함수는 docstring 작성
- 내부 함수 간 dict 전달: TypedDict 사용 (런타임 오버헤드 없이 키 오타/타입 불일치 정적 검출)
- API 경계 (요청/응답): Pydantic 모델 사용

- DB: psycopg3 context manager + parameterized query (SQL injection 방지)

# 리소스 기반 구조화

- 리소스 기반 경로 — 동사(image-processing) → 명사(/files)
- 라우터-서비스-repo 1:1 매칭 — 파일명 통일 (files.py → files_service.py → files_repo.py)
- 복수형 통일 — 리소스는 복수형 (files, filters, presets, processes)
- 역할별 세그먼트 — /files/crop, /files/process, /files/dzi 처럼 동작을 하위 경로로
- 프론트-백엔드 네이밍 일치 — 백엔드 /files/crop → 프론트 filesApi.createCrop

# naming

## boolean 변수
- `is_`, `has_`, `can_` 접두사 사용 (예: `is_own_conn`, `has_vib_data`, `is_valid`)

## 리스트 변수
- 복수형 가능한 단어: `s` 접미사 (예: `pulses`, `samples`, `errors`)
- 축 식별자 등 복수형이 어색한 경우: `_arr` 접미사 (예: `accel_x_arr`, `vib_z_arr`)
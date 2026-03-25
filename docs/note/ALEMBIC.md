# Alembic 마이그레이션 가이드

## 개요
Alembic은 DB 스키마 변경을 버전 관리하는 도구.
`alembic/versions/` 디렉토리에 마이그레이션 파일이 순서대로 쌓인다.

## 기본 명령어

```bash
# 현재 적용된 버전 확인
alembic current

# 마이그레이션 히스토리 보기
alembic history

# 새 마이그레이션 생성
alembic revision -m "add column xyz"

# 최신까지 적용
alembic upgrade head

# 1단계 롤백
alembic downgrade -1

# 특정 버전으로 이동
alembic upgrade <revision_id>
alembic downgrade <revision_id>
```

## 마이그레이션 파일 작성법

`alembic revision -m "설명"` 실행 시 `alembic/versions/`에 파일이 생성된다.
이 프로젝트에서는 SQLAlchemy ORM 없이 **raw SQL**로 작성한다.

```python
def upgrade() -> None:
    op.execute("""
        ALTER TABLE t_cycle ADD COLUMN new_col DOUBLE PRECISION DEFAULT 0;
    """)

def downgrade() -> None:
    op.execute("""
        ALTER TABLE t_cycle DROP COLUMN new_col;
    """)
```

### 주의사항
- `upgrade()`와 `downgrade()`는 반드시 짝으로 작성
- `downgrade()`가 없으면 롤백 불가
- `CREATE TABLE`은 `IF NOT EXISTS`, `DROP`은 `IF EXISTS` 사용 권장

## DB URL 설정
`alembic.ini`에 URL을 직접 넣지 않고, `alembic/env.py`에서 `config.py`의 `DATABASE_URL`을 읽는다.
즉 `.env` 파일의 `DATABASE_URL`이 그대로 사용된다.

## 자주 쓰는 패턴

### 컬럼 추가
```python
def upgrade() -> None:
    op.execute("ALTER TABLE t_cycle ADD COLUMN new_col TEXT")

def downgrade() -> None:
    op.execute("ALTER TABLE t_cycle DROP COLUMN new_col")
```

### 컬럼명 변경
```python
def upgrade() -> None:
    op.execute("ALTER TABLE t_cycle RENAME COLUMN old_name TO new_name")

def downgrade() -> None:
    op.execute("ALTER TABLE t_cycle RENAME COLUMN new_name TO old_name")
```

### 인덱스 추가
```python
def upgrade() -> None:
    op.execute("CREATE INDEX idx_name ON t_cycle(column_name)")

def downgrade() -> None:
    op.execute("DROP INDEX idx_name")
```

### 테이블 추가
```python
def upgrade() -> None:
    op.execute("""
        CREATE TABLE t_new (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS t_new")
```

## 파일 구조

```
alembic/
├── env.py              # DB 연결 설정 (config.py에서 URL 읽음)
├── script.py.mako      # 마이그레이션 파일 템플릿
└── versions/           # 마이그레이션 파일들
    └── 115d3a5fcde6_initial_schema.py
```

"""Shared fixtures for tests."""
import os

# 테스트 환경 강제 설정 (config.py 로드 전에 설정해야 함)
os.environ.setdefault("APP_ENV", "test")

import psycopg
from psycopg.rows import dict_row
import pytest
from dotenv import load_dotenv
from alembic.config import Config
from alembic import command

load_dotenv(".env.test")

# 테스트 DB URL (환경변수 또는 기본값)
_TEST_DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:dash@localhost:5435/dash_test")


@pytest.fixture(autouse=True)
def _use_test_db(monkeypatch):
    """Each test gets a clean PostgreSQL schema."""
    # autocommit=True로 스키마 초기화 (DDL 락 방지)
    admin = psycopg.connect(_TEST_DB_URL, autocommit=True)  # type: ignore[call-overload]
    admin.execute("DROP SCHEMA public CASCADE")
    admin.execute("CREATE SCHEMA public")
    admin.close()

    def _get_test_connection():
        return psycopg.connect(_TEST_DB_URL, row_factory=dict_row, autocommit=False)  # type: ignore[call-overload]

    monkeypatch.setattr("services.database.get_connection", _get_test_connection)
    monkeypatch.setenv("DATABASE_URL", _TEST_DB_URL)

    # alembic으로 스키마 생성 + 설정 시드
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    from services.database import seed_settings
    seed_settings()

    yield


@pytest.fixture
def sample_pulse_line_old():
    """Old format PULSE CSV line (no unix timestamp)."""
    return "2025-09-20 08:26:23.212, [{'pulse': 5507, 'accel_x': 0.08, 'accel_y': 0.98, 'accel_z': 0.02}, {'pulse': 6228, 'accel_x': 0.08, 'accel_y': 0.98, 'accel_z': 0.02}, {'pulse': 5028, 'accel_x': 0.07, 'accel_y': 0.98, 'accel_z': 0.02}, {'pulse': 7887, 'accel_x': 0.07, 'accel_y': 0.98, 'accel_z': 0.02}, {'pulse': 6019, 'accel_x': 0.07, 'accel_y': 0.98, 'accel_z': 0.02}, {'pulse': 6601, 'accel_x': 0.07, 'accel_y': 0.98, 'accel_z': 0.02}]"


@pytest.fixture
def sample_pulse_line_new():
    """New format PULSE CSV line (with unix timestamp)."""
    return "2026-03-11 15:05:34.853, 1773212400, [{'pulse': 8751, 'accel_x': 0.08, 'accel_y': 0.98, 'accel_z': 0.02}, {'pulse': 6312, 'accel_x': 0.07, 'accel_y': 0.98, 'accel_z': 0.02}, {'pulse': 5199, 'accel_x': 0.08, 'accel_y': 0.98, 'accel_z': 0.02}]"


@pytest.fixture
def sample_vib_line_old():
    """Old format VIB CSV line."""
    return "2025-09-20 08:26:50.100, [{'accel_x': 0.07, 'accel_z': 0.02}, {'accel_x': 0.08, 'accel_z': 0.03}]"


@pytest.fixture
def sample_vib_line_new():
    """New format VIB CSV line."""
    return "2026-03-11 15:06:01.584, 1773212400, [{'accel_x': 0.08, 'accel_z': 0.02}, {'accel_x': 0.07, 'accel_z': 0.03}]"

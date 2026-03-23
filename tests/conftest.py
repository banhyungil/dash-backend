"""Shared fixtures for tests."""
import sqlite3
import pytest


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    """Each test gets its own fresh SQLite DB."""
    test_db = str(tmp_path / "test.db")

    def _get_test_connection():
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    monkeypatch.setattr("services.database.get_connection", _get_test_connection)

    from services.database import init_db
    init_db()


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

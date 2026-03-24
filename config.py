import os
from pathlib import Path

current_file = Path(__file__).resolve()
backend_dir = current_file.parent

# ---------------------------------------------------------------------------
# 서버 환경 설정
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("DATA_DIR", backend_dir / "data"))
CACHE_DIR = Path(os.environ.get("CACHE_DIR", backend_dir / ".cache"))
DB_PATH = Path(os.environ.get("DB_PATH", backend_dir / "dash.db"))
SETTINGS_FILE = Path(os.environ.get("SETTINGS_FILE", backend_dir / "device_settings.json"))
CACHE_VERSION = 3
VIB_SAMPLE_RATE = 1000  # Hz (ADXL355)
RPM_READ_OFFSET = 2     # Skip first N pulses

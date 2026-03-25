import os
from pathlib import Path

from dotenv import load_dotenv

current_file = Path(__file__).resolve()
backend_dir = current_file.parent

# APP_ENV에 따라 .env 파일 선택 (기본: development)
# development → .env, production → .env.production, test → .env.test
_app_env = os.environ.get("APP_ENV", "development")
_env_file = backend_dir / f".env.{_app_env}" if _app_env != "development" else backend_dir / ".env"
load_dotenv(_env_file)

# ---------------------------------------------------------------------------
# 서버 환경 설정
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("DATA_DIR", backend_dir / "data"))
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:dash@localhost:5432/dash")
SETTINGS_FILE = Path(os.environ.get("SETTINGS_FILE", backend_dir / "device_settings.json"))
VIB_SAMPLE_RATE = 1000  # Hz (ADXL355)
RPM_READ_OFFSET = 2     # Skip first N pulses

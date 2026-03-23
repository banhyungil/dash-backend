import os
from pathlib import Path

current_file = Path(__file__).resolve()
backend_dir = current_file.parent

DATA_DIR = Path(os.environ.get("DATA_DIR", backend_dir / "data"))
CACHE_DIR = Path(os.environ.get("CACHE_DIR", backend_dir / ".cache"))

# Device settings
DEFAULT_SHAFT_DIA = 50     # mm
DEFAULT_PATTERN_WIDTH = 10 # mm
DEFAULT_TARGET_RPM = 100

# Roll diameter for MPM calculation
ROLL_DIAMETER_MM = 140  # mm (actual roll diameter, different from shaft_dia)

# Sampling
VIB_SAMPLE_RATE = 1000  # Hz (ADXL355)
RPM_READ_OFFSET = 2     # Skip first N pulses

# RPM tolerance bands (from viewer/backend/config.py)
ALLOW_RPM_ERROR_PER_SET = {
    "stage01": {"val": 10, "type": "rpm_tol_1", "color": "#DDCC00"},   # yellow
    "stage02": {"val": 20, "type": "rpm_tol_2", "color": "#FF5E00"},   # orange
    "stage03": {"val": 30, "type": "rpm_tol_3", "color": "#FF0000"},   # red
}

# Expected calculation tolerance (10%)
EXPECTED_TOLERANCE = 0.1

# Cache version
CACHE_VERSION = 3  # Bumped: parser switched from ast.literal_eval to json.loads

# SQLite database
DB_PATH = Path(os.environ.get("DB_PATH", backend_dir / "dash.db"))

# Settings file for device parameters
SETTINGS_FILE = Path(os.environ.get("SETTINGS_FILE", backend_dir / "device_settings.json"))

# Device to Session mapping
DEVICE_SESSION_MAP = {
    "0013A20041F71B01": "R1",
    "0013A20041F9D466": "R2",
    "0013A20041F98275": "R3",
    "0013A20041F9D4F8": "R4",
}

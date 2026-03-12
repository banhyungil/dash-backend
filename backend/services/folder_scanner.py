import re
import logging
from pathlib import Path
from config import DATA_DIR
from services.cache_manager import read_manifest

logger = logging.getLogger(__name__)


def get_available_months() -> list[dict]:
    """Scan data/ for Measured_YYMM folders and return month list."""
    months = []
    if not DATA_DIR.exists():
        return months

    for folder in sorted(DATA_DIR.iterdir()):
        if folder.is_dir() and folder.name.startswith("Measured_"):
            yymm = folder.name.replace("Measured_", "")
            if len(yymm) == 4 and yymm.isdigit():
                yy = yymm[:2]
                mm = yymm[2:]
                label = f"20{yy}년 {mm}월"
                months.append({"month": yymm, "label": label})

    return months


def _get_month_base(month: str) -> Path:
    """Return the Measured/ base path for a given month code."""
    return DATA_DIR / f"Measured_{month}" / "Measured"


def get_sessions_for_month(month: str) -> list[str]:
    """Return list of session folder names (YYYYMMDD_HHMMSS) for a month."""
    base = _get_month_base(month)
    if not base.exists():
        return []

    sessions = []
    for folder in sorted(base.iterdir()):
        if folder.is_dir() and re.match(r"\d{8}_\d{6}", folder.name):
            sessions.append(folder.name)
    return sessions


def get_devices_for_month(month: str) -> list[str]:
    """Return unique MAC addresses across all sessions in a month."""
    base = _get_month_base(month)
    if not base.exists():
        return []

    devices = set()
    for session_dir in base.iterdir():
        if not session_dir.is_dir():
            continue
        measure_dir = session_dir / "measure"
        if not measure_dir.exists():
            continue
        for mac_dir in measure_dir.iterdir():
            if mac_dir.is_dir() and re.match(r"[0-9A-Fa-f]{16}", mac_dir.name):
                devices.add(mac_dir.name)

    return sorted(devices)


def get_dates_for_month_device(month: str, device: str) -> list[dict]:
    """Return dates with cycle counts for a given month and device.
    Tries manifest cache first, falls back to filesystem scan.
    """
    # Try manifest first
    manifest = read_manifest()
    if manifest:
        month_data = manifest.get("months", {}).get(month)
        if month_data:
            device_data = month_data.get("devices", {}).get(device)
            if device_data:
                return device_data.get("dates", [])

    # Fallback: filesystem scan
    return _scan_dates_for_month_device(month, device)


def _scan_dates_for_month_device(month: str, device: str) -> list[dict]:
    """Filesystem scan fallback for get_dates_for_month_device."""
    base = _get_month_base(month)
    if not base.exists():
        return []

    date_map: dict[str, list[dict]] = {}

    for session_dir in sorted(base.iterdir()):
        if not session_dir.is_dir():
            continue
        mac_dir = session_dir / "measure" / device
        if not mac_dir.exists():
            continue

        for csv_file in sorted(mac_dir.glob("PULSE_*.csv")):
            match = re.match(r"PULSE_(\d{6})\.csv", csv_file.name)
            if not match:
                continue
            date_str = match.group(1)
            try:
                with open(csv_file, "r", encoding="utf-8") as f:
                    line_count = sum(1 for line in f if line.strip())
            except Exception:
                line_count = 0

            if date_str not in date_map:
                date_map[date_str] = []
            date_map[date_str].append({
                "session": session_dir.name,
                "file": str(csv_file),
                "cycle_count": line_count,
            })

    results = []
    for date_str in sorted(date_map.keys()):
        entries = date_map[date_str]
        total_cycles = sum(e["cycle_count"] for e in entries)
        results.append({
            "date": date_str,
            "session": entries[0]["session"],
            "cycle_count": total_cycles,
        })

    return results


def get_csv_files(month: str, date: str, device: str) -> dict[str, list[dict]]:
    """Return PULSE and VIB CSV file paths for a given month/date/device.
    Returns: {"pulse": [{"session": ..., "path": ...}], "vib": [...]}
    """
    base = _get_month_base(month)
    result = {"pulse": [], "vib": []}

    if not base.exists():
        return result

    for session_dir in sorted(base.iterdir()):
        if not session_dir.is_dir():
            continue
        mac_dir = session_dir / "measure" / device
        if not mac_dir.exists():
            continue

        pulse_file = mac_dir / f"PULSE_{date}.csv"
        vib_file = mac_dir / f"VIB_{date}.csv"

        if pulse_file.exists():
            result["pulse"].append({
                "session": session_dir.name,
                "path": str(pulse_file),
            })
        if vib_file.exists():
            result["vib"].append({
                "session": session_dir.name,
                "path": str(vib_file),
            })

    return result


def find_session_for_device(month: str, session: str, device: str) -> Path | None:
    """Return the MAC directory path for a specific session."""
    base = _get_month_base(month)
    mac_dir = base / session / "measure" / device
    if mac_dir.exists():
        return mac_dir
    return None

"""API endpoints for day viewer."""
import sys
import json
import math
import logging
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException

logger = logging.getLogger(__name__)

# Import all services from day_viewer (all copied from viewer)
from config import DEFAULT_SHAFT_DIA, DEFAULT_PATTERN_WIDTH, DEFAULT_TARGET_RPM, DATA_DIR, DEVICE_SESSION_MAP, ROLL_DIAMETER_MM
from services.folder_scanner import get_available_months, get_devices_for_month, get_dates_for_month_device, get_csv_files
from services.cached_csv_parser import parse_pulse_cached, parse_vib_cached
from services.rpm_service import process_pulse_compact_to_rpm
from services.expected_filter import is_expected_valid, calculate_expected_pulse_count
from services.session_merger import merge_sessions_by_timestamp, calculate_continuous_timeline
from services.test_export import copy_raw_csv_files, create_integrated_csv_raw


def calc_mpm_from_rpm(rpm: float, roll_dia: float) -> float:
    """RPM + roll_dia(mm) -> MPM"""
    return round(rpm * math.pi * roll_dia / 1000, 2)

# Load device settings from viewer's settings file
current_file = Path(__file__).resolve()
backend_dir = current_file.parent.parent
code_dir = backend_dir.parent.parent
_settings_file = code_dir / "viewer" / "backend" / "device_settings.json"

def load_device_settings(mac: str) -> dict | None:
    """Load device settings from viewer's JSON file."""
    if _settings_file.exists():
        try:
            with open(_settings_file, "r", encoding="utf-8") as f:
                all_settings = json.load(f)
                return all_settings.get(mac)
        except Exception:
            return None
    return None

router = APIRouter(prefix="/api")


def _load_settings(device: str, shaft_dia: float = None, pattern_width: float = None, target_rpm: float = None):
    """Load device settings with optional overrides."""
    settings = load_device_settings(device)
    s_dia = shaft_dia if shaft_dia is not None else (settings.get("shaft_dia", DEFAULT_SHAFT_DIA) if settings else DEFAULT_SHAFT_DIA)
    p_wid = pattern_width if pattern_width is not None else (settings.get("pattern_width", DEFAULT_PATTERN_WIDTH) if settings else DEFAULT_PATTERN_WIDTH)
    t_rpm = target_rpm if target_rpm is not None else (settings.get("target_rpm", DEFAULT_TARGET_RPM) if settings else DEFAULT_TARGET_RPM)
    return s_dia, p_wid, t_rpm


@router.get("/months")
def get_months():
    """Get available months."""
    return get_available_months()


@router.get("/devices")
def get_devices(month: str = Query(...)):
    """Get devices for a month."""
    return get_devices_for_month(month)


@router.get("/dates")
def get_dates(month: str = Query(...), device: str = Query(...)):
    """Get dates for a month and device."""
    return get_dates_for_month_device(month, device)


@router.get("/cycles/daily")
def get_daily_data(
    month: str = Query(...),
    date: str = Query(...),
    shaft_dia: float = Query(None),
    pattern_width: float = Query(None),
    target_rpm: float = Query(None),
):
    """
    Get daily data for a specific date, merging all devices and sessions by timestamp.
    Only includes cycles where expected validation passes (10% tolerance).

    Returns:
        - rpm_data: List of cycles with RPM timeline data
        - vib_data: List of cycles with Pulse + VIB accelerometer data
    """
    # Get all devices for this month
    devices = get_devices_for_month(month)

    # Use first device's settings as default for shaft_dia and target_rpm
    first_device = devices[0] if devices else None
    default_settings = load_device_settings(first_device) if first_device else {}
    default_s_dia = shaft_dia if shaft_dia is not None else (default_settings.get("shaft_dia", DEFAULT_SHAFT_DIA) if default_settings else DEFAULT_SHAFT_DIA)
    default_t_rpm = target_rpm if target_rpm is not None else (default_settings.get("target_rpm", DEFAULT_TARGET_RPM) if default_settings else DEFAULT_TARGET_RPM)

    # Collect data from all devices
    all_pulse_cycles = []
    all_vib_data = []
    skipped_rpm_none = 0
    skipped_expected = 0

    for device in devices:
        # Load device-specific settings
        device_settings = load_device_settings(device)

        # Get device-specific pattern_width, or use query param, or use default
        device_s_dia = shaft_dia if shaft_dia is not None else (device_settings.get("shaft_dia", default_s_dia) if device_settings else default_s_dia)
        device_p_wid = pattern_width if pattern_width is not None else (device_settings.get("pattern_width", DEFAULT_PATTERN_WIDTH) if device_settings else DEFAULT_PATTERN_WIDTH)
        device_t_rpm = target_rpm if target_rpm is not None else (device_settings.get("target_rpm", default_t_rpm) if device_settings else default_t_rpm)

        csv_files = get_csv_files(month, date, device)

        # Process PULSE files from this device
        for pulse_info in csv_files["pulse"]:
            session = pulse_info["session"]
            pulse_path = Path(pulse_info["path"])

            # Parse pulse data
            parsed = parse_pulse_cached(pulse_path)

            for i, cycle in enumerate(parsed["cycles"]):
                set_count = len(cycle["pulses"])

                # Calculate RPM using device-specific pattern_width
                rpm_result = process_pulse_compact_to_rpm(
                    cycle["pulses"],
                    cycle["accel_x"],
                    cycle["accel_y"],
                    cycle["accel_z"],
                    device_s_dia,
                    device_p_wid,
                )

                if rpm_result is None:
                    skipped_rpm_none += 1
                    continue

                rpm_mean = rpm_result["rpmMean"]

                # Check expected validation (10% tolerance) using device-specific pattern_width
                if not is_expected_valid(set_count, rpm_mean, device_s_dia, device_p_wid):
                    skipped_expected += 1
                    continue

                # Add to results
                expected_count = calculate_expected_pulse_count(rpm_mean, device_s_dia, device_p_wid)

                # Map device to session name (R1, R2, R3, R4)
                session_name = DEVICE_SESSION_MAP.get(device, device)

                # Calculate MPM using ROLL_DIAMETER_MM (not shaft_dia)
                mpm_mean = calc_mpm_from_rpm(rpm_mean, ROLL_DIAMETER_MM)
                mpm_min = calc_mpm_from_rpm(rpm_result["rpmMin"], ROLL_DIAMETER_MM)
                mpm_max = calc_mpm_from_rpm(rpm_result["rpmMax"], ROLL_DIAMETER_MM)
                mpm_data = [calc_mpm_from_rpm(rpm, ROLL_DIAMETER_MM) for rpm in rpm_result["dataRPM"]]

                all_pulse_cycles.append({
                    "timestamp": parsed["timestamps"][i],
                    "session": session_name,
                    "device": device,
                    "cycle_index": i,
                    "date": date,
                    "rpm_mean": round(rpm_mean, 2),
                    "rpm_min": round(rpm_result["rpmMin"], 2),
                    "rpm_max": round(rpm_result["rpmMax"], 2),
                    "rpm_timeline": rpm_result["timeLine"],
                    "rpm_data": rpm_result["dataRPM"],
                    "mpm_mean": mpm_mean,
                    "mpm_min": mpm_min,
                    "mpm_max": mpm_max,
                    "mpm_data": mpm_data,
                    "duration_ms": round(rpm_result["durationms"], 2),
                    "set_count": set_count,
                    "expected_count": expected_count,
                    # Pulse accelerometer data (for vibration tab)
                    "pulse_timeline": rpm_result.get("rawTimeLine", []),
                    "pulse_accel_x": rpm_result.get("rawAccelX", []),
                    "pulse_accel_y": rpm_result.get("rawAccelY", []),
                    "pulse_accel_z": rpm_result.get("rawAccelZ", []),
                })

        # Process VIB files from this device
        for vib_info in csv_files["vib"]:
            session = vib_info["session"]
            vib_path = Path(vib_info["path"])

            parsed_vib = parse_vib_cached(vib_path)

            for i, cycle in enumerate(parsed_vib["cycles"]):
                # Map device to session name (R1, R2, R3, R4)
                session_name = DEVICE_SESSION_MAP.get(device, device)

                all_vib_data.append({
                    "device": device,
                    "session": session_name,
                    "cycle_index": i,
                    "vib_accel_x": cycle["accel_x"],
                    "vib_accel_z": cycle["accel_z"],
                })

    logger.info(
        "Date %s: %d cycles OK, skipped %d (rpm_none=%d, expected=%d)",
        date, len(all_pulse_cycles),
        skipped_rpm_none + skipped_expected,
        skipped_rpm_none, skipped_expected,
    )

    # Merge all cycles by timestamp (preserve individual session names)
    # Don't pass "session": "all" - let each cycle keep its own session name (R1~R4)
    merged_pulse = merge_sessions_by_timestamp([{"cycles": all_pulse_cycles}])
    rpm_cycles = merged_pulse["cycles"]

    # Calculate continuous timeline offsets
    rpm_cycles = calculate_continuous_timeline(rpm_cycles)

    # Attach VIB data to matching cycles
    for cycle in rpm_cycles:
        # Find matching VIB data by device, session, and cycle_index
        matching_vib = next(
            (v for v in all_vib_data
             if v["device"] == cycle["device"]
             and v["session"] == cycle["session"]
             and v["cycle_index"] == cycle["cycle_index"]),
            None
        )

        if matching_vib:
            cycle["vib_accel_x"] = matching_vib["vib_accel_x"]
            cycle["vib_accel_z"] = matching_vib["vib_accel_z"]
        else:
            cycle["vib_accel_x"] = []
            cycle["vib_accel_z"] = []

    # Build device settings map
    device_settings_map = {}
    for device in devices:
        settings = load_device_settings(device)
        session_name = DEVICE_SESSION_MAP.get(device, device)
        device_settings_map[session_name] = {
            "shaft_dia": settings.get("shaft_dia", DEFAULT_SHAFT_DIA) if settings else DEFAULT_SHAFT_DIA,
            "pattern_width": settings.get("pattern_width", DEFAULT_PATTERN_WIDTH) if settings else DEFAULT_PATTERN_WIDTH,
            "target_rpm": settings.get("target_rpm", DEFAULT_TARGET_RPM) if settings else DEFAULT_TARGET_RPM,
        }

    return {
        "date": date,
        "device": "all",  # All devices merged
        "settings": device_settings_map,  # Device-specific settings
        "cycles": rpm_cycles,
        "total_cycles": len(rpm_cycles),
    }


@router.get("/cycles/export")
def export(
    month: str = Query(...),
    date: str = Query(...),
    shaft_dia: float = Query(None),
    pattern_width: float = Query(None),
    target_rpm: float = Query(None),
):
    """
    Test endpoint: Copy raw CSV files and create integrated CSV from cached data.

    This endpoint:
    1. Copies raw PULSE and VIB CSV files to test folder
    2. Loads data from cache
    3. Creates integrated CSV files (sorted by timestamp)
    """
    print(f"\n=== TEST EXPORT START ===")
    print(f"Month: {month}, Date: {date}")

    # Get all devices for this month
    print(f"[1] Getting devices for month {month}...")
    devices = get_devices_for_month(month)
    print(f"[1] Found {len(devices)} devices: {devices}")

    if not devices:
        print(f"[ERROR] No devices found!")
        raise HTTPException(404, f"No devices found for month {month}")

    # Use first device's settings as default
    first_device = devices[0]
    print(f"[2] Loading settings for first device: {first_device}")
    s_dia, p_wid, t_rpm = _load_settings(first_device, shaft_dia, pattern_width, target_rpm)
    print(f"[2] Settings: shaft_dia={s_dia}, pattern_width={p_wid}, target_rpm={t_rpm}")

    # Create test directory
    test_dir = Path(__file__).resolve().parent.parent.parent / "test" / f"{month}_{date}"
    print(f"[3] Test directory: {test_dir}")

    # Step 1: Copy raw CSV files
    print(f"[4] Copying raw CSV files from {DATA_DIR}...")
    copied_files = copy_raw_csv_files(month, date, devices, DATA_DIR, test_dir / "raw")
    print(f"[4] Copied {len(copied_files)} files")

    # Step 2: Create integrated CSV from raw data (no RPM calculation, no filtering)
    print(f"[5] Creating integrated CSV from raw data...")
    integrated_files = create_integrated_csv_raw(month, date, devices, test_dir / "integrated")
    print(f"[5] Created {len(integrated_files)} integrated files")

    print(f"=== TEST EXPORT COMPLETE ===\n")

    return {
        "status": "success",
        "test_dir": str(test_dir),
        "raw_files_copied": len(copied_files),
        "raw_files": copied_files,
        "integrated_files": integrated_files,
        "total_cycles": "raw data (no filtering)",
    }


# OLD CODE BELOW - keeping for reference but not used
def _old_test_export_with_rpm_filtering():
    # Step 2: Load data from cache (same logic as daily-data endpoint)
    print(f"[5] Loading data from cache...")
    all_pulse_cycles = []
    all_vib_data = []

    for device in devices:
        print(f"[5] Processing device: {device}")
        csv_files = get_csv_files(month, date, device)
        print(f"[5]   Found {len(csv_files['pulse'])} PULSE files, {len(csv_files['vib'])} VIB files")

        # Process PULSE files from this device
        for pulse_info in csv_files["pulse"]:
            session = pulse_info["session"]
            pulse_path = Path(pulse_info["path"])

            # Parse pulse data
            parsed = parse_pulse_cached(pulse_path)

            for i, cycle in enumerate(parsed["cycles"]):
                set_count = len(cycle["pulses"])

                # Calculate RPM
                rpm_result = process_pulse_compact_to_rpm(
                    cycle["pulses"],
                    cycle["accel_x"],
                    cycle["accel_y"],
                    cycle["accel_z"],
                    s_dia,
                    p_wid,
                )

                if rpm_result is None:
                    continue

                rpm_mean = rpm_result["rpmMean"]

                # Check expected validation (10% tolerance)
                if not is_expected_valid(set_count, rpm_mean, s_dia, p_wid):
                    continue  # Skip cycles that don't pass expected check

                # Add to results
                expected_count = calculate_expected_pulse_count(rpm_mean, s_dia, p_wid)

                # Map device to session name (R1, R2, R3, R4)
                session_name = DEVICE_SESSION_MAP.get(device, device)

                all_pulse_cycles.append({
                    "timestamp": parsed["timestamps"][i],
                    "session": session_name,
                    "device": device,
                    "cycle_index": i,
                    "date": date,
                    "rpm_mean": round(rpm_mean, 2),
                    "rpm_min": round(rpm_result["rpmMin"], 2),
                    "rpm_max": round(rpm_result["rpmMax"], 2),
                    "rpm_timeline": rpm_result["timeLine"],
                    "rpm_data": rpm_result["dataRPM"],
                    "duration_ms": round(rpm_result["durationms"], 2),
                    "set_count": set_count,
                    "expected_count": expected_count,
                    # Pulse accelerometer data (for vibration tab)
                    "pulse_timeline": rpm_result.get("rawTimeLine", []),
                    "pulse_accel_x": rpm_result.get("rawAccelX", []),
                    "pulse_accel_y": rpm_result.get("rawAccelY", []),
                    "pulse_accel_z": rpm_result.get("rawAccelZ", []),
                })

        # Process VIB files from this device
        for vib_info in csv_files["vib"]:
            session = vib_info["session"]
            vib_path = Path(vib_info["path"])

            parsed_vib = parse_vib_cached(vib_path)

            for i, cycle in enumerate(parsed_vib["cycles"]):
                # Map device to session name (R1, R2, R3, R4)
                session_name = DEVICE_SESSION_MAP.get(device, device)

                all_vib_data.append({
                    "device": device,
                    "session": session_name,
                    "cycle_index": i,
                    "vib_accel_x": cycle["accel_x"],
                    "vib_accel_z": cycle["accel_z"],
                })

    # Attach VIB data to matching cycles
    for cycle in all_pulse_cycles:
        # Find matching VIB data by device, session, and cycle_index
        matching_vib = next(
            (v for v in all_vib_data
             if v["device"] == cycle["device"]
             and v["session"] == cycle["session"]
             and v["cycle_index"] == cycle["cycle_index"]),
            None
        )

        if matching_vib:
            cycle["vib_accel_x"] = matching_vib["vib_accel_x"]
            cycle["vib_accel_z"] = matching_vib["vib_accel_z"]
        else:
            cycle["vib_accel_x"] = []
            cycle["vib_accel_z"] = []

    # Step 3: Create integrated CSV files
    print(f"[6] Creating integrated CSV files...")
    print(f"[6] Total cycles to export: {len(all_pulse_cycles)}")
    integrated_files = create_integrated_csv(all_pulse_cycles, test_dir / "integrated", date, include_vib=True)
    print(f"[6] Created {len(integrated_files)} integrated files")

    print(f"=== TEST EXPORT COMPLETE ===\n")

    return {
        "status": "success",
        "test_dir": str(test_dir),
        "raw_files_copied": len(copied_files),
        "raw_files": copied_files,
        "integrated_files": integrated_files,
        "total_cycles": len(all_pulse_cycles),
        "filtered_cycles": len(all_pulse_cycles),  # Already filtered by expected
    }

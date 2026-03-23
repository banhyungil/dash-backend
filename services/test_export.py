"""Test export service for debugging and data validation."""
import shutil
import csv
from pathlib import Path
from typing import List, Dict, Any
from config import DEVICE_SESSION_MAP


def copy_raw_csv_files(month: str, date: str, devices: List[str], source_data_dir: Path, dest_dir: Path):
    """
    Copy raw CSV files for a specific date from all devices.

    Args:
        month: Month code (e.g., '2601')
        date: Date string (e.g., '250920')
        devices: List of device MAC addresses
        source_data_dir: Source data directory
        dest_dir: Destination test directory
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied_files = []

    for device in devices:
        # Find device folder in month directory (recursively)
        month_dir = source_data_dir / f"Measured_{month}"
        if not month_dir.exists():
            continue

        # Search for device folder recursively (MAC address folders)
        device_folders = list(month_dir.rglob(f"*{device}*"))
        device_folders = [f for f in device_folders if f.is_dir()]

        if not device_folders:
            continue

        # For each device folder found
        for device_folder in device_folders:
            # Copy PULSE and VIB files for this date directly from device folder
            pulse_file = device_folder / f"PULSE_{date}.csv"
            vib_file = device_folder / f"VIB_{date}.csv"

            # Get session name from device mapping (R1, R2, R3, R4)
            session_name = DEVICE_SESSION_MAP.get(device, device)

            if pulse_file.exists():
                dest_file = dest_dir / f"{session_name}_PULSE_{date}.csv"
                shutil.copy2(pulse_file, dest_file)
                copied_files.append(str(dest_file))

            if vib_file.exists():
                dest_file = dest_dir / f"{session_name}_VIB_{date}.csv"
                shutil.copy2(vib_file, dest_file)
                copied_files.append(str(dest_file))

    return copied_files


def create_integrated_csv_raw(
    month: str,
    date: str,
    devices: List[str],
    dest_dir: Path,
):
    """
    Create integrated CSV from RAW data (no RPM calculation, no filtering).
    Just parse raw CSV and sort by timestamp.

    Args:
        month: Month code
        date: Date string
        devices: List of device MAC addresses
        dest_dir: Destination directory
    """
    from services.folder_scanner import get_csv_files
    from services.cached_csv_parser import parse_pulse_cached, parse_vib_cached
    from config import DEVICE_SESSION_MAP

    dest_dir.mkdir(parents=True, exist_ok=True)

    all_pulse_cycles = []
    all_vib_cycles = []

    # Collect all raw data from all devices
    for device in devices:
        csv_files = get_csv_files(month, date, device)
        session_name = DEVICE_SESSION_MAP.get(device, device)

        # Parse PULSE files
        for pulse_info in csv_files["pulse"]:
            pulse_path = Path(pulse_info["path"])
            parsed = parse_pulse_cached(pulse_path)

            for i, cycle in enumerate(parsed["cycles"]):
                all_pulse_cycles.append({
                    "timestamp": parsed["timestamps"][i],
                    "device": device,
                    "session": session_name,
                    "cycle_index": i,
                    "pulses": cycle["pulses"],
                    "accel_x": cycle["accel_x"],
                    "accel_y": cycle["accel_y"],
                    "accel_z": cycle["accel_z"],
                })

        # Parse VIB files
        for vib_info in csv_files["vib"]:
            vib_path = Path(vib_info["path"])
            parsed_vib = parse_vib_cached(vib_path)

            for i, cycle in enumerate(parsed_vib["cycles"]):
                all_vib_cycles.append({
                    "timestamp": parsed_vib["timestamps"][i],
                    "device": device,
                    "session": session_name,
                    "cycle_index": i,
                    "accel_x": cycle["accel_x"],
                    "accel_z": cycle["accel_z"],
                })

    # Sort by timestamp
    all_pulse_cycles.sort(key=lambda c: c["timestamp"])
    all_vib_cycles.sort(key=lambda c: c["timestamp"])

    result_files = []

    # Create PULSE integrated CSV (counts only)
    pulse_csv_path = dest_dir / f"integrated_raw_PULSE_{date}.csv"

    with open(pulse_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'timestamp',
            'device',
            'session',
            'cycle_index',
            'pulse_count',
        ])

        # Data rows
        for cycle in all_pulse_cycles:
            writer.writerow([
                cycle['timestamp'],
                cycle['device'],
                cycle['session'],
                cycle['cycle_index'],
                len(cycle['pulses']),
            ])

    result_files.append(str(pulse_csv_path))

    # Create VIB integrated CSV (merge PULSE and VIB by timestamp, counts only)
    vib_csv_path = dest_dir / f"integrated_raw_VIB_{date}.csv"

    # Prepare merged cycles (PULSE + VIB)
    merged_cycles = []

    # Add PULSE cycles with type marker
    for cycle in all_pulse_cycles:
        merged_cycles.append({
            'timestamp': cycle['timestamp'],
            'device': cycle['device'],
            'session': cycle['session'],
            'cycle_index': cycle['cycle_index'],
            'type': 'PULSE',
            'pulse_accel_x_count': len(cycle['accel_x']),
            'pulse_accel_z_count': len(cycle['accel_z']),
            'vib_accel_x_count': '',
            'vib_accel_z_count': '',
        })

    # Add VIB cycles with type marker
    for cycle in all_vib_cycles:
        merged_cycles.append({
            'timestamp': cycle['timestamp'],
            'device': cycle['device'],
            'session': cycle['session'],
            'cycle_index': cycle['cycle_index'],
            'type': 'VIB',
            'pulse_accel_x_count': '',
            'pulse_accel_z_count': '',
            'vib_accel_x_count': len(cycle['accel_x']),
            'vib_accel_z_count': len(cycle['accel_z']),
        })

    # Sort by timestamp
    merged_cycles.sort(key=lambda c: c['timestamp'])

    with open(vib_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'timestamp',
            'device',
            'session',
            'cycle_index',
            'pulse_accel_x_count',
            'pulse_accel_z_count',
            'vib_accel_x_count',
            'vib_accel_z_count',
        ])

        # Data rows
        for cycle in merged_cycles:
            writer.writerow([
                cycle['timestamp'],
                cycle['device'],
                cycle['session'],
                cycle['cycle_index'],
                cycle['pulse_accel_x_count'],
                cycle['pulse_accel_z_count'],
                cycle['vib_accel_x_count'],
                cycle['vib_accel_z_count'],
            ])

    result_files.append(str(vib_csv_path))

    return result_files

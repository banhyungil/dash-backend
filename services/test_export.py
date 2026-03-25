"""Test export service for debugging and data validation."""
import shutil
import csv
from pathlib import Path
from typing import List, Dict, Any
from services.settings_service import get_setting


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

            # Get device name from device mapping (R1, R2, R3, R4)
            device_name = get_setting("device_name_map").get(device, device)

            if pulse_file.exists():
                dest_file = dest_dir / f"{device_name}_PULSE_{date}.csv"
                shutil.copy2(pulse_file, dest_file)
                copied_files.append(str(dest_file))

            if vib_file.exists():
                dest_file = dest_dir / f"{device_name}_VIB_{date}.csv"
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
    Create integrated CSV from DB waveform data (no RPM calculation, no filtering).
    Query waveforms by cycle id and sort by timestamp.

    Args:
        month: Month code
        date: Date string
        devices: List of device MAC addresses
        dest_dir: Destination directory
    """
    from repos.cycles_repo import find_by_date
    from repos.pulse_waveform_repo import find_by_cycle_id as find_pulse_waveform
    from repos.vib_waveform_repo import find_by_cycle_id as find_vib_waveform

    dest_dir.mkdir(parents=True, exist_ok=True)

    # DB에서 해당 날짜의 사이클 조회
    db_cycles = find_by_date(month, date)

    all_pulse_cycles = []
    all_vib_cycles = []

    for cycle in db_cycles:
        cycle_id = cycle["id"]
        device = cycle["device"]
        device_name = cycle["device_name"]
        cycle_index = cycle["cycle_index"]
        timestamp = cycle["timestamp"]

        # PULSE 파형 조회
        pw = find_pulse_waveform(cycle_id)
        if pw:
            all_pulse_cycles.append({
                "timestamp": timestamp,
                "device": device,
                "device_name": device_name,
                "cycle_index": cycle_index,
                "pulses": pw["pulses"],
                "accel_x": pw["accel_x"],
                "accel_y": pw["accel_y"],
                "accel_z": pw["accel_z"],
            })

        # VIB 파형 조회
        vw = find_vib_waveform(cycle_id)
        if vw:
            all_vib_cycles.append({
                "timestamp": timestamp,
                "device": device,
                "device_name": device_name,
                "cycle_index": cycle_index,
                "accel_x": vw["accel_x"],
                "accel_z": vw["accel_z"],
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
            'device_name',
            'cycle_index',
            'pulse_count',
        ])

        # Data rows
        for cycle in all_pulse_cycles:
            writer.writerow([
                cycle['timestamp'],
                cycle['device'],
                cycle['device_name'],
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
            'device_name': cycle['device_name'],
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
            'device_name': cycle['device_name'],
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
            'device_name',
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
                cycle['device_name'],
                cycle['cycle_index'],
                cycle['pulse_accel_x_count'],
                cycle['pulse_accel_z_count'],
                cycle['vib_accel_x_count'],
                cycle['vib_accel_z_count'],
            ])

    result_files.append(str(vib_csv_path))

    return result_files

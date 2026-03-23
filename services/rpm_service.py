import math
import numpy as np
from itertools import accumulate
from config import ALLOW_RPM_ERROR_PER_SET, RPM_READ_OFFSET


def calc_rpm(pulse_duration: float, shaft_dia: float, pattern_width: float) -> float:
    """Convert single pulse duration (microseconds) to RPM."""
    if pulse_duration <= 0:
        return 0
    radius = shaft_dia / 2
    return (60 / (2 * math.pi)) * (pattern_width / (radius * (pulse_duration / 1000))) * 1000


def calc_edge_masking(rpm_data: np.ndarray) -> np.ndarray:
    """Create boolean mask to remove pattern edge artifacts."""
    mean_val = np.mean(rpm_data)
    min_val = np.min(rpm_data)
    center_val = (mean_val + min_val) / 2
    return rpm_data >= center_val


def expand_false_regions(masking: np.ndarray, n: int = 1) -> np.ndarray:
    """Expand False regions by n pulses on each side."""
    mask = masking.copy()
    false_idx = np.where(~mask)[0]
    for idx in false_idx:
        start = max(0, idx - n)
        end = min(len(mask), idx + n + 1)
        mask[start:end] = False
    return mask


def calc_timeline(pulse_data: list, read_offset: int = 0) -> list[float]:
    """Convert pulse durations to cumulative timeline (seconds)."""
    data = pulse_data[read_offset:]
    return [acc / 1_000_000 for acc in accumulate(data)]


def process_pulse_to_rpm(
    raw_data: list[dict],
    shaft_dia: float,
    pattern_width: float,
    read_offset: int = RPM_READ_OFFSET,
) -> dict:
    """Process raw pulse data into RPM with edge masking.
    Returns dict with rpmMean, timeLine, dataRPM, dataAccelX/Y/Z, durationms.
    """
    if not raw_data or len(raw_data) <= read_offset:
        return None

    raw_pulses = [item["pulse"] for item in raw_data][read_offset:]
    raw_accel_x = np.array([item.get("accel_x", 0) for item in raw_data][read_offset:])
    raw_accel_y = np.array([item.get("accel_y", 0) for item in raw_data][read_offset:])
    raw_accel_z = np.array([item.get("accel_z", 0) for item in raw_data][read_offset:])

    raw_timeline = np.array(calc_timeline(raw_pulses, 0))
    rpm_converted = np.array([calc_rpm(val, shaft_dia, pattern_width) for val in raw_pulses])

    if len(rpm_converted) == 0:
        return None

    masking = calc_edge_masking(rpm_converted)
    masking = expand_false_regions(masking, n=1)

    masked_rpm = rpm_converted[masking]
    if len(masked_rpm) == 0:
        return None

    return {
        "rpmMean": float(masked_rpm.mean()),
        "rpmMin": float(masked_rpm.min()),
        "rpmMax": float(masked_rpm.max()),
        "timeLine": raw_timeline[masking].tolist(),
        "dataRPM": masked_rpm.tolist(),
        "dataAccelX": raw_accel_x[masking].tolist(),
        "dataAccelY": raw_accel_y[masking].tolist(),
        "dataAccelZ": raw_accel_z[masking].tolist(),
        "durationms": sum(raw_pulses) / 1000,
        # Raw (unmasked) accel data for vibration analysis
        "rawTimeLine": raw_timeline.tolist(),
        "rawAccelX": raw_accel_x.tolist(),
        "rawAccelY": raw_accel_y.tolist(),
        "rawAccelZ": raw_accel_z.tolist(),
    }


def process_pulse_compact_to_rpm(
    pulses: list[int],
    accel_x: list[float],
    accel_y: list[float],
    accel_z: list[float],
    shaft_dia: float,
    pattern_width: float,
    read_offset: int = RPM_READ_OFFSET,
) -> dict | None:
    """Process pre-parsed flat arrays into RPM with edge masking.
    Same output as process_pulse_to_rpm but takes columnar data directly.
    """
    if not pulses or len(pulses) <= read_offset:
        return None

    raw_pulses = pulses[read_offset:]
    raw_accel_x = np.array(accel_x[read_offset:])
    raw_accel_y = np.array(accel_y[read_offset:])
    raw_accel_z = np.array(accel_z[read_offset:])

    raw_timeline = np.array(calc_timeline(raw_pulses, 0))
    rpm_converted = np.array([calc_rpm(val, shaft_dia, pattern_width) for val in raw_pulses])

    if len(rpm_converted) == 0:
        return None

    masking = calc_edge_masking(rpm_converted)
    masking = expand_false_regions(masking, n=1)

    masked_rpm = rpm_converted[masking]
    if len(masked_rpm) == 0:
        return None

    return {
        "rpmMean": float(masked_rpm.mean()),
        "rpmMin": float(masked_rpm.min()),
        "rpmMax": float(masked_rpm.max()),
        "timeLine": raw_timeline[masking].tolist(),
        "dataRPM": masked_rpm.tolist(),
        "dataAccelX": raw_accel_x[masking].tolist(),
        "dataAccelY": raw_accel_y[masking].tolist(),
        "dataAccelZ": raw_accel_z[masking].tolist(),
        "durationms": sum(raw_pulses) / 1000,
        "rawTimeLine": raw_timeline.tolist(),
        "rawAccelX": raw_accel_x.tolist(),
        "rawAccelY": raw_accel_y.tolist(),
        "rawAccelZ": raw_accel_z.tolist(),
    }


def calc_rpm_state(rpm_data: list[float], target_rpm: float) -> str:
    """Determine RPM status based on tolerance levels."""
    if not rpm_data:
        return "normal"

    max_rpm = max(rpm_data)
    min_rpm = min(rpm_data)
    status = "normal"

    for _k, v in reversed(ALLOW_RPM_ERROR_PER_SET.items()):
        low_th = round(target_rpm * (1 - (v["val"] / 100)), 3)
        high_th = round(target_rpm * (1 + (v["val"] / 100)), 3)
        if max_rpm > high_th or min_rpm < low_th:
            status = v["type"]
            break

    return status

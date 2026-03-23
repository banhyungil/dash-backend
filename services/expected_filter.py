"""Expected pulse count calculation and filtering logic."""
import math
from config import EXPECTED_TOLERANCE


def calculate_expected_pulse_count(
    rpm_mean: float,
    shaft_dia: float,
    pattern_width: float,
) -> int:
    """
    Calculate expected pulse count based on mean RPM.

    Logic from TimelineView.tsx:
    - RPM_CONSTANT = 60 / (2 * PI) = 9.549296586
    - SAMPLING_TIME = 5 seconds = 5,000,000 microseconds
    - pulse_width = pattern_width / (rpm_mean / RPM_CONSTANT / 1000) / (shaft_dia / 2) * 1000
    - expected_count = CEILING(SAMPLING_TIME / pulse_width)
    """
    RPM_CONSTANT = 9.549296586
    SAMPLING_TIME_US = 5 * 1000 * 1000

    # Calculate pulse width in microseconds
    radius = shaft_dia / 2
    pulse_width = pattern_width / (rpm_mean / RPM_CONSTANT / 1000) / radius * 1000

    # Expected pulse count
    expected_count = math.ceil(SAMPLING_TIME_US / pulse_width)

    return expected_count


def is_expected_valid(
    set_count: int,
    rpm_mean: float,
    shaft_dia: float,
    pattern_width: float,
    tolerance: float = EXPECTED_TOLERANCE,
) -> bool:
    """
    Check if actual pulse count (set_count) is within tolerance of expected count.

    Args:
        set_count: Actual pulse count from data
        rpm_mean: Mean RPM calculated from pulses
        shaft_dia: Shaft diameter (mm)
        pattern_width: Pattern width (mm)
        tolerance: Acceptable tolerance (default 10% = 0.1)

    Returns:
        True if abs(set_count - expected) / expected <= tolerance
    """
    expected_count = calculate_expected_pulse_count(rpm_mean, shaft_dia, pattern_width)

    if expected_count == 0:
        return False

    deviation = abs(set_count - expected_count) / expected_count

    return deviation <= tolerance

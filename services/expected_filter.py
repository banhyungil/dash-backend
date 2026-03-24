"""Expected pulse count calculation logic."""
import math


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

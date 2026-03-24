"""Tests for expected_filter: pulse count calculation."""
from services.expected_filter import calculate_expected_pulse_count


class TestCalculateExpectedPulseCount:
    def test_typical_values(self):
        """With default shaft_dia=50, pattern_width=10, rpm=100."""
        count = calculate_expected_pulse_count(100, 50, 10)
        assert isinstance(count, int)
        assert count > 0

    def test_higher_rpm_more_pulses(self):
        """Higher RPM should produce more expected pulses."""
        count_low = calculate_expected_pulse_count(50, 50, 10)
        count_high = calculate_expected_pulse_count(200, 50, 10)
        assert count_high > count_low

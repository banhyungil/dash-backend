"""Tests for expected_filter: pulse count validation."""
from services.expected_filter import calculate_expected_pulse_count, is_expected_valid


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


class TestIsExpectedValid:
    def test_exact_match(self):
        """Exact match should be valid."""
        expected = calculate_expected_pulse_count(100, 50, 10)
        assert is_expected_valid(expected, 100, 50, 10)

    def test_within_tolerance(self):
        """Within 10% should be valid."""
        expected = calculate_expected_pulse_count(100, 50, 10)
        # 5% off
        almost = int(expected * 1.05)
        assert is_expected_valid(almost, 100, 50, 10)

    def test_outside_tolerance(self):
        """More than 10% off should be invalid."""
        expected = calculate_expected_pulse_count(100, 50, 10)
        way_off = expected * 2
        assert not is_expected_valid(way_off, 100, 50, 10)

    def test_custom_tolerance(self):
        expected = calculate_expected_pulse_count(100, 50, 10)
        # 15% off — fails default 10%, passes 20%
        off_15 = int(expected * 1.15)
        assert not is_expected_valid(off_15, 100, 50, 10, tolerance=0.1)
        assert is_expected_valid(off_15, 100, 50, 10, tolerance=0.2)

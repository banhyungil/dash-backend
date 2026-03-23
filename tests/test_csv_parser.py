"""Tests for csv_parser: old/new format handling."""
from pathlib import Path
from services.csv_parser import parse_pulse_csv, parse_vib_csv


class TestParsePulseCsv:
    def test_old_format(self, tmp_path, sample_pulse_line_old):
        """Old format: DATETIME, [JSON] — timestamp should be clean datetime."""
        csv = tmp_path / "PULSE_250920.csv"
        csv.write_text(sample_pulse_line_old + "\n")

        result = parse_pulse_csv(csv)
        assert len(result) == 1
        assert result[0]["timestamp"] == "2025-09-20 08:26:23.212"
        assert "," not in result[0]["timestamp"]  # No unix timestamp
        assert len(result[0]["data"]) == 6
        assert result[0]["data"][0]["pulse"] == 5507

    def test_new_format(self, tmp_path, sample_pulse_line_new):
        """New format: DATETIME, UNIX_TS, [JSON] — unix timestamp stripped."""
        csv = tmp_path / "PULSE_260311.csv"
        csv.write_text(sample_pulse_line_new + "\n")

        result = parse_pulse_csv(csv)
        assert len(result) == 1
        assert result[0]["timestamp"] == "2026-03-11 15:05:34.853"
        assert "1773212400" not in result[0]["timestamp"]
        assert len(result[0]["data"]) == 3

    def test_mixed_formats(self, tmp_path, sample_pulse_line_old, sample_pulse_line_new):
        """Both old and new format lines in same file."""
        csv = tmp_path / "PULSE_mixed.csv"
        csv.write_text(sample_pulse_line_old + "\n" + sample_pulse_line_new + "\n")

        result = parse_pulse_csv(csv)
        assert len(result) == 2
        assert result[0]["timestamp"] == "2025-09-20 08:26:23.212"
        assert result[1]["timestamp"] == "2026-03-11 15:05:34.853"

    def test_empty_file(self, tmp_path):
        csv = tmp_path / "PULSE_empty.csv"
        csv.write_text("")
        assert parse_pulse_csv(csv) == []

    def test_missing_file(self, tmp_path):
        assert parse_pulse_csv(tmp_path / "nonexistent.csv") == []

    def test_malformed_line_skipped(self, tmp_path, sample_pulse_line_old):
        """Malformed lines are skipped, valid lines are kept."""
        csv = tmp_path / "PULSE_bad.csv"
        csv.write_text("garbage data\n" + sample_pulse_line_old + "\n")

        result = parse_pulse_csv(csv)
        assert len(result) == 1  # Only the valid line


class TestParseVibCsv:
    def test_old_format(self, tmp_path, sample_vib_line_old):
        csv = tmp_path / "VIB_250920.csv"
        csv.write_text(sample_vib_line_old + "\n")

        result = parse_vib_csv(csv)
        assert len(result) == 1
        assert result[0]["timestamp"] == "2025-09-20 08:26:50.100"
        assert len(result[0]["data"]) == 2

    def test_new_format(self, tmp_path, sample_vib_line_new):
        csv = tmp_path / "VIB_260311.csv"
        csv.write_text(sample_vib_line_new + "\n")

        result = parse_vib_csv(csv)
        assert len(result) == 1
        assert result[0]["timestamp"] == "2026-03-11 15:06:01.584"
        assert "1773212400" not in result[0]["timestamp"]

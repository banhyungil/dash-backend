"""Tests for csv_ingester: end-to-end pipeline."""
from pathlib import Path
from services.csv_ingester import ingest_file, ingest_paths, scan_folder
from repos.file_repo import is_file_ingested
from repos.cycle_repo import get_ingest_status


class TestScanFolder:
    def test_scan_empty_dir(self, tmp_path):
        files = scan_folder(str(tmp_path))
        assert files == []

    def test_scan_with_csv_files(self, tmp_path, sample_pulse_line_old):
        pulse = tmp_path / "PULSE_250920.csv"
        pulse.write_text(sample_pulse_line_old + "\n")
        vib = tmp_path / "VIB_250920.csv"
        vib.write_text("2025-09-20 08:26:50.100, [{'accel_x': 0.07, 'accel_z': 0.02}]\n")
        # Non-matching file should be ignored
        (tmp_path / "readme.csv").write_text("hello\n")

        files = scan_folder(str(tmp_path))
        assert len(files) == 2
        types = {f["type"] for f in files}
        assert types == {"PULSE", "VIB"}

    def test_scan_nonexistent_folder(self):
        files = scan_folder("/nonexistent/path")
        assert files == []

    def test_scan_marks_already_ingested(self, tmp_path, sample_pulse_line_old):
        pulse = tmp_path / "PULSE_250920.csv"
        pulse.write_text(sample_pulse_line_old + "\n")

        # First scan — not ingested
        files = scan_folder(str(tmp_path))
        assert not files[0]["already_ingested"]

        # Ingest it
        ingest_file(str(pulse))

        # Second scan — now ingested
        files = scan_folder(str(tmp_path))
        assert files[0]["already_ingested"]


class TestIngestFile:
    def test_ingest_pulse_file(self, tmp_path, sample_pulse_line_old):
        csv = tmp_path / "PULSE_250920.csv"
        csv.write_text(sample_pulse_line_old + "\n")

        result = ingest_file(str(csv))
        assert result["filename"] == "PULSE_250920.csv"
        assert result["cycles_ingested"] >= 0
        assert isinstance(result["errors"], list)

        # File should be recorded
        assert is_file_ingested(str(csv.resolve()))

    def test_ingest_vib_file(self, tmp_path, sample_vib_line_old):
        csv = tmp_path / "VIB_250920.csv"
        csv.write_text(sample_vib_line_old + "\n")

        result = ingest_file(str(csv))
        assert result["filename"] == "VIB_250920.csv"
        assert is_file_ingested(str(csv.resolve()))

    def test_ingest_unknown_type(self, tmp_path):
        csv = tmp_path / "DATA_250920.csv"
        csv.write_text("some data\n")

        result = ingest_file(str(csv))
        assert result["cycles_ingested"] == 0
        assert len(result["errors"]) > 0


class TestIngestPaths:
    def test_ingest_multiple(self, tmp_path, sample_pulse_line_old, sample_vib_line_old):
        p1 = tmp_path / "PULSE_250920.csv"
        p1.write_text(sample_pulse_line_old + "\n")
        p2 = tmp_path / "VIB_250920.csv"
        p2.write_text(sample_vib_line_old + "\n")

        result = ingest_paths([str(p1), str(p2)])
        assert result["total_files"] == 2
        assert len(result["details"]) == 2

    def test_ingest_updates_status(self, tmp_path, sample_pulse_line_old):
        csv = tmp_path / "PULSE_250920.csv"
        csv.write_text(sample_pulse_line_old + "\n")

        ingest_file(str(csv))
        status = get_ingest_status()
        assert status["total_cycles"] >= 0

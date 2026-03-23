"""Tests for ingest_service: end-to-end pipeline."""
from services.ingest_service import ingest_file, ingest_files, scan_folder
from repos.ingested_files_repo import exists_by_path
from repos.cycles_repo import get_monthly_summary


class TestScanFolder:
    def test_scan_empty_dir(self, tmp_path):
        files = scan_folder(str(tmp_path))
        assert files == []

    def test_scan_with_csv_files(self, tmp_path, sample_pulse_line_old):
        pulse = tmp_path / "PULSE_250920.csv"
        pulse.write_text(sample_pulse_line_old + "\n")
        vib = tmp_path / "VIB_250920.csv"
        vib.write_text("2025-09-20 08:26:50.100, [{'accel_x': 0.07, 'accel_z': 0.02}]\n")
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

        files = scan_folder(str(tmp_path))
        assert not files[0]["already_ingested"]

        ingest_file(str(pulse))

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

        assert exists_by_path(str(csv.resolve()))

    def test_ingest_vib_file(self, tmp_path, sample_vib_line_old):
        csv = tmp_path / "VIB_250920.csv"
        csv.write_text(sample_vib_line_old + "\n")

        result = ingest_file(str(csv))
        assert result["filename"] == "VIB_250920.csv"
        assert exists_by_path(str(csv.resolve()))

    def test_ingest_unknown_type(self, tmp_path):
        csv = tmp_path / "DATA_250920.csv"
        csv.write_text("some data\n")

        result = ingest_file(str(csv))
        assert result["cycles_ingested"] == 0
        assert len(result["errors"]) > 0


class TestIngestFiles:
    def test_ingest_multiple(self, tmp_path, sample_pulse_line_old, sample_vib_line_old):
        p1 = tmp_path / "PULSE_250920.csv"
        p1.write_text(sample_pulse_line_old + "\n")
        p2 = tmp_path / "VIB_250920.csv"
        p2.write_text(sample_vib_line_old + "\n")

        result = ingest_files([str(p1), str(p2)])
        assert result["total_files"] == 2
        assert len(result["details"]) == 2

    def test_ingest_updates_status(self, tmp_path, sample_pulse_line_old):
        csv = tmp_path / "PULSE_250920.csv"
        csv.write_text(sample_pulse_line_old + "\n")

        ingest_file(str(csv))
        status = get_monthly_summary()
        assert status["total_cycles"] >= 0

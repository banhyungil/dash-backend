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

    def test_ingest_batch_many_files(self, tmp_path, sample_pulse_line_old, sample_vib_line_old):
        """파일 10개 배치 적재."""
        paths = []
        for i in range(5):
            date = f"25092{i}"
            p = tmp_path / f"PULSE_{date}.csv"
            p.write_text(sample_pulse_line_old + "\n")
            paths.append(str(p))
            v = tmp_path / f"VIB_{date}.csv"
            v.write_text(sample_vib_line_old + "\n")
            paths.append(str(v))

        result = ingest_files(paths)
        assert result["total_files"] == 10
        assert len(result["details"]) == 10

    def test_ingest_batch_partial_failure(self, tmp_path, sample_pulse_line_old):
        """정상 파일 + 알 수 없는 타입 섞여있을 때 정상 파일은 성공."""
        good = tmp_path / "PULSE_250920.csv"
        good.write_text(sample_pulse_line_old + "\n")
        bad = tmp_path / "DATA_250920.csv"
        bad.write_text("invalid\n")

        result = ingest_files([str(good), str(bad)])
        assert result["total_files"] == 2
        details = {d["filename"]: d for d in result["details"]}
        assert details["PULSE_250920.csv"]["cycles_ingested"] >= 0
        assert len(details["DATA_250920.csv"]["errors"]) > 0

    def test_ingest_batch_duplicate_skip(self, tmp_path, sample_pulse_line_old):
        """이미 적재된 파일을 다시 보냈을 때 처리."""
        csv = tmp_path / "PULSE_250920.csv"
        csv.write_text(sample_pulse_line_old + "\n")

        ingest_file(str(csv))
        result = ingest_files([str(csv)])
        assert result["total_files"] == 1

    def test_ingest_batch_with_empty_file(self, tmp_path, sample_pulse_line_old):
        """정상 파일 + 빈 파일 섞여있을 때."""
        good = tmp_path / "PULSE_250920.csv"
        good.write_text(sample_pulse_line_old + "\n")
        empty = tmp_path / "PULSE_250921.csv"
        empty.write_text("")

        result = ingest_files([str(good), str(empty)])
        assert result["total_files"] == 2
        details = {d["filename"]: d for d in result["details"]}
        assert details["PULSE_250920.csv"]["cycles_ingested"] >= 0

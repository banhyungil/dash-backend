"""Tests for repos: cycles_repo and ingested_files_repo."""
from repos.cycles_repo import insert_many, get_monthly_summary
from repos.ingested_files_repo import upsert, exists_by_path


class TestCyclesRepo:
    def _make_cycle(self, **overrides):
        defaults = {
            "timestamp": "2026-03-11 15:05:34.853",
            "date": "260311",
            "month": "2603",
            "device": "0013A20041F9D4F8",
            "session": "R4",
            "cycle_index": 0,
            "rpm_mean": 95.42,
            "rpm_min": 92.15,
            "rpm_max": 98.67,
            "mpm_mean": 42.0,
            "mpm_min": 40.5,
            "mpm_max": 43.5,
            "duration_ms": 2629.37,
            "set_count": 5,
            "expected_count": 5,
            "is_valid": 1,
            "max_vib_x": 0.08,
            "max_vib_z": 0.02,
            "high_vib_event": 0,
            "source_path": "/test/PULSE_260311.csv",
        }
        defaults.update(overrides)
        return defaults

    def test_insert_and_status(self):
        cycles = [
            self._make_cycle(cycle_index=0),
            self._make_cycle(cycle_index=1, is_valid=0),
            self._make_cycle(cycle_index=2, high_vib_event=1),
        ]
        inserted = insert_many(cycles)
        assert inserted == 3

        status = get_monthly_summary()
        assert status["total_cycles"] == 3
        assert status["total_dates"] == 1
        assert len(status["months"]) == 1

        month = status["months"][0]
        assert month["month"] == "2603"
        assert month["total_cycles"] == 3
        assert month["valid_cycles"] == 2
        assert month["high_vib_events"] == 1

    def test_insert_empty(self):
        assert insert_many([]) == 0

    def test_upsert_on_duplicate(self):
        """INSERT OR REPLACE should update on duplicate (device, date, cycle_index)."""
        cycle = self._make_cycle(rpm_mean=90.0)
        insert_many([cycle])

        cycle_updated = self._make_cycle(rpm_mean=100.0)
        insert_many([cycle_updated])

        status = get_monthly_summary()
        assert status["total_cycles"] == 1

    def test_multiple_months(self):
        cycles = [
            self._make_cycle(month="2509", date="250920", cycle_index=0),
            self._make_cycle(month="2509", date="250921", cycle_index=0, device="D2"),
            self._make_cycle(month="2603", date="260311", cycle_index=0, device="D3"),
        ]
        insert_many(cycles)

        status = get_monthly_summary()
        assert len(status["months"]) == 2
        assert status["total_dates"] == 3
        assert status["total_cycles"] == 3


class TestIngestedFilesRepo:
    def test_record_and_check(self):
        assert not exists_by_path("/test/PULSE_260311.csv")

        upsert("/test/PULSE_260311.csv", "PULSE_260311.csv", "PULSE", 10, 2, 0)

        assert exists_by_path("/test/PULSE_260311.csv")
        assert not exists_by_path("/test/PULSE_260312.csv")

    def test_re_record_overwrites(self):
        upsert("/test/PULSE_260311.csv", "PULSE_260311.csv", "PULSE", 10, 2, 0)
        upsert("/test/PULSE_260311.csv", "PULSE_260311.csv", "PULSE", 15, 1, 0)

        assert exists_by_path("/test/PULSE_260311.csv")

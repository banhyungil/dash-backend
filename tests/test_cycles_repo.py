"""Tests for repos: cycles_repo and ingested_files_repo."""
from repos.cycles_repo import insert_many, get_monthly_summary, find_by_date, _STAT_COLUMNS
from repos.ingested_files_repo import upsert, exists_by_path


def _make_cycle(**overrides):
    """테스트용 사이클 dict 생성. stats 컬럼 포함."""
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
        "burst_count": 2,
        "peak_impact_count": 1,
        "source_path": "/test/PULSE_260311.csv",
    }
    # stats 컬럼 기본값 0
    for col in _STAT_COLUMNS:
        defaults.setdefault(col, 0)
    defaults.update(overrides)
    return defaults


class TestCyclesRepo:

    def test_insert_and_status(self):
        cycles = [
            _make_cycle(cycle_index=0),
            _make_cycle(cycle_index=1, is_valid=0),
            _make_cycle(cycle_index=2, high_vib_event=1),
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
        cycle = _make_cycle(rpm_mean=90.0)
        insert_many([cycle])

        cycle_updated = _make_cycle(rpm_mean=100.0)
        insert_many([cycle_updated])

        status = get_monthly_summary()
        assert status["total_cycles"] == 1

    def test_multiple_months(self):
        cycles = [
            _make_cycle(month="2509", date="250920", cycle_index=0),
            _make_cycle(month="2509", date="250921", cycle_index=0, device="D2"),
            _make_cycle(month="2603", date="260311", cycle_index=0, device="D3"),
        ]
        insert_many(cycles)

        status = get_monthly_summary()
        assert len(status["months"]) == 2
        assert status["total_dates"] == 3
        assert status["total_cycles"] == 3


class TestCycleDataIntegrity:
    """DB 저장/조회 시 주요 컬럼 값이 정상인지 검증."""

    def test_duration_ms_persisted(self):
        """duration_ms가 insert → find_by_date 시 보존되는지 확인."""
        cycle = _make_cycle(duration_ms=4886.32)
        insert_many([cycle])

        rows = find_by_date("2603", "260311")
        assert len(rows) == 1
        assert rows[0]["duration_ms"] == 4886.32

    def test_stats_columns_persisted(self):
        """stats 컬럼(q1/median/q3 등)이 저장 후 조회되는지 확인."""
        cycle = _make_cycle(
            pulse_x_rms=0.005,
            pulse_x_q1=0.002,
            pulse_x_median=0.003,
            pulse_x_q3=0.006,
            vib_x_rms=0.004,
            vib_x_exceed_count=15,
        )
        insert_many([cycle])

        rows = find_by_date("2603", "260311")
        row = rows[0]
        assert row["pulse_x_rms"] == 0.005
        assert row["pulse_x_q1"] == 0.002
        assert row["pulse_x_median"] == 0.003
        assert row["pulse_x_q3"] == 0.006
        assert row["vib_x_rms"] == 0.004
        assert row["vib_x_exceed_count"] == 15

    def test_burst_and_impact_persisted(self):
        """burst_count, peak_impact_count 저장 확인."""
        cycle = _make_cycle(burst_count=5, peak_impact_count=3)
        insert_many([cycle])

        rows = find_by_date("2603", "260311")
        assert rows[0]["burst_count"] == 5
        assert rows[0]["peak_impact_count"] == 3

    def test_zero_duration_ms(self):
        """duration_ms가 0이면 가동시간도 0."""
        cycle = _make_cycle(duration_ms=0)
        insert_many([cycle])

        rows = find_by_date("2603", "260311")
        assert rows[0]["duration_ms"] == 0

    def test_multiple_sessions_duration(self):
        """여러 세션의 duration_ms 합산 확인."""
        cycles = [
            _make_cycle(session="R1", cycle_index=0, duration_ms=5000.0, device="D1"),
            _make_cycle(session="R2", cycle_index=0, duration_ms=4500.0, device="D2"),
            _make_cycle(session="R3", cycle_index=0, duration_ms=4800.0, device="D3"),
        ]
        insert_many(cycles)

        rows = find_by_date("2603", "260311")
        total_ms = sum(r["duration_ms"] for r in rows)
        assert total_ms == 14300.0


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

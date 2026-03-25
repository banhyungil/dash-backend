"""진동 이벤트 분석 서비스 — burst/peak impact 구분."""
from __future__ import annotations

import math
import numpy as np
from config import VIB_SAMPLE_RATE
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.ingest_service import AxisStats


def analyze_axis(samples: list[float], sample_rate: int = VIB_SAMPLE_RATE, threshold: float = 0.1) -> "AxisStats":
    """축별 진동 이벤트 분석.

    Returns:
        rms, peak, min, max, q1, median, q3: 분포 통계
        exceed_count: threshold 초과 샘플 수
        exceed_ratio: 초과 비율
        exceed_duration_ms: 초과 총 시간 (ms)
        burst_count: 지속 진동 이벤트 (≥500ms)
        peak_impact_count: 순간 충격 이벤트 (<500ms)
    """
    if not samples:
        return _empty_stats()

    arr = np.array(samples, dtype=np.float64)
    abs_arr = np.abs(arr)

    # 분포 통계
    rms = float(np.sqrt(np.mean(arr ** 2)))
    peak = float(np.max(abs_arr))
    q1, median, q3 = [float(v) for v in np.percentile(abs_arr, [25, 50, 75])]

    # Threshold 초과 분석
    exceed_mask = abs_arr > threshold
    exceed_count = int(np.sum(exceed_mask))
    exceed_ratio = exceed_count / len(arr) if len(arr) > 0 else 0.0
    exceed_duration_ms = (exceed_count / sample_rate) * 1000

    # Burst vs Peak Impact 분류
    burst_count, peak_impact_count = _classify_events(exceed_mask, sample_rate)

    return {
        "rms": round(rms, 6),
        "peak": round(peak, 6),
        "min": round(float(np.min(arr)), 6),
        "max": round(float(np.max(arr)), 6),
        "q1": round(q1, 6),
        "median": round(median, 6),
        "q3": round(q3, 6),
        "exceed_count": exceed_count,
        "exceed_ratio": round(exceed_ratio, 4),
        "exceed_duration_ms": round(exceed_duration_ms, 2),
        "burst_count": burst_count,
        "peak_impact_count": peak_impact_count,
    }


def analyze_cycle(cycle: dict, sample_rate: int = VIB_SAMPLE_RATE) -> dict:
    """사이클의 모든 축에 대해 분석 수행. 결과를 stats_* 키로 반환."""
    stats = {}
    axis_map = {
        "stats_pulse_x": "pulse_accel_x",
        "stats_pulse_y": "pulse_accel_y",
        "stats_pulse_z": "pulse_accel_z",
        "stats_vib_x": "vib_accel_x",
        "stats_vib_z": "vib_accel_z",
    }
    for stat_key, data_key in axis_map.items():
        data = cycle.get(data_key, [])
        stats[stat_key] = analyze_axis(data, sample_rate)
    return stats


def _classify_events(exceed_mask: np.ndarray, sample_rate: int) -> tuple[int, int]:
    """연속 초과 구간을 burst(≥500ms) / peak impact(<500ms)로 분류."""
    burst_count = 0
    peak_impact_count = 0
    min_burst_samples = int(sample_rate * 0.5)  # 500ms

    # 연속 구간 찾기
    in_event = False
    event_len = 0

    for exceeded in exceed_mask:
        if exceeded:
            if not in_event:
                in_event = True
                event_len = 0
            event_len += 1
        else:
            if in_event:
                if event_len >= min_burst_samples:
                    burst_count += 1
                else:
                    peak_impact_count += 1
                in_event = False

    # 마지막 이벤트 처리
    if in_event:
        if event_len >= min_burst_samples:
            burst_count += 1
        else:
            peak_impact_count += 1

    return burst_count, peak_impact_count


def _empty_stats() -> "AxisStats":
    return {
        "rms": 0, "peak": 0, "min": 0, "max": 0,
        "q1": 0, "median": 0, "q3": 0,
        "exceed_count": 0, "exceed_ratio": 0, "exceed_duration_ms": 0,
        "burst_count": 0, "peak_impact_count": 0,
    }

"""CSV 파서: PULSE/VIB CSV 파일 파싱.
구/신 포맷 모두 지원.

ast.literal_eval 대신 json.loads 사용 (5~10배 빠름).
CSV 데이터가 Python dict 리터럴 형식({'key': val})이므로
작은따옴표 → 큰따옴표로 변환 후 JSON 파싱.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_data(data_str: str) -> list[dict]:
    """Python dict 리터럴 문자열을 JSON으로 변환 후 파싱.
    예: [{'pulse': 5507, 'accel_x': 0.08}] → JSON 파싱
    """
    # 작은따옴표 → 큰따옴표 (Python dict → JSON 변환)
    json_str = data_str.replace("'", '"')
    return json.loads(json_str)


def _parse_csv_lines(file_path: Path) -> list[dict]:
    """CSV 파일의 각 줄을 파싱. PULSE/VIB 공통 로직.
    반환: [{"timestamp": str, "data": [dict, ...]}, ...]
    """
    cycles = []
    if not file_path.exists():
        return cycles

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                # 줄 구조: "timestamp, [데이터배열]" 또는 "timestamp, unix_ts, [데이터배열]"
                # ", [" 를 기준으로 앞쪽(timestamp 부분)과 뒤쪽(JSON 배열)을 분리
                comma_idx = line.index(", [")

                # 앞쪽에서 timestamp 추출
                timestamp = line[:comma_idx].strip()
                # 신 포맷("2026-03-11 15:05:34, 1773212400")이면 쉼표 기준 첫 부분만 사용
                if ", " in timestamp:
                    timestamp = timestamp.split(", ")[0].strip()

                # 뒤쪽 JSON 배열 파싱 ("[{...}, {...}, ...]")
                data_str = line[comma_idx + 2:]  # ", " 2글자 건너뛰기
                data = _parse_data(data_str)

                cycles.append({"timestamp": timestamp, "data": data})
            except (ValueError, json.JSONDecodeError) as e:
                # 파싱 실패한 줄은 스킵하고 로그 남김
                logger.warning("Skipped line %d in %s: %s", line_num, file_path, e)
                continue

    return cycles


def parse_pulse_csv(file_path: str | Path) -> list[dict]:
    """PULSE CSV 파싱. 각 줄 = 1 사이클.
    반환: [{"timestamp": str, "data": [{"pulse": int, "accel_x": float, ...}, ...]}, ...]
    """
    return _parse_csv_lines(Path(file_path))


def parse_vib_csv(file_path: str | Path) -> list[dict]:
    """VIB CSV 파싱. 각 줄 = 1 사이클.
    반환: [{"timestamp": str, "data": [{"accel_x": float, "accel_z": float}, ...]}, ...]
    """
    return _parse_csv_lines(Path(file_path))

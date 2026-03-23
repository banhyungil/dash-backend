import ast
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_pulse_csv(file_path: str | Path) -> list[dict]:
    """Parse PULSE CSV file. Each line = 1 cycle.
    Format (old): timestamp, [{pulse, accel_x, accel_y, accel_z}, ...]
    Format (new): timestamp, unix_ts, [{pulse, accel_x, accel_y, accel_z}, ...]
    Returns list of {"timestamp": str, "data": [dict, ...]}
    """
    cycles = []
    path = Path(file_path)
    if not path.exists():
        return cycles

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                comma_idx = line.index(", [")
                timestamp = line[:comma_idx].strip()
                # Handle new format: "datetime, unix_ts" -> extract just datetime
                if ", " in timestamp:
                    timestamp = timestamp.split(", ")[0].strip()
                data_str = line[comma_idx + 2:]
                data = ast.literal_eval(data_str)
                cycles.append({"timestamp": timestamp, "data": data})
            except (ValueError, SyntaxError) as e:
                logger.warning("Skipped line %d in %s: %s", line_num, file_path, e)
                continue

    return cycles


def parse_vib_csv(file_path: str | Path) -> list[dict]:
    """Parse VIB CSV file. Each line = 1 cycle.
    Format (old): timestamp, [{accel_x, accel_z}, ...]
    Format (new): timestamp, unix_ts, [{accel_x, accel_z}, ...]
    Returns list of {"timestamp": str, "data": [dict, ...]}
    """
    cycles = []
    path = Path(file_path)
    if not path.exists():
        return cycles

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                comma_idx = line.index(", [")
                timestamp = line[:comma_idx].strip()
                if ", " in timestamp:
                    timestamp = timestamp.split(", ")[0].strip()
                data_str = line[comma_idx + 2:]
                data = ast.literal_eval(data_str)
                cycles.append({"timestamp": timestamp, "data": data})
            except (ValueError, SyntaxError) as e:
                logger.warning("Skipped line %d in %s: %s", line_num, file_path, e)
                continue

    return cycles

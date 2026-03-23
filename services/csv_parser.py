import ast
from pathlib import Path


def parse_pulse_csv(file_path: str | Path) -> list[dict]:
    """Parse PULSE CSV file. Each line = 1 cycle.
    Format: timestamp, [{pulse, accel_x, accel_y, accel_z}, ...]
    Returns list of {"timestamp": str, "data": [dict, ...]}
    """
    cycles = []
    path = Path(file_path)
    if not path.exists():
        return cycles

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                # Split at first ", [" to separate timestamp from data
                comma_idx = line.index(", [")
                timestamp = line[:comma_idx].strip()
                data_str = line[comma_idx + 2:]  # skip ", "
                data = ast.literal_eval(data_str)
                cycles.append({"timestamp": timestamp, "data": data})
            except (ValueError, SyntaxError):
                continue

    return cycles


def parse_vib_csv(file_path: str | Path) -> list[dict]:
    """Parse VIB CSV file. Each line = 1 cycle.
    Format: timestamp, [{accel_x, accel_z}, ...]
    Returns list of {"timestamp": str, "data": [dict, ...]}
    """
    cycles = []
    path = Path(file_path)
    if not path.exists():
        return cycles

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                comma_idx = line.index(", [")
                timestamp = line[:comma_idx].strip()
                data_str = line[comma_idx + 2:]
                data = ast.literal_eval(data_str)
                cycles.append({"timestamp": timestamp, "data": data})
            except (ValueError, SyntaxError):
                continue

    return cycles

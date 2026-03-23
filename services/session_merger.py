"""Merge multiple sessions (r1~r4) into a single timeline by timestamp."""
from typing import List, Dict, Any


def merge_sessions_by_timestamp(sessions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge multiple sessions (r1, r2, r3, r4) into a single continuous timeline.

    Each session contains cycles with timestamps. This function:
    1. Collects all cycles from all sessions
    2. Sorts by timestamp
    3. Returns merged data with continuous timeline

    Args:
        sessions_data: List of session data, each containing:
            - session: session name (r1, r2, r3, r4)
            - cycles: list of cycle data

    Returns:
        Merged data with all cycles sorted by timestamp
    """
    all_cycles = []

    # Collect all cycles from all sessions
    for session_data in sessions_data:
        session_name = session_data.get("session", "")
        cycles = session_data.get("cycles", [])

        for cycle in cycles:
            # Add session info to each cycle ONLY if it doesn't already have one
            if "session" not in cycle or not cycle["session"]:
                cycle["session"] = session_name
            all_cycles.append(cycle)

    # Sort by timestamp
    all_cycles.sort(key=lambda c: c.get("timestamp", ""))

    return {
        "cycles": all_cycles,
        "total_cycles": len(all_cycles),
    }


def calculate_continuous_timeline(
    cycles: List[Dict[str, Any]],
    gap_seconds: float = 0.1,
) -> List[Dict[str, Any]]:
    """
    Calculate continuous timeline offsets for merged cycles.

    For visualization, we need to place cycles on a continuous timeline.
    This function adds a 'timeline_offset' to each cycle.

    Args:
        cycles: List of cycles (already sorted by timestamp)
        gap_seconds: Gap between cycles in seconds (default 0.1s)

    Returns:
        Cycles with added 'timeline_offset' field
    """
    current_offset = 0.0

    for cycle in cycles:
        cycle["timeline_offset"] = current_offset

        # Get cycle duration from rpm_timeline or duration_ms
        if "rpm_timeline" in cycle and len(cycle["rpm_timeline"]) > 0:
            cycle_duration = cycle["rpm_timeline"][-1]  # Last time in timeline
        elif "duration_ms" in cycle:
            cycle_duration = cycle["duration_ms"] / 1000.0  # Convert to seconds
        else:
            cycle_duration = 5.0  # Default 5 seconds

        # Update offset for next cycle
        current_offset += cycle_duration + gap_seconds

    return cycles

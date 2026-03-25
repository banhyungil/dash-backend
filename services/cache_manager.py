"""Cache manager: read/write/validate msgpack-based caches.

Cache structure:
  .cache/parsed/{month}/{device}/{device_name}/PULSE_{date}.msgpack
  .cache/parsed/{month}/{device}/{device_name}/VIB_{date}.msgpack
  .cache/derived/{month}/{device}/{device_name}/VIB_{date}_c{cycle}.msgpack
  .cache/manifest.msgpack
"""

import logging
from pathlib import Path
from typing import Any, cast

import msgpack

from config import CACHE_DIR, CACHE_VERSION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def _source_meta(source_path: Path) -> dict:
    """Return mtime + size metadata for a source file."""
    stat = source_path.stat()
    return {
        "mtime": stat.st_mtime,
        "size": stat.st_size,
        "cache_version": CACHE_VERSION,
    }


def _is_valid(cached_meta: dict, source_path: Path) -> bool:
    """Check if cached metadata matches the current source file."""
    if cached_meta.get("cache_version") != CACHE_VERSION:
        return False
    try:
        stat = source_path.stat()
        return (
            cached_meta.get("mtime") == stat.st_mtime
            and cached_meta.get("size") == stat.st_size
        )
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _parsed_cache_path(month: str, device: str, device_name: str, filename: str) -> Path:
    """Return cache path for a parsed CSV file.
    filename: e.g. 'PULSE_260101' or 'VIB_260101' (no extension).
    """
    return CACHE_DIR / "parsed" / month / device / device_name / f"{filename}.msgpack"


def _derived_cache_path(month: str, device: str, device_name: str, date: str, cycle_index: int) -> Path:
    """Return cache path for derived VIB analysis (FFT/spectrogram/RMS)."""
    return CACHE_DIR / "derived" / month / device / device_name / f"VIB_{date}_c{cycle_index}.msgpack"


def _manifest_path() -> Path:
    return CACHE_DIR / "manifest.msgpack"


# ---------------------------------------------------------------------------
# Generic read / write
# ---------------------------------------------------------------------------

def write_cache(cache_path: Path, data: dict, source_path: Path) -> None:
    """Write data + metadata to cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": _source_meta(source_path),
        "data": data,
    }
    with open(cache_path, "wb") as f:
        msgpack.pack(payload, f, use_bin_type=True)


def read_cache(cache_path: Path, source_path: Path) -> dict | None:
    """Read cached data if valid, else return None."""
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "rb") as f:
            payload = cast(dict[str, Any], msgpack.unpack(f, raw=False))
        if _is_valid(payload.get("meta", {}), source_path):
            return payload["data"]
        # Stale cache
        return None
    except Exception:
        logger.warning("Corrupt cache file: %s", cache_path)
        return None


# ---------------------------------------------------------------------------
# Parsed CSV cache
# ---------------------------------------------------------------------------

def read_parsed_cache(month: str, device: str, device_name: str, csv_stem: str, source_path: Path) -> dict | None:
    """Read parsed CSV cache. csv_stem e.g. 'PULSE_260101'."""
    cp = _parsed_cache_path(month, device, device_name, csv_stem)
    return read_cache(cp, source_path)


def write_parsed_cache(month: str, device: str, device_name: str, csv_stem: str, source_path: Path, data: dict) -> None:
    """Write parsed CSV cache."""
    cp = _parsed_cache_path(month, device, device_name, csv_stem)
    write_cache(cp, data, source_path)


# ---------------------------------------------------------------------------
# Derived VIB cache (FFT/spectrogram per cycle)
# ---------------------------------------------------------------------------

def read_derived_cache(month: str, device: str, device_name: str, date: str, cycle_index: int, source_path: Path) -> dict | None:
    cp = _derived_cache_path(month, device, device_name, date, cycle_index)
    return read_cache(cp, source_path)


def write_derived_cache(month: str, device: str, device_name: str, date: str, cycle_index: int, source_path: Path, data: dict) -> None:
    cp = _derived_cache_path(month, device, device_name, date, cycle_index)
    write_cache(cp, data, source_path)


# ---------------------------------------------------------------------------
# Manifest (Layer 0)
# ---------------------------------------------------------------------------

def read_manifest() -> dict | None:
    """Read the manifest file. Returns None if missing/corrupt."""
    mp = _manifest_path()
    if not mp.exists():
        return None
    try:
        with open(mp, "rb") as f:
            return cast(dict[str, Any], msgpack.unpack(f, raw=False))
    except Exception:
        logger.warning("Corrupt manifest: %s", mp)
        return None


def write_manifest(data: dict) -> None:
    """Write manifest data."""
    mp = _manifest_path()
    mp.parent.mkdir(parents=True, exist_ok=True)
    with open(mp, "wb") as f:
        msgpack.pack(data, f, use_bin_type=True)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def clean_cache() -> None:
    """Remove entire cache directory."""
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        logger.info("Cache cleaned: %s", CACHE_DIR)

"""Formatting helpers for human-readable file sizes, dimensions, and EXIF values."""

from __future__ import annotations

from datetime import datetime
from math import gcd


def format_file_size(size_bytes: int | None) -> str:
    """Format a byte count into a clean human-readable string."""
    if size_bytes is None or size_bytes < 0:
        return "Unavailable"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    units = ["KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    for unit in units:
        value /= 1024.0
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}"
    return f"{size_bytes} B"


def format_aspect_ratio(width: int, height: int) -> str:
    """Compute simplified aspect ratio and decimal representation."""
    if width <= 0 or height <= 0:
        return "Unavailable"
    divisor = gcd(width, height)
    w_ratio = width // divisor
    h_ratio = height // divisor
    decimal = width / height
    if w_ratio > 100 or h_ratio > 100:
        return f"{decimal:.2f}:1"
    return f"{w_ratio}:{h_ratio} ({decimal:.2f}:1)"


def format_dimensions(width: int | None, height: int | None) -> str:
    """Format pixel dimensions cleanly."""
    if not width or not height:
        return "Unavailable"
    return f"{width:,} x {height:,} px"


def format_datetime(dt: datetime | None) -> str:
    """Format a datetime object into a readable local timestamp."""
    if dt is None:
        return "Unavailable"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_exif_datetime(raw_value: str | None) -> str:
    """Convert EXIF 'YYYY:MM:DD HH:MM:SS' timestamps to 'YYYY-MM-DD HH:MM:SS'."""
    if not raw_value:
        return ""
    cleaned = str(raw_value).strip().strip("\x00")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
            if fmt == "%Y:%m:%d":
                return parsed.strftime("%Y-%m-%d")
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return cleaned


def format_gps_coordinate(decimal_deg: float, is_latitude: bool) -> str:
    """Format decimal GPS degrees with hemisphere direction and DMS representation."""
    if is_latitude:
        hemi = "N" if decimal_deg >= 0 else "S"
    else:
        hemi = "E" if decimal_deg >= 0 else "W"

    abs_val = abs(decimal_deg)
    degrees = int(abs_val)
    minutes_full = (abs_val - degrees) * 60.0
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60.0
    return f"{decimal_deg:.6f} ({degrees}° {minutes}' {seconds:.2f}\" {hemi})"


def sanitize_error_message(error: Exception) -> str:
    """Convert an exception into a concise user-facing message without paths or metadata."""
    text = str(error).strip()
    if not text:
        return "An unexpected error occurred while processing the file."
    # Keep only the first line to avoid exposing stack traces
    return text.splitlines()[0][:240]


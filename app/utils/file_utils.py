"""File system validation and discovery helpers."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from app.config import (
    HEIF_EXTENSIONS,
    MAX_SAFE_FILE_SIZE_BYTES,
    get_supported_extensions,
    is_heif_supported,
)


class ImageFileError(Exception):
    """Human-readable error raised when an image file cannot be accessed or supported."""


def validate_image_path(path: str | Path) -> Path:
    """Validate that the path exists, is readable, and uses a supported extension."""
    file_path = Path(path)

    if not file_path.exists():
        raise ImageFileError("The selected file could not be found.")
    if not file_path.is_file():
        raise ImageFileError("The selected path is not a file.")

    ext = file_path.suffix.lower()
    if ext in HEIF_EXTENSIONS and not is_heif_supported():
        raise ImageFileError(
            "HEIC/HEIF images require the optional 'pillow-heif' decoder, "
            "which is not installed."
        )

    if ext not in get_supported_extensions():
        raise ImageFileError(
            f"Unsupported file format '{ext or 'unknown'}'. "
            "Supported formats: JPG, PNG, WEBP, TIFF, BMP, GIF"
            + (", HEIC/HEIF." if is_heif_supported() else ".")
        )

    try:
        size_bytes = file_path.stat().st_size
    except PermissionError as exc:
        raise ImageFileError("Permission denied while reading the file.") from exc
    except OSError as exc:
        raise ImageFileError("Unable to access file properties.") from exc

    if size_bytes == 0:
        raise ImageFileError("The selected file is empty (0 bytes).")

    if size_bytes > MAX_SAFE_FILE_SIZE_BYTES:
        raise ImageFileError(
            "The selected file exceeds the 250 MB safety limit for local preview."
        )

    if not os.access(file_path, os.R_OK):
        raise ImageFileError("Permission denied: the file is not readable.")

    return file_path


def get_file_timestamps(file_path: Path) -> tuple[datetime | None, datetime | None]:
    """Return (created_at, modified_at) local datetimes from the filesystem."""
    try:
        stat = file_path.stat()
        created_ts = getattr(stat, "st_birthtime", None) or stat.st_ctime
        created = datetime.fromtimestamp(created_ts)
        modified = datetime.fromtimestamp(stat.st_mtime)
        return created, modified
    except OSError:
        return None, None


def collect_image_files(
    folder: str | Path,
    recursive: bool = True,
) -> list[Path]:
    """Collect supported image files from a directory in deterministic order."""
    root = Path(folder)
    if not root.exists() or not root.is_dir():
        raise ImageFileError("The selected folder does not exist.")

    supported = set(get_supported_extensions())
    files: list[Path] = []

    try:
        iterator = root.rglob("*") if recursive else root.iterdir()
        for entry in iterator:
            try:
                if entry.is_file() and entry.suffix.lower() in supported:
                    files.append(entry)
            except OSError:
                continue
    except PermissionError as exc:
        raise ImageFileError("Permission denied while scanning the folder.") from exc
    except OSError as exc:
        raise ImageFileError("Failed to scan the selected folder.") from exc

    files.sort(key=lambda p: p.name.lower())
    return files


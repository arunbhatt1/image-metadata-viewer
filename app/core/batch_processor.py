"""Batch image scanning, aggregation, filtering, and sorting with cancellation."""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.config import get_logger
from app.core.exif_parser import parse_exif
from app.core.image_loader import load_image_properties
from app.utils.file_utils import ImageFileError, collect_image_files
from app.utils.formatters import format_datetime, format_file_size, sanitize_error_message

logger = get_logger("batch_processor")


@dataclass(frozen=True)
class BatchItem:
    """Extracted metadata summary for a single image in a batch scan."""

    file_path: Path
    file_name: str
    file_format: str
    file_size_bytes: int
    width: int
    height: int
    aspect_ratio: str
    camera_model: str
    capture_date: str
    has_exif: bool
    has_gps: bool

    def to_export_dict(self) -> dict[str, object]:
        """Convert item into a readable dictionary for JSON/CSV export."""
        return {
            "File Name": self.file_name,
            "File Location": str(self.file_path.parent),
            "Format": self.file_format,
            "File Size": format_file_size(self.file_size_bytes),
            "File Size (Bytes)": self.file_size_bytes,
            "Width (px)": self.width,
            "Height (px)": self.height,
            "Aspect Ratio": self.aspect_ratio,
            "Camera Model": self.camera_model or "",
            "Capture Date": self.capture_date or "",
            "EXIF Available": "Yes" if self.has_exif else "No",
            "GPS Available": "Yes" if self.has_gps else "No",
        }


@dataclass(frozen=True)
class BatchSummary:
    """Aggregate statistics for a completed or partial batch scan."""

    total_scanned: int = 0
    error_count: int = 0
    total_size_bytes: int = 0
    avg_width: int = 0
    avg_height: int = 0
    exif_count: int = 0
    gps_count: int = 0
    format_distribution: dict[str, int] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result container returned after a batch scan."""

    items: list[BatchItem] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    summary: BatchSummary = field(default_factory=BatchSummary)
    cancelled: bool = False


def compute_batch_summary(
    items: list[BatchItem],
    error_count: int = 0,
) -> BatchSummary:
    """Compute aggregate statistics from scanned BatchItems."""
    total = len(items)
    if total == 0:
        return BatchSummary(total_scanned=0, error_count=error_count)

    total_size = sum(item.file_size_bytes for item in items)
    avg_w = round(sum(item.width for item in items) / total)
    avg_h = round(sum(item.height for item in items) / total)
    exif_count = sum(1 for item in items if item.has_exif)
    gps_count = sum(1 for item in items if item.has_gps)
    fmt_counts = dict(sorted(Counter(item.file_format for item in items).items()))

    return BatchSummary(
        total_scanned=total,
        error_count=error_count,
        total_size_bytes=total_size,
        avg_width=avg_w,
        avg_height=avg_h,
        exif_count=exif_count,
        gps_count=gps_count,
        format_distribution=fmt_counts,
    )


def filter_batch_items(
    items: list[BatchItem],
    format_filter: str = "All",
    exif_filter: str = "All",
    gps_filter: str = "All",
) -> list[BatchItem]:
    """Filter batch items by format, EXIF presence, and GPS presence."""
    result: list[BatchItem] = []
    for item in items:
        if format_filter != "All" and item.file_format.upper() != format_filter.upper():
            continue
        if exif_filter == "With EXIF" and not item.has_exif:
            continue
        if exif_filter == "Without EXIF" and item.has_exif:
            continue
        if gps_filter == "With GPS" and not item.has_gps:
            continue
        if gps_filter == "Without GPS" and item.has_gps:
            continue
        result.append(item)
    return result


def sort_batch_items(
    items: list[BatchItem],
    sort_key: str = "file_name",
    ascending: bool = True,
) -> list[BatchItem]:
    """Sort batch items deterministically by the selected column key."""
    key_funcs: dict[str, Callable[[BatchItem], object]] = {
        "file_name": lambda x: x.file_name.lower(),
        "file_format": lambda x: x.file_format.lower(),
        "file_size_bytes": lambda x: x.file_size_bytes,
        "width": lambda x: (x.width, x.height),
        "height": lambda x: (x.height, x.width),
        "aspect_ratio": lambda x: (x.width / x.height) if x.height else 0.0,
        "camera_model": lambda x: x.camera_model.lower(),
        "capture_date": lambda x: x.capture_date,
        "has_gps": lambda x: x.has_gps,
    }
    extractor = key_funcs.get(sort_key, key_funcs["file_name"])
    return sorted(items, key=extractor, reverse=not ascending)


class BatchProcessor:
    """Runs batch metadata scanning synchronously or on a cancellable worker thread."""

    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        """Return True when a background batch scan is currently active."""
        return self._thread is not None and self._thread.is_alive()

    def cancel(self) -> None:
        """Signal any active batch scan to stop cleanly after the current file."""
        self._cancel_event.set()

    def scan_folder(
        self,
        folder: str | Path,
        recursive: bool = True,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> BatchResult:
        """Collect supported files in a folder and scan them synchronously."""
        files = collect_image_files(folder, recursive=recursive)
        return self.scan_files(files, progress_callback=progress_callback)

    def scan_files(
        self,
        paths: list[str | Path],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> BatchResult:
        """Scan a list of image paths synchronously."""
        self._cancel_event.clear()
        items: list[BatchItem] = []
        errors: list[tuple[str, str]] = []
        total = len(paths)
        cancelled = False

        for idx, raw_path in enumerate(paths, start=1):
            if self._cancel_event.is_set():
                cancelled = True
                break

            file_path = Path(raw_path)
            if progress_callback is not None:
                progress_callback(idx, total, file_path.name)

            try:
                props = load_image_properties(file_path)
                exif = parse_exif(file_path)
                capture_date = exif.capture_date or (
                    format_datetime(props.modified_at) if props.modified_at else ""
                )
                # Only use EXIF capture date as capture date; leave blank if absent
                capture_date_exif = exif.capture_date
                items.append(
                    BatchItem(
                        file_path=props.file_path,
                        file_name=props.file_name,
                        file_format=props.file_format,
                        file_size_bytes=props.file_size_bytes,
                        width=props.width,
                        height=props.height,
                        aspect_ratio=props.aspect_ratio,
                        camera_model=exif.camera_model,
                        capture_date=capture_date_exif,
                        has_exif=exif.has_exif,
                        has_gps=exif.has_gps,
                    )
                )
            except ImageFileError as exc:
                errors.append((file_path.name, sanitize_error_message(exc)))
            except Exception as exc:
                logger.warning("Unexpected error during batch scan: %s", type(exc).__name__)
                errors.append((file_path.name, "Failed to read image metadata."))

        summary = compute_batch_summary(items, error_count=len(errors))
        return BatchResult(
            items=items,
            errors=errors,
            summary=summary,
            cancelled=cancelled,
        )

    def start_async(
        self,
        paths: list[str | Path],
        progress_callback: Callable[[int, int, str], None] | None = None,
        completion_callback: Callable[[BatchResult], None] | None = None,
    ) -> None:
        """Run scan_files in a background daemon thread."""
        if self.is_running:
            return

        self._cancel_event.clear()

        def worker() -> None:
            result = self.scan_files(paths, progress_callback=progress_callback)
            if completion_callback is not None:
                completion_callback(result)

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()


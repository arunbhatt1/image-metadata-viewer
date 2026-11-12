"""Metadata export to JSON and CSV with readable field names and safe overwrite checks."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.config import get_logger
from app.core.batch_processor import BatchItem, BatchSummary
from app.core.metadata_extractor import ImageRecord
from app.utils.formatters import format_file_size

logger = get_logger("exporter")


class ExportError(Exception):
    """Human-readable error raised when metadata export fails."""


def _validate_output_path(path: str | Path, overwrite: bool) -> Path:
    """Validate destination path and enforce explicit overwrite consent."""
    out_path = Path(path)
    if out_path.exists() and not overwrite:
        raise FileExistsError(
            "The destination file already exists and overwrite was not confirmed."
        )
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExportError("Unable to create the destination folder.") from exc
    return out_path


def export_single_json(
    record: ImageRecord,
    output_path: str | Path,
    overwrite: bool = False,
) -> Path:
    """Export single-image metadata to a formatted JSON file."""
    out_path = _validate_output_path(output_path, overwrite=overwrite)
    payload = record.to_export_dict()
    try:
        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except PermissionError as exc:
        raise ExportError("Permission denied writing the JSON export file.") from exc
    except OSError as exc:
        logger.warning("Failed to write JSON export: %s", type(exc).__name__)
        raise ExportError("Failed to write the JSON export file.") from exc
    return out_path


def export_single_csv(
    record: ImageRecord,
    output_path: str | Path,
    overwrite: bool = False,
) -> Path:
    """Export single-image metadata as readable Section/Field/Value CSV rows."""
    out_path = _validate_output_path(output_path, overwrite=overwrite)
    rows = record.to_flat_rows()
    try:
        with out_path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=["Section", "Field", "Value"])
            writer.writeheader()
            writer.writerows(rows)
    except PermissionError as exc:
        raise ExportError("Permission denied writing the CSV export file.") from exc
    except OSError as exc:
        logger.warning("Failed to write CSV export: %s", type(exc).__name__)
        raise ExportError("Failed to write the CSV export file.") from exc
    return out_path


def export_batch_json(
    items: list[BatchItem],
    summary: BatchSummary,
    output_path: str | Path,
    overwrite: bool = False,
) -> Path:
    """Export batch analysis summary and per-image records to JSON."""
    out_path = _validate_output_path(output_path, overwrite=overwrite)
    payload: dict[str, Any] = {
        "Summary": {
            "Total Images Scanned": summary.total_scanned,
            "Errors": summary.error_count,
            "Total Storage Size": format_file_size(summary.total_size_bytes),
            "Total Storage Size (Bytes)": summary.total_size_bytes,
            "Average Dimensions (px)": (
                f"{summary.avg_width} x {summary.avg_height}"
                if summary.total_scanned
                else "N/A"
            ),
            "Images With EXIF": summary.exif_count,
            "Images With GPS": summary.gps_count,
            "Format Distribution": dict(summary.format_distribution),
        },
        "Images": [item.to_export_dict() for item in items],
    }
    try:
        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except PermissionError as exc:
        raise ExportError("Permission denied writing the batch JSON export.") from exc
    except OSError as exc:
        logger.warning("Failed to write batch JSON export: %s", type(exc).__name__)
        raise ExportError("Failed to write the batch JSON export.") from exc
    return out_path


def export_batch_csv(
    items: list[BatchItem],
    output_path: str | Path,
    overwrite: bool = False,
) -> Path:
    """Export batch analysis image records to a tabular CSV file."""
    out_path = _validate_output_path(output_path, overwrite=overwrite)
    fieldnames = [
        "File Name",
        "File Location",
        "Format",
        "File Size",
        "File Size (Bytes)",
        "Width (px)",
        "Height (px)",
        "Aspect Ratio",
        "Camera Model",
        "Capture Date",
        "EXIF Available",
        "GPS Available",
    ]
    rows = [item.to_export_dict() for item in items]
    try:
        with out_path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except PermissionError as exc:
        raise ExportError("Permission denied writing the batch CSV export.") from exc
    except OSError as exc:
        logger.warning("Failed to write batch CSV export: %s", type(exc).__name__)
        raise ExportError("Failed to write the batch CSV export.") from exc
    return out_path


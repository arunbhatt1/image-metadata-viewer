"""Tests for JSON and CSV metadata export and overwrite protection."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.core.batch_processor import BatchProcessor
from app.core.exporter import (
    export_batch_csv,
    export_batch_json,
    export_single_csv,
    export_single_json,
)
from app.core.metadata_extractor import extract_image_record


def test_export_single_json_and_csv(jpeg_with_exif: Path, tmp_path: Path) -> None:
    record = extract_image_record(jpeg_with_exif, include_colors=True)

    json_out = tmp_path / "single.json"
    export_single_json(record, json_out)
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["File Information"]["File Name"] == "sample_exif.jpg"
    assert payload["EXIF Available"] is True
    assert payload["GPS Available"] is True
    assert payload["EXIF Metadata"]["Camera Information"]["Camera Model"] == "Model X100"
    assert "Color Analysis" in payload

    csv_out = tmp_path / "single.csv"
    export_single_csv(record, csv_out)
    with csv_out.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    fields = {r["Field"]: r["Value"] for r in rows}
    assert fields["File Name"] == "sample_exif.jpg"
    assert fields["ISO"] == "ISO 200"


def test_export_batch_json_and_csv(
    jpeg_with_exif: Path,
    png_no_exif: Path,
    tmp_path: Path,
) -> None:
    processor = BatchProcessor()
    result = processor.scan_files([jpeg_with_exif, png_no_exif])

    json_out = tmp_path / "batch.json"
    export_batch_json(result.items, result.summary, json_out)
    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["Summary"]["Total Images Scanned"] == 2
    assert len(data["Images"]) == 2

    csv_out = tmp_path / "batch.csv"
    export_batch_csv(result.items, csv_out)
    with csv_out.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert {r["File Name"] for r in rows} == {"sample_exif.jpg", "plain_graphic.png"}


def test_export_refuses_overwrite_without_confirmation(
    png_no_exif: Path,
    tmp_path: Path,
) -> None:
    record = extract_image_record(png_no_exif, include_colors=False)
    target = tmp_path / "existing.json"
    target.write_text("original", encoding="utf-8")

    with pytest.raises(FileExistsError):
        export_single_json(record, target, overwrite=False)
    assert target.read_text(encoding="utf-8") == "original"

    export_single_json(record, target, overwrite=True)
    assert "plain_graphic.png" in target.read_text(encoding="utf-8")


"""Tests for batch scanning, filtering, sorting, error isolation, and cancellation."""

from __future__ import annotations

from pathlib import Path

from app.core.batch_processor import (
    BatchProcessor,
    filter_batch_items,
    sort_batch_items,
)
from app.utils.file_utils import collect_image_files


def test_batch_scan_mixed_folder_and_summary(
    jpeg_with_exif: Path,
    png_no_exif: Path,
    corrupted_image: Path,
    unsupported_file: Path,
    tmp_path: Path,
) -> None:
    discovered = collect_image_files(tmp_path)
    assert unsupported_file not in discovered
    assert jpeg_with_exif in discovered
    assert png_no_exif in discovered
    assert corrupted_image in discovered

    processor = BatchProcessor()
    result = processor.scan_files(discovered)

    assert result.cancelled is False
    assert result.summary.total_scanned == 2
    assert result.summary.error_count == 1
    assert result.summary.exif_count == 1
    assert result.summary.gps_count == 1
    assert result.summary.format_distribution == {"JPEG": 1, "PNG": 1}
    assert result.summary.avg_width == 110
    assert result.summary.avg_height == 65


def test_batch_filtering_and_sorting(
    jpeg_with_exif: Path,
    png_no_exif: Path,
) -> None:
    processor = BatchProcessor()
    result = processor.scan_files([jpeg_with_exif, png_no_exif])

    only_png = filter_batch_items(result.items, format_filter="PNG")
    assert [i.file_name for i in only_png] == ["plain_graphic.png"]

    with_exif = filter_batch_items(result.items, exif_filter="With EXIF")
    assert [i.file_name for i in with_exif] == ["sample_exif.jpg"]

    without_gps = filter_batch_items(result.items, gps_filter="Without GPS")
    assert [i.file_name for i in without_gps] == ["plain_graphic.png"]

    sorted_by_width_desc = sort_batch_items(result.items, sort_key="width", ascending=False)
    assert [i.width for i in sorted_by_width_desc] == [120, 100]


def test_batch_empty_folder(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    assert collect_image_files(empty_dir) == []

    processor = BatchProcessor()
    result = processor.scan_folder(empty_dir)
    assert result.summary.total_scanned == 0
    assert result.items == []


def test_batch_cancellation(jpeg_with_exif: Path, png_no_exif: Path) -> None:
    processor = BatchProcessor()

    def progress_cb(current: int, _total: int, _name: str) -> None:
        if current == 1:
            processor.cancel()

    result = processor.scan_files([jpeg_with_exif, png_no_exif], progress_callback=progress_cb)
    assert result.cancelled is True
    assert len(result.items) == 1


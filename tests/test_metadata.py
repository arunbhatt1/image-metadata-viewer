"""Tests for image loading, property extraction, error handling, and read-only safety."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from app.core.image_loader import load_image_properties, load_preview_image
from app.core.metadata_extractor import extract_image_record
from app.utils.file_utils import ImageFileError


def test_load_image_properties_jpeg(jpeg_with_exif: Path) -> None:
    props = load_image_properties(jpeg_with_exif)
    assert props.file_name == "sample_exif.jpg"
    assert props.file_format == "JPEG"
    assert props.width == 120
    assert props.height == 80
    assert props.aspect_ratio == "3:2 (1.50:1)"
    assert props.color_mode == "RGB"
    assert props.file_size_bytes == jpeg_with_exif.stat().st_size
    assert "300" in props.resolution
    assert props.created_at is not None
    assert props.modified_at is not None


def test_load_image_properties_png_and_webp(tmp_path: Path, png_no_exif: Path) -> None:
    props_png = load_image_properties(png_no_exif)
    assert props_png.file_format == "PNG"
    assert props_png.width == 100
    assert props_png.height == 50
    assert props_png.aspect_ratio == "2:1 (2.00:1)"
    assert props_png.color_mode == "RGBA"

    webp_path = tmp_path / "sample.webp"
    Image.new("RGB", (64, 64), color=(10, 20, 30)).save(webp_path, format="WEBP")
    props_webp = load_image_properties(webp_path)
    assert props_webp.file_format == "WEBP"
    assert props_webp.width == 64
    assert props_webp.height == 64


def test_load_preview_image_scales_preserving_aspect(tmp_path: Path) -> None:
    wide_path = tmp_path / "wide.png"
    Image.new("RGB", (800, 400), color=(90, 90, 90)).save(wide_path)
    preview = load_preview_image(wide_path, max_size=200)
    assert preview.size == (200, 100)


def test_original_file_not_modified_during_extraction(jpeg_with_exif: Path) -> None:
    before_hash = hashlib.sha256(jpeg_with_exif.read_bytes()).hexdigest()
    record = extract_image_record(jpeg_with_exif, include_colors=True)
    _ = load_preview_image(jpeg_with_exif, max_size=120)
    after_hash = hashlib.sha256(jpeg_with_exif.read_bytes()).hexdigest()
    assert before_hash == after_hash
    assert record.properties.file_name == "sample_exif.jpg"


def test_corrupted_image_raises_friendly_error(corrupted_image: Path) -> None:
    with pytest.raises(ImageFileError):
        load_image_properties(corrupted_image)


def test_unsupported_extension_raises_friendly_error(unsupported_file: Path) -> None:
    with pytest.raises(ImageFileError, match="Unsupported file format"):
        load_image_properties(unsupported_file)


def test_missing_and_empty_files_raise_friendly_error(tmp_path: Path) -> None:
    with pytest.raises(ImageFileError, match="could not be found"):
        load_image_properties(tmp_path / "nonexistent.jpg")

    empty_jpg = tmp_path / "empty.jpg"
    empty_jpg.write_bytes(b"")
    with pytest.raises(ImageFileError, match="empty"):
        load_image_properties(empty_jpg)


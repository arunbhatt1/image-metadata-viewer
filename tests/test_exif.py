"""Tests for EXIF extraction, human-readable conversion, and missing EXIF handling."""

from __future__ import annotations

from pathlib import Path

from app.core.exif_parser import parse_exif


def test_parse_exif_extracts_all_sections(jpeg_with_exif: Path) -> None:
    exif = parse_exif(jpeg_with_exif)
    assert exif.has_exif is True
    assert exif.has_gps is True

    assert exif.get_value("Camera Manufacturer") == "TestCamCorp"
    assert exif.get_value("Camera Model") == "Model X100"
    assert exif.get_value("Lens Model") == "35mm f/1.8"
    assert exif.get_value("Software Used") == "TestFirmware 1.0"

    assert exif.get_value("ISO") == "ISO 200"
    assert exif.get_value("Aperture") == "f/2.8"
    assert exif.get_value("Shutter Speed") == "1/125 s"
    assert "35 mm" in exif.get_value("Focal Length")
    assert "52 mm equiv." in exif.get_value("Focal Length")
    assert exif.get_value("Flash Status") == "Did not fire"
    assert exif.get_value("Metering Mode") == "Pattern (Evaluative)"

    assert exif.get_value("Original Capture Date") == "2025-06-15 14:25:10"
    assert exif.get_value("Digitized Date") == "2025-06-15 14:25:10"
    assert exif.get_value("Metadata Modification Date") == "2025-06-15 14:30:00"

    assert "37.7749" in exif.get_value("GPS Latitude")
    assert "-122.4194" in exif.get_value("GPS Longitude")
    assert "42.5 m" in exif.get_value("Altitude")
    assert "2025-06-15" in exif.get_value("GPS Timestamp")

    assert exif.get_value("Orientation") == "Normal (Horizontal)"
    assert exif.get_value("Color Space") == "sRGB"
    assert exif.camera_model == "TestCamCorp Model X100"
    assert len(exif.raw_tags) > 0


def test_parse_exif_handles_missing_exif_gracefully(png_no_exif: Path) -> None:
    exif = parse_exif(png_no_exif)
    assert exif.has_exif is False
    assert exif.has_gps is False
    assert exif.entries == []
    assert exif.raw_tags == {}
    assert exif.camera_model == ""
    assert exif.capture_date == ""


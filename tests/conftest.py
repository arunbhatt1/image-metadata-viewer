"""Pytest fixtures generating synthetic test images without external dependencies."""

from __future__ import annotations

from pathlib import Path

import piexif
import pytest
from PIL import Image


def build_sample_exif_bytes() -> bytes:
    """Create synthetic EXIF bytes with camera, exposure, date, and GPS tags."""
    zeroth_ifd = {
        piexif.ImageIFD.Make: b"TestCamCorp",
        piexif.ImageIFD.Model: b"Model X100",
        piexif.ImageIFD.Software: b"TestFirmware 1.0",
        piexif.ImageIFD.DateTime: b"2025:06:15 14:30:00",
        piexif.ImageIFD.Orientation: 1,
    }
    exif_ifd = {
        piexif.ExifIFD.LensModel: b"35mm f/1.8",
        piexif.ExifIFD.ISOSpeedRatings: 200,
        piexif.ExifIFD.FNumber: (28, 10),
        piexif.ExifIFD.ExposureTime: (1, 125),
        piexif.ExifIFD.FocalLength: (35, 1),
        piexif.ExifIFD.FocalLengthIn35mmFilm: 52,
        piexif.ExifIFD.ExposureBiasValue: (1, 3),
        piexif.ExifIFD.Flash: 0,
        piexif.ExifIFD.MeteringMode: 5,
        piexif.ExifIFD.DateTimeOriginal: b"2025:06:15 14:25:10",
        piexif.ExifIFD.DateTimeDigitized: b"2025:06:15 14:25:10",
        piexif.ExifIFD.PixelXDimension: 120,
        piexif.ExifIFD.PixelYDimension: 80,
        piexif.ExifIFD.ColorSpace: 1,
    }
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((37, 1), (46, 1), (2988, 100)),
        piexif.GPSIFD.GPSLongitudeRef: b"W",
        piexif.GPSIFD.GPSLongitude: ((122, 1), (25, 1), (984, 100)),
        piexif.GPSIFD.GPSAltitudeRef: 0,
        piexif.GPSIFD.GPSAltitude: (425, 10),
        piexif.GPSIFD.GPSDateStamp: b"2025:06:15",
        piexif.GPSIFD.GPSTimeStamp: ((14, 1), (25, 1), (10, 1)),
    }
    return piexif.dump({"0th": zeroth_ifd, "Exif": exif_ifd, "GPS": gps_ifd})


@pytest.fixture
def jpeg_with_exif(tmp_path: Path) -> Path:
    """Create a synthetic 120x80 JPEG containing synthetic EXIF and GPS tags."""
    path = tmp_path / "sample_exif.jpg"
    img = Image.new("RGB", (120, 80), color=(70, 130, 110))
    img.save(path, format="JPEG", exif=build_sample_exif_bytes(), dpi=(300, 300))
    return path


@pytest.fixture
def png_no_exif(tmp_path: Path) -> Path:
    """Create a synthetic 100x50 PNG image with no EXIF data."""
    path = tmp_path / "plain_graphic.png"
    img = Image.new("RGBA", (100, 50), color=(200, 80, 60, 255))
    img.save(path, format="PNG")
    return path


@pytest.fixture
def tricolor_image(tmp_path: Path) -> Path:
    """Create a 90x30 PNG split evenly into red, green, and blue blocks."""
    path = tmp_path / "tricolor.png"
    img = Image.new("RGB", (90, 30))
    for x in range(90):
        color = (220, 20, 20) if x < 30 else ((20, 200, 20) if x < 60 else (20, 40, 220))
        for y in range(30):
            img.putpixel((x, y), color)
    img.save(path, format="PNG")
    return path


@pytest.fixture
def corrupted_image(tmp_path: Path) -> Path:
    """Create a corrupted JPEG file with invalid byte payload."""
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0not_a_real_jpeg_payload")
    return path


@pytest.fixture
def unsupported_file(tmp_path: Path) -> Path:
    """Create a plain text file with unsupported extension."""
    path = tmp_path / "notes.txt"
    path.write_text("just text", encoding="utf-8")
    return path


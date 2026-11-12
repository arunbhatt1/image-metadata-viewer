"""EXIF metadata extraction and human-readable translation using ExifRead and piexif."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import exifread
import piexif
from PIL import Image

from app.config import get_logger
from app.utils.file_utils import validate_image_path
from app.utils.formatters import format_exif_datetime, format_gps_coordinate

logger = get_logger("exif_parser")
logging.getLogger("exifread").setLevel(logging.ERROR)

SECTION_ORDER: tuple[str, ...] = (
    "Camera Information",
    "Exposure Information",
    "Date and Time",
    "Location Information",
    "Image Information",
)

_ORIENTATION_MAP: dict[int, str] = {
    1: "Normal (Horizontal)",
    2: "Mirrored Horizontal",
    3: "Rotated 180°",
    4: "Mirrored Vertical",
    5: "Mirrored Horizontal & Rotated 270° CW",
    6: "Rotated 90° CW",
    7: "Mirrored Horizontal & Rotated 90° CW",
    8: "Rotated 270° CW",
}

_METERING_MODE_MAP: dict[int, str] = {
    0: "Unknown",
    1: "Average",
    2: "Center-Weighted Average",
    3: "Spot",
    4: "Multi-Spot",
    5: "Pattern (Evaluative)",
    6: "Partial",
    255: "Other",
}

_COLOR_SPACE_MAP: dict[int, str] = {
    1: "sRGB",
    2: "Adobe RGB",
    65535: "Uncalibrated",
}

_COMPRESSION_MAP: dict[int, str] = {
    1: "Uncompressed",
    2: "CCITT 1D",
    3: "T4 / Group 3 Fax",
    4: "T6 / Group 4 Fax",
    5: "LZW",
    6: "JPEG (Old-style)",
    7: "JPEG",
    8: "Adobe Deflate",
    32773: "PackBits",
    32946: "Deflate",
}

_FLASH_MAP: dict[int, str] = {
    0x00: "Did not fire",
    0x01: "Fired",
    0x05: "Fired, return light not detected",
    0x07: "Fired, return light detected",
    0x08: "On, did not fire",
    0x09: "On, fired",
    0x0D: "On, return light not detected",
    0x0F: "On, return light detected",
    0x10: "Off, did not fire",
    0x14: "Off, did not fire, return not detected",
    0x18: "Auto, did not fire",
    0x19: "Auto, fired",
    0x1D: "Auto, fired, return not detected",
    0x1F: "Auto, fired, return detected",
    0x20: "No flash function",
    0x30: "Off, no flash function",
    0x41: "Fired, red-eye reduction",
    0x45: "Fired, red-eye reduction, return not detected",
    0x47: "Fired, red-eye reduction, return detected",
    0x49: "On, red-eye reduction",
    0x50: "Off, red-eye reduction",
    0x58: "Auto, did not fire, red-eye reduction",
    0x59: "Auto, fired, red-eye reduction",
}

# Binary/thumbnail tags omitted from raw tag display to keep the UI readable
_EXCLUDED_RAW_TAGS = {
    "JPEGThumbnail",
    "TIFFThumbnail",
    "EXIF MakerNote",
    "EXIF UserComment",
}


@dataclass(frozen=True)
class ExifEntry:
    """Single parsed EXIF field belonging to a logical section."""

    section: str
    label: str
    value: str
    raw_tag: str
    raw_value: str


@dataclass
class ExifData:
    """Structured EXIF metadata container for an image."""

    has_exif: bool = False
    has_gps: bool = False
    entries: list[ExifEntry] = field(default_factory=list)
    raw_tags: dict[str, str] = field(default_factory=dict)

    def get_value(self, label: str, default: str = "") -> str:
        """Return formatted value by human-readable label."""
        for entry in self.entries:
            if entry.label == label:
                return entry.value
        return default

    @property
    def camera_model(self) -> str:
        """Return camera model or manufacturer+model if available."""
        model = self.get_value("Camera Model")
        make = self.get_value("Camera Manufacturer")
        if model and make and not model.lower().startswith(make.lower()):
            return f"{make} {model}"
        return model or make

    @property
    def capture_date(self) -> str:
        """Return original capture date, or digitized/modified date fallback."""
        return (
            self.get_value("Original Capture Date")
            or self.get_value("Digitized Date")
            or self.get_value("Metadata Modification Date")
        )


def _ratio_to_float(item: Any) -> float | None:
    """Convert an ExifRead Ratio or piexif (num, den) tuple to float."""
    if item is None:
        return None
    if hasattr(item, "num") and hasattr(item, "den"):
        den = float(item.den)
        return float(item.num) / den if den != 0 else None
    if isinstance(item, (tuple, list)) and len(item) == 2:
        try:
            den = float(item[1])
            return float(item[0]) / den if den != 0 else None
        except (TypeError, ValueError):
            return None
    try:
        return float(item)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str:
    """Decode bytes or clean printable EXIF string values."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    return text.replace("\x00", "").strip()


def _tag_first_int(tag: Any) -> int | None:
    """Extract first integer from an ExifRead tag or scalar."""
    if tag is None:
        return None
    values = getattr(tag, "values", tag)
    if isinstance(values, (list, tuple)) and values:
        first = values[0]
        if hasattr(first, "num"):
            val = _ratio_to_float(first)
            return int(round(val)) if val is not None else None
        try:
            return int(first)
        except (TypeError, ValueError):
            return None
    try:
        return int(values)
    except (TypeError, ValueError):
        return None


def _tag_first_float(tag: Any) -> float | None:
    """Extract first float from an ExifRead tag or rational tuple."""
    if tag is None:
        return None
    values = getattr(tag, "values", tag)
    if isinstance(values, (list, tuple)) and values:
        # Handle direct (num, den) tuple from piexif
        if len(values) == 2 and all(isinstance(v, (int, float)) for v in values):
            return _ratio_to_float(values)
        return _ratio_to_float(values[0])
    return _ratio_to_float(values)


def _dms_to_decimal(values: Any, ref: str) -> float | None:
    """Convert EXIF DMS rational triplet + hemisphere reference to decimal degrees."""
    if not isinstance(values, (list, tuple)) or len(values) < 3:
        return None
    deg = _ratio_to_float(values[0])
    minutes = _ratio_to_float(values[1])
    seconds = _ratio_to_float(values[2])
    if deg is None or minutes is None or seconds is None:
        return None
    decimal = deg + (minutes / 60.0) + (seconds / 3600.0)
    if ref.upper() in ("S", "W"):
        decimal = -abs(decimal)
    return decimal


def _format_shutter_speed(seconds: float | None) -> str:
    """Format exposure duration cleanly (e.g. '1/125 s' or '2.5 s')."""
    if seconds is None or seconds <= 0:
        return ""
    if seconds < 1.0:
        denom = round(1.0 / seconds)
        if denom > 1:
            return f"1/{denom} s"
    if seconds.is_integer():
        return f"{int(seconds)} s"
    return f"{seconds:.2f}".rstrip("0").rstrip(".") + " s"


def _format_aperture(f_number: float | None) -> str:
    """Format f-number cleanly (e.g. 'f/2.8')."""
    if f_number is None or f_number <= 0:
        return ""
    if f_number.is_integer():
        return f"f/{int(f_number)}"
    return f"f/{f_number:.1f}"


def _format_exposure_bias(ev: float | None) -> str:
    """Format exposure compensation in EV."""
    if ev is None:
        return ""
    if abs(ev) < 0.01:
        return "0 EV"
    sign = "+" if ev > 0 else ""
    return f"{sign}{ev:.2f}".rstrip("0").rstrip(".") + " EV"


def _extract_piexif_fallback(file_path: Path) -> dict[str, Any]:
    """Use piexif/Pillow as a structured fallback for formats like PNG/WEBP EXIF chunks."""
    tags: dict[str, Any] = {}
    exif_bytes: bytes | None = None
    try:
        with Image.open(file_path) as img:
            raw = img.info.get("exif")
            if isinstance(raw, bytes) and raw:
                exif_bytes = raw
    except Exception:
        return tags

    if not exif_bytes:
        return tags

    try:
        exif_dict = piexif.load(exif_bytes)
    except Exception:
        return tags

    mapping: dict[tuple[str, int], str] = {
        ("0th", piexif.ImageIFD.Make): "Image Make",
        ("0th", piexif.ImageIFD.Model): "Image Model",
        ("0th", piexif.ImageIFD.Software): "Image Software",
        ("0th", piexif.ImageIFD.DateTime): "Image DateTime",
        ("0th", piexif.ImageIFD.Orientation): "Image Orientation",
        ("0th", piexif.ImageIFD.Compression): "Image Compression",
        ("Exif", piexif.ExifIFD.LensModel): "EXIF LensModel",
        ("Exif", piexif.ExifIFD.ISOSpeedRatings): "EXIF ISOSpeedRatings",
        ("Exif", piexif.ExifIFD.FNumber): "EXIF FNumber",
        ("Exif", piexif.ExifIFD.ExposureTime): "EXIF ExposureTime",
        ("Exif", piexif.ExifIFD.FocalLength): "EXIF FocalLength",
        ("Exif", piexif.ExifIFD.FocalLengthIn35mmFilm): "EXIF FocalLengthIn35mmFilm",
        ("Exif", piexif.ExifIFD.ExposureBiasValue): "EXIF ExposureBiasValue",
        ("Exif", piexif.ExifIFD.Flash): "EXIF Flash",
        ("Exif", piexif.ExifIFD.MeteringMode): "EXIF MeteringMode",
        ("Exif", piexif.ExifIFD.DateTimeOriginal): "EXIF DateTimeOriginal",
        ("Exif", piexif.ExifIFD.DateTimeDigitized): "EXIF DateTimeDigitized",
        ("Exif", piexif.ExifIFD.PixelXDimension): "EXIF ExifImageWidth",
        ("Exif", piexif.ExifIFD.PixelYDimension): "EXIF ExifImageLength",
        ("Exif", piexif.ExifIFD.ColorSpace): "EXIF ColorSpace",
        ("GPS", piexif.GPSIFD.GPSLatitude): "GPS GPSLatitude",
        ("GPS", piexif.GPSIFD.GPSLatitudeRef): "GPS GPSLatitudeRef",
        ("GPS", piexif.GPSIFD.GPSLongitude): "GPS GPSLongitude",
        ("GPS", piexif.GPSIFD.GPSLongitudeRef): "GPS GPSLongitudeRef",
        ("GPS", piexif.GPSIFD.GPSAltitude): "GPS GPSAltitude",
        ("GPS", piexif.GPSIFD.GPSAltitudeRef): "GPS GPSAltitudeRef",
        ("GPS", piexif.GPSIFD.GPSDateStamp): "GPS GPSDate",
        ("GPS", piexif.GPSIFD.GPSTimeStamp): "GPS GPSTimeStamp",
    }

    for (ifd_name, tag_id), unified_name in mapping.items():
        ifd = exif_dict.get(ifd_name)
        if isinstance(ifd, dict) and tag_id in ifd:
            tags[unified_name] = ifd[tag_id]

    return tags


def parse_exif(path: str | Path) -> ExifData:
    """Extract and normalize available EXIF metadata from an image file."""
    file_path = validate_image_path(path)
    raw_tags_obj: dict[str, Any] = {}

    try:
        with file_path.open("rb") as fh:
            raw_tags_obj = exifread.process_file(
                fh,
                details=True,
                extract_thumbnail=False,
            )
    except Exception as exc:
        logger.debug("ExifRead skipped or failed cleanly: %s", type(exc).__name__)
        raw_tags_obj = {}

    if not raw_tags_obj:
        raw_tags_obj = _extract_piexif_fallback(file_path)

    if not raw_tags_obj:
        return ExifData(has_exif=False, has_gps=False)

    # Build clean raw tag dictionary for inspection
    raw_tags: dict[str, str] = {}
    for key, val in raw_tags_obj.items():
        if key in _EXCLUDED_RAW_TAGS or "Thumbnail" in key or "MakerNote" in key:
            continue
        cleaned = _clean_text(getattr(val, "printable", val))
        if cleaned:
            raw_tags[key] = cleaned

    entries: list[ExifEntry] = []

    def add_entry(section: str, label: str, value: str, raw_tag: str) -> None:
        if not value:
            return
        raw_val = raw_tags.get(raw_tag, _clean_text(raw_tags_obj.get(raw_tag, value)))
        entries.append(
            ExifEntry(
                section=section,
                label=label,
                value=value,
                raw_tag=raw_tag,
                raw_value=raw_val,
            )
        )

    # 1. Camera Information
    add_entry("Camera Information", "Camera Manufacturer", raw_tags.get("Image Make", ""), "Image Make")
    add_entry("Camera Information", "Camera Model", raw_tags.get("Image Model", ""), "Image Model")
    add_entry("Camera Information", "Lens Model", raw_tags.get("EXIF LensModel", ""), "EXIF LensModel")
    add_entry("Camera Information", "Software Used", raw_tags.get("Image Software", ""), "Image Software")

    # 2. Exposure Information
    iso_tag = "EXIF ISOSpeedRatings" if "EXIF ISOSpeedRatings" in raw_tags_obj else "EXIF PhotographicSensitivity"
    if iso_tag in raw_tags_obj:
        iso_val = _tag_first_int(raw_tags_obj[iso_tag])
        if iso_val is not None:
            add_entry("Exposure Information", "ISO", f"ISO {iso_val}", iso_tag)

    if "EXIF FNumber" in raw_tags_obj:
        aperture = _format_aperture(_tag_first_float(raw_tags_obj["EXIF FNumber"]))
        add_entry("Exposure Information", "Aperture", aperture, "EXIF FNumber")
    elif "EXIF ApertureValue" in raw_tags_obj:
        apex_av = _tag_first_float(raw_tags_obj["EXIF ApertureValue"])
        if apex_av is not None:
            aperture = _format_aperture(2 ** (apex_av / 2.0))
            add_entry("Exposure Information", "Aperture", aperture, "EXIF ApertureValue")

    if "EXIF ExposureTime" in raw_tags_obj:
        shutter = _format_shutter_speed(_tag_first_float(raw_tags_obj["EXIF ExposureTime"]))
        add_entry("Exposure Information", "Shutter Speed", shutter, "EXIF ExposureTime")
    elif "EXIF ShutterSpeedValue" in raw_tags_obj:
        apex_tv = _tag_first_float(raw_tags_obj["EXIF ShutterSpeedValue"])
        if apex_tv is not None:
            shutter = _format_shutter_speed(2 ** (-apex_tv))
            add_entry("Exposure Information", "Shutter Speed", shutter, "EXIF ShutterSpeedValue")

    if "EXIF FocalLength" in raw_tags_obj:
        focal = _tag_first_float(raw_tags_obj["EXIF FocalLength"])
        if focal is not None and focal > 0:
            focal_str = f"{focal:g} mm"
            eq35 = _tag_first_int(raw_tags_obj.get("EXIF FocalLengthIn35mmFilm"))
            if eq35 and eq35 > 0:
                focal_str += f" ({eq35} mm equiv.)"
            add_entry("Exposure Information", "Focal Length", focal_str, "EXIF FocalLength")

    if "EXIF ExposureBiasValue" in raw_tags_obj:
        bias = _format_exposure_bias(_tag_first_float(raw_tags_obj["EXIF ExposureBiasValue"]))
        add_entry("Exposure Information", "Exposure Compensation", bias, "EXIF ExposureBiasValue")

    if "EXIF Flash" in raw_tags_obj:
        flash_code = _tag_first_int(raw_tags_obj["EXIF Flash"])
        if flash_code is not None:
            flash_text = _FLASH_MAP.get(flash_code)
            if flash_text is None:
                flash_text = "Fired" if (flash_code & 0x01) else "Did not fire"
            add_entry("Exposure Information", "Flash Status", flash_text, "EXIF Flash")

    if "EXIF MeteringMode" in raw_tags_obj:
        m_code = _tag_first_int(raw_tags_obj["EXIF MeteringMode"])
        if m_code is not None:
            m_text = _METERING_MODE_MAP.get(m_code, f"Mode {m_code}")
            add_entry("Exposure Information", "Metering Mode", m_text, "EXIF MeteringMode")

    # 3. Date and Time
    if "EXIF DateTimeOriginal" in raw_tags:
        add_entry(
            "Date and Time",
            "Original Capture Date",
            format_exif_datetime(raw_tags["EXIF DateTimeOriginal"]),
            "EXIF DateTimeOriginal",
        )
    if "EXIF DateTimeDigitized" in raw_tags:
        add_entry(
            "Date and Time",
            "Digitized Date",
            format_exif_datetime(raw_tags["EXIF DateTimeDigitized"]),
            "EXIF DateTimeDigitized",
        )
    if "Image DateTime" in raw_tags:
        add_entry(
            "Date and Time",
            "Metadata Modification Date",
            format_exif_datetime(raw_tags["Image DateTime"]),
            "Image DateTime",
        )

    # 4. Location Information
    has_gps = False
    lat_obj = raw_tags_obj.get("GPS GPSLatitude")
    lat_ref = _clean_text(getattr(raw_tags_obj.get("GPS GPSLatitudeRef"), "printable", raw_tags_obj.get("GPS GPSLatitudeRef", "N"))) or "N"
    lon_obj = raw_tags_obj.get("GPS GPSLongitude")
    lon_ref = _clean_text(getattr(raw_tags_obj.get("GPS GPSLongitudeRef"), "printable", raw_tags_obj.get("GPS GPSLongitudeRef", "E"))) or "E"

    if lat_obj is not None:
        lat_vals = getattr(lat_obj, "values", lat_obj)
        lat_dec = _dms_to_decimal(lat_vals, lat_ref)
        if lat_dec is not None:
            has_gps = True
            add_entry(
                "Location Information",
                "GPS Latitude",
                format_gps_coordinate(lat_dec, is_latitude=True),
                "GPS GPSLatitude",
            )

    if lon_obj is not None:
        lon_vals = getattr(lon_obj, "values", lon_obj)
        lon_dec = _dms_to_decimal(lon_vals, lon_ref)
        if lon_dec is not None:
            has_gps = True
            add_entry(
                "Location Information",
                "GPS Longitude",
                format_gps_coordinate(lon_dec, is_latitude=False),
                "GPS GPSLongitude",
            )

    if "GPS GPSAltitude" in raw_tags_obj:
        alt_val = _tag_first_float(raw_tags_obj["GPS GPSAltitude"])
        alt_ref = _tag_first_int(raw_tags_obj.get("GPS GPSAltitudeRef"))
        if alt_val is not None:
            has_gps = True
            ref_desc = "below sea level" if alt_ref == 1 else "above sea level"
            add_entry(
                "Location Information",
                "Altitude",
                f"{alt_val:.1f} m ({ref_desc})",
                "GPS GPSAltitude",
            )

    gps_date = raw_tags.get("GPS GPSDate", "")
    gps_time_obj = raw_tags_obj.get("GPS GPSTimeStamp")
    gps_time_str = ""
    if gps_time_obj is not None:
        t_vals = getattr(gps_time_obj, "values", gps_time_obj)
        if isinstance(t_vals, (list, tuple)) and len(t_vals) >= 3:
            hh = _ratio_to_float(t_vals[0])
            mm = _ratio_to_float(t_vals[1])
            ss = _ratio_to_float(t_vals[2])
            if hh is not None and mm is not None and ss is not None:
                gps_time_str = f"{int(hh):02d}:{int(mm):02d}:{ss:04.1f}".rstrip("0").rstrip(".") + " UTC"
                if "." not in gps_time_str:
                    gps_time_str = f"{int(hh):02d}:{int(mm):02d}:{int(round(ss)):02d} UTC"

    if gps_date or gps_time_str:
        has_gps = True
        combined_ts = " ".join(part for part in (format_exif_datetime(gps_date), gps_time_str) if part)
        raw_ts_key = "GPS GPSTimeStamp" if gps_time_str else "GPS GPSDate"
        add_entry("Location Information", "GPS Timestamp", combined_ts, raw_ts_key)

    # 5. Image Information
    if "Image Orientation" in raw_tags_obj:
        ori_code = _tag_first_int(raw_tags_obj["Image Orientation"])
        if ori_code is not None:
            add_entry(
                "Image Information",
                "Orientation",
                _ORIENTATION_MAP.get(ori_code, f"Orientation {ori_code}"),
                "Image Orientation",
            )

    exif_w = _tag_first_int(raw_tags_obj.get("EXIF ExifImageWidth"))
    exif_h = _tag_first_int(raw_tags_obj.get("EXIF ExifImageLength"))
    if exif_w and exif_h:
        add_entry(
            "Image Information",
            "EXIF Image Dimensions",
            f"{exif_w:,} x {exif_h:,} px",
            "EXIF ExifImageWidth",
        )

    if "EXIF ColorSpace" in raw_tags_obj:
        cs_code = _tag_first_int(raw_tags_obj["EXIF ColorSpace"])
        if cs_code is not None:
            add_entry(
                "Image Information",
                "Color Space",
                _COLOR_SPACE_MAP.get(cs_code, f"Color Space {cs_code}"),
                "EXIF ColorSpace",
            )

    comp_key = "Image Compression" if "Image Compression" in raw_tags_obj else "Thumbnail Compression"
    if comp_key in raw_tags_obj:
        comp_code = _tag_first_int(raw_tags_obj[comp_key])
        if comp_code is not None:
            add_entry(
                "Image Information",
                "Compression",
                _COMPRESSION_MAP.get(comp_code, f"Compression {comp_code}"),
                comp_key,
            )

    has_exif = bool(entries or raw_tags)
    return ExifData(
        has_exif=has_exif,
        has_gps=has_gps,
        entries=entries,
        raw_tags=raw_tags,
    )

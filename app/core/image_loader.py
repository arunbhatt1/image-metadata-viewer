"""Read-only image loading and basic file/image property extraction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_logger, is_heif_supported
from app.utils.file_utils import ImageFileError, get_file_timestamps, validate_image_path
from app.utils.formatters import format_aspect_ratio

logger = get_logger("image_loader")

_HEIF_REGISTERED = False


def _ensure_heif_registered() -> None:
    """Register pillow-heif opener once when available."""
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    if is_heif_supported():
        try:
            import pillow_heif  # type: ignore

            pillow_heif.register_heif_opener()
            _HEIF_REGISTERED = True
        except Exception as exc:
            logger.warning("Optional HEIF decoder could not be initialized: %s", type(exc).__name__)


@dataclass(frozen=True)
class ImageProperties:
    """Basic file and pixel properties for an image."""

    file_path: Path
    file_name: str
    file_location: str
    file_format: str
    file_size_bytes: int
    width: int
    height: int
    aspect_ratio: str
    color_mode: str
    resolution: str
    created_at: datetime | None
    modified_at: datetime | None


def _extract_resolution(img: Image.Image) -> str:
    """Extract DPI/PPI resolution from image info when present."""
    dpi = img.info.get("dpi")
    if isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
        try:
            x_dpi = float(dpi[0])
            y_dpi = float(dpi[1])
            if x_dpi > 0 and y_dpi > 0:
                if abs(x_dpi - y_dpi) < 0.01:
                    return f"{x_dpi:g} DPI"
                return f"{x_dpi:g} x {y_dpi:g} DPI"
        except (TypeError, ValueError):
            pass

    density = img.info.get("jfif_density")
    unit = img.info.get("jfif_unit")
    if isinstance(density, (tuple, list)) and len(density) >= 2 and unit in (1, 2):
        try:
            x_val, y_val = float(density[0]), float(density[1])
            if x_val > 0 and y_val > 0:
                unit_label = "DPI" if unit == 1 else "DPCM"
                if abs(x_val - y_val) < 0.01:
                    return f"{x_val:g} {unit_label}"
                return f"{x_val:g} x {y_val:g} {unit_label}"
        except (TypeError, ValueError):
            pass

    return "Unavailable"


def load_image_properties(path: str | Path) -> ImageProperties:
    """Load non-destructive image properties from disk."""
    _ensure_heif_registered()
    file_path = validate_image_path(path)
    file_size = file_path.stat().st_size
    created_at, modified_at = get_file_timestamps(file_path)

    try:
        with Image.open(file_path) as img:
            width, height = img.size
            if width <= 0 or height <= 0:
                raise ImageFileError("The image has invalid dimensions.")
            img_format = (img.format or file_path.suffix.lstrip(".") or "Unknown").upper()
            color_mode = img.mode or "Unknown"
            resolution = _extract_resolution(img)
    except ImageFileError:
        raise
    except Image.DecompressionBombError as exc:
        logger.warning("Image exceeded decompression pixel limit: %s", type(exc).__name__)
        raise ImageFileError(
            "This image is too large to safely decode in memory."
        ) from exc
    except UnidentifiedImageError as exc:
        logger.warning("Unidentified image format encountered.")
        raise ImageFileError(
            "The file could not be decoded as a valid image. It may be corrupted or unsupported."
        ) from exc
    except PermissionError as exc:
        logger.warning("Permission denied opening image file.")
        raise ImageFileError("Permission denied while opening the image file.") from exc
    except OSError as exc:
        logger.warning("OS error opening image file: %s", type(exc).__name__)
        raise ImageFileError(
            "Unable to read the image file. The file may be corrupted or locked."
        ) from exc

    return ImageProperties(
        file_path=file_path,
        file_name=file_path.name,
        file_location=str(file_path.parent),
        file_format=img_format,
        file_size_bytes=file_size,
        width=width,
        height=height,
        aspect_ratio=format_aspect_ratio(width, height),
        color_mode=color_mode,
        resolution=resolution,
        created_at=created_at,
        modified_at=modified_at,
    )


def load_preview_image(path: str | Path, max_size: int = 440) -> Image.Image:
    """Load a resized, orientation-corrected in-memory copy for UI display."""
    _ensure_heif_registered()
    file_path = validate_image_path(path)

    try:
        with Image.open(file_path) as img:
            # Handle animated GIFs by taking the first frame cleanly
            if getattr(img, "is_animated", False):
                img.seek(0)

            working = ImageOps.exif_transpose(img)
            if working.mode not in ("RGB", "RGBA"):
                if "A" in working.getbands() or working.mode in ("P", "LA", "PA"):
                    working = working.convert("RGBA")
                else:
                    working = working.convert("RGB")
            else:
                working = working.copy()

            working.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            return working
    except Image.DecompressionBombError as exc:
        raise ImageFileError("The image is too large to render a preview.") from exc
    except UnidentifiedImageError as exc:
        raise ImageFileError("The image could not be decoded for preview.") from exc
    except OSError as exc:
        raise ImageFileError("Unable to load image preview.") from exc


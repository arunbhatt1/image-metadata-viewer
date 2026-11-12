"""Local image color analysis using Pillow, NumPy, and OpenCV."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.image_loader import _ensure_heif_registered
from app.utils.file_utils import ImageFileError, validate_image_path


@dataclass(frozen=True)
class DominantColor:
    """Single dominant color cluster with RGB, HEX, and pixel share."""

    rgb: tuple[int, int, int]
    hex_code: str
    percentage: float


@dataclass(frozen=True)
class ColorAnalysis:
    """Summary of an image's color profile."""

    average_rgb: tuple[int, int, int]
    average_hex: str
    dominant_colors: list[DominantColor]
    channel_distribution: dict[str, float]


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert an (R, G, B) tuple to uppercase HEX notation."""
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def analyze_colors(path: str | Path, num_colors: int = 5) -> ColorAnalysis:
    """Compute average color, channel distribution, and dominant swatches locally."""
    _ensure_heif_registered()
    file_path = validate_image_path(path)

    try:
        with Image.open(file_path) as img:
            if getattr(img, "is_animated", False):
                img.seek(0)
            working = ImageOps.exif_transpose(img).convert("RGB")
            working.thumbnail((160, 160), Image.Resampling.BILINEAR)
            rgb_array = np.asarray(working, dtype=np.uint8)
    except Image.DecompressionBombError as exc:
        raise ImageFileError("Image exceeds safe size limit for color analysis.") from exc
    except UnidentifiedImageError as exc:
        raise ImageFileError("Unable to decode image for color analysis.") from exc
    except OSError as exc:
        raise ImageFileError("Unable to read image for color analysis.") from exc

    pixels = rgb_array.reshape(-1, 3)
    if pixels.size == 0:
        raise ImageFileError("Image contains no pixel data.")

    # Average RGB and HEX
    mean_rgb_float = pixels.mean(axis=0)
    avg_rgb = (
        int(round(float(mean_rgb_float[0]))),
        int(round(float(mean_rgb_float[1]))),
        int(round(float(mean_rgb_float[2]))),
    )
    avg_hex = rgb_to_hex(avg_rgb)

    # Channel distribution (relative share of R, G, B energy)
    total_energy = float(mean_rgb_float.sum())
    if total_energy > 0:
        r_pct = (float(mean_rgb_float[0]) / total_energy) * 100.0
        g_pct = (float(mean_rgb_float[1]) / total_energy) * 100.0
        b_pct = (float(mean_rgb_float[2]) / total_energy) * 100.0
    else:
        r_pct = g_pct = b_pct = 33.3

    channel_distribution = {
        "Red": round(r_pct, 1),
        "Green": round(g_pct, 1),
        "Blue": round(b_pct, 1),
    }

    # Dominant colors via OpenCV k-means clustering
    unique_colors = np.unique(pixels, axis=0)
    k = max(1, min(num_colors, len(unique_colors)))

    if k == 1:
        c = tuple(int(v) for v in unique_colors[0])
        dominant = [DominantColor(rgb=c, hex_code=rgb_to_hex(c), percentage=100.0)]
    else:
        samples = np.float32(pixels)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(
            samples, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS
        )
        counts = np.bincount(labels.flatten(), minlength=k)
        total_pixels = float(len(pixels))

        clusters: list[DominantColor] = []
        for idx in np.argsort(-counts):
            count = int(counts[idx])
            if count == 0:
                continue
            center = centers[idx]
            rgb = (
                int(round(float(center[0]))),
                int(round(float(center[1]))),
                int(round(float(center[2]))),
            )
            pct = round((count / total_pixels) * 100.0, 1)
            clusters.append(
                DominantColor(rgb=rgb, hex_code=rgb_to_hex(rgb), percentage=pct)
            )
        dominant = clusters

    return ColorAnalysis(
        average_rgb=avg_rgb,
        average_hex=avg_hex,
        dominant_colors=dominant,
        channel_distribution=channel_distribution,
    )


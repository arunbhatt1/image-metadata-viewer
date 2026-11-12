"""Unified metadata extraction orchestrator combining properties, EXIF, and colors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.color_analyzer import ColorAnalysis, analyze_colors
from app.core.exif_parser import ExifData, parse_exif
from app.core.image_loader import ImageProperties, load_image_properties
from app.utils.formatters import format_datetime, format_file_size


@dataclass
class ImageRecord:
    """Complete local analysis result for a single image."""

    properties: ImageProperties
    exif: ExifData
    colors: ColorAnalysis | None = None

    def to_export_dict(self) -> dict[str, Any]:
        """Build a readable, structured dictionary suitable for JSON export."""
        props = self.properties
        data: dict[str, Any] = {
            "File Information": {
                "File Name": props.file_name,
                "File Location": props.file_location,
                "File Format": props.file_format,
                "File Size Bytes": props.file_size_bytes,
                "File Size": format_file_size(props.file_size_bytes),
                "Width (px)": props.width,
                "Height (px)": props.height,
                "Aspect Ratio": props.aspect_ratio,
                "Color Mode": props.color_mode,
                "Resolution": props.resolution,
                "Created At": format_datetime(props.created_at),
                "Modified At": format_datetime(props.modified_at),
            },
            "EXIF Available": self.exif.has_exif,
            "GPS Available": self.exif.has_gps,
            "EXIF Metadata": {},
        }

        if self.exif.entries:
            grouped: dict[str, dict[str, str]] = {}
            for entry in self.exif.entries:
                grouped.setdefault(entry.section, {})[entry.label] = entry.value
            data["EXIF Metadata"] = grouped

        if self.exif.raw_tags:
            data["Raw EXIF Tags"] = dict(self.exif.raw_tags)

        if self.colors is not None:
            data["Color Analysis"] = {
                "Average RGB": list(self.colors.average_rgb),
                "Average HEX": self.colors.average_hex,
                "Channel Distribution (%)": dict(self.colors.channel_distribution),
                "Dominant Colors": [
                    {
                        "HEX": swatch.hex_code,
                        "RGB": list(swatch.rgb),
                        "Share (%)": swatch.percentage,
                    }
                    for swatch in self.colors.dominant_colors
                ],
            }

        return data

    def to_flat_rows(self) -> list[dict[str, str]]:
        """Build flat readable key-value rows suitable for single-image CSV export."""
        props = self.properties
        rows: list[dict[str, str]] = [
            {"Section": "File Information", "Field": "File Name", "Value": props.file_name},
            {"Section": "File Information", "Field": "File Location", "Value": props.file_location},
            {"Section": "File Information", "Field": "File Format", "Value": props.file_format},
            {"Section": "File Information", "Field": "File Size", "Value": format_file_size(props.file_size_bytes)},
            {"Section": "File Information", "Field": "File Size (Bytes)", "Value": str(props.file_size_bytes)},
            {"Section": "File Information", "Field": "Width (px)", "Value": str(props.width)},
            {"Section": "File Information", "Field": "Height (px)", "Value": str(props.height)},
            {"Section": "File Information", "Field": "Aspect Ratio", "Value": props.aspect_ratio},
            {"Section": "File Information", "Field": "Color Mode", "Value": props.color_mode},
            {"Section": "File Information", "Field": "Resolution", "Value": props.resolution},
            {"Section": "File Information", "Field": "Created At", "Value": format_datetime(props.created_at)},
            {"Section": "File Information", "Field": "Modified At", "Value": format_datetime(props.modified_at)},
            {"Section": "EXIF Summary", "Field": "EXIF Available", "Value": "Yes" if self.exif.has_exif else "No"},
            {"Section": "EXIF Summary", "Field": "GPS Available", "Value": "Yes" if self.exif.has_gps else "No"},
        ]

        for entry in self.exif.entries:
            rows.append(
                {
                    "Section": entry.section,
                    "Field": entry.label,
                    "Value": entry.value,
                }
            )

        if self.colors is not None:
            rows.append(
                {
                    "Section": "Color Analysis",
                    "Field": "Average HEX",
                    "Value": self.colors.average_hex,
                }
            )
            rows.append(
                {
                    "Section": "Color Analysis",
                    "Field": "Average RGB",
                    "Value": f"rgb{self.colors.average_rgb}",
                }
            )
            for idx, swatch in enumerate(self.colors.dominant_colors, start=1):
                rows.append(
                    {
                        "Section": "Color Analysis",
                        "Field": f"Dominant Color {idx}",
                        "Value": f"{swatch.hex_code} ({swatch.percentage}%)",
                    }
                )

        return rows


def extract_image_record(
    path: str | Path,
    include_colors: bool = True,
) -> ImageRecord:
    """Extract properties, EXIF metadata, and optional color analysis for an image."""
    props = load_image_properties(path)
    exif = parse_exif(props.file_path)
    colors = analyze_colors(props.file_path) if include_colors else None
    return ImageRecord(properties=props, exif=exif, colors=colors)


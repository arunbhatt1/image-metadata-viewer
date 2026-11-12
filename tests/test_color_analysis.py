"""Tests for local color analysis (average RGB/HEX, distribution, dominant swatches)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.core.color_analyzer import analyze_colors, rgb_to_hex


def test_rgb_to_hex_conversion() -> None:
    assert rgb_to_hex((85, 124, 112)) == "#557C70"
    assert rgb_to_hex((0, 255, 16)) == "#00FF10"


def test_analyze_colors_solid_image(tmp_path: Path) -> None:
    solid_path = tmp_path / "solid.png"
    Image.new("RGB", (40, 40), color=(80, 120, 160)).save(solid_path)

    analysis = analyze_colors(solid_path)
    assert analysis.average_rgb == (80, 120, 160)
    assert analysis.average_hex == "#5078A0"
    assert len(analysis.dominant_colors) == 1
    assert analysis.dominant_colors[0].hex_code == "#5078A0"
    assert analysis.dominant_colors[0].percentage == 100.0
    assert abs(sum(analysis.channel_distribution.values()) - 100.0) <= 0.3


def test_analyze_colors_tricolor_image(tricolor_image: Path) -> None:
    analysis = analyze_colors(tricolor_image, num_colors=5)
    assert len(analysis.dominant_colors) == 3
    total_pct = sum(c.percentage for c in analysis.dominant_colors)
    assert 99.0 <= total_pct <= 101.0
    assert set(analysis.channel_distribution.keys()) == {"Red", "Green", "Blue"}


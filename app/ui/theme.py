"""Centralized design tokens: colors, bundled typography, spacing, and radii."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

import customtkinter as ctk

from app.config import ThemeMode

# ---------------------------------------------------------------------------
# Color Tokens (single source of truth for Light & Dark themes)
# ---------------------------------------------------------------------------

DARK_TOKENS: dict[str, str] = {
    "bg_main": "#0E0F11",
    "bg_sidebar": "#131417",
    "bg_surface": "#1A1B1F",
    "bg_surface_alt": "#141519",
    "bg_hover": "#212329",
    "bg_selected": "#23252C",
    "bg_diff": "#221C11",
    "bg_notice": "#191713",
    "bg_danger": "#221617",
    "border": "#2A2C31",
    "border_hover": "#454852",
    "border_strong": "#353840",
    "text_primary": "#E8E9EB",
    "text_secondary": "#8B8E96",
    "text_muted": "#5C5F66",
    "accent": "#FFB020",
    "accent_hover": "#FFC14D",
    "accent_pressed": "#E09610",
    "accent_text": "#0E0F11",
    "accent_subtle": "#292214",
}

LIGHT_TOKENS: dict[str, str] = {
    "bg_main": "#F7F7F5",
    "bg_sidebar": "#EFEFEC",
    "bg_surface": "#FFFFFF",
    "bg_surface_alt": "#F2F2EF",
    "bg_hover": "#EAEAE5",
    "bg_selected": "#ECECE6",
    "bg_diff": "#FDF5E4",
    "bg_notice": "#FBF5E8",
    "bg_danger": "#F9ECEB",
    "border": "#DADAD6",
    "border_hover": "#9D9E99",
    "border_strong": "#C4C4BF",
    "text_primary": "#111214",
    "text_secondary": "#5C5F66",
    "text_muted": "#8B8E96",
    "accent": "#E69500",
    "accent_hover": "#CC8400",
    "accent_pressed": "#B37300",
    "accent_text": "#111214",
    "accent_subtle": "#F8EBD2",
}

# ---------------------------------------------------------------------------
# Shape & Spacing Tokens (4px grid)
# ---------------------------------------------------------------------------

RADIUS_SM = 4
RADIUS_MD = 5
RADIUS_LG = 6

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24

# ---------------------------------------------------------------------------
# Bundled Font Loading & Detection
# ---------------------------------------------------------------------------

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONTS_REGISTERED = False


def register_bundled_fonts() -> None:
    """Register bundled offline TTF fonts in-process on Windows."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    _FONTS_REGISTERED = True

    if sys.platform != "win32" or not FONTS_DIR.exists():
        return

    fr_private = 0x10
    try:
        add_font = ctypes.windll.gdi32.AddFontResourceExW
        for ttf in sorted(FONTS_DIR.glob("*.ttf")):
            add_font(str(ttf.resolve()), fr_private, 0)
    except Exception:
        pass


def _pick_font(candidates: tuple[str, ...], fallback: str) -> str:
    try:
        available = set(tkfont.families())
        for name in candidates:
            if name in available:
                return name
    except tk.TclError:
        pass
    return fallback


class ThemeManager:
    """Centralized typography, spacing, and color token provider."""

    def __init__(self, mode: ThemeMode = "dark") -> None:
        self.mode: ThemeMode = mode
        self.ui_font: str = "Segoe UI"
        self.ui_medium_font: str = "Segoe UI"
        self.ui_semibold_font: str = "Segoe UI"
        self.mono_font: str = "Consolas"
        self.mono_medium_font: str = "Consolas"
        self._fonts_initialized = False

    def initialize(self, _root: tk.Misc) -> None:
        """Register bundled fonts, resolve font families, and apply theme."""
        register_bundled_fonts()
        self.ui_font = _pick_font(("Geist", "Inter Tight", "Segoe UI", "Arial"), "Segoe UI")
        self.ui_medium_font = _pick_font(("Geist Medium", self.ui_font), self.ui_font)
        self.ui_semibold_font = _pick_font(("Geist SemiBold", self.ui_font), self.ui_font)
        self.mono_font = _pick_font(
            ("Geist Mono", "JetBrains Mono", "Cascadia Mono", "Consolas", "Courier New"),
            "Consolas",
        )
        self.mono_medium_font = _pick_font(("Geist Mono SemiBold", "Geist Mono Medium", self.mono_font), self.mono_font)
        self._fonts_initialized = True
        self.apply_mode(self.mode)

    def apply_mode(self, mode: ThemeMode) -> None:
        """Switch CustomTkinter appearance mode ('dark', 'light', 'system')."""
        self.mode = mode
        ctk.set_appearance_mode(mode)

    def is_dark(self) -> bool:
        """Return True if the effective resolved appearance is dark."""
        resolved = ctk.get_appearance_mode()
        return str(resolved).lower() == "dark"

    def color(self, key: str) -> str:
        """Return concrete hex color for the active resolved theme."""
        tokens = DARK_TOKENS if self.is_dark() else LIGHT_TOKENS
        return tokens[key]

    def pair(self, key: str) -> tuple[str, str]:
        """Return (light_hex, dark_hex) pair for CustomTkinter adaptive widgets."""
        return (LIGHT_TOKENS[key], DARK_TOKENS[key])

    def font(self, role: str = "body", weight: str = "normal") -> ctk.CTkFont:
        """Create a CTkFont adhering to the precision-instrument typography scale."""
        if role == "page_title":
            family = self.ui_semibold_font
            w = "normal" if "SemiBold" in family else "bold"
            return ctk.CTkFont(family=family, size=22, weight=w)

        if role == "section_heading":
            family = self.ui_semibold_font
            w = "normal" if "SemiBold" in family else "bold"
            return ctk.CTkFont(family=family, size=13, weight=w)

        if role == "label":
            family = self.ui_medium_font
            w = "normal" if ("Medium" in family or weight == "normal") else "bold"
            return ctk.CTkFont(family=family, size=11, weight=w)

        if role == "secondary":
            return ctk.CTkFont(family=self.ui_font, size=12, weight=weight)

        if role == "mono":
            family = self.mono_medium_font if weight == "bold" else self.mono_font
            w = "normal" if ("Medium" in family or "SemiBold" in family or weight == "normal") else "bold"
            return ctk.CTkFont(family=family, size=12, weight=w)

        if role == "mono_sm":
            return ctk.CTkFont(family=self.mono_font, size=11, weight=weight)

        # Default body
        family = self.ui_medium_font if weight == "bold" else self.ui_font
        w = "normal" if ("Medium" in family or weight == "normal") else "bold"
        return ctk.CTkFont(family=family, size=13, weight=w)

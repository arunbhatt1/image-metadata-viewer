"""Left navigation sidebar with precision 2px amber bar and tight 32px rows."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from app.config import APP_VERSION
from app.ui.theme import RADIUS_SM, SPACE_2, SPACE_3, SPACE_4, SPACE_5, ThemeManager

NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("inspector", "Image Inspector"),
    ("exif", "EXIF Viewer"),
    ("batch", "Batch Analysis"),
    ("compare", "Compare Images"),
    ("settings", "Settings"),
)


class Sidebar(ctk.CTkFrame):
    """Compact fixed-width navigation rail without tinted active backgrounds."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        on_navigate: Callable[[str], None],
    ) -> None:
        super().__init__(
            master,
            width=204,
            fg_color=theme.pair("bg_sidebar"),
            corner_radius=0,
        )
        self.pack_propagate(False)
        self.theme = theme
        self.on_navigate = on_navigate
        self.active_key = "inspector"

        self._rows: dict[str, ctk.CTkFrame] = {}
        self._indicators: dict[str, tk.Frame] = {}
        self._buttons: dict[str, ctk.CTkButton] = {}

        # 1px hairline right border
        ctk.CTkFrame(
            self,
            width=1,
            fg_color=theme.pair("border"),
            corner_radius=0,
        ).pack(side="right", fill="y")

        # App identity block
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.pack(fill="x", padx=SPACE_4, pady=(SPACE_5, SPACE_4))

        ctk.CTkLabel(
            brand,
            text="IMAGE METADATA",
            font=theme.font("label"),
            text_color=theme.pair("text_primary"),
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            brand,
            text=f"VIEWER // v{APP_VERSION}",
            font=theme.font("mono_sm"),
            text_color=theme.pair("text_muted"),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        ctk.CTkFrame(
            self,
            height=1,
            fg_color=theme.pair("border"),
            corner_radius=0,
        ).pack(fill="x", padx=SPACE_4, pady=(0, SPACE_3))

        # Navigation items (32px height, no tinted active background)
        nav_container = ctk.CTkFrame(self, fg_color="transparent")
        nav_container.pack(fill="x", padx=SPACE_2)

        for key, label in NAV_ITEMS:
            row = ctk.CTkFrame(
                nav_container,
                fg_color="transparent",
                corner_radius=RADIUS_SM,
                height=32,
            )
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            indicator = tk.Frame(
                row,
                width=2,
                height=16,
                bd=0,
                highlightthickness=0,
                background=theme.color("bg_sidebar"),
            )
            indicator.pack(side="left", padx=(2, 6), pady=8)
            indicator.pack_propagate(False)

            btn = ctk.CTkButton(
                row,
                text=label,
                anchor="w",
                height=30,
                corner_radius=RADIUS_SM,
                font=theme.font("body"),
                fg_color="transparent",
                hover_color=theme.pair("bg_hover"),
                text_color=theme.pair("text_secondary"),
                command=lambda k=key: self._handle_click(k),
            )
            btn.pack(side="left", fill="both", expand=True)

            self._rows[key] = row
            self._indicators[key] = indicator
            self._buttons[key] = btn

        # Bottom local privacy indicator
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=SPACE_4, pady=SPACE_4)

        ctk.CTkFrame(
            footer,
            height=1,
            fg_color=theme.pair("border"),
            corner_radius=0,
        ).pack(fill="x", pady=(0, SPACE_2))

        ctk.CTkLabel(
            footer,
            text="LOCAL ENGINE",
            font=theme.font("label"),
            text_color=theme.pair("text_secondary"),
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            footer,
            text="Read-only inspection. Zero telemetry or uploads.",
            font=theme.font("secondary"),
            text_color=theme.pair("text_muted"),
            justify="left",
            wraplength=168,
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        self.set_active("inspector")

    def _handle_click(self, key: str) -> None:
        self.set_active(key)
        self.on_navigate(key)

    def refresh_theme(self) -> None:
        """Re-apply active/inactive indicator colors after a theme switch."""
        self.set_active(self.active_key)

    def set_active(self, key: str) -> None:
        """Highlight active item with 2px amber left bar and primary text only."""
        self.active_key = key
        inactive_bg = self.theme.color("bg_sidebar")
        active_bg = self.theme.color("accent")
        for item_key, row in self._rows.items():
            is_active = item_key == key
            row.configure(fg_color="transparent")
            self._indicators[item_key].configure(
                background=active_bg if is_active else inactive_bg
            )
            self._buttons[item_key].configure(
                font=self.theme.font("body", weight="bold" if is_active else "normal"),
                fg_color="transparent",
                hover_color=self.theme.pair("bg_hover"),
                text_color=(
                    self.theme.pair("text_primary")
                    if is_active
                    else self.theme.pair("text_secondary")
                ),
            )

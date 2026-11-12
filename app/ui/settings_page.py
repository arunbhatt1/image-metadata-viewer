"""Settings page: theme toggle, export defaults, preview size, and session controls."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from app.config import ConfigManager, ExportFormat, PreviewSize, ThemeMode, is_heif_supported
from app.ui.components import NoticeBanner, SurfaceCard, make_secondary_button
from app.ui.theme import (
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_6,
    ThemeManager,
)


class SegmentedControl(ctk.CTkFrame):
    """Precision segmented pill bar with solid amber active button and near-black text."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        values: list[str],
        initial: str,
        command: Callable[[str], None],
    ) -> None:
        super().__init__(
            master,
            fg_color=theme.pair("bg_surface_alt"),
            border_color=theme.pair("border"),
            border_width=1,
            corner_radius=RADIUS_SM,
        )
        self.theme = theme
        self.command = command
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._current = initial

        for idx, val in enumerate(values):
            btn = ctk.CTkButton(
                self,
                text=val,
                height=26,
                width=68,
                corner_radius=3,
                font=theme.font("mono_sm"),
                command=lambda v=val: self._select(v),
            )
            btn.pack(side="left", padx=(2 if idx == 0 else 1, 2 if idx == len(values) - 1 else 1), pady=2)
            self._buttons[val] = btn

        self.set(initial)

    def _select(self, val: str) -> None:
        self.set(val)
        self.command(val)

    def set(self, val: str) -> None:
        self._current = val
        for key, btn in self._buttons.items():
            active = key == val
            btn.configure(
                fg_color=self.theme.pair("accent") if active else "transparent",
                hover_color=self.theme.pair("accent_hover") if active else self.theme.pair("bg_hover"),
                text_color=self.theme.pair("accent_text") if active else self.theme.pair("text_secondary"),
                font=self.theme.font("mono_sm", weight="bold" if active else "normal"),
            )


class SettingsPage(ctk.CTkFrame):
    """Application preferences and local privacy/session management page."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        config_manager: ConfigManager,
        on_theme_changed: Callable[[ThemeMode], None],
        on_preview_size_changed: Callable[[PreviewSize], None],
        on_clear_session: Callable[[], None],
        on_status: Callable[[str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.theme = theme
        self.config_manager = config_manager
        self.on_theme_changed = on_theme_changed
        self.on_preview_size_changed = on_preview_size_changed
        self.on_clear_session = on_clear_session
        self.on_status = on_status

        self._theme_var = tk.StringVar(value=config_manager.settings.theme.capitalize())
        self._export_var = tk.StringVar(
            value=config_manager.settings.default_export_format.upper()
        )
        size_labels = {
            "compact": "Compact (280 px)",
            "medium": "Medium (360 px)",
            "large": "Large (480 px)",
        }
        self._preview_var = tk.StringVar(
            value=size_labels.get(config_manager.settings.preview_size, "Medium (360 px)")
        )

        self._build_header()
        self._build_body()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACE_6, pady=(SPACE_4, SPACE_3))

        ctk.CTkLabel(
            header,
            text="Settings",
            font=self.theme.font("page_title"),
            text_color=self.theme.pair("text_primary"),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Configure appearance, export defaults, preview size, and session data.",
            font=self.theme.font("secondary"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkFrame(
            self,
            height=1,
            fg_color=self.theme.pair("border"),
            corner_radius=0,
        ).pack(fill="x", padx=SPACE_6)

    def _build_body(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=SPACE_6, pady=SPACE_3)

        container = ctk.CTkFrame(scroll, fg_color="transparent")
        container.pack(anchor="nw", fill="x", padx=(0, SPACE_2))

        # Appearance card
        app_card = SurfaceCard(container, self.theme, title="Appearance & Display")
        app_card.pack(fill="x", pady=(0, SPACE_3))

        self.theme_control: SegmentedControl | None = None

        def build_theme_seg(parent: ctk.CTkFrame) -> tk.Misc:
            ctrl = SegmentedControl(
                parent,
                theme=self.theme,
                values=["Dark", "Light", "System"],
                initial=self._theme_var.get(),
                command=self._handle_theme_select,
            )
            self.theme_control = ctrl
            return ctrl

        self._add_setting_row(
            app_card,
            label="Color Theme",
            description="Switch between precision dark mode, light mode, or follow your OS theme.",
            control_factory=build_theme_seg,
        )

        self._add_divider(app_card)

        self._add_setting_row(
            app_card,
            label="Preview Size",
            description="Maximum preview dimension used in the Image Inspector.",
            control_factory=lambda parent: ctk.CTkOptionMenu(
                parent,
                values=["Compact (280 px)", "Medium (360 px)", "Large (480 px)"],
                variable=self._preview_var,
                command=self._handle_preview_select,
                width=176,
                height=30,
                corner_radius=RADIUS_SM,
                font=self.theme.font("mono_sm"),
                fg_color=self.theme.pair("bg_surface_alt"),
                button_color=self.theme.pair("border"),
                button_hover_color=self.theme.pair("border_hover"),
                text_color=self.theme.pair("text_primary"),
                dropdown_fg_color=self.theme.pair("bg_surface"),
                dropdown_hover_color=self.theme.pair("bg_hover"),
                dropdown_text_color=self.theme.pair("text_primary"),
            ),
        )

        ctk.CTkFrame(app_card, height=SPACE_2, fg_color="transparent").pack()

        # Export card
        exp_card = SurfaceCard(container, self.theme, title="Export Preferences")
        exp_card.pack(fill="x", pady=(0, SPACE_3))

        self._add_setting_row(
            exp_card,
            label="Default Export Format",
            description="Preselected format when exporting single-image or batch metadata.",
            control_factory=lambda parent: SegmentedControl(
                parent,
                theme=self.theme,
                values=["JSON", "CSV"],
                initial=self._export_var.get(),
                command=self._handle_export_select,
            ),
        )
        ctk.CTkFrame(exp_card, height=SPACE_2, fg_color="transparent").pack()

        # Session & Privacy card
        priv_card = SurfaceCard(container, self.theme, title="Session & Local Privacy")
        priv_card.pack(fill="x", pady=(0, SPACE_3))

        self._add_setting_row(
            priv_card,
            label="Clear Session History",
            description="Unload current images, EXIF view, batch scan results, and comparison slots from memory.",
            control_factory=lambda parent: make_secondary_button(
                parent,
                self.theme,
                text="Clear Session",
                command=self.on_clear_session,
                width=120,
                host_bg="bg_surface",
            ),
        )

        NoticeBanner(
            priv_card,
            self.theme,
            (
                "All image processing runs strictly offline. Original files are never "
                "modified or stripped, and preferences never store image contents or GPS coordinates."
            ),
        ).pack(fill="x", padx=SPACE_4, pady=(SPACE_1, SPACE_3))

        # Format Capabilities card
        fmt_card = SurfaceCard(container, self.theme, title="Decoder Capabilities")
        fmt_card.pack(fill="x")

        heif_status = (
            "Installed (HEIC / HEIF enabled)"
            if is_heif_supported()
            else "Not installed (optional 'pillow-heif' required for HEIC/HEIF)"
        )
        rows = (
            ("Standard Formats", "JPG / JPEG, PNG, WEBP, TIFF, BMP, GIF — Ready"),
            ("HEIC / HEIF Plugin", heif_status),
            ("Settings File", str(self.config_manager.config_path)),
        )
        for idx, (lbl, val) in enumerate(rows):
            row = ctk.CTkFrame(fmt_card, fg_color="transparent")
            row.pack(fill="x", padx=SPACE_4, pady=SPACE_2)
            ctk.CTkLabel(
                row,
                text=lbl.upper(),
                font=self.theme.font("label"),
                text_color=self.theme.pair("text_secondary"),
                width=156,
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=val,
                font=self.theme.font("mono_sm"),
                text_color=self.theme.pair("text_primary"),
                anchor="w",
                wraplength=460,
                justify="left",
            ).pack(side="left", fill="x", expand=True)
            if idx < len(rows) - 1:
                self._add_divider(fmt_card)
        ctk.CTkFrame(fmt_card, height=SPACE_2, fg_color="transparent").pack()

    def _add_setting_row(
        self,
        parent: ctk.CTkFrame,
        label: str,
        description: str,
        control_factory: Callable[[ctk.CTkFrame], tk.Misc],
    ) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_4, pady=SPACE_2)

        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True, padx=(0, SPACE_4))

        ctk.CTkLabel(
            text_col,
            text=label,
            font=self.theme.font("body", weight="bold"),
            text_color=self.theme.pair("text_primary"),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_col,
            text=description,
            font=self.theme.font("secondary"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        control = control_factory(row)
        control.pack(side="right", anchor="center")

    def _add_divider(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkFrame(
            parent,
            height=1,
            fg_color=self.theme.pair("border"),
            corner_radius=0,
        ).pack(fill="x", padx=SPACE_4, pady=SPACE_1)

    def _handle_theme_select(self, value: str) -> None:
        self._theme_var.set(value)
        if self.theme_control is not None and self.theme_control._current != value:
            self.theme_control.set(value)
        mode: ThemeMode = value.lower()  # type: ignore[assignment]
        self.config_manager.settings.theme = mode
        self.config_manager.save()
        self.on_theme_changed(mode)
        self.on_status(f"Theme set to {value}.")

    def _handle_export_select(self, value: str) -> None:
        self._export_var.set(value)
        fmt: ExportFormat = value.lower()  # type: ignore[assignment]
        self.config_manager.settings.default_export_format = fmt
        self.config_manager.save()
        self.on_status(f"Default export format set to {value}.")

    def _handle_preview_select(self, value: str) -> None:
        mapping: dict[str, PreviewSize] = {
            "Compact (280 px)": "compact",
            "Medium (360 px)": "medium",
            "Large (480 px)": "large",
        }
        size_key = mapping.get(value, "medium")
        self.config_manager.settings.preview_size = size_key
        self.config_manager.save()
        self.on_preview_size_changed(size_key)
        self.on_status(f"Preview size set to {value}.")

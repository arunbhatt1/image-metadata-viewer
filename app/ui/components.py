"""Reusable precision-instrument UI primitives: cards, focus-ring buttons, banners, tooltips."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable

import customtkinter as ctk

from app.config import get_supported_extensions, is_heif_supported
from app.ui.theme import (
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    ThemeManager,
)


class Tooltip:
    """Crisp delayed hover tooltip styled with 1px hairline border."""

    def __init__(
        self,
        widget: tk.Misc,
        text: str,
        theme: ThemeManager,
        delay_ms: int = 400,
    ) -> None:
        self.widget = widget
        self.text = text
        self.theme = theme
        self.delay_ms = delay_ms
        self._after_id: str | None = None
        self._tip_window: tk.Toplevel | None = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event: tk.Event) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event: tk.Event) -> None:
        self._cancel()
        self._hide()

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip_window is not None or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 4
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except tk.TclError:
            return

        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")

        bg = self.theme.color("bg_surface")
        fg = self.theme.color("text_primary")
        border = self.theme.color("border_strong")

        frame = tk.Frame(
            tip,
            background=bg,
            highlightbackground=border,
            highlightthickness=1,
            padx=8,
            pady=4,
        )
        frame.pack()
        tk.Label(
            frame,
            text=self.text,
            background=bg,
            foreground=fg,
            font=(self.theme.ui_font, 10),
            justify="left",
        ).pack()
        self._tip_window = tip

    def _hide(self) -> None:
        if self._tip_window is not None:
            try:
                self._tip_window.destroy()
            except tk.TclError:
                pass
            self._tip_window = None


class SurfaceCard(ctk.CTkFrame):
    """Flat, 1px-bordered instrument panel without drop shadows."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        title: str | None = None,
        subtitle: str | None = None,
        **kwargs: object,
    ) -> None:
        defaults = {
            "fg_color": theme.pair("bg_surface"),
            "border_color": theme.pair("border"),
            "border_width": 1,
            "corner_radius": RADIUS_MD,
        }
        defaults.update(kwargs)
        super().__init__(master, **defaults)
        self.theme = theme

        if title:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.pack(fill="x", padx=SPACE_4, pady=(SPACE_3, SPACE_1))

            ctk.CTkLabel(
                header,
                text=title.upper(),
                font=theme.font("label"),
                text_color=theme.pair("text_secondary"),
                anchor="w",
            ).pack(side="left")

            if subtitle:
                ctk.CTkLabel(
                    header,
                    text=subtitle,
                    font=theme.font("mono_sm"),
                    text_color=theme.pair("text_muted"),
                    anchor="e",
                ).pack(side="right")

            ctk.CTkFrame(
                self,
                height=1,
                fg_color=theme.pair("border"),
                corner_radius=0,
            ).pack(fill="x", padx=SPACE_4, pady=(SPACE_1, SPACE_2))


class FocusRingButton(ctk.CTkFrame):
    """Button wrapped with a 2px amber keyboard focus ring and 2px offset."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        host_bg: str = "bg_main",
        is_secondary: bool = False,
        **btn_kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            fg_color="transparent",
            border_width=2,
            border_color=theme.pair(host_bg),
            corner_radius=RADIUS_LG,
        )
        self.theme = theme
        self._host_bg = host_bg
        self._is_secondary = is_secondary

        self.button = ctk.CTkButton(self, **btn_kwargs)
        self.button.pack(padx=4, pady=4)

        try:
            self.button._canvas.configure(takefocus=1)
            self.button._canvas.bind("<FocusIn>", self._on_focus_in, add="+")
            self.button._canvas.bind("<FocusOut>", self._on_focus_out, add="+")
            self.button._canvas.bind("<Return>", lambda _e: self._invoke_if_enabled(), add="+")
            self.button._canvas.bind("<space>", lambda _e: self._invoke_if_enabled(), add="+")
        except Exception:
            pass

        if is_secondary:
            for target in (self.button, getattr(self.button, "_canvas", self.button)):
                target.bind("<Enter>", self._on_sec_enter, add="+")
                target.bind("<Leave>", self._on_sec_leave, add="+")

    def _invoke_if_enabled(self) -> None:
        if self.button.cget("state") != "disabled":
            self.button.invoke()

    def _on_focus_in(self, _event: tk.Event) -> None:
        super().configure(border_color=self.theme.pair("accent"))

    def _on_focus_out(self, _event: tk.Event) -> None:
        super().configure(border_color=self.theme.pair(self._host_bg))

    def _on_sec_enter(self, _event: tk.Event) -> None:
        if self.button.cget("state") != "disabled":
            self.button.configure(border_color=self.theme.pair("border_hover"))

    def _on_sec_leave(self, _event: tk.Event) -> None:
        self.button.configure(border_color=self.theme.pair("border"))

    def configure(self, **kwargs: Any) -> None:  # type: ignore[override]
        frame_keys = {"border_color", "border_width", "fg_color", "corner_radius"}
        frame_args = {k: v for k, v in kwargs.items() if k in frame_keys and k != "fg_color"}
        btn_args = {k: v for k, v in kwargs.items() if k not in frame_args}
        if frame_args:
            super().configure(**frame_args)
        if btn_args:
            self.button.configure(**btn_args)

    def cget(self, attribute_name: str) -> Any:
        if attribute_name in ("state", "text", "command"):
            return self.button.cget(attribute_name)
        return super().cget(attribute_name)


def make_primary_button(
    master: tk.Misc,
    theme: ThemeManager,
    text: str,
    command: Callable[[], None] | None = None,
    width: int = 112,
    tooltip: str | None = None,
    host_bg: str = "bg_main",
) -> FocusRingButton:
    """Create a solid electric-amber primary button with near-black text."""
    btn = FocusRingButton(
        master,
        theme=theme,
        host_bg=host_bg,
        is_secondary=False,
        text=text,
        command=command,
        height=30,
        width=width,
        corner_radius=RADIUS_SM,
        font=theme.font("body", weight="bold"),
        fg_color=theme.pair("accent"),
        hover_color=theme.pair("accent_hover"),
        text_color=theme.pair("accent_text"),
        text_color_disabled=theme.pair("text_muted"),
    )
    if tooltip:
        Tooltip(btn.button, tooltip, theme)
    return btn


def make_secondary_button(
    master: tk.Misc,
    theme: ThemeManager,
    text: str,
    command: Callable[[], None] | None = None,
    width: int = 100,
    tooltip: str | None = None,
    host_bg: str = "bg_main",
) -> FocusRingButton:
    """Create a transparent secondary button with 1px border that brightens on hover."""
    btn = FocusRingButton(
        master,
        theme=theme,
        host_bg=host_bg,
        is_secondary=True,
        text=text,
        command=command,
        height=30,
        width=width,
        corner_radius=RADIUS_SM,
        font=theme.font("body"),
        fg_color="transparent",
        hover_color=theme.pair("bg_hover"),
        border_color=theme.pair("border"),
        border_width=1,
        text_color=theme.pair("text_primary"),
        text_color_disabled=theme.pair("text_muted"),
    )
    if tooltip:
        Tooltip(btn.button, tooltip, theme)
    return btn


class NoticeBanner(ctk.CTkFrame):
    """Compact hairline-bordered inline notice using the single amber accent."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        message: str,
        kind: str = "info",
    ) -> None:
        bg_key = "bg_danger" if kind == "error" else "bg_notice"
        super().__init__(
            master,
            height=32,
            fg_color=theme.pair(bg_key),
            border_color=theme.pair("border"),
            border_width=1,
            corner_radius=RADIUS_SM,
        )
        bar = ctk.CTkFrame(
            self,
            width=2,
            height=16,
            fg_color=theme.pair("accent"),
            corner_radius=1,
        )
        bar.pack(side="left", fill="y", padx=(8, 10), pady=7)

        self.label = ctk.CTkLabel(
            self,
            text=message,
            font=theme.font("secondary"),
            text_color=theme.pair("text_primary"),
            justify="left",
            wraplength=560,
            anchor="w",
        )
        self.label.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=6)
        self.bind("<Configure>", self._update_wraplength)

    def _update_wraplength(self, event: tk.Event) -> None:
        try:
            scale = ctk.ScalingTracker.get_widget_scaling(self)
        except Exception:
            scale = 1.0
        logical_w = int(event.width / max(scale, 0.5))
        self.label.configure(wraplength=max(220, logical_w - 48))

    def set_message(self, message: str) -> None:
        self.label.configure(text=message)


def build_image_filetypes() -> list[tuple[str, str]]:
    """Build file dialog extension filter list based on available decoders."""
    exts = get_supported_extensions()
    patterns = " ".join(f"*{ext}" for ext in exts)
    types = [
        ("Supported Images", patterns),
        ("JPEG Images", "*.jpg *.jpeg"),
        ("PNG Images", "*.png"),
        ("WEBP Images", "*.webp"),
        ("TIFF Images", "*.tiff *.tif"),
        ("BMP & GIF Images", "*.bmp *.gif"),
    ]
    if is_heif_supported():
        types.append(("HEIC / HEIF Images", "*.heic *.heif"))
    types.append(("All Files", "*.*"))
    return types


def ask_open_image_dialog(parent: tk.Misc, title: str = "Open Image") -> Path | None:
    """Show a native file dialog to select a single image."""
    selected = filedialog.askopenfilename(
        parent=parent,
        title=title,
        filetypes=build_image_filetypes(),
    )
    return Path(selected) if selected else None


def ask_open_multiple_images_dialog(parent: tk.Misc) -> list[Path]:
    """Show a native file dialog to select multiple images."""
    selected = filedialog.askopenfilenames(
        parent=parent,
        title="Select Images for Batch Analysis",
        filetypes=build_image_filetypes(),
    )
    return [Path(p) for p in selected] if selected else []


def ask_export_destination(
    parent: tk.Misc,
    default_format: str,
    suggested_stem: str,
) -> tuple[Path, str, bool] | None:
    """Prompt user for export file location and confirm overwrite if needed."""
    fmt = default_format.lower() if default_format.lower() in ("json", "csv") else "json"
    if fmt == "json":
        filetypes = [("JSON File", "*.json"), ("CSV File", "*.csv")]
        default_ext = ".json"
    else:
        filetypes = [("CSV File", "*.csv"), ("JSON File", "*.json")]
        default_ext = ".csv"

    chosen = filedialog.asksaveasfilename(
        parent=parent,
        title="Export Metadata",
        initialfile=f"{suggested_stem}{default_ext}",
        defaultextension=default_ext,
        filetypes=filetypes,
        confirmoverwrite=False,
    )
    if not chosen:
        return None

    out_path = Path(chosen)
    chosen_ext = out_path.suffix.lower()
    chosen_fmt = "csv" if chosen_ext == ".csv" else "json"
    if chosen_ext not in (".json", ".csv"):
        chosen_fmt = fmt
        out_path = out_path.with_suffix(f".{fmt}")

    overwrite = False
    if out_path.exists():
        confirmed = messagebox.askyesno(
            "Confirm Overwrite",
            f"The file '{out_path.name}' already exists.\n\nDo you want to replace it?",
            parent=parent,
        )
        if not confirmed:
            return None
        overwrite = True

    return out_path, chosen_fmt, overwrite

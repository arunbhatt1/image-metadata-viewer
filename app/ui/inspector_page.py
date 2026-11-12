"""Image Inspector page: preview, properties, color analysis, and line-icon empty state."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from app.config import get_supported_extensions
from app.core.image_loader import load_preview_image
from app.core.metadata_extractor import ImageRecord
from app.ui.components import (
    NoticeBanner,
    SurfaceCard,
    make_primary_button,
    make_secondary_button,
)
from app.ui.theme import (
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_6,
    ThemeManager,
)
from app.utils.file_utils import ImageFileError
from app.utils.formatters import format_datetime, format_dimensions, format_file_size


class InspectorPage(ctk.CTkFrame):
    """Primary single-image inspection view with preview, properties, and color profile."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        on_open_image: Callable[[], None],
        on_view_exif: Callable[[], None],
        on_export: Callable[[], None],
        get_preview_max_px: Callable[[], int],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.theme = theme
        self.on_open_image = on_open_image
        self.on_view_exif = on_view_exif
        self.on_export = on_export
        self.get_preview_max_px = get_preview_max_px

        self._record: ImageRecord | None = None
        self._ctk_preview: ctk.CTkImage | None = None
        self._icon_canvas: tk.Canvas | None = None

        self._build_header()
        self._build_body()
        self.refresh_theme()
        self.show_empty()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACE_6, pady=(SPACE_4, SPACE_3))

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_block,
            text="Image Inspector",
            font=self.theme.font("page_title"),
            text_color=self.theme.pair("text_primary"),
            anchor="w",
        ).pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            title_block,
            text="Inspect file properties, resolution, timestamps, and color values.",
            font=self.theme.font("secondary"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right", anchor="center")

        self.btn_exif = make_secondary_button(
            actions,
            self.theme,
            text="View EXIF",
            command=self.on_view_exif,
            width=92,
            tooltip="Open full EXIF metadata table for the current image",
        )
        self.btn_exif.pack(side="left", padx=(0, SPACE_1))

        self.btn_export = make_secondary_button(
            actions,
            self.theme,
            text="Export",
            command=self.on_export,
            width=84,
            tooltip="Export image properties and metadata to JSON or CSV",
        )
        self.btn_export.pack(side="left", padx=(0, SPACE_1))

        self.btn_open = make_primary_button(
            actions,
            self.theme,
            text="Open Image",
            command=self.on_open_image,
            width=112,
            tooltip="Choose an image file from disk (Ctrl+O)",
        )
        self.btn_open.pack(side="left")

        ctk.CTkFrame(
            self,
            height=1,
            fg_color=self.theme.pair("border"),
            corner_radius=0,
        ).pack(fill="x", padx=SPACE_6)

    def _build_body(self) -> None:
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=SPACE_6, pady=SPACE_3)

        # Empty state container
        self.empty_frame = SurfaceCard(self.content_area, self.theme)
        empty_inner = ctk.CTkFrame(self.empty_frame, fg_color="transparent")
        empty_inner.place(relx=0.5, rely=0.48, anchor="center")

        self._icon_canvas = tk.Canvas(
            empty_inner,
            width=56,
            height=48,
            highlightthickness=0,
            bd=0,
        )
        self._icon_canvas.pack(pady=(0, SPACE_3))

        ctk.CTkLabel(
            empty_inner,
            text="No image loaded",
            font=self.theme.font("section_heading"),
            text_color=self.theme.pair("text_primary"),
        ).pack(pady=(0, SPACE_1))

        ctk.CTkLabel(
            empty_inner,
            text="Open a local file to inspect properties, EXIF tags, and color values.",
            font=self.theme.font("secondary"),
            text_color=self.theme.pair("text_secondary"),
        ).pack(pady=(0, SPACE_4))

        make_primary_button(
            empty_inner,
            self.theme,
            text="Open Image",
            command=self.on_open_image,
            width=128,
            host_bg="bg_surface",
        ).pack(pady=(0, SPACE_4))

        # Monospace supported format chips
        chips_row = ctk.CTkFrame(empty_inner, fg_color="transparent")
        chips_row.pack()

        seen_chips: list[str] = []
        for ext in get_supported_extensions():
            label = ext.lstrip(".").upper()
            if label in ("TIF", "HEIF") or label in seen_chips:
                continue
            seen_chips.append(label)

        for fmt_label in seen_chips:
            chip = ctk.CTkFrame(
                chips_row,
                fg_color=self.theme.pair("bg_surface_alt"),
                border_color=self.theme.pair("border"),
                border_width=1,
                corner_radius=RADIUS_SM,
            )
            chip.pack(side="left", padx=3)
            ctk.CTkLabel(
                chip,
                text=fmt_label,
                font=self.theme.font("mono_sm"),
                text_color=self.theme.pair("text_secondary"),
            ).pack(padx=7, pady=2)

        # Loaded state scrollable workspace
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.content_area,
            fg_color="transparent",
            corner_radius=0,
        )
        self.scroll_frame.grid_columnconfigure(0, weight=5, uniform="col")
        self.scroll_frame.grid_columnconfigure(1, weight=6, uniform="col")

        self.left_col = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.left_col.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_2))

        self.preview_card = SurfaceCard(self.left_col, self.theme, title="Preview")
        self.preview_card.pack(fill="x", pady=(0, SPACE_3))

        self.preview_box = ctk.CTkFrame(
            self.preview_card,
            fg_color=self.theme.pair("bg_surface_alt"),
            corner_radius=RADIUS_SM,
            border_color=self.theme.pair("border"),
            border_width=1,
        )
        self.preview_box.pack(fill="x", padx=SPACE_4, pady=(SPACE_1, SPACE_2))

        self.preview_label = ctk.CTkLabel(
            self.preview_box,
            text="",
            anchor="center",
        )
        self.preview_label.pack(padx=SPACE_3, pady=SPACE_3)

        self.preview_caption = ctk.CTkLabel(
            self.preview_card,
            text="",
            font=self.theme.font("mono_sm"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        )
        self.preview_caption.pack(fill="x", padx=SPACE_4, pady=(0, SPACE_3))

        self.color_card = SurfaceCard(
            self.left_col,
            self.theme,
            title="Image Color Analysis",
            subtitle="LOCAL SAMPLE",
        )
        self.color_card.pack(fill="x")
        self.color_content = ctk.CTkFrame(self.color_card, fg_color="transparent")
        self.color_content.pack(fill="x", padx=SPACE_4, pady=(0, SPACE_3))

        self.right_col = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.right_col.grid(row=0, column=1, sticky="nsew", padx=(SPACE_2, 0))

        self.props_card = SurfaceCard(
            self.right_col,
            self.theme,
            title="File & Image Properties",
        )
        self.props_card.pack(fill="x", pady=(0, SPACE_3))
        self.props_content = ctk.CTkFrame(self.props_card, fg_color="transparent")
        self.props_content.pack(fill="x", padx=SPACE_4, pady=(0, SPACE_3))

        self.status_card = SurfaceCard(
            self.right_col,
            self.theme,
            title="Metadata Summary",
        )
        self.status_card.pack(fill="x")
        self.status_content = ctk.CTkFrame(self.status_card, fg_color="transparent")
        self.status_content.pack(fill="x", padx=SPACE_4, pady=(0, SPACE_3))

    def refresh_theme(self) -> None:
        """Draw the empty-state dashed image line-icon using active theme tokens."""
        if self._icon_canvas is None:
            return
        bg = self.theme.color("bg_surface")
        stroke = self.theme.color("text_muted")
        self._icon_canvas.configure(background=bg)
        self._icon_canvas.delete("all")
        # Dashed-outline image frame (1.5px stroke)
        self._icon_canvas.create_rectangle(
            4, 4, 52, 44,
            outline=stroke,
            width=1.5,
            dash=(4, 3),
        )
        # Minimal horizon + sun line inside frame
        self._icon_canvas.create_oval(
            13, 12, 20, 19,
            outline=stroke,
            width=1.5,
        )
        self._icon_canvas.create_line(
            8, 38, 22, 24, 31, 32, 38, 26, 48, 38,
            fill=stroke,
            width=1.5,
            joinstyle="miter",
        )

    def show_empty(self) -> None:
        """Reset inspector to empty state."""
        self._record = None
        self._ctk_preview = None
        self.subtitle_label.configure(
            text="Inspect file properties, resolution, timestamps, and color values.",
            font=self.theme.font("secondary"),
        )
        self.btn_exif.configure(state="disabled")
        self.btn_export.configure(state="disabled")
        self.scroll_frame.pack_forget()
        self.empty_frame.pack(fill="both", expand=True)

    def display_record(self, record: ImageRecord) -> None:
        """Render the loaded ImageRecord across preview, properties, and colors."""
        self._record = record
        props = record.properties
        self.subtitle_label.configure(
            text=props.file_name,
            font=self.theme.font("mono"),
        )
        self.btn_exif.configure(state="normal")
        self.btn_export.configure(state="normal")

        self.empty_frame.pack_forget()
        self.scroll_frame.pack(fill="both", expand=True)

        self._render_preview(record)
        self._render_properties(record)
        self._render_metadata_summary(record)
        self._render_color_analysis(record)

    def refresh_preview_size(self) -> None:
        """Re-render preview if the user changed preview size in Settings."""
        if self._record is not None:
            self._render_preview(self._record)

    def _render_preview(self, record: ImageRecord) -> None:
        props = record.properties
        max_px = self.get_preview_max_px()
        try:
            pil_img = load_preview_image(props.file_path, max_size=max_px)
            w, h = pil_img.size
            self._ctk_preview = ctk.CTkImage(
                light_image=pil_img,
                dark_image=pil_img,
                size=(w, h),
            )
            self.preview_label.configure(image=self._ctk_preview, text="")
        except ImageFileError as exc:
            self._ctk_preview = None
            self.preview_label.configure(
                image=None,
                text=f"Preview unavailable: {exc}",
                font=self.theme.font("secondary"),
                text_color=self.theme.pair("text_secondary"),
            )

        self.preview_caption.configure(
            text=f"{props.file_format}  |  {format_dimensions(props.width, props.height)}  |  {props.aspect_ratio}"
        )

    def _render_properties(self, record: ImageRecord) -> None:
        for child in self.props_content.winfo_children():
            child.destroy()

        props = record.properties
        rows = [
            ("File Name", props.file_name, True),
            ("File Location", props.file_location, False),
            ("File Format", props.file_format, False),
            ("File Size", f"{format_file_size(props.file_size_bytes)} ({props.file_size_bytes:,} B)", False),
            ("Dimensions", format_dimensions(props.width, props.height), True),
            ("Aspect Ratio", props.aspect_ratio, False),
            ("Color Mode", props.color_mode, False),
            ("Resolution", props.resolution, False),
            ("Created", format_datetime(props.created_at), False),
            ("Modified", format_datetime(props.modified_at), False),
        ]

        for idx, (label, value, is_key) in enumerate(rows):
            row = ctk.CTkFrame(self.props_content, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row,
                text=label.upper(),
                font=self.theme.font("label"),
                text_color=self.theme.pair("text_secondary"),
                width=120,
                anchor="w",
            ).pack(side="left", anchor="n")

            ctk.CTkLabel(
                row,
                text=value,
                font=self.theme.font("mono", weight="bold" if is_key else "normal"),
                text_color=self.theme.pair("text_primary"),
                anchor="w",
                justify="left",
                wraplength=280,
            ).pack(side="left", fill="x", expand=True)

            if idx < len(rows) - 1:
                ctk.CTkFrame(
                    self.props_content,
                    height=1,
                    fg_color=self.theme.pair("border"),
                    corner_radius=0,
                ).pack(fill="x", pady=(2, 0))

    def _render_metadata_summary(self, record: ImageRecord) -> None:
        for child in self.status_content.winfo_children():
            child.destroy()

        exif = record.exif
        summary_rows = [
            (
                "EXIF Metadata",
                f"AVAILABLE ({len(exif.entries)} fields)" if exif.has_exif else "NOT PRESENT",
                False,
            ),
            (
                "Camera",
                exif.camera_model or "—",
                False,
            ),
            (
                "Capture Date",
                exif.capture_date or "—",
                False,
            ),
            (
                "GPS Location",
                "EMBEDDED IN FILE" if exif.has_gps else "NOT PRESENT",
                exif.has_gps,
            ),
        ]

        for idx, (label, value, highlight_amber) in enumerate(summary_rows):
            row = ctk.CTkFrame(self.status_content, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                row,
                text=label.upper(),
                font=self.theme.font("label"),
                text_color=self.theme.pair("text_secondary"),
                width=120,
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=value,
                font=self.theme.font("mono", weight="bold" if highlight_amber else "normal"),
                text_color=(
                    self.theme.pair("accent")
                    if highlight_amber
                    else self.theme.pair("text_primary")
                ),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            if idx < len(summary_rows) - 1:
                ctk.CTkFrame(
                    self.status_content,
                    height=1,
                    fg_color=self.theme.pair("border"),
                    corner_radius=0,
                ).pack(fill="x", pady=(2, 0))

        if exif.has_gps:
            NoticeBanner(
                self.status_content,
                self.theme,
                "Privacy notice: GPS metadata in this file may reveal where the photo was taken.",
            ).pack(fill="x", pady=(SPACE_2, 2))

    def _render_color_analysis(self, record: ImageRecord) -> None:
        for child in self.color_content.winfo_children():
            child.destroy()

        colors = record.colors
        if colors is None:
            ctk.CTkLabel(
                self.color_content,
                text="Color analysis unavailable for this image.",
                font=self.theme.font("secondary"),
                text_color=self.theme.pair("text_secondary"),
            ).pack(anchor="w")
            return

        avg_row = ctk.CTkFrame(self.color_content, fg_color="transparent")
        avg_row.pack(fill="x", pady=(SPACE_1, SPACE_2))

        avg_swatch = ctk.CTkFrame(
            avg_row,
            width=32,
            height=32,
            fg_color=colors.average_hex,
            border_color=self.theme.pair("border_strong"),
            border_width=1,
            corner_radius=RADIUS_SM,
        )
        avg_swatch.pack(side="left", padx=(0, SPACE_3))
        avg_swatch.pack_propagate(False)

        avg_info = ctk.CTkFrame(avg_row, fg_color="transparent")
        avg_info.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            avg_info,
            text="AVERAGE COLOR",
            font=self.theme.font("label"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        ).pack(anchor="w")

        r, g, b = colors.average_rgb
        ctk.CTkLabel(
            avg_info,
            text=f"{colors.average_hex}   |   RGB({r}, {g}, {b})",
            font=self.theme.font("mono", weight="bold"),
            text_color=self.theme.pair("text_primary"),
            anchor="w",
        ).pack(anchor="w")

        dist_frame = ctk.CTkFrame(
            self.color_content,
            fg_color=self.theme.pair("bg_surface_alt"),
            corner_radius=RADIUS_SM,
            border_color=self.theme.pair("border"),
            border_width=1,
        )
        dist_frame.pack(fill="x", pady=(0, SPACE_3))

        dist_text = "  |  ".join(
            f"{channel[0]}: {pct:.1f}%"
            for channel, pct in colors.channel_distribution.items()
        )
        ctk.CTkLabel(
            dist_frame,
            text=f"CHANNELS  //  {dist_text}",
            font=self.theme.font("mono_sm"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        ).pack(fill="x", padx=SPACE_2, pady=6)

        ctk.CTkLabel(
            self.color_content,
            text="DOMINANT SWATCHES",
            font=self.theme.font("label"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        ).pack(anchor="w", pady=(0, SPACE_1))

        swatch_grid = ctk.CTkFrame(self.color_content, fg_color="transparent")
        swatch_grid.pack(fill="x")

        for idx, swatch in enumerate(colors.dominant_colors):
            swatch_grid.grid_columnconfigure(idx, weight=1, uniform="swatch")
            cell = ctk.CTkFrame(swatch_grid, fg_color="transparent")
            cell.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else SPACE_1, 0))

            ctk.CTkFrame(
                cell,
                height=26,
                fg_color=swatch.hex_code,
                border_color=self.theme.pair("border_strong"),
                border_width=1,
                corner_radius=RADIUS_SM,
            ).pack(fill="x")

            ctk.CTkLabel(
                cell,
                text=swatch.hex_code,
                font=self.theme.font("mono_sm"),
                text_color=self.theme.pair("text_primary"),
            ).pack(anchor="w", pady=(SPACE_1, 0))

            ctk.CTkLabel(
                cell,
                text=f"{swatch.percentage:.1f}%",
                font=self.theme.font("mono_sm"),
                text_color=self.theme.pair("text_secondary"),
            ).pack(anchor="w")

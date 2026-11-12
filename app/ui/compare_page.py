"""Compare Images page: side-by-side previews and technical diff comparison."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from app.core.image_loader import load_preview_image
from app.core.metadata_extractor import ImageRecord, extract_image_record
from app.ui.components import (
    SurfaceCard,
    ask_open_image_dialog,
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
from app.utils.formatters import format_dimensions, format_file_size, sanitize_error_message


class ComparePage(ctk.CTkFrame):
    """Side-by-side comparison of two images highlighting property differences."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        on_status: Callable[[str], None],
        on_error: Callable[[str, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.theme = theme
        self.on_status = on_status
        self.on_error = on_error

        self._record_a: ImageRecord | None = None
        self._record_b: ImageRecord | None = None
        self._img_a: ctk.CTkImage | None = None
        self._img_b: ctk.CTkImage | None = None

        self._build_header()
        self._build_body()
        self._render_comparison()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACE_6, pady=(SPACE_4, SPACE_3))

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_block,
            text="Compare Images",
            font=self.theme.font("page_title"),
            text_color=self.theme.pair("text_primary"),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_block,
            text="Inspect two images side-by-side and highlight metadata differences.",
            font=self.theme.font("secondary"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right", anchor="center")

        self.btn_clear = make_secondary_button(
            actions,
            self.theme,
            text="Clear",
            command=self.clear,
            width=74,
        )
        self.btn_clear.pack(side="left", padx=(0, SPACE_1))

        self.btn_swap = make_secondary_button(
            actions,
            self.theme,
            text="Swap A / B",
            command=self._swap_images,
            width=92,
        )
        self.btn_swap.pack(side="left", padx=(0, SPACE_1))

        make_primary_button(
            actions,
            self.theme,
            text="Select Image A",
            command=lambda: self._pick_image("A"),
            width=116,
        ).pack(side="left", padx=(0, SPACE_1))

        make_primary_button(
            actions,
            self.theme,
            text="Select Image B",
            command=lambda: self._pick_image("B"),
            width=116,
        ).pack(side="left")

        ctk.CTkFrame(
            self,
            height=1,
            fg_color=self.theme.pair("border"),
            corner_radius=0,
        ).pack(fill="x", padx=SPACE_6)

    def _build_body(self) -> None:
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self.scroll.pack(fill="both", expand=True, padx=SPACE_6, pady=SPACE_3)

        previews = ctk.CTkFrame(self.scroll, fg_color="transparent")
        previews.pack(fill="x", pady=(0, SPACE_3))
        previews.grid_columnconfigure(0, weight=1, uniform="cmp")
        previews.grid_columnconfigure(1, weight=1, uniform="cmp")

        self.card_a, self.preview_a, self.name_a = self._build_preview_slot(
            previews, "Image A", lambda: self._pick_image("A")
        )
        self.card_a.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_2))

        self.card_b, self.preview_b, self.name_b = self._build_preview_slot(
            previews, "Image B", lambda: self._pick_image("B")
        )
        self.card_b.grid(row=0, column=1, sticky="nsew", padx=(SPACE_2, 0))

        self.table_card = SurfaceCard(
            self.scroll,
            self.theme,
            title="Property Comparison",
            subtitle="AUTO DIFF",
        )
        self.table_card.pack(fill="x")
        self.table_body = ctk.CTkFrame(self.table_card, fg_color="transparent")
        self.table_body.pack(fill="x", padx=SPACE_4, pady=(0, SPACE_3))

    def _build_preview_slot(
        self,
        parent: tk.Misc,
        title: str,
        on_select: Callable[[], None],
    ) -> tuple[SurfaceCard, ctk.CTkLabel, ctk.CTkLabel]:
        card = SurfaceCard(parent, self.theme, title=title)

        box = ctk.CTkFrame(
            card,
            height=210,
            fg_color=self.theme.pair("bg_surface_alt"),
            border_color=self.theme.pair("border"),
            border_width=1,
            corner_radius=RADIUS_SM,
        )
        box.pack(fill="x", padx=SPACE_4, pady=(SPACE_1, SPACE_2))
        box.pack_propagate(False)

        preview_lbl = ctk.CTkLabel(
            box,
            text="NO IMAGE SELECTED",
            font=self.theme.font("mono_sm"),
            text_color=self.theme.pair("text_muted"),
            anchor="center",
        )
        preview_lbl.pack(expand=True, fill="both", padx=SPACE_2, pady=SPACE_2)

        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=SPACE_4, pady=(0, SPACE_3))

        name_lbl = ctk.CTkLabel(
            footer,
            text="Select local file",
            font=self.theme.font("mono_sm"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        )
        name_lbl.pack(side="left", fill="x", expand=True)

        make_secondary_button(
            footer,
            self.theme,
            text="Choose...",
            command=on_select,
            width=82,
            host_bg="bg_surface",
        ).pack(side="right")

        return card, preview_lbl, name_lbl

    def _pick_image(self, slot: str) -> None:
        path = ask_open_image_dialog(self, title=f"Select Image {slot}")
        if path is None:
            return
        self.load_slot(slot, path)

    def load_slot(self, slot: str, path: Path) -> None:
        """Load an image read-only into slot 'A' or 'B'."""
        try:
            record = extract_image_record(path, include_colors=False)
            pil_preview = load_preview_image(path, max_size=240)
        except ImageFileError as exc:
            self.on_error("Unable to Load Image", sanitize_error_message(exc))
            return
        except Exception as exc:
            self.on_error("Unable to Load Image", sanitize_error_message(exc))
            return

        ctk_img = ctk.CTkImage(
            light_image=pil_preview,
            dark_image=pil_preview,
            size=pil_preview.size,
        )

        if slot == "A":
            self._record_a = record
            self._img_a = ctk_img
            self.preview_a.configure(image=ctk_img, text="")
            self.name_a.configure(text=record.properties.file_name)
        else:
            self._record_b = record
            self._img_b = ctk_img
            self.preview_b.configure(image=ctk_img, text="")
            self.name_b.configure(text=record.properties.file_name)

        self.on_status(f"Loaded '{record.properties.file_name}' into Image {slot}.")
        self._render_comparison()

    def _swap_images(self) -> None:
        self._record_a, self._record_b = self._record_b, self._record_a
        self._img_a, self._img_b = self._img_b, self._img_a

        if self._record_a and self._img_a:
            self.preview_a.configure(image=self._img_a, text="")
            self.name_a.configure(text=self._record_a.properties.file_name)
        else:
            self.preview_a.configure(image=None, text="NO IMAGE SELECTED")
            self.name_a.configure(text="Select local file")

        if self._record_b and self._img_b:
            self.preview_b.configure(image=self._img_b, text="")
            self.name_b.configure(text=self._record_b.properties.file_name)
        else:
            self.preview_b.configure(image=None, text="NO IMAGE SELECTED")
            self.name_b.configure(text="Select local file")

        self._render_comparison()

    def clear(self) -> None:
        """Reset both comparison slots."""
        self._record_a = None
        self._record_b = None
        self._img_a = None
        self._img_b = None
        self.preview_a.configure(image=None, text="NO IMAGE SELECTED")
        self.preview_b.configure(image=None, text="NO IMAGE SELECTED")
        self.name_a.configure(text="Select local file")
        self.name_b.configure(text="Select local file")
        self._render_comparison()

    def _extract_fields(self, record: ImageRecord | None) -> dict[str, str]:
        if record is None:
            return {}
        props = record.properties
        exif = record.exif
        return {
            "File Size": format_file_size(props.file_size_bytes),
            "Format": props.file_format,
            "Dimensions": format_dimensions(props.width, props.height),
            "Aspect Ratio": props.aspect_ratio,
            "Color Mode": props.color_mode,
            "EXIF Availability": f"Yes ({len(exif.entries)} fields)" if exif.has_exif else "No",
            "Camera Model": exif.camera_model or "—",
            "Capture Date": exif.capture_date or "—",
            "GPS Availability": "Yes" if exif.has_gps else "No",
        }

    def _render_comparison(self) -> None:
        for child in self.table_body.winfo_children():
            child.destroy()

        has_both = self._record_a is not None and self._record_b is not None
        self.btn_swap.configure(state="normal" if (self._record_a or self._record_b) else "disabled")
        self.btn_clear.configure(state="normal" if (self._record_a or self._record_b) else "disabled")

        fields_a = self._extract_fields(self._record_a)
        fields_b = self._extract_fields(self._record_b)

        hdr = ctk.CTkFrame(
            self.table_body,
            fg_color=self.theme.pair("bg_surface_alt"),
            corner_radius=RADIUS_SM,
        )
        hdr.pack(fill="x", pady=(SPACE_1, SPACE_1))
        hdr.grid_columnconfigure(0, weight=2, uniform="tbl")
        hdr.grid_columnconfigure(1, weight=3, uniform="tbl")
        hdr.grid_columnconfigure(2, weight=3, uniform="tbl")

        for col_idx, col_title in enumerate(("PROPERTY", "IMAGE A", "IMAGE B")):
            ctk.CTkLabel(
                hdr,
                text=col_title,
                font=self.theme.font("label"),
                text_color=self.theme.pair("text_secondary"),
                anchor="w",
            ).grid(row=0, column=col_idx, sticky="ew", padx=SPACE_2, pady=5)

        prop_keys = (
            "File Size",
            "Format",
            "Dimensions",
            "Aspect Ratio",
            "Color Mode",
            "EXIF Availability",
            "Camera Model",
            "Capture Date",
            "GPS Availability",
        )

        diff_count = 0
        for idx, prop_name in enumerate(prop_keys):
            val_a = fields_a.get(prop_name, "—")
            val_b = fields_b.get(prop_name, "—")
            is_diff = has_both and val_a != val_b
            if is_diff:
                diff_count += 1

            row = ctk.CTkFrame(
                self.table_body,
                fg_color=self.theme.pair("bg_diff") if is_diff else "transparent",
                corner_radius=RADIUS_SM,
            )
            row.pack(fill="x", pady=1)
            row.grid_columnconfigure(0, weight=2, uniform="tbl")
            row.grid_columnconfigure(1, weight=3, uniform="tbl")
            row.grid_columnconfigure(2, weight=3, uniform="tbl")

            label_text = f"{prop_name.upper()}  *" if is_diff else prop_name.upper()
            ctk.CTkLabel(
                row,
                text=label_text,
                font=self.theme.font("label"),
                text_color=(
                    self.theme.pair("accent")
                    if is_diff
                    else self.theme.pair("text_secondary")
                ),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=SPACE_2, pady=6)

            ctk.CTkLabel(
                row,
                text=val_a,
                font=self.theme.font("mono"),
                text_color=self.theme.pair("text_primary"),
                anchor="w",
                wraplength=220,
            ).grid(row=0, column=1, sticky="ew", padx=SPACE_2, pady=6)

            ctk.CTkLabel(
                row,
                text=val_b,
                font=self.theme.font("mono"),
                text_color=self.theme.pair("text_primary"),
                anchor="w",
                wraplength=220,
            ).grid(row=0, column=2, sticky="ew", padx=SPACE_2, pady=6)

            if idx < len(prop_keys) - 1:
                ctk.CTkFrame(
                    self.table_body,
                    height=1,
                    fg_color=self.theme.pair("border"),
                    corner_radius=0,
                ).pack(fill="x", padx=SPACE_1)

        if has_both:
            summary_text = (
                f"{diff_count} DIFFERENCE{'S' if diff_count != 1 else ''} DETECTED"
                if diff_count > 0
                else "ALL COMPARED PROPERTIES MATCH"
            )
            ctk.CTkLabel(
                self.table_body,
                text=summary_text,
                font=self.theme.font("mono_sm"),
                text_color=self.theme.pair("accent" if diff_count > 0 else "text_secondary"),
                anchor="w",
            ).pack(anchor="w", padx=SPACE_2, pady=(SPACE_2, 0))

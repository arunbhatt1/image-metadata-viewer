"""EXIF Viewer page: technical table with uppercase labels, mono values, and focus rings."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from app.core.exif_parser import SECTION_ORDER, ExifEntry
from app.core.metadata_extractor import ImageRecord
from app.ui.components import (
    NoticeBanner,
    SurfaceCard,
    Tooltip,
    make_primary_button,
    make_secondary_button,
)
from app.ui.theme import (
    RADIUS_LG,
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_6,
    ThemeManager,
)


class ExifPage(ctk.CTkFrame):
    """Structured EXIF metadata viewer with search, raw tag toggle, and clipboard actions."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        on_open_image: Callable[[], None],
        on_export: Callable[[], None],
        on_status: Callable[[str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.theme = theme
        self.on_open_image = on_open_image
        self.on_export = on_export
        self.on_status = on_status

        self._record: ImageRecord | None = None
        self._selected_value: str | None = None
        self._selected_label: str | None = None
        self._row_frames: list[tuple[ctk.CTkFrame, str]] = []
        self._visible_rows_text: list[str] = []

        self._raw_var = tk.BooleanVar(value=False)

        self._build_header()
        self._build_toolbar()
        self._build_body()
        self.show_empty()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACE_6, pady=(SPACE_4, SPACE_3))

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_block,
            text="EXIF Viewer",
            font=self.theme.font("page_title"),
            text_color=self.theme.pair("text_primary"),
            anchor="w",
        ).pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            title_block,
            text="Explore camera, exposure, timestamp, location, and image metadata.",
            font=self.theme.font("secondary"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right", anchor="center")

        self.btn_copy_val = make_secondary_button(
            actions,
            self.theme,
            text="Copy Value",
            command=self._copy_selected_value,
            width=94,
            tooltip="Copy the selected row's value to clipboard",
        )
        self.btn_copy_val.pack(side="left", padx=(0, SPACE_1))

        self.btn_copy_all = make_secondary_button(
            actions,
            self.theme,
            text="Copy All",
            command=self._copy_all_values,
            width=84,
            tooltip="Copy all visible EXIF metadata fields to clipboard",
        )
        self.btn_copy_all.pack(side="left", padx=(0, SPACE_1))

        self.btn_export = make_secondary_button(
            actions,
            self.theme,
            text="Export",
            command=self.on_export,
            width=82,
            tooltip="Export metadata to JSON or CSV",
        )
        self.btn_export.pack(side="left", padx=(0, SPACE_1))

        self.btn_open = make_primary_button(
            actions,
            self.theme,
            text="Open Image",
            command=self.on_open_image,
            width=110,
        )
        self.btn_open.pack(side="left")

        ctk.CTkFrame(
            self,
            height=1,
            fg_color=self.theme.pair("border"),
            corner_radius=0,
        ).pack(fill="x", padx=SPACE_6)

    def _build_toolbar(self) -> None:
        self.toolbar = ctk.CTkFrame(self, fg_color="transparent")

        self.search_ring = ctk.CTkFrame(
            self.toolbar,
            fg_color="transparent",
            border_width=2,
            border_color=self.theme.pair("bg_main"),
            corner_radius=RADIUS_LG,
        )
        self.search_ring.pack(side="left", fill="x", expand=True, padx=(0, SPACE_3))

        self.search_entry = ctk.CTkEntry(
            self.search_ring,
            placeholder_text="Search tags, fields, or values...",
            height=30,
            corner_radius=RADIUS_SM,
            font=self.theme.font("mono"),
            fg_color=self.theme.pair("bg_surface"),
            border_color=self.theme.pair("border"),
            border_width=1,
            text_color=self.theme.pair("text_primary"),
        )
        self.search_entry.pack(fill="x", padx=4, pady=4)
        self.search_entry.bind("<KeyRelease>", lambda _e: self._rebuild_table())
        try:
            self.search_entry._entry.bind(
                "<FocusIn>",
                lambda _e: self.search_ring.configure(border_color=self.theme.pair("accent")),
                add="+",
            )
            self.search_entry._entry.bind(
                "<FocusOut>",
                lambda _e: self.search_ring.configure(border_color=self.theme.pair("bg_main")),
                add="+",
            )
        except Exception:
            pass

        self.raw_switch = ctk.CTkSwitch(
            self.toolbar,
            text="RAW TAGS",
            variable=self._raw_var,
            command=self._rebuild_table,
            font=self.theme.font("label"),
            text_color=self.theme.pair("text_secondary"),
            progress_color=self.theme.pair("accent"),
            button_color=self.theme.pair("text_primary"),
            button_hover_color=self.theme.pair("text_primary"),
            fg_color=self.theme.pair("border_strong"),
        )
        self.raw_switch.pack(side="right")
        Tooltip(
            self.raw_switch,
            "Show original EXIF tag identifiers and unformatted raw tag values",
            self.theme,
        )

    def _build_body(self) -> None:
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=SPACE_6, pady=SPACE_3)

        self.empty_card = SurfaceCard(self.content_area, self.theme)
        inner = ctk.CTkFrame(self.empty_card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.48, anchor="center")

        self.empty_title = ctk.CTkLabel(
            inner,
            text="No image loaded",
            font=self.theme.font("section_heading"),
            text_color=self.theme.pair("text_primary"),
        )
        self.empty_title.pack(pady=(0, SPACE_1))

        self.empty_desc = ctk.CTkLabel(
            inner,
            text="Open an image to inspect its EXIF camera, exposure, timestamp, and location tags.",
            font=self.theme.font("secondary"),
            text_color=self.theme.pair("text_secondary"),
            justify="center",
            wraplength=440,
        )
        self.empty_desc.pack(pady=(0, SPACE_4))

        make_primary_button(
            inner,
            self.theme,
            text="Open Image",
            command=self.on_open_image,
            width=124,
            host_bg="bg_surface",
        ).pack()

        self.scroll_area = ctk.CTkScrollableFrame(
            self.content_area,
            fg_color="transparent",
            corner_radius=0,
        )

    def show_empty(self) -> None:
        """Reset EXIF view to empty state."""
        self._record = None
        self._selected_value = None
        self._selected_label = None
        self.subtitle_label.configure(
            text="Explore camera, exposure, timestamp, location, and image metadata.",
            font=self.theme.font("secondary"),
        )
        self.toolbar.pack_forget()
        self.scroll_area.pack_forget()
        self.empty_title.configure(text="No image loaded")
        self.empty_desc.configure(
            text="Open an image to inspect its EXIF camera, exposure, timestamp, and location tags."
        )
        self.empty_card.pack(fill="both", expand=True)
        self.btn_copy_val.configure(state="disabled")
        self.btn_copy_all.configure(state="disabled")
        self.btn_export.configure(state="disabled")

    def display_record(self, record: ImageRecord) -> None:
        """Populate EXIF viewer with extracted metadata from ImageRecord."""
        self._record = record
        self._selected_value = None
        self._selected_label = None
        self.subtitle_label.configure(
            text=record.properties.file_name,
            font=self.theme.font("mono"),
        )
        self.btn_export.configure(state="normal")

        if not record.exif.has_exif:
            self.toolbar.pack_forget()
            self.scroll_area.pack_forget()
            self.empty_title.configure(text="No EXIF metadata available")
            self.empty_desc.configure(
                text=(
                    f"'{record.properties.file_name}' contains no EXIF metadata.\n"
                    "Screenshots, PNG graphics, and web-optimized exports often omit EXIF tags."
                )
            )
            self.empty_card.pack(fill="both", expand=True)
            self.btn_copy_val.configure(state="disabled")
            self.btn_copy_all.configure(state="disabled")
            return

        self.empty_card.pack_forget()
        self.toolbar.pack(fill="x", padx=SPACE_6, pady=(SPACE_2, 0), before=self.content_area)
        self.scroll_area.pack(fill="both", expand=True)
        self.btn_copy_val.configure(state="disabled")
        self.btn_copy_all.configure(state="normal")
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        if self._record is None or not self._record.exif.has_exif:
            return

        for child in self.scroll_area.winfo_children():
            child.destroy()

        self._row_frames.clear()
        self._visible_rows_text.clear()
        self._selected_value = None
        self._selected_label = None
        self.btn_copy_val.configure(state="disabled")

        exif = self._record.exif
        query = self.search_entry.get().strip().lower()
        show_raw = self._raw_var.get()

        if exif.has_gps:
            NoticeBanner(
                self.scroll_area,
                self.theme,
                "Privacy notice: GPS metadata below may reveal where this photograph was captured.",
            ).pack(fill="x", pady=(0, SPACE_3))

        by_section: dict[str, list[ExifEntry]] = {sec: [] for sec in SECTION_ORDER}
        for entry in exif.entries:
            if query:
                haystack = f"{entry.section} {entry.label} {entry.value} {entry.raw_tag} {entry.raw_value}".lower()
                if query not in haystack:
                    continue
            by_section.setdefault(entry.section, []).append(entry)

        any_rendered = False
        for section in SECTION_ORDER:
            entries = by_section.get(section, [])
            if not entries:
                continue
            any_rendered = True
            self._render_section_card(section, entries, show_raw)

        if show_raw and exif.raw_tags:
            mapped_raw_tags = {e.raw_tag for e in exif.entries}
            extra_raw = []
            for tag_name, tag_val in sorted(exif.raw_tags.items()):
                if tag_name in mapped_raw_tags:
                    continue
                if query and query not in f"{tag_name} {tag_val}".lower():
                    continue
                extra_raw.append(
                    ExifEntry(
                        section="Additional Raw Tags",
                        label=tag_name,
                        value=tag_val,
                        raw_tag=tag_name,
                        raw_value=tag_val,
                    )
                )
            if extra_raw:
                any_rendered = True
                self._render_section_card("Additional Raw Tags", extra_raw, show_raw=True)

        if not any_rendered:
            NoticeBanner(
                self.scroll_area,
                self.theme,
                f"No metadata fields matched '{self.search_entry.get().strip()}'.",
            ).pack(fill="x", pady=SPACE_2)
            self.btn_copy_all.configure(state="disabled")
        else:
            self.btn_copy_all.configure(state="normal")

    def _render_section_card(
        self,
        title: str,
        entries: list[ExifEntry],
        show_raw: bool,
    ) -> None:
        card = SurfaceCard(
            self.scroll_area,
            self.theme,
            title=title,
            subtitle=f"{len(entries)} TAG{'S' if len(entries) != 1 else ''}",
        )
        card.pack(fill="x", pady=(0, SPACE_3))

        hdr = ctk.CTkFrame(card, fg_color=self.theme.pair("bg_surface_alt"), corner_radius=RADIUS_SM)
        hdr.pack(fill="x", padx=SPACE_3, pady=(0, SPACE_1))

        ctk.CTkLabel(
            hdr,
            text="FIELD",
            font=self.theme.font("label"),
            text_color=self.theme.pair("text_secondary"),
            width=190,
            anchor="w",
        ).pack(side="left", padx=(SPACE_2, SPACE_2), pady=5)

        ctk.CTkLabel(
            hdr,
            text="VALUE",
            font=self.theme.font("label"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(0, SPACE_2), pady=5)

        if show_raw:
            ctk.CTkLabel(
                hdr,
                text="RAW TAG / VALUE",
                font=self.theme.font("label"),
                text_color=self.theme.pair("text_secondary"),
                width=240,
                anchor="w",
            ).pack(side="right", padx=(0, 56), pady=5)

        for idx, entry in enumerate(entries):
            row = ctk.CTkFrame(card, fg_color="transparent", corner_radius=RADIUS_SM)
            row.pack(fill="x", padx=SPACE_3, pady=1)

            copy_val = entry.raw_value if (show_raw and title == "Additional Raw Tags") else entry.value
            self._visible_rows_text.append(f"{entry.label}: {entry.value}")

            lbl_field = ctk.CTkLabel(
                row,
                text=entry.label.upper(),
                font=self.theme.font("label"),
                text_color=self.theme.pair("text_secondary"),
                width=190,
                anchor="w",
            )
            lbl_field.pack(side="left", padx=(SPACE_2, SPACE_2), pady=5)

            lbl_val = ctk.CTkLabel(
                row,
                text=entry.value,
                font=self.theme.font("mono"),
                text_color=self.theme.pair("text_primary"),
                anchor="w",
                justify="left",
                wraplength=320 if show_raw else 500,
            )
            lbl_val.pack(side="left", fill="x", expand=True, padx=(0, SPACE_2), pady=5)

            copy_btn = ctk.CTkButton(
                row,
                text="Copy",
                width=48,
                height=24,
                corner_radius=RADIUS_SM,
                font=self.theme.font("mono_sm"),
                fg_color="transparent",
                hover_color=self.theme.pair("bg_hover"),
                border_color=self.theme.pair("border"),
                border_width=1,
                text_color=self.theme.pair("text_secondary"),
                command=lambda v=copy_val, lb=entry.label: self._copy_specific(lb, v),
            )
            copy_btn.pack(side="right", padx=(6, 4), pady=4)

            if show_raw:
                raw_text = f"{entry.raw_tag} = {entry.raw_value}"
                lbl_raw = ctk.CTkLabel(
                    row,
                    text=raw_text,
                    font=self.theme.font("mono_sm"),
                    text_color=self.theme.pair("text_muted"),
                    width=235,
                    anchor="w",
                    justify="left",
                    wraplength=230,
                )
                lbl_raw.pack(side="right", padx=(4, 4), pady=5)
                for w in (row, lbl_field, lbl_val, lbl_raw):
                    w.bind(
                        "<Button-1>",
                        lambda _e, r=row, lb=entry.label, v=copy_val: self._select_row(r, lb, v),
                    )
            else:
                for w in (row, lbl_field, lbl_val):
                    w.bind(
                        "<Button-1>",
                        lambda _e, r=row, lb=entry.label, v=copy_val: self._select_row(r, lb, v),
                    )

            self._row_frames.append((row, copy_val))

            if idx < len(entries) - 1:
                ctk.CTkFrame(
                    card,
                    height=1,
                    fg_color=self.theme.pair("border"),
                    corner_radius=0,
                ).pack(fill="x", padx=SPACE_4)

        ctk.CTkFrame(card, height=SPACE_2, fg_color="transparent").pack()

    def _select_row(self, selected_row: ctk.CTkFrame, label: str, value: str) -> None:
        for row, _ in self._row_frames:
            row.configure(
                fg_color=self.theme.pair("bg_selected") if row is selected_row else "transparent"
            )
        self._selected_label = label
        self._selected_value = value
        self.btn_copy_val.configure(state="normal")

    def _copy_specific(self, label: str, value: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(value)
        self.on_status(f"Copied '{label}' to clipboard.")

    def _copy_selected_value(self) -> None:
        if self._selected_value is None:
            return
        self._copy_specific(self._selected_label or "value", self._selected_value)

    def _copy_all_values(self) -> None:
        if not self._visible_rows_text:
            return
        text = "\n".join(self._visible_rows_text)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.on_status(f"Copied {len(self._visible_rows_text)} metadata fields to clipboard.")

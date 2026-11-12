"""Batch Analysis page: multi-file/folder scanning, filtering, sorting, and export."""

from __future__ import annotations

import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

import customtkinter as ctk

from app.core.batch_processor import (
    BatchItem,
    BatchProcessor,
    BatchResult,
    compute_batch_summary,
    filter_batch_items,
    sort_batch_items,
)
from app.core.exporter import ExportError, export_batch_csv, export_batch_json
from app.ui.components import (
    SurfaceCard,
    Tooltip,
    ask_export_destination,
    ask_open_multiple_images_dialog,
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
from app.utils.file_utils import ImageFileError, collect_image_files
from app.utils.formatters import format_file_size, sanitize_error_message

COLUMNS: tuple[tuple[str, str, int, str], ...] = (
    ("file_name", "FILE NAME", 190, "w"),
    ("file_format", "FORMAT", 72, "center"),
    ("file_size_bytes", "SIZE", 90, "e"),
    ("width", "WIDTH", 72, "e"),
    ("height", "HEIGHT", 72, "e"),
    ("aspect_ratio", "ASPECT RATIO", 115, "center"),
    ("camera_model", "CAMERA MODEL", 160, "w"),
    ("capture_date", "CAPTURE DATE", 148, "center"),
    ("has_gps", "GPS", 60, "center"),
)


class BatchPage(ctk.CTkFrame):
    """Batch folder and multi-image metadata scanner with sortable results table."""

    def __init__(
        self,
        master: tk.Misc,
        theme: ThemeManager,
        get_default_export_format: Callable[[], str],
        on_open_in_inspector: Callable[[Path], None],
        on_status: Callable[[str], None],
        on_error: Callable[[str, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.theme = theme
        self.get_default_export_format = get_default_export_format
        self.on_open_in_inspector = on_open_in_inspector
        self.on_status = on_status
        self.on_error = on_error

        self.processor = BatchProcessor()
        self._event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._polling = False
        self._all_items: list[BatchItem] = []
        self._visible_items: list[BatchItem] = []
        self._scan_errors: list[tuple[str, str]] = []
        self._sort_col = "file_name"
        self._sort_asc = True
        self._hovered_iid: str | None = None

        self._format_var = tk.StringVar(value="All")
        self._exif_var = tk.StringVar(value="All")
        self._gps_var = tk.StringVar(value="All")

        self._build_header()
        self._build_progress_strip()
        self._build_summary_strip()
        self._build_filter_bar()
        self._build_table()
        self.refresh_theme()
        self._update_controls_state(scanning=False)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACE_6, pady=(SPACE_4, SPACE_3))

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_block,
            text="Batch Analysis",
            font=self.theme.font("page_title"),
            text_color=self.theme.pair("text_primary"),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_block,
            text="Scan multiple images or a folder to summarize formats, EXIF, and GPS presence.",
            font=self.theme.font("secondary"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right", anchor="center")

        self.btn_cancel = make_secondary_button(
            actions,
            self.theme,
            text="Cancel",
            command=self._cancel_scan,
            width=80,
            tooltip="Cancel the active batch scan",
        )
        self.btn_cancel.pack(side="left", padx=(0, SPACE_1))

        self.btn_export = make_secondary_button(
            actions,
            self.theme,
            text="Export",
            command=self._export_batch,
            width=82,
            tooltip="Export scanned metadata table to JSON or CSV",
        )
        self.btn_export.pack(side="left", padx=(0, SPACE_1))

        self.btn_files = make_secondary_button(
            actions,
            self.theme,
            text="Select Images",
            command=self._select_images,
            width=112,
        )
        self.btn_files.pack(side="left", padx=(0, SPACE_1))

        self.btn_folder = make_primary_button(
            actions,
            self.theme,
            text="Select Folder",
            command=self._select_folder,
            width=114,
        )
        self.btn_folder.pack(side="left")

        ctk.CTkFrame(
            self,
            height=1,
            fg_color=self.theme.pair("border"),
            corner_radius=0,
        ).pack(fill="x", padx=SPACE_6)

    def _build_progress_strip(self) -> None:
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=SPACE_6, pady=(SPACE_2, 0))

        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="Select images or a folder to begin batch analysis.",
            font=self.theme.font("mono_sm"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        )
        self.progress_label.pack(side="left", fill="x", expand=True)

        self.btn_warnings = ctk.CTkButton(
            self.progress_frame,
            text="Warnings",
            height=24,
            width=124,
            corner_radius=RADIUS_SM,
            font=self.theme.font("mono_sm"),
            fg_color=self.theme.pair("bg_notice"),
            hover_color=self.theme.pair("bg_hover"),
            border_color=self.theme.pair("border"),
            border_width=1,
            text_color=self.theme.pair("accent"),
            command=self._show_warnings,
        )

        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=3,
            corner_radius=2,
            fg_color=self.theme.pair("border"),
            progress_color=self.theme.pair("accent"),
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=SPACE_6, pady=(SPACE_1, SPACE_2))

    def _build_summary_strip(self) -> None:
        self.summary_card = SurfaceCard(self, self.theme)
        self.summary_card.pack(fill="x", padx=SPACE_6, pady=(0, SPACE_2))

        grid = ctk.CTkFrame(self.summary_card, fg_color="transparent")
        grid.pack(fill="x", padx=SPACE_4, pady=(SPACE_2, SPACE_1))
        for i in range(5):
            grid.grid_columnconfigure(i, weight=1, uniform="sum")

        self._metric_labels: dict[str, ctk.CTkLabel] = {}
        metrics = (
            ("total", "IMAGES SCANNED"),
            ("size", "TOTAL STORAGE"),
            ("avg_dim", "AVG DIMENSIONS"),
            ("exif", "WITH EXIF"),
            ("gps", "WITH GPS"),
        )
        for col, (key, title) in enumerate(metrics):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew")
            ctk.CTkLabel(
                cell,
                text=title,
                font=self.theme.font("label"),
                text_color=self.theme.pair("text_secondary"),
                anchor="w",
            ).pack(anchor="w")
            val_lbl = ctk.CTkLabel(
                cell,
                text="—",
                font=self.theme.font("mono", weight="bold"),
                text_color=self.theme.pair("accent" if key == "total" else "text_primary"),
                anchor="w",
            )
            val_lbl.pack(anchor="w", pady=(1, 0))
            self._metric_labels[key] = val_lbl

        self.format_dist_label = ctk.CTkLabel(
            self.summary_card,
            text="FORMATS // —",
            font=self.theme.font("mono_sm"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        )
        self.format_dist_label.pack(fill="x", padx=SPACE_4, pady=(2, SPACE_2))

    def _build_filter_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=SPACE_6, pady=(0, SPACE_2))

        menu_style = {
            "height": 28,
            "corner_radius": RADIUS_SM,
            "font": self.theme.font("mono_sm"),
            "fg_color": self.theme.pair("bg_surface"),
            "button_color": self.theme.pair("border"),
            "button_hover_color": self.theme.pair("border_hover"),
            "text_color": self.theme.pair("text_primary"),
            "dropdown_fg_color": self.theme.pair("bg_surface"),
            "dropdown_hover_color": self.theme.pair("bg_hover"),
            "dropdown_text_color": self.theme.pair("text_primary"),
        }

        ctk.CTkLabel(
            bar,
            text="FORMAT",
            font=self.theme.font("label"),
            text_color=self.theme.pair("text_secondary"),
        ).pack(side="left", padx=(0, 6))

        self.format_menu = ctk.CTkOptionMenu(
            bar,
            variable=self._format_var,
            values=["All"],
            width=96,
            command=lambda _v: self._apply_filters_and_sort(),
            **menu_style,
        )
        self.format_menu.pack(side="left", padx=(0, SPACE_3))

        ctk.CTkLabel(
            bar,
            text="EXIF",
            font=self.theme.font("label"),
            text_color=self.theme.pair("text_secondary"),
        ).pack(side="left", padx=(0, 6))

        self.exif_menu = ctk.CTkOptionMenu(
            bar,
            variable=self._exif_var,
            values=["All", "With EXIF", "Without EXIF"],
            width=120,
            command=lambda _v: self._apply_filters_and_sort(),
            **menu_style,
        )
        self.exif_menu.pack(side="left", padx=(0, SPACE_3))

        ctk.CTkLabel(
            bar,
            text="GPS",
            font=self.theme.font("label"),
            text_color=self.theme.pair("text_secondary"),
        ).pack(side="left", padx=(0, 6))

        self.gps_menu = ctk.CTkOptionMenu(
            bar,
            variable=self._gps_var,
            values=["All", "With GPS", "Without GPS"],
            width=116,
            command=lambda _v: self._apply_filters_and_sort(),
            **menu_style,
        )
        self.gps_menu.pack(side="left", padx=(0, SPACE_2))

        make_secondary_button(
            bar,
            self.theme,
            text="Reset",
            command=self._reset_filters,
            width=66,
        ).pack(side="left")

        self.count_label = ctk.CTkLabel(
            bar,
            text="0 IMAGES",
            font=self.theme.font("mono_sm"),
            text_color=self.theme.pair("text_secondary"),
            anchor="e",
        )
        self.count_label.pack(side="right")

    def _build_table(self) -> None:
        self.table_card = SurfaceCard(self, self.theme)
        self.table_card.pack(fill="both", expand=True, padx=SPACE_6, pady=(0, SPACE_3))

        inner = ctk.CTkFrame(self.table_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        col_ids = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(
            inner,
            columns=col_ids,
            show="headings",
            selectmode="browse",
            style="Batch.Treeview",
        )

        for col_id, title, width, anchor in COLUMNS:
            self.tree.heading(
                col_id,
                text=title,
                anchor=anchor,
                command=lambda c=col_id: self._toggle_sort(c),
            )
            self.tree.column(col_id, width=width, minwidth=55, anchor=anchor)

        y_scroll = ctk.CTkScrollbar(inner, orientation="vertical", command=self.tree.yview)
        x_scroll = ctk.CTkScrollbar(inner, orientation="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns", padx=(2, 0))
        x_scroll.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._on_row_double_click)
        self.tree.bind("<Motion>", self._on_tree_hover)
        self.tree.bind("<Leave>", self._on_tree_leave)
        Tooltip(
            self.tree,
            "Click column headers to sort. Double-click a row to inspect that image.",
            self.theme,
            delay_ms=900,
        )

    def refresh_theme(self) -> None:
        """Apply current tokens to ttk.Treeview without zebra striping."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        bg = self.theme.color("bg_surface")
        bg_hdr = self.theme.color("bg_surface_alt")
        fg = self.theme.color("text_primary")
        fg_hdr = self.theme.color("text_secondary")
        sel_bg = self.theme.color("bg_selected")
        border = self.theme.color("border")
        hover_bg = self.theme.color("bg_hover")

        style.configure(
            "Batch.Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            bordercolor=border,
            borderwidth=0,
            rowheight=28,
            font=(self.theme.mono_font, 9),
        )
        style.map(
            "Batch.Treeview",
            background=[("selected", sel_bg)],
            foreground=[("selected", fg)],
        )
        style.configure(
            "Batch.Treeview.Heading",
            background=bg_hdr,
            foreground=fg_hdr,
            bordercolor=border,
            relief="flat",
            padding=(8, 6),
            font=(self.theme.ui_medium_font, 9),
        )
        style.map(
            "Batch.Treeview.Heading",
            background=[("active", hover_bg)],
        )
        self.tree.tag_configure("hover", background=hover_bg)
        self.tree.tag_configure("row", background=bg)

    def clear_results(self) -> None:
        """Clear current batch results (used by Clear Session History)."""
        if self.processor.is_running:
            self.processor.cancel()
        self._all_items = []
        self._visible_items = []
        self._scan_errors = []
        self._format_var.set("All")
        self._exif_var.set("All")
        self._gps_var.set("All")
        self.format_menu.configure(values=["All"])
        self.progress_bar.set(0)
        self.progress_label.configure(text="Select images or a folder to begin batch analysis.")
        self.btn_warnings.pack_forget()
        self._update_summary(compute_batch_summary([]))
        self._render_table([])
        self._update_controls_state(scanning=False)

    def _select_images(self) -> None:
        paths = ask_open_multiple_images_dialog(self)
        if not paths:
            return
        self._start_scan(paths)

    def _select_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="Select Folder to Scan")
        if not folder:
            return
        try:
            paths = collect_image_files(folder, recursive=True)
        except ImageFileError as exc:
            self.on_error("Folder Scan Error", sanitize_error_message(exc))
            return

        if not paths:
            self.on_error(
                "No Supported Images Found",
                "The selected folder does not contain any supported image files.",
            )
            self.progress_label.configure(text="No supported images found in selected folder.")
            return

        self._start_scan(paths)

    def _start_scan(self, paths: list[Path]) -> None:
        self._all_items = []
        self._visible_items = []
        self._scan_errors = []
        self.btn_warnings.pack_forget()
        self._render_table([])
        self._update_summary(compute_batch_summary([]))
        self._update_controls_state(scanning=True)
        self.progress_bar.set(0)
        self.progress_label.configure(text=f"Preparing scan: {len(paths)} file(s)...")

        def on_progress(current: int, total: int, name: str) -> None:
            self._event_queue.put(("progress", (current, total, name)))

        def on_complete(result: BatchResult) -> None:
            self._event_queue.put(("complete", result))

        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                break

        self.processor.start_async(
            paths,
            progress_callback=on_progress,
            completion_callback=on_complete,
        )
        self._start_queue_poll()

    def _start_queue_poll(self) -> None:
        if not self._polling:
            self._polling = True
            self.after(40, self._poll_queue)

    def _poll_queue(self) -> None:
        finished = False
        while True:
            try:
                kind, payload = self._event_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                current, total, name = payload  # type: ignore[misc]
                self._handle_progress(current, total, name)
            elif kind == "complete":
                self._handle_complete(payload)  # type: ignore[arg-type]
                finished = True

        if not finished and (self.processor.is_running or not self._event_queue.empty()):
            self.after(40, self._poll_queue)
        else:
            self._polling = False

    def _handle_progress(self, current: int, total: int, name: str) -> None:
        frac = (current / total) if total > 0 else 0.0
        self.progress_bar.set(frac)
        self.progress_label.configure(text=f"Scanning [{current}/{total}] {name}")

    def _handle_complete(self, result: BatchResult) -> None:
        self._all_items = result.items
        self._scan_errors = result.errors
        self._update_controls_state(scanning=False)

        formats = sorted({item.file_format for item in self._all_items})
        self.format_menu.configure(values=["All", *formats])
        if self._format_var.get() not in (["All"] + formats):
            self._format_var.set("All")

        self._update_summary(result.summary)
        self._apply_filters_and_sort()

        if result.cancelled:
            self.progress_label.configure(
                text=f"Cancelled — {len(result.items)} image(s) processed."
            )
            self.on_status(f"Batch scan cancelled ({len(result.items)} images processed).")
        else:
            self.progress_bar.set(1.0 if result.items else 0.0)
            err_note = f" ({len(result.errors)} failed)" if result.errors else ""
            self.progress_label.configure(
                text=f"Completed — {len(result.items)} image(s) scanned{err_note}."
            )
            self.on_status(f"Batch scan complete: {len(result.items)} image(s) analyzed.")

        if result.errors:
            self.btn_warnings.configure(text=f"Warnings ({len(result.errors)})")
            self.btn_warnings.pack(side="right")
        else:
            self.btn_warnings.pack_forget()

    def _cancel_scan(self) -> None:
        if self.processor.is_running:
            self.processor.cancel()
            self.progress_label.configure(text="Cancelling scan...")

    def _update_controls_state(self, scanning: bool) -> None:
        self.btn_cancel.configure(state="normal" if scanning else "disabled")
        self.btn_files.configure(state="disabled" if scanning else "normal")
        self.btn_folder.configure(state="disabled" if scanning else "normal")
        self.btn_export.configure(
            state="normal" if (not scanning and bool(self._all_items)) else "disabled"
        )

    def _update_summary(self, summary) -> None:
        if summary.total_scanned == 0:
            self._metric_labels["total"].configure(text="0")
            self._metric_labels["size"].configure(text="—")
            self._metric_labels["avg_dim"].configure(text="—")
            self._metric_labels["exif"].configure(text="0")
            self._metric_labels["gps"].configure(text="0")
            self.format_dist_label.configure(text="FORMATS // —")
            return

        self._metric_labels["total"].configure(text=f"{summary.total_scanned:,}")
        self._metric_labels["size"].configure(text=format_file_size(summary.total_size_bytes))
        self._metric_labels["avg_dim"].configure(
            text=f"{summary.avg_width:,} x {summary.avg_height:,} px"
        )
        self._metric_labels["exif"].configure(text=f"{summary.exif_count:,}")
        self._metric_labels["gps"].configure(text=f"{summary.gps_count:,}")

        dist = "  |  ".join(
            f"{fmt}: {cnt}" for fmt, cnt in summary.format_distribution.items()
        )
        self.format_dist_label.configure(text=f"FORMATS // {dist or '—'}")

    def _reset_filters(self) -> None:
        self._format_var.set("All")
        self._exif_var.set("All")
        self._gps_var.set("All")
        self._apply_filters_and_sort()

    def _toggle_sort(self, column: str) -> None:
        if self._sort_col == column:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = column
            self._sort_asc = True
        self._apply_filters_and_sort()

    def _apply_filters_and_sort(self) -> None:
        filtered = filter_batch_items(
            self._all_items,
            format_filter=self._format_var.get(),
            exif_filter=self._exif_var.get(),
            gps_filter=self._gps_var.get(),
        )
        sorted_items = sort_batch_items(
            filtered,
            sort_key=self._sort_col,
            ascending=self._sort_asc,
        )
        self._visible_items = sorted_items
        self._update_heading_indicators()
        self._render_table(sorted_items)

        total = len(self._all_items)
        shown = len(sorted_items)
        self.count_label.configure(
            text=f"{shown} / {total} IMAGES" if total else "0 IMAGES"
        )

    def _update_heading_indicators(self) -> None:
        arrow = " ^" if self._sort_asc else " v"
        for col_id, title, _, _ in COLUMNS:
            label = f"{title}{arrow}" if col_id == self._sort_col else title
            self.tree.heading(col_id, text=label)

    def _render_table(self, items: list[BatchItem]) -> None:
        self._hovered_iid = None
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        for idx, item in enumerate(items):
            values = (
                item.file_name,
                item.file_format,
                format_file_size(item.file_size_bytes),
                f"{item.width:,}",
                f"{item.height:,}",
                item.aspect_ratio,
                item.camera_model or "—",
                item.capture_date or "—",
                "Yes" if item.has_gps else "No",
            )
            self.tree.insert("", "end", iid=str(idx), values=values, tags=("row",))

    def _on_tree_hover(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid == self._hovered_iid:
            return
        if self._hovered_iid and self.tree.exists(self._hovered_iid):
            self.tree.item(self._hovered_iid, tags=("row",))
        self._hovered_iid = iid or None
        if self._hovered_iid and self.tree.exists(self._hovered_iid):
            self.tree.item(self._hovered_iid, tags=("hover",))

    def _on_tree_leave(self, _event: tk.Event) -> None:
        if self._hovered_iid and self.tree.exists(self._hovered_iid):
            self.tree.item(self._hovered_iid, tags=("row",))
        self._hovered_iid = None

    def _on_row_double_click(self, _event: tk.Event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self._visible_items):
            self.on_open_in_inspector(self._visible_items[idx].file_path)

    def _show_warnings(self) -> None:
        if not self._scan_errors:
            return
        preview_lines = [
            f"- {name}: {reason}" for name, reason in self._scan_errors[:12]
        ]
        if len(self._scan_errors) > 12:
            preview_lines.append(f"... and {len(self._scan_errors) - 12} more.")
        messagebox.showwarning(
            "Batch Scan Warnings",
            "Some files could not be processed:\n\n" + "\n".join(preview_lines),
            parent=self,
        )

    def _export_batch(self) -> None:
        if not self._visible_items and not self._all_items:
            return
        items_to_export = self._visible_items if self._visible_items else self._all_items
        dest = ask_export_destination(
            self,
            default_format=self.get_default_export_format(),
            suggested_stem="batch_metadata_export",
        )
        if dest is None:
            return
        out_path, fmt, overwrite = dest
        try:
            summary = compute_batch_summary(
                items_to_export, error_count=len(self._scan_errors)
            )
            if fmt == "csv":
                export_batch_csv(items_to_export, out_path, overwrite=overwrite)
            else:
                export_batch_json(
                    items_to_export, summary, out_path, overwrite=overwrite
                )
            self.on_status(f"Exported {len(items_to_export)} batch records to '{out_path.name}'.")
        except (ExportError, FileExistsError) as exc:
            self.on_error("Export Failed", sanitize_error_message(exc))

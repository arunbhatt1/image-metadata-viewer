"""Main CustomTkinter application window and page orchestration."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from app.config import (
    APP_NAME,
    ConfigManager,
    PreviewSize,
    ThemeMode,
    get_assets_dir,
    get_logger,
    setup_logging,
)
from app.core.exporter import ExportError, export_single_csv, export_single_json
from app.core.metadata_extractor import ImageRecord, extract_image_record
from app.ui.batch_page import BatchPage
from app.ui.compare_page import ComparePage
from app.ui.components import ask_export_destination, ask_open_image_dialog
from app.ui.exif_page import ExifPage
from app.ui.inspector_page import InspectorPage
from app.ui.settings_page import SettingsPage
from app.ui.sidebar import Sidebar
from app.ui.theme import ThemeManager
from app.utils.file_utils import ImageFileError
from app.utils.formatters import sanitize_error_message

logger = get_logger("application")


class ImageMetadataViewerApp(ctk.CTk):
    """Top-level desktop window coordinating navigation, state, and local processing."""

    def __init__(self, config_manager: ConfigManager | None = None) -> None:
        super().__init__()
        setup_logging()

        self.config_manager = config_manager or ConfigManager()
        self.theme = ThemeManager(mode=self.config_manager.settings.theme)
        self.theme.initialize(self)

        self.title(APP_NAME)
        self.geometry("1220x780")
        self.minsize(980, 640)
        self.configure(fg_color=self.theme.pair("bg_main"))
        self._apply_window_icon()
        self.after(100, self._apply_window_icon)

        self._current_record: ImageRecord | None = None
        self._active_page_key = "inspector"
        self._pages: dict[str, ctk.CTkFrame] = {}

        self._build_layout()
        self.bind_all("<Control-o>", lambda _e: self.open_image_dialog())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.navigate("inspector")

    def _build_layout(self) -> None:
        root_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        root_container.pack(fill="both", expand=True)

        self.sidebar = Sidebar(
            root_container,
            theme=self.theme,
            on_navigate=self.navigate,
        )
        self.sidebar.pack(side="left", fill="y")

        right_pane = ctk.CTkFrame(
            root_container,
            fg_color=self.theme.pair("bg_main"),
            corner_radius=0,
        )
        right_pane.pack(side="left", fill="both", expand=True)

        self.page_host = ctk.CTkFrame(
            right_pane,
            fg_color=self.theme.pair("bg_main"),
            corner_radius=0,
        )
        self.page_host.pack(fill="both", expand=True)

        # Status bar at bottom (monospace 11px + amber dot for Offline / Read-Only)
        ctk.CTkFrame(
            right_pane,
            height=1,
            fg_color=self.theme.pair("border"),
            corner_radius=0,
        ).pack(fill="x")

        status_bar = ctk.CTkFrame(
            right_pane,
            height=26,
            fg_color=self.theme.pair("bg_sidebar"),
            corner_radius=0,
        )
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_bar,
            text="Ready — local read-only mode",
            font=self.theme.font("mono_sm"),
            text_color=self.theme.pair("text_secondary"),
            anchor="w",
        )
        self.status_label.pack(side="left", padx=16)

        badge_box = ctk.CTkFrame(status_bar, fg_color="transparent")
        badge_box.pack(side="right", padx=16)

        self.status_dot = ctk.CTkFrame(
            badge_box,
            width=6,
            height=6,
            corner_radius=3,
            fg_color=self.theme.pair("accent"),
        )
        self.status_dot.pack(side="left", padx=(0, 6), pady=10)
        self.status_dot.pack_propagate(False)

        self.privacy_badge = ctk.CTkLabel(
            badge_box,
            text="Offline / Read-Only",
            font=self.theme.font("mono_sm"),
            text_color=self.theme.pair("text_secondary"),
            anchor="e",
        )
        self.privacy_badge.pack(side="left")

        # Initialize pages
        self.inspector_page = InspectorPage(
            self.page_host,
            theme=self.theme,
            on_open_image=self.open_image_dialog,
            on_view_exif=lambda: self.navigate("exif"),
            on_export=self.export_current_image,
            get_preview_max_px=self.config_manager.get_preview_max_px,
        )
        self.exif_page = ExifPage(
            self.page_host,
            theme=self.theme,
            on_open_image=self.open_image_dialog,
            on_export=self.export_current_image,
            on_status=self.set_status,
        )
        self.batch_page = BatchPage(
            self.page_host,
            theme=self.theme,
            get_default_export_format=lambda: self.config_manager.settings.default_export_format,
            on_open_in_inspector=self._open_from_batch,
            on_status=self.set_status,
            on_error=self.show_error,
        )
        self.compare_page = ComparePage(
            self.page_host,
            theme=self.theme,
            on_status=self.set_status,
            on_error=self.show_error,
        )
        self.settings_page = SettingsPage(
            self.page_host,
            theme=self.theme,
            config_manager=self.config_manager,
            on_theme_changed=self._on_theme_changed,
            on_preview_size_changed=self._on_preview_size_changed,
            on_clear_session=self.clear_session_history,
            on_status=self.set_status,
        )

        self._pages = {
            "inspector": self.inspector_page,
            "exif": self.exif_page,
            "batch": self.batch_page,
            "compare": self.compare_page,
            "settings": self.settings_page,
        }

    def navigate(self, page_key: str) -> None:
        """Switch visible content page and sync sidebar highlight."""
        if page_key not in self._pages:
            return
        for key, frame in self._pages.items():
            if key == page_key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        self._active_page_key = page_key
        self.sidebar.set_active(page_key)

    def set_status(self, message: str) -> None:
        """Update bottom status bar text."""
        self.status_label.configure(text=message)

    def show_error(self, title: str, message: str) -> None:
        """Display a clean user-facing error dialog without raw tracebacks."""
        messagebox.showerror(title, message, parent=self)
        self.set_status(f"Error: {message}")

    def open_image_dialog(self) -> None:
        """Prompt user for a single image file and load it."""
        path = ask_open_image_dialog(self)
        if path is None:
            return
        self.load_image(path)

    def _open_from_batch(self, path: Path) -> None:
        if self.load_image(path):
            self.navigate("inspector")

    def load_image(self, path: Path) -> bool:
        """Load image properties, EXIF, and color analysis read-only."""
        try:
            record = extract_image_record(path, include_colors=True)
        except ImageFileError as exc:
            self.show_error("Unable to Open Image", sanitize_error_message(exc))
            return False
        except Exception as exc:
            logger.error("Unexpected image loading error: %s", type(exc).__name__)
            self.show_error(
                "Unable to Open Image",
                "The image could not be loaded. It may be corrupted or in an unsupported format.",
            )
            return False

        self._current_record = record
        self.inspector_page.display_record(record)
        self.exif_page.display_record(record)
        self.set_status(
            f"Loaded {record.properties.file_name}  ·  {record.properties.file_format}  ·  "
            f"{record.properties.width:,} x {record.properties.height:,} px"
        )
        return True

    def export_current_image(self) -> None:
        """Export metadata for the currently loaded image to JSON or CSV."""
        if self._current_record is None:
            return
        stem = f"{self._current_record.properties.file_path.stem}_metadata"
        dest = ask_export_destination(
            self,
            default_format=self.config_manager.settings.default_export_format,
            suggested_stem=stem,
        )
        if dest is None:
            return
        out_path, fmt, overwrite = dest
        try:
            if fmt == "csv":
                export_single_csv(self._current_record, out_path, overwrite=overwrite)
            else:
                export_single_json(self._current_record, out_path, overwrite=overwrite)
            self.set_status(f"Exported metadata to '{out_path.name}'.")
        except (ExportError, FileExistsError) as exc:
            self.show_error("Export Failed", sanitize_error_message(exc))

    def _on_theme_changed(self, mode: ThemeMode) -> None:
        self.theme.apply_mode(mode)
        self.after(30, self._refresh_themed_widgets)

    def _refresh_themed_widgets(self) -> None:
        self.sidebar.refresh_theme()
        self.inspector_page.refresh_theme()
        self.batch_page.refresh_theme()

    def _on_preview_size_changed(self, _size: PreviewSize) -> None:
        self.inspector_page.refresh_preview_size()

    def clear_session_history(self) -> None:
        """Clear all loaded images and scan results from memory."""
        self._current_record = None
        self.inspector_page.show_empty()
        self.exif_page.show_empty()
        self.batch_page.clear_results()
        self.compare_page.clear()
        self.set_status("Session history cleared.")

    def _apply_window_icon(self) -> None:
        """Apply custom precision-instrument icon when running on Windows."""
        icon_path = get_assets_dir() / "app_icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(default=str(icon_path))
            except Exception:
                pass

    def _on_close(self) -> None:
        if self.batch_page.processor.is_running:
            self.batch_page.processor.cancel()
        self.destroy()


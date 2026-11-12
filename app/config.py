"""Application configuration, theme definitions, and privacy-safe logging."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Literal

APP_NAME = "Image Metadata Viewer"
APP_VERSION = "1.0.0"

ThemeMode = Literal["light", "dark", "system"]
ExportFormat = Literal["json", "csv"]
PreviewSize = Literal["compact", "medium", "large"]

PREVIEW_SIZE_MAP: dict[str, int] = {
    "compact": 280,
    "medium": 360,
    "large": 480,
}

BASE_IMAGE_EXTENSIONS: tuple[str, ...] = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".tiff",
    ".tif",
    ".bmp",
    ".gif",
)

HEIF_EXTENSIONS: tuple[str, ...] = (".heic", ".heif")

# 250 MB safety threshold to avoid exhausting memory on abnormally massive files
MAX_SAFE_FILE_SIZE_BYTES = 250 * 1024 * 1024

DEFAULT_CONFIG_DIR = Path.home() / ".image_metadata_viewer"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "settings.json"
DEFAULT_LOG_DIR = DEFAULT_CONFIG_DIR / "logs"


def is_heif_supported() -> bool:
    """Return True if the optional pillow-heif decoder is installed and usable."""
    try:
        import pillow_heif  # type: ignore  # noqa: F401

        return True
    except ImportError:
        return False


def get_supported_extensions() -> tuple[str, ...]:
    """Return all supported image extensions based on available decoders."""
    if is_heif_supported():
        return BASE_IMAGE_EXTENSIONS + HEIF_EXTENSIONS
    return BASE_IMAGE_EXTENSIONS


@dataclass
class AppSettings:
    """User preferences persisted locally without any image or GPS data."""

    theme: ThemeMode = "dark"
    default_export_format: ExportFormat = "json"
    preview_size: PreviewSize = "medium"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        """Create validated AppSettings from a raw dictionary."""
        theme = data.get("theme", "dark")
        if theme not in ("light", "dark", "system"):
            theme = "dark"

        export_fmt = data.get("default_export_format", "json")
        if export_fmt not in ("json", "csv"):
            export_fmt = "json"

        preview_size = data.get("preview_size", "medium")
        if preview_size not in PREVIEW_SIZE_MAP:
            preview_size = "medium"

        return cls(
            theme=theme,
            default_export_format=export_fmt,
            preview_size=preview_size,
        )


class ConfigManager:
    """Manages loading and saving user preferences to a local JSON file."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or DEFAULT_CONFIG_FILE
        self.settings = self.load()

    def load(self) -> AppSettings:
        """Load settings from disk, returning defaults if missing or invalid."""
        try:
            if self.config_path.exists():
                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return AppSettings.from_dict(raw)
        except (OSError, json.JSONDecodeError):
            pass
        return AppSettings()

    def save(self, settings: AppSettings | None = None) -> bool:
        """Persist settings to disk safely. Never stores image or GPS data."""
        if settings is not None:
            self.settings = settings
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            payload = asdict(self.settings)
            self.config_path.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
            return True
        except OSError:
            return False

    def get_preview_max_px(self) -> int:
        """Return the configured maximum preview dimension in pixels."""
        return PREVIEW_SIZE_MAP.get(self.settings.preview_size, 440)


def setup_logging(log_dir: Path | None = None) -> logging.Logger:
    """Configure local rotating error logging without exposing sensitive metadata."""
    logger = logging.getLogger("image_metadata_viewer")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    target_dir = log_dir or DEFAULT_LOG_DIR
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            target_dir / "app.log",
            maxBytes=512 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return an application logger."""
    base = setup_logging()
    if name:
        return base.getChild(name)
    return base


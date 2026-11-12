"""Tests for local configuration persistence and privacy guarantees."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import AppSettings, ConfigManager, get_assets_dir
from app.ui.theme import DARK_TOKENS, LIGHT_TOKENS


def test_theme_tokens_share_consistent_keys() -> None:
    assert set(DARK_TOKENS.keys()) == set(LIGHT_TOKENS.keys())
    assert DARK_TOKENS["bg_main"] == "#0E0F11"
    assert DARK_TOKENS["accent"] == "#FFB020"
    assert LIGHT_TOKENS["bg_main"] == "#F7F7F5"
    assert LIGHT_TOKENS["accent"] == "#E69500"


def test_config_manager_persists_preferences_without_sensitive_fields(
    tmp_path: Path,
) -> None:
    cfg_path = tmp_path / "settings.json"
    manager = ConfigManager(config_path=cfg_path)
    assert manager.settings.theme == "dark"
    assert manager.settings.default_export_format == "json"
    assert manager.settings.preview_size == "medium"

    manager.settings = AppSettings(
        theme="light",
        default_export_format="csv",
        preview_size="large",
    )
    assert manager.save() is True

    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert set(raw.keys()) == {"theme", "default_export_format", "preview_size"}

    reloaded = ConfigManager(config_path=cfg_path)
    assert reloaded.settings.theme == "light"
    assert reloaded.settings.default_export_format == "csv"
    assert reloaded.settings.preview_size == "large"
    assert reloaded.get_preview_max_px() == 480


def test_get_assets_dir_source_and_frozen(monkeypatch, tmp_path: Path) -> None:
    assets_dir = get_assets_dir()
    assert (assets_dir / "app_icon.ico").exists()
    assert (assets_dir / "fonts").exists()

    monkeypatch.setattr("app.config.sys.frozen", True, raising=False)
    monkeypatch.setattr("app.config.sys._MEIPASS", str(tmp_path), raising=False)
    assert get_assets_dir() == tmp_path / "app" / "assets"


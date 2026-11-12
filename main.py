"""Entry point for Image Metadata Viewer desktop application."""

from __future__ import annotations

from app.application import ImageMetadataViewerApp


def main() -> None:
    """Launch the Image Metadata Viewer application."""
    app = ImageMetadataViewerApp()
    app.mainloop()


if __name__ == "__main__":
    main()


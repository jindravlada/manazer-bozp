"""Bezpečné otevření HTTPS odkazu v systémovém prohlížeči."""

from __future__ import annotations

from urllib.parse import urlparse

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget


def is_https_url(value: str | None) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def open_https_url(value: str | None, *, parent: QWidget | None = None) -> bool:
    text = str(value or "").strip()
    if not is_https_url(text):
        if parent is not None:
            QMessageBox.warning(
                parent,
                "Odkaz",
                "Otevřít lze jen odkaz se schématem HTTPS.",
            )
        return False
    return bool(QDesktopServices.openUrl(QUrl(text)))

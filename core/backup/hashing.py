"""SHA-256 pomocné funkce pro záložní balíčky (čtení po blocích)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def sha256_bytes(data: bytes) -> str:
    """Vrátí hex SHA-256 bytových dat."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """
    Spočítá SHA-256 souboru po blocích (ne načtením celého souboru do paměti).
    """
    if chunk_size < 1:
        raise ValueError("chunk_size musí být >= 1")
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def sha256_stream(stream: BinaryIO, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Spočítá SHA-256 z již otevřeného binárního streamu."""
    if chunk_size < 1:
        raise ValueError("chunk_size musí být >= 1")
    digest = hashlib.sha256()
    while True:
        block = stream.read(chunk_size)
        if not block:
            break
        digest.update(block)
    return digest.hexdigest()


def hashes_equal(expected: str | None, actual: str | None) -> bool:
    """Porovná očekávaný a skutečný hash (case-insensitive, strip)."""
    if expected is None or actual is None:
        return False
    left = str(expected).strip().lower()
    right = str(actual).strip().lower()
    if not left or not right:
        return False
    return left == right

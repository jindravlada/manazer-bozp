#!/usr/bin/env python3
"""Ověří SHA-256 linuxdeploy AppImage proti packaging/linuxdeploy.pin."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

_PIN_PATH = Path(__file__).resolve().parent / "linuxdeploy.pin"
_CHUNK_SIZE = 1024 * 1024


def expected_sha256(pin_path: Path = _PIN_PATH) -> str:
    for raw_line in pin_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("LINUXDEPLOY_SHA256="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise ValueError(f"Chybí LINUXDEPLOY_SHA256 v {pin_path}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_linuxdeploy(path: Path, *, pin_path: Path = _PIN_PATH) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Chybí linuxdeploy: {path}")
    expected = expected_sha256(pin_path)
    actual = file_sha256(path)
    if actual.lower() != expected.lower():
        raise ValueError(
            "SHA-256 linuxdeploy nesouhlasí.\n"
            f"očekáváno: {expected}\n"
            f"skutečné:  {actual}"
        )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Použití: verify_linuxdeploy.py CESTA", file=sys.stderr)
        return 2
    try:
        verify_linuxdeploy(Path(argv[1]))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

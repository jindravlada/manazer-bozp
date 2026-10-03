#!/usr/bin/env python3
"""Ověří nebo stáhne linuxdeploy AppImage podle packaging/linuxdeploy.pin."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

_PIN_PATH = Path(__file__).resolve().parent / "linuxdeploy.pin"
_CHUNK_SIZE = 1024 * 1024
_DOWNLOAD_TIMEOUT_SECONDS = 120


def load_pin(pin_path: Path = _PIN_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in pin_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def expected_sha256(pin_path: Path = _PIN_PATH) -> str:
    digest = load_pin(pin_path).get("LINUXDEPLOY_SHA256", "")
    if not digest:
        raise ValueError(f"Chybí LINUXDEPLOY_SHA256 v {pin_path}")
    return digest


def expected_url(pin_path: Path = _PIN_PATH) -> str:
    url = load_pin(pin_path).get("LINUXDEPLOY_URL", "")
    if not url:
        raise ValueError(f"Chybí LINUXDEPLOY_URL v {pin_path}")
    return url


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _hash_mismatch_message(expected: str, actual: str, *, downloaded: bool) -> str:
    if downloaded:
        lead = "SHA-256 staženého linuxdeploy nesouhlasí. Soubor nebude použit."
    else:
        lead = "SHA-256 linuxdeploy nesouhlasí. Místní soubor nebude použit."
    return f"{lead}\nočekáváno: {expected}\nskutečné:  {actual}"


def verify_linuxdeploy(path: Path, *, pin_path: Path = _PIN_PATH) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Chybí linuxdeploy: {path}")
    expected = expected_sha256(pin_path)
    actual = file_sha256(path)
    if actual.lower() != expected.lower():
        raise ValueError(_hash_mismatch_message(expected, actual, downloaded=False))


def download_url(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "manazer-bozp-build"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            with destination.open("wb") as handle:
                while True:
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
    except Exception as exc:
        raise OSError(f"Stažení linuxdeploy selhalo: {url}") from exc


def ensure_linuxdeploy(
    path: Path,
    *,
    pin_path: Path = _PIN_PATH,
    downloader=None,
) -> None:
    """Použije místní soubor se shodným hashem, jinak ho stáhne podle pinu."""
    expected = expected_sha256(pin_path)
    if path.is_file():
        actual = file_sha256(path)
        if actual.lower() != expected.lower():
            raise ValueError(_hash_mismatch_message(expected, actual, downloaded=False))
        print("Místní linuxdeploy odpovídá pinu.")
        return

    url = expected_url(pin_path)
    partial = path.with_name(path.name + ".partial")
    fetch = downloader or download_url
    try:
        fetch(url, partial)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        if isinstance(exc, ValueError) and str(exc).startswith("Stažení linuxdeploy selhalo"):
            raise
        raise ValueError(f"Stažení linuxdeploy selhalo: {url}") from exc

    if not partial.is_file():
        raise ValueError(f"Stažení linuxdeploy selhalo: {url}")

    actual = file_sha256(partial)
    if actual.lower() != expected.lower():
        partial.unlink(missing_ok=True)
        raise ValueError(_hash_mismatch_message(expected, actual, downloaded=True))

    partial.replace(path)
    path.chmod(path.stat().st_mode | 0o755)
    print("linuxdeploy stažen a SHA-256 ověřen.")


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    ensure = False
    if args and args[0] == "--ensure":
        ensure = True
        args = args[1:]
    if len(args) != 1:
        print(
            "Použití: verify_linuxdeploy.py [--ensure] CESTA",
            file=sys.stderr,
        )
        return 2
    try:
        if ensure:
            ensure_linuxdeploy(Path(args[0]))
        else:
            verify_linuxdeploy(Path(args[0]))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

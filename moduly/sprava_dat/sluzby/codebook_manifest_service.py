from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

from moduly.sprava_dat.sluzby.codebook_catalog_service import CodebookEntry

EXPORT_VERSION = 1
APPLICATION_NAME = "Manažer BOZP"
MANIFEST_FILENAME = "MANIFEST.json"
ZIP_PREFIX_CISELNIKY = "ciselniky/"
ZIP_PREFIX_DATABASE = "databaze-ciselniky/"
ZIP_PREFIX_BUNDLED = "vestavene/"


class CodebookManifestService:
    """Sestavení a ověření manifestu exportu číselníků."""

    def build_single_export_manifest(
        self,
        *,
        path: Path | str,
        entry: CodebookEntry,
        item_count: int,
    ) -> dict:
        source = Path(path)
        size_bytes = source.stat().st_size if source.is_file() else 0
        return {
            "export_type": "single",
            "path": str(source.resolve()),
            "file_name": source.name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "codebook_id": entry.codebook_id,
            "codebook_name": entry.name,
            "module": entry.module,
            "storage_type": entry.storage_type,
            "item_count": item_count,
            "size_bytes": size_bytes,
            "verified": source.is_file(),
        }

    def build_bulk_export_manifest(
        self,
        *,
        path: Path | str,
        entries: list[dict],
    ) -> dict:
        source = Path(path)
        size_bytes = source.stat().st_size if source.is_file() else 0
        return {
            "export_type": "bulk",
            "export_version": EXPORT_VERSION,
            "application": APPLICATION_NAME,
            "path": str(source.resolve()),
            "file_name": source.name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "codebook_count": len(entries),
            "size_bytes": size_bytes,
            "codebooks": entries,
            "verified": source.is_file(),
        }

    def verify_single_export(self, path: Path | str, entry: CodebookEntry | None = None) -> dict:
        source = Path(path)
        manifest: dict = {
            "path": str(source.resolve()),
            "verified": False,
            "verification_errors": [],
            "item_count": 0,
            "size_bytes": 0,
        }

        if not source.is_file():
            manifest["verification_errors"].append("Exportní soubor neexistuje.")
            return manifest

        manifest["size_bytes"] = source.stat().st_size
        manifest["file_name"] = source.name

        if entry is None:
            manifest["verified"] = True
            return manifest

        try:
            if entry.kind in {"json_workspace", "json_bundled"}:
                payload = json.loads(source.read_text(encoding="utf-8"))
                manifest["item_count"] = self._count_json_payload(payload, entry)
            elif entry.kind == "hardcoded":
                payload = json.loads(source.read_text(encoding="utf-8"))
                manifest["item_count"] = len(payload.get("items") or [])
            else:
                payload = json.loads(source.read_text(encoding="utf-8"))
                records = payload.get("records") or []
                manifest["item_count"] = len(records) if isinstance(records, list) else 0
        except (OSError, json.JSONDecodeError) as exc:
            manifest["verification_errors"].append(f"Exportní soubor nelze načíst: {exc}")

        manifest["verified"] = not manifest["verification_errors"]
        return manifest

    def verify_bulk_export(self, path: Path | str) -> dict:
        source = Path(path)
        manifest: dict = {
            "path": str(source.resolve()),
            "verified": False,
            "verification_errors": [],
            "codebook_count": 0,
            "size_bytes": 0,
            "codebooks": [],
        }

        if not source.is_file():
            manifest["verification_errors"].append("ZIP soubor neexistuje.")
            return manifest

        manifest["size_bytes"] = source.stat().st_size
        manifest["file_name"] = source.name

        try:
            with zipfile.ZipFile(source, "r") as zf:
                bad_file = zf.testzip()
                if bad_file:
                    manifest["verification_errors"].append(
                        f"Kontrolní součet ZIPu selhal u souboru: {bad_file}"
                    )

                if MANIFEST_FILENAME not in zf.namelist():
                    manifest["verification_errors"].append("ZIP neobsahuje manifest.")
                else:
                    payload = json.loads(zf.read(MANIFEST_FILENAME).decode("utf-8"))
                    if payload.get("export_version") != EXPORT_VERSION:
                        manifest["verification_errors"].append("Manifest má nepodporovanou verzi.")
                    codebooks = payload.get("codebooks") or []
                    if not isinstance(codebooks, list):
                        manifest["verification_errors"].append("Manifest neobsahuje seznam číselníků.")
                    else:
                        manifest["codebooks"] = codebooks
                        manifest["codebook_count"] = len(codebooks)
        except zipfile.BadZipFile:
            manifest["verification_errors"].append("ZIP soubor nelze otevřít.")
        except (OSError, json.JSONDecodeError) as exc:
            manifest["verification_errors"].append(f"Manifest nelze načíst: {exc}")

        manifest["verified"] = not manifest["verification_errors"]
        return manifest

    def rows_from_single_manifest(self, manifest: dict | None) -> list[tuple[str, str, str]]:
        if not manifest:
            return []

        status = "V pořádku" if manifest.get("verified") else "Problém"
        size = manifest.get("size_bytes", 0)
        return [
            ("Soubor", str(manifest.get("file_name") or Path(str(manifest.get("path") or "")).name), status),
            (
                "Datum",
                self._format_timestamp(str(manifest.get("created_at") or "")),
                status,
            ),
            ("Cesta", str(manifest.get("path") or "—"), status),
            ("Počet položek", str(manifest.get("item_count", 0)), status),
            ("Velikost souboru", self._format_size(size), status),
        ]

    def rows_from_bulk_manifest(self, manifest: dict | None) -> list[tuple[str, str, str]]:
        if not manifest:
            return []

        status = "V pořádku" if manifest.get("verified") else "Problém"
        rows = [
            ("Soubor", str(manifest.get("file_name") or "—"), status),
            (
                "Datum",
                self._format_timestamp(str(manifest.get("created_at") or "")),
                status,
            ),
            ("Cesta", str(manifest.get("path") or "—"), status),
            ("Počet číselníků", str(manifest.get("codebook_count", 0)), status),
            ("Velikost souboru", self._format_size(manifest.get("size_bytes", 0)), status),
        ]
        for item in manifest.get("codebooks") or []:
            if not isinstance(item, dict):
                continue
            rows.append(
                (
                    str(item.get("name") or item.get("codebook_id") or "—"),
                    f"{item.get('item_count', 0)} ({item.get('storage_type', '—')})",
                    status,
                )
            )
        return rows

    def entry_manifest_row(self, entry: CodebookEntry) -> dict:
        return {
            "codebook_id": entry.codebook_id,
            "name": entry.name,
            "module": entry.module,
            "item_count": entry.item_count,
            "storage_type": entry.storage_type,
        }

    def _count_json_payload(self, payload, entry: CodebookEntry) -> int:
        from moduly.sprava_dat.sluzby.codebook_catalog_service import codebook_catalog_service

        relative = entry.relative_path or ""
        if relative:
            path = Path(relative)
            return codebook_catalog_service._count_json_file(path, relative)
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            if "records" in payload:
                records = payload.get("records") or []
                return len(records) if isinstance(records, list) else 0
            if "items" in payload:
                items = payload.get("items") or []
                return len(items) if isinstance(items, list) else 0
        return 0

    @staticmethod
    def _format_timestamp(value: str) -> str:
        if not value:
            return "—"
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            return value

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KiB"
        return f"{size_bytes / (1024 * 1024):.1f} MiB"


codebook_manifest_service = CodebookManifestService()

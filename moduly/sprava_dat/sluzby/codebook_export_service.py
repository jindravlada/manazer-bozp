from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from core.database.session import get_session
from core.services.storage_service import storage_service
from moduly.kniha_urazu.services.ciselnik_service import kniha_urazu_ciselnik_service
from moduly.nastaveni.modely.employer import Employer
from moduly.nastaveni.modely.person import Person
from moduly.nastaveni.modely.responsibility_role import ResponsibilityRole
from moduly.nastaveni.modely.thp_worker import ThpWorker
from moduly.nastaveni.modely.workplace import Workplace
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.sprava_dat.sluzby.codebook_catalog_service import (
    CodebookEntry,
    codebook_catalog_service,
)
from moduly.sprava_dat.sluzby.codebook_manifest_service import (
    APPLICATION_NAME,
    EXPORT_VERSION,
    MANIFEST_FILENAME,
    ZIP_PREFIX_BUNDLED,
    ZIP_PREFIX_CISELNIKY,
    ZIP_PREFIX_DATABASE,
    codebook_manifest_service,
)


@dataclass(frozen=True)
class CodebookExportResult:
    path: Path
    manifest: dict
    item_count: int


class CodebookExportService:
    """Export jednotlivých číselníků a hromadný export do ZIP."""

    def default_single_export_path(self, entry: CodebookEntry) -> Path:
        storage_service.ensure_structure()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safe_name = self._safe_filename(entry.name)
        suffix = ".zip" if entry.kind == "bulk" else ".json"
        return storage_service.exports_dir / f"ciselnik-{safe_name}-{timestamp}{suffix}"

    def default_bulk_export_path(self) -> Path:
        storage_service.ensure_structure()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return storage_service.exports_dir / f"ciselniky-vse-{timestamp}.zip"

    def export_codebook(self, entry: CodebookEntry, target_path: Path | str) -> CodebookExportResult:
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if entry.kind == "json_workspace":
            source = Path(entry.path)
            shutil.copy2(source, target)
            item_count = entry.item_count
        elif entry.kind == "json_bundled":
            source = Path(entry.path)
            if not source.is_file():
                raise ValueError(f"Zdrojový soubor číselníku {entry.name} neexistuje.")
            shutil.copy2(source, target)
            item_count = entry.item_count
        elif entry.kind == "hardcoded":
            if entry.codebook_id == "hardcoded:zdravotni_pojistovny":
                items = kniha_urazu_ciselnik_service.zdravotni_pojistovny()
            elif entry.codebook_id == "hardcoded:okresy":
                items = kniha_urazu_ciselnik_service.okresy()
            else:
                items = []
            payload = {
                "codebook_id": entry.codebook_id,
                "name": entry.name,
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "items": items,
            }
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            item_count = len(items)
        elif entry.kind == "database":
            payload = self._export_database_payload(entry)
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            item_count = len(payload.get("records") or [])
        else:
            raise ValueError(f"Číselník {entry.name} nelze exportovat.")

        manifest = codebook_manifest_service.build_single_export_manifest(
            path=target,
            entry=entry,
            item_count=item_count,
        )
        return CodebookExportResult(path=target.resolve(), manifest=manifest, item_count=item_count)

    def export_all_codebooks(self, target_path: Path | str) -> CodebookExportResult:
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        entries = codebook_catalog_service.list_codebooks()
        manifest_entries: list[dict] = []

        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for entry in entries:
                if not entry.exportable:
                    continue

                try:
                    zip_path, item_count = self._write_entry_to_zip(zf, entry)
                except (OSError, ValueError):
                    continue

                row = codebook_manifest_service.entry_manifest_row(entry)
                row["path_in_zip"] = zip_path
                row["item_count"] = item_count
                manifest_entries.append(row)

            bulk_manifest = {
                "export_version": EXPORT_VERSION,
                "application": APPLICATION_NAME,
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "codebooks": manifest_entries,
            }
            zf.writestr(
                MANIFEST_FILENAME,
                json.dumps(bulk_manifest, ensure_ascii=False, indent=2) + "\n",
            )

        manifest = codebook_manifest_service.build_bulk_export_manifest(
            path=target,
            entries=manifest_entries,
        )
        verified = codebook_manifest_service.verify_bulk_export(target)
        manifest["verified"] = verified.get("verified", False)
        manifest["verification_errors"] = verified.get("verification_errors", [])
        return CodebookExportResult(
            path=target.resolve(),
            manifest=manifest,
            item_count=len(manifest_entries),
        )

    def _write_entry_to_zip(self, zf: zipfile.ZipFile, entry: CodebookEntry) -> tuple[str, int]:
        if entry.kind == "json_workspace" and entry.relative_path:
            source = Path(entry.path)
            zip_path = f"{ZIP_PREFIX_CISELNIKY}{entry.relative_path}"
            zf.write(source, zip_path)
            return zip_path, entry.item_count

        if entry.kind == "json_bundled" and entry.relative_path:
            source = Path(entry.path)
            if not source.is_file():
                raise ValueError(f"Zdrojový soubor číselníku {entry.name} neexistuje.")
            zip_path = f"{ZIP_PREFIX_BUNDLED}{entry.relative_path}"
            zf.write(source, zip_path)
            return zip_path, entry.item_count

        if entry.kind == "hardcoded":
            if entry.codebook_id == "hardcoded:zdravotni_pojistovny":
                items = kniha_urazu_ciselnik_service.zdravotni_pojistovny()
            elif entry.codebook_id == "hardcoded:okresy":
                items = kniha_urazu_ciselnik_service.okresy()
            else:
                items = []
            payload = {
                "codebook_id": entry.codebook_id,
                "name": entry.name,
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "items": items,
            }
            zip_path = f"{ZIP_PREFIX_BUNDLED}{entry.codebook_id.replace(':', '/')}.json"
            zf.writestr(
                zip_path,
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            )
            return zip_path, len(payload["items"])

        if entry.kind == "database":
            payload = self._export_database_payload(entry)
            table_name = entry.codebook_id.split(":", 1)[-1]
            zip_path = f"{ZIP_PREFIX_DATABASE}{table_name}.json"
            zf.writestr(
                zip_path,
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            )
            return zip_path, len(payload.get("records") or [])

        raise ValueError(f"Číselník {entry.name} nelze zahrnout do hromadného exportu.")

    def _export_database_payload(self, entry: CodebookEntry) -> dict:
        records = self._load_database_records(entry)
        return {
            "codebook_id": entry.codebook_id,
            "name": entry.name,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "records": records,
        }

    def _load_database_records(self, entry: CodebookEntry) -> list[dict]:
        if entry.codebook_id == "db:workplaces":
            return [self._model_to_dict(item) for item in settings_service.get_workplaces(include_inactive=True)]
        if entry.codebook_id == "db:thp_workers":
            return [self._model_to_dict(item) for item in settings_service.get_workers(include_inactive=True)]
        if entry.codebook_id == "db:employer":
            employer = settings_service.get_employer()
            return [self._model_to_dict(employer)] if employer is not None else []
        if entry.codebook_id == "db:responsibility_roles":
            return [
                self._model_to_dict(item)
                for item in responsibility_role_service.get_all(include_inactive=True)
            ]
        if entry.codebook_id == "db:persons":
            return [self._model_to_dict(item) for item in person_service.get_all(include_inactive=True)]
        if entry.codebook_id == "db:control_processes":
            return self._load_control_process_records()
        return []

    def _load_control_process_records(self) -> list[dict]:
        with get_session() as session:
            rows = session.scalars(
                select(LegalRequirement).where(LegalRequirement.parent_requirement_id.is_not(None))
            ).all()
            return [self._model_to_dict(row) for row in rows]

    @staticmethod
    def _model_to_dict(model) -> dict:
        result: dict = {}
        for column in model.__table__.columns:
            value = getattr(model, column.name)
            if isinstance(value, datetime):
                value = value.isoformat(timespec="seconds")
            result[column.name] = value
        return result

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = "".join(char if char.isalnum() else "-" for char in name.lower())
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-") or "ciselnik"


codebook_export_service = CodebookExportService()

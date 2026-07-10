from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.sprava_dat.sluzby.codebook_catalog_service import (
    CodebookEntry,
    codebook_catalog_service,
)
from moduly.sprava_dat.sluzby.codebook_manifest_service import (
    MANIFEST_FILENAME,
    ZIP_PREFIX_CISELNIKY,
    ZIP_PREFIX_DATABASE,
    codebook_manifest_service,
)


@dataclass
class CodebookImportSummary:
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "updated": list(self.updated),
            "skipped": list(self.skipped),
            "errors": list(self.errors),
            "updated_count": len(self.updated),
            "skipped_count": len(self.skipped),
            "error_count": len(self.errors),
        }


class CodebookImportService:
    """Import jednotlivých číselníků a hromadného ZIP balíčku."""

    def import_codebook(self, entry: CodebookEntry, source_path: Path | str) -> CodebookImportSummary:
        summary = CodebookImportSummary()
        source = Path(source_path)

        if not entry.importable:
            summary.skipped.append(f"{entry.name}: číselník nelze importovat.")
            return summary

        if not source.is_file():
            summary.errors.append(f"{entry.name}: soubor neexistuje.")
            return summary

        try:
            if entry.kind == "json_workspace" and entry.relative_path:
                target = Path(entry.path)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                summary.updated.append(entry.name)
            elif entry.kind == "database":
                payload = json.loads(source.read_text(encoding="utf-8"))
                self._import_database_payload(entry, payload, summary)
            else:
                summary.skipped.append(f"{entry.name}: nepodporovaný typ importu.")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            summary.errors.append(f"{entry.name}: {exc}")

        return summary

    def import_all_codebooks(self, source_path: Path | str) -> CodebookImportSummary:
        source = Path(source_path)
        summary = CodebookImportSummary()

        if not source.is_file():
            summary.errors.append("ZIP soubor neexistuje.")
            return summary

        manifest = codebook_manifest_service.verify_bulk_export(source)
        if not manifest.get("verified"):
            for error in manifest.get("verification_errors") or []:
                summary.errors.append(error)
            return summary

        codebooks_by_id = {
            entry.codebook_id: entry for entry in codebook_catalog_service.list_codebooks()
        }

        with zipfile.ZipFile(source, "r") as zf:
            for item in manifest.get("codebooks") or []:
                if not isinstance(item, dict):
                    continue
                codebook_id = str(item.get("codebook_id") or "")
                entry = codebooks_by_id.get(codebook_id)
                if entry is None:
                    summary.skipped.append(f"Neznámý číselník: {codebook_id}")
                    continue

                zip_inner_path = str(item.get("path_in_zip") or "")
                if not zip_inner_path or zip_inner_path not in zf.namelist():
                    summary.errors.append(f"{entry.name}: soubor v ZIP chybí.")
                    continue

                temp_dir = source.parent / ".codebook-import-temp"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_file = temp_dir / Path(zip_inner_path).name
                temp_file.write_bytes(zf.read(zip_inner_path))

                part = self.import_codebook(entry, temp_file)
                summary.updated.extend(part.updated)
                summary.skipped.extend(part.skipped)
                summary.errors.extend(part.errors)

                try:
                    temp_file.unlink(missing_ok=True)
                except OSError:
                    pass

        return summary

    def import_group_codebooks(self, module: str, source_path: Path | str) -> CodebookImportSummary:
        source = Path(source_path)
        summary = CodebookImportSummary()

        if not source.is_file():
            summary.errors.append("ZIP soubor neexistuje.")
            return summary

        manifest = codebook_manifest_service.verify_bulk_export(source)
        if not manifest.get("verified"):
            for error in manifest.get("verification_errors") or []:
                summary.errors.append(error)
            return summary

        group_entries = {
            entry.codebook_id: entry
            for entry in codebook_catalog_service.list_group_entries(module)
        }

        with zipfile.ZipFile(source, "r") as zf:
            for item in manifest.get("codebooks") or []:
                if not isinstance(item, dict):
                    continue
                codebook_id = str(item.get("codebook_id") or "")
                entry = group_entries.get(codebook_id)
                if entry is None:
                    summary.skipped.append(f"Mimo skupinu: {codebook_id}")
                    continue

                zip_inner_path = str(item.get("path_in_zip") or "")
                if not zip_inner_path or zip_inner_path not in zf.namelist():
                    summary.errors.append(f"{entry.name}: soubor v ZIP chybí.")
                    continue

                temp_dir = source.parent / ".codebook-import-temp"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_file = temp_dir / Path(zip_inner_path).name
                temp_file.write_bytes(zf.read(zip_inner_path))

                part = self.import_codebook(entry, temp_file)
                summary.updated.extend(part.updated)
                summary.skipped.extend(part.skipped)
                summary.errors.extend(part.errors)

                try:
                    temp_file.unlink(missing_ok=True)
                except OSError:
                    pass

        return summary

    def _import_database_payload(
        self,
        entry: CodebookEntry,
        payload: dict,
        summary: CodebookImportSummary,
    ) -> None:
        records = payload.get("records") or []
        if not isinstance(records, list):
            raise ValueError("Export neobsahuje platný seznam záznamů.")

        if entry.codebook_id == "db:workplaces":
            for record in records:
                settings_service.save_workplace(**record)
            summary.updated.append(entry.name)
            return

        if entry.codebook_id == "db:thp_workers":
            for record in records:
                settings_service.save_worker(**record)
            summary.updated.append(entry.name)
            return

        if entry.codebook_id == "db:employer":
            for record in records:
                settings_service.save_employer(**record)
            summary.updated.append(entry.name)
            return

        if entry.codebook_id == "db:responsibility_roles":
            for record in records:
                role_id = record.get("id")
                if role_id:
                    updated = responsibility_role_service.update_role(
                        role_id,
                        name=str(record.get("name") or ""),
                        description=str(record.get("description") or ""),
                        active=bool(record.get("active", True)),
                    )
                    if updated is None:
                        responsibility_role_service.create_role(
                            name=str(record.get("name") or ""),
                            description=str(record.get("description") or ""),
                            active=bool(record.get("active", True)),
                        )
                else:
                    responsibility_role_service.create_role(
                        name=str(record.get("name") or ""),
                        description=str(record.get("description") or ""),
                        active=bool(record.get("active", True)),
                    )
            summary.updated.append(entry.name)
            return

        if entry.codebook_id == "db:persons":
            for record in records:
                person_id = record.get("id")
                if person_id:
                    updated = person_service.update_person(person_id, **self._person_kwargs(record))
                    if updated is None:
                        person_service.create_person(**self._person_kwargs(record))
                else:
                    person_service.create_person(**self._person_kwargs(record))
            summary.updated.append(entry.name)
            return

        summary.skipped.append(f"{entry.name}: import databázového číselníku není podporován.")

    @staticmethod
    def _person_kwargs(record: dict) -> dict:
        return {
            "title_before": str(record.get("title_before") or ""),
            "first_name": str(record.get("first_name") or ""),
            "last_name": str(record.get("last_name") or ""),
            "title_after": str(record.get("title_after") or ""),
            "organization": str(record.get("organization") or ""),
            "job_title": str(record.get("job_title") or ""),
            "email": str(record.get("email") or ""),
            "phone": str(record.get("phone") or ""),
            "note": str(record.get("note") or ""),
            "active": bool(record.get("active", True)),
            "is_employee": bool(record.get("is_employee", False)),
        }


codebook_import_service = CodebookImportService()

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import delete, text

from core.database.session import get_session
from core.version import app_display_name, is_compatible_application_name
from moduly.pravni_pozadavky.import_export.legal_registry_export_service import EXPORT_VERSION
from moduly.pravni_pozadavky.modely.legal_change import LegalChange
from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.modely.legal_requirement_sanction import LegalRequirementSanction
from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
from moduly.pravni_pozadavky.modely.legal_section import LegalSection

SUPPORTED_EXPORT_VERSIONS = {1, 2}


@dataclass(frozen=True)
class LegalRegistryImportResult:
    document_count: int
    version_count: int
    section_count: int
    requirement_count: int
    source_count: int
    sanction_count: int
    check_run_count: int
    change_count: int
    change_section_count: int


class LegalRegistryImportService:
    def import_from_file(self, path: str | Path) -> LegalRegistryImportResult:
        data = self._load_data(path)
        self._validate_data(data)

        with get_session() as session:
            self._clear_registry_tables(session)
            documents = data.get("documents", [])
            versions = data.get("versions", [])
            sections = data.get("sections", [])
            requirements = data.get("requirements", [])
            sources = data.get("sources", [])
            sanctions = data.get("sanctions", [])
            check_runs = data.get("check_runs", [])
            changes = data.get("changes", [])
            change_sections = data.get("change_sections", [])

            document_max_id = self._import_documents(session, documents)
            version_max_id = self._import_versions(session, versions)
            section_max_id = self._import_sections(session, sections)
            requirement_max_id = self._import_requirements(session, requirements)
            source_max_id = self._import_sources(session, sources)
            sanction_max_id = self._import_sanctions(session, sanctions)
            check_run_max_id = self._import_check_runs(session, check_runs)
            change_max_id = self._import_changes(session, changes)
            change_section_max_id = self._import_change_sections(session, change_sections)
            self._update_sqlite_sequences(
                session,
                {
                    "legal_documents": document_max_id,
                    "legal_document_versions": version_max_id,
                    "legal_sections": section_max_id,
                    "legal_requirements": requirement_max_id,
                    "legal_requirement_sources": source_max_id,
                    "legal_requirement_sanctions": sanction_max_id,
                    "legal_check_runs": check_run_max_id,
                    "legal_changes": change_max_id,
                    "legal_change_sections": change_section_max_id,
                },
            )
            session.commit()

        return LegalRegistryImportResult(
            document_count=len(documents),
            version_count=len(versions),
            section_count=len(sections),
            requirement_count=len(requirements),
            source_count=len(sources),
            sanction_count=len(sanctions),
            check_run_count=len(check_runs),
            change_count=len(changes),
            change_section_count=len(change_sections),
        )

    def _load_data(self, path: str | Path) -> dict:
        file_path = Path(path)
        if not file_path.exists():
            raise ValueError("Soubor zálohy registru nebyl nalezen.")
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Soubor zálohy registru nelze načíst.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Soubor zálohy registru má neplatný formát.")
        return payload

    def _validate_data(self, data: dict) -> None:
        export_version = data.get("export_version")
        if export_version not in SUPPORTED_EXPORT_VERSIONS:
            raise ValueError("Soubor zálohy registru má nepodporovanou verzi exportu.")

        application = self._text(data.get("application"))
        if application and not is_compatible_application_name(application):
            raise ValueError(
                f"Soubor zálohy registru nepochází z {app_display_name()}."
            )

        for key in (
            "documents",
            "versions",
            "sections",
            "requirements",
            "sources",
            "sanctions",
            "check_runs",
            "changes",
            "change_sections",
        ):
            value = data.get(key, [])
            if value is None:
                continue
            if not isinstance(value, list):
                raise ValueError("Soubor zálohy registru má neplatný formát.")

    def _clear_registry_tables(self, session) -> None:
        session.execute(delete(LegalChangeSection))
        session.execute(delete(LegalChange))
        session.execute(delete(LegalCheckRun))
        session.execute(delete(LegalRequirementSanction))
        session.execute(delete(LegalRequirementSource))
        session.execute(delete(LegalRequirement))
        session.execute(delete(LegalSection))
        session.execute(delete(LegalDocumentVersion))
        session.execute(delete(LegalDocument))

    def _import_documents(self, session, records: list[dict]) -> int:
        max_id = 0
        for record in records:
            document = LegalDocument(
                id=record["id"],
                document_type=self._text(record.get("document_type")),
                number=self._text(record.get("number")),
                year=record.get("year"),
                title=self._text(record.get("title")),
                short_title=self._text(record.get("short_title")),
                valid_from=self._parse_date(record.get("valid_from")),
                valid_to=self._parse_date(record.get("valid_to")),
                effective_from=self._parse_date(record.get("effective_from")),
                effective_to=self._parse_date(record.get("effective_to")),
                source_url=self._text(record.get("source_url")),
                local_file_path=self._text(record.get("local_file_path")),
                note=self._text(record.get("note")),
                active=bool(record.get("active", True)),
                included_in_processes=bool(record.get("included_in_processes", False)),
                created_at=self._parse_datetime(record.get("created_at")) or datetime.now(),
                updated_at=self._parse_datetime(record.get("updated_at")) or datetime.now(),
            )
            session.add(document)
            max_id = max(max_id, document.id)
        return max_id

    def _import_versions(self, session, records: list[dict]) -> int:
        max_id = 0
        for record in records:
            version = LegalDocumentVersion(
                id=record["id"],
                legal_document_id=record["legal_document_id"],
                version_name=self._text(record.get("version_name")),
                valid_from=self._parse_date(record.get("valid_from")),
                valid_to=self._parse_date(record.get("valid_to")),
                effective_from=self._parse_date(record.get("effective_from")),
                effective_to=self._parse_date(record.get("effective_to")),
                publication_date=self._parse_date(record.get("publication_date")),
                source_url=self._text(record.get("source_url")),
                local_file_path=self._text(record.get("local_file_path")),
                checksum=self._text(record.get("checksum")),
                note=self._text(record.get("note")),
                pending_adoption=bool(record.get("pending_adoption", False)),
                active=bool(record.get("active", True)),
                created_at=self._parse_datetime(record.get("created_at")) or datetime.now(),
                updated_at=self._parse_datetime(record.get("updated_at")) or datetime.now(),
            )
            session.add(version)
            max_id = max(max_id, version.id)
        return max_id

    def _import_sections(self, session, records: list[dict]) -> int:
        max_id = 0
        for record in self._sort_by_parent(records, parent_key="parent_section_id"):
            section = LegalSection(
                id=record["id"],
                legal_document_id=record["legal_document_id"],
                legal_document_version_id=record["legal_document_version_id"],
                parent_section_id=record.get("parent_section_id"),
                section_type=self._text(record.get("section_type")),
                section_number=self._text(record.get("section_number")),
                paragraph=self._text(record.get("paragraph")),
                item_letter=self._text(record.get("item_letter")),
                title=self._text(record.get("title")),
                text=self._text(record.get("text")),
                sort_order=int(record.get("sort_order") or 0),
                note=self._text(record.get("note")),
                active=bool(record.get("active", True)),
                created_at=self._parse_datetime(record.get("created_at")) or datetime.now(),
                updated_at=self._parse_datetime(record.get("updated_at")) or datetime.now(),
            )
            session.add(section)
            max_id = max(max_id, section.id)
        return max_id

    def _import_requirements(self, session, records: list[dict]) -> int:
        max_id = 0
        for record in self._sort_by_parent(records, parent_key="parent_requirement_id"):
            requirement = LegalRequirement(
                id=record["id"],
                title=self._text(record.get("title")),
                process_code=self._text(record.get("process_code")),
                regulation_name=self._text(record.get("regulation_name")),
                regulation_number=self._text(record.get("regulation_number")),
                provision=self._text(record.get("provision")),
                area=self._text(record.get("area")),
                legal_document_id=record.get("legal_document_id"),
                legal_section_id=record.get("legal_section_id"),
                source_section_id=record.get("source_section_id"),
                requirement_summary=self._text(record.get("requirement_summary")),
                organization_impact=self._text(record.get("organization_impact")),
                responsible_person_id=record.get("responsible_person_id"),
                responsible_person_name=self._text(record.get("responsible_person_name")),
                responsible_role_id=record.get("responsible_role_id"),
                responsible_role_name=self._text(record.get("responsible_role_name")),
                verification_periodicity=self._text(record.get("verification_periodicity")),
                last_verification_date=self._parse_date(record.get("last_verification_date")),
                next_verification_date=self._parse_date(record.get("next_verification_date")),
                compliance_status=self._text(record.get("compliance_status")),
                processing_status=self._text(record.get("processing_status")),
                note=self._text(record.get("note")),
                active=bool(record.get("active", True)),
                merged_into_requirement_id=record.get("merged_into_requirement_id"),
                parent_requirement_id=record.get("parent_requirement_id"),
                created_at=self._parse_datetime(record.get("created_at")) or datetime.now(),
                updated_at=self._parse_datetime(record.get("updated_at")) or datetime.now(),
            )
            session.add(requirement)
            max_id = max(max_id, requirement.id)
        return max_id

    def _import_sources(self, session, records: list[dict]) -> int:
        max_id = 0
        for record in records:
            source = LegalRequirementSource(
                id=record["id"],
                requirement_id=record["requirement_id"],
                legal_section_id=record["legal_section_id"],
                sort_order=int(record.get("sort_order") or 0),
                created_at=self._parse_datetime(record.get("created_at")) or datetime.now(),
            )
            session.add(source)
            max_id = max(max_id, source.id)
        return max_id

    def _import_sanctions(self, session, records: list[dict]) -> int:
        max_id = 0
        for record in records:
            sanction = LegalRequirementSanction(
                id=record["id"],
                requirement_id=record["requirement_id"],
                authority=self._text(record.get("authority")),
                legal_reference=self._text(record.get("legal_reference")),
                description=self._text(record.get("description")),
                max_amount=self._parse_decimal(record.get("max_amount")),
                currency=self._text(record.get("currency")) or "Kč",
                note=self._text(record.get("note")),
                active=bool(record.get("active", True)),
                created_at=self._parse_datetime(record.get("created_at")) or datetime.now(),
                updated_at=self._parse_datetime(record.get("updated_at")) or datetime.now(),
            )
            session.add(sanction)
            max_id = max(max_id, sanction.id)
        return max_id

    def _import_check_runs(self, session, records: list[dict]) -> int:
        max_id = 0
        for record in records:
            period_from = self._parse_date(record.get("period_from"))
            period_to = self._parse_date(record.get("period_to"))
            if period_from is None or period_to is None:
                raise ValueError("Soubor zálohy registru má neplatný formát.")
            run = LegalCheckRun(
                id=record["id"],
                title=self._text(record.get("title")),
                period_from=period_from,
                period_to=period_to,
                checked_at=self._parse_datetime(record.get("checked_at")),
                checked_by=self._text(record.get("checked_by")),
                status=self._text(record.get("status")),
                note=self._text(record.get("note")),
                error_message=self._text(record.get("error_message")),
                started_at=self._parse_datetime(record.get("started_at")),
                documents_checked_count=record.get("documents_checked_count"),
                changes_found_count=record.get("changes_found_count"),
                active=bool(record.get("active", True)),
                created_at=self._parse_datetime(record.get("created_at")) or datetime.now(),
                updated_at=self._parse_datetime(record.get("updated_at")) or datetime.now(),
            )
            session.add(run)
            max_id = max(max_id, run.id)
        return max_id

    def _import_changes(self, session, records: list[dict]) -> int:
        max_id = 0
        for record in records:
            change = LegalChange(
                id=record["id"],
                legal_document_id=record["legal_document_id"],
                legal_document_version_id=record.get("legal_document_version_id"),
                new_legal_document_version_id=record.get("new_legal_document_version_id"),
                legal_section_id=record.get("legal_section_id"),
                legal_check_run_id=record.get("legal_check_run_id"),
                change_type=self._text(record.get("change_type")),
                title=self._text(record.get("title")),
                description=self._text(record.get("description")),
                published_at=self._parse_date(record.get("published_at")),
                effective_from=self._parse_date(record.get("effective_from")),
                evaluated=bool(record.get("evaluated", False)),
                evaluated_at=self._parse_datetime(record.get("evaluated_at")),
                evaluated_by=self._text(record.get("evaluated_by")),
                note=self._text(record.get("note")),
                evaluation_note=self._text(record.get("evaluation_note")),
                active=bool(record.get("active", True)),
                created_at=self._parse_datetime(record.get("created_at")) or datetime.now(),
                updated_at=self._parse_datetime(record.get("updated_at")) or datetime.now(),
            )
            session.add(change)
            max_id = max(max_id, change.id)
        return max_id

    def _import_change_sections(self, session, records: list[dict]) -> int:
        max_id = 0
        for record in records:
            section = LegalChangeSection(
                id=record["id"],
                legal_change_id=record["legal_change_id"],
                section_key=self._text(record.get("section_key")),
                section_label=self._text(record.get("section_label")),
                change_type=self._text(record.get("change_type")),
                old_text=record.get("old_text"),
                new_text=record.get("new_text"),
                note=record.get("note"),
                created_at=self._parse_datetime(record.get("created_at")) or datetime.now(),
            )
            session.add(section)
            max_id = max(max_id, section.id)
        return max_id

    def _sort_by_parent(
        self,
        records: list[dict],
        *,
        parent_key: str,
    ) -> list[dict]:
        remaining = list(records)
        sorted_records: list[dict] = []
        known_ids: set[int] = set()

        while remaining:
            progress = False
            next_remaining: list[dict] = []
            for record in remaining:
                parent_id = record.get(parent_key)
                if parent_id is None or parent_id in known_ids:
                    sorted_records.append(record)
                    known_ids.add(record["id"])
                    progress = True
                else:
                    next_remaining.append(record)
            if not progress:
                raise ValueError("Soubor zálohy registru obsahuje neplatné vazby.")
            remaining = next_remaining
        return sorted_records

    def _update_sqlite_sequences(self, session, table_max_ids: dict[str, int]) -> None:
        sequence_table_exists = session.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name = 'sqlite_sequence'",
            ),
        ).scalar()
        if not sequence_table_exists:
            return

        for table_name, max_id in table_max_ids.items():
            if max_id <= 0:
                continue
            session.execute(
                text(
                    "INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES (:name, :seq)",
                ),
                {"name": table_name, "seq": max_id},
            )

    def _text(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _parse_date(self, value) -> date | None:
        if not value:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return date.fromisoformat(str(value))

    def _parse_datetime(self, value) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))

    def _parse_decimal(self, value) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Soubor zálohy registru má neplatný formát.") from exc


legal_registry_import_service = LegalRegistryImportService()

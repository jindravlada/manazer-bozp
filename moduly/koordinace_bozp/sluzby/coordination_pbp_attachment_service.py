"""Generování přílohy PBP pro koordinaci (COORD-007).

Používá veřejné API ``pravidla_bezpecne_prace_service.generate`` a stejnou
normalizaci / deduplikaci / řazení jako modul PBP.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.export.open_export import open_local_file
from core.services.storage_service import storage_service
from moduly.koordinace_bozp.constants import (
    COORDINATION_PBP_INFO_TEXT,
    COORDINATION_PBP_INTRO_TEXT,
    MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE,
)
from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
    CoordinationPbpRevision,
)
from moduly.koordinace_bozp.repository.coordination_pbp_revision_repository import (
    CoordinationPbpRevisionRepository,
)
from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
    coordination_workplace_service,
)
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_document_format import (
    format_numbered_valid_rules,
)
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
    PravidloBezpecnePrace,
    pravidla_bezpecne_prace_service,
)


class CoordinationPbpAttachmentError(ValueError):
    pass


@dataclass(frozen=True)
class CoordinationPbpGenerateResult:
    revision: CoordinationPbpRevision | None
    created: bool
    rules: list[PravidloBezpecnePrace]
    message: str


def merge_pbp_rules(items: list[PravidloBezpecnePrace]) -> list[PravidloBezpecnePrace]:
    """Stejná deduplikace a řazení jako ``PravidlaBezpecnePraceService._dedupe_and_sort``."""
    return pravidla_bezpecne_prace_service._dedupe_and_sort(  # noqa: SLF001 – sdílená logika PBP
        sorted(items, key=lambda item: item.measure_id)
    )


def content_hash_for_rules(rules: list[PravidloBezpecnePrace]) -> str:
    payload = "\n".join(rule.text for rule in rules)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def current_username() -> str:
    try:
        return getpass.getuser() or ""
    except Exception:  # noqa: BLE001
        return ""


class CoordinationPbpAttachmentService:
    ENTITY_TYPE = "coordination_pbp"

    def __init__(self) -> None:
        self.repository = CoordinationPbpRevisionRepository()

    def list_revisions(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationPbpRevision]:
        return self.repository.list_for_coordination(
            coordination_id,
            include_inactive=include_inactive,
        )

    def get_current(self, coordination_id: int) -> CoordinationPbpRevision | None:
        return self.repository.get_current(coordination_id)

    def get_by_id(self, revision_id: int | None) -> CoordinationPbpRevision | None:
        if not revision_id:
            return None
        return self.repository.get_by_id(revision_id)

    def collect_rules_for_coordination(
        self,
        coordination_id: int,
    ) -> list[PravidloBezpecnePrace]:
        places = coordination_workplace_service.list_for_coordination(
            coordination_id,
            include_inactive=False,
        )
        if not places:
            raise CoordinationPbpAttachmentError(
                "Nejdříve zadejte alespoň jedno aktivní místo výkonu práce."
            )

        groups = exposed_group_service.get_all(include_inactive=False)
        if not groups:
            return []

        collected: list[PravidloBezpecnePrace] = []
        for place in places:
            for group in groups:
                collected.extend(
                    pravidla_bezpecne_prace_service.generate(
                        endangered_group_id=group.id,
                        operation_id=place.operation_id,
                        workplace_id=place.workplace_id,
                        workplace_part_id=place.workplace_part_id,
                    )
                )
        return merge_pbp_rules(collected)

    def generate_or_update(
        self,
        coordination_id: int,
        *,
        force: bool = False,
    ) -> CoordinationPbpGenerateResult:
        """Vygeneruje přílohu. Při shodném hash nevytváří novou revizi."""
        rules = self.collect_rules_for_coordination(coordination_id)
        if not rules:
            raise CoordinationPbpAttachmentError(
                "Pro aktivní místa výkonu práce nebyla nalezena žádná platná PBP."
            )

        digest = content_hash_for_rules(rules)
        current = self.repository.get_current(coordination_id)
        if current is not None and current.content_hash == digest and not force:
            return CoordinationPbpGenerateResult(
                revision=current,
                created=False,
                rules=rules,
                message="Obsah se nezměnil – nová revize se nevytváří.",
            )

        revision_number = self.repository.next_revision_number(coordination_id)
        filename = (
            f"PBP-koordinace-{coordination_id}-r{revision_number:04d}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.odt"
        )
        target_dir = storage_service.attachment_dir(self.ENTITY_TYPE, coordination_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / filename
        try:
            storage_service.attachment_absolute(
                str(output_path.resolve().relative_to(
                    storage_service.attachments_dir.resolve()
                ))
            )
        except ValueError as exc:
            raise CoordinationPbpAttachmentError(
                "Cílová cesta přílohy musí zůstat v adresáři prilohy."
            ) from exc
        self._write_odt(output_path, rules=rules)

        relative_path = output_path.resolve().relative_to(
            storage_service.attachments_dir.resolve()
        ).as_posix()
        self.repository.clear_current(coordination_id)
        revision = CoordinationPbpRevision(
            coordination_id=coordination_id,
            revision_number=revision_number,
            title=MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE,
            content_hash=digest,
            rules_count=len(rules),
            rules_json=json.dumps(
                [
                    {
                        "text": rule.text,
                        "severity": rule.severity,
                        "measure_id": rule.measure_id,
                    }
                    for rule in rules
                ],
                ensure_ascii=False,
            ),
            file_path=relative_path,
            stored_filename=filename,
            created_by=current_username(),
            is_current=True,
            active=True,
        )
        saved = self.repository.add(revision)
        return CoordinationPbpGenerateResult(
            revision=saved,
            created=True,
            rules=rules,
            message=f"Vytvořena revize {revision_number} ({len(rules)} pravidel).",
        )

    def resolve_path(self, revision: CoordinationPbpRevision) -> Path:
        try:
            return storage_service.attachment_absolute(revision.file_path)
        except ValueError as exc:
            raise CoordinationPbpAttachmentError(
                "Cesta přílohy je mimo úložiště."
            ) from exc

    def open_revision(self, revision_id: int, parent=None) -> bool:
        revision = self.repository.get_by_id(revision_id)
        if revision is None:
            raise CoordinationPbpAttachmentError("Revize nebyla nalezena.")
        path = self.resolve_path(revision)
        if not path.exists():
            raise CoordinationPbpAttachmentError("Soubor přílohy nebyl nalezen.")
        return bool(
            open_local_file(
                path,
                parent=parent,
                title=MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE,
            )
        )

    def export_current_odt(self, coordination_id: int, target_path: str | Path) -> Path:
        revision = self.repository.get_current(coordination_id)
        if revision is None:
            raise CoordinationPbpAttachmentError(
                "Nejdříve vygenerujte přílohu PBP."
            )
        source = self.resolve_path(revision)
        if not source.exists():
            raise CoordinationPbpAttachmentError("Soubor aktuální přílohy nebyl nalezen.")
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return target

    def _write_odt(self, output_path: Path, *, rules: list[PravidloBezpecnePrace]) -> Path:
        rules_text = format_numbered_valid_rules(rules, None)
        title = MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE
        body = "\n".join(
            [
                title,
                "",
                "1. Úvod",
                "",
                COORDINATION_PBP_INTRO_TEXT,
                "",
                "2. Pravidla bezpečné práce",
                "",
                rules_text,
                "",
                "3. Informace",
                "",
                COORDINATION_PBP_INFO_TEXT,
            ]
        )
        paragraphs_xml = "".join(
            f"<text:p text:style-name=\"Standard\">{self._escape_xml(line)}</text:p>"
            if line
            else '<text:p text:style-name="Standard"/>'
            for line in body.split("\n")
        )
        content_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-content '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
            'office:version="1.2">'
            "<office:body><office:text>"
            f"{paragraphs_xml}"
            "</office:text></office:body></office:document-content>"
        )
        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-styles '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'office:version="1.2">'
            "<office:styles/>"
            "</office:document-styles>"
        )
        meta_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-meta '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'office:version="1.2">'
            "<office:meta/>"
            "</office:document-meta>"
        )
        manifest_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<manifest:manifest '
            'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2">'
            '<manifest:file-entry manifest:full-path="/" '
            'manifest:version="1.2" '
            'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
            '<manifest:file-entry manifest:full-path="content.xml" '
            'manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="styles.xml" '
            'manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="meta.xml" '
            'manifest:media-type="text/xml"/>'
            "</manifest:manifest>"
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w") as zout:
            # mimetype must be first and uncompressed
            info = zipfile.ZipInfo("mimetype")
            info.compress_type = zipfile.ZIP_STORED
            zout.writestr(info, "application/vnd.oasis.opendocument.text")
            zout.writestr("content.xml", content_xml.encode("utf-8"))
            zout.writestr("styles.xml", styles_xml.encode("utf-8"))
            zout.writestr("meta.xml", meta_xml.encode("utf-8"))
            zout.writestr("META-INF/manifest.xml", manifest_xml.encode("utf-8"))
        return output_path

    @staticmethod
    def _escape_xml(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


coordination_pbp_attachment_service = CoordinationPbpAttachmentService()

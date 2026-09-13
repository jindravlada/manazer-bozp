"""Služba příloh koordinace (COORD-006)."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from core.export.open_export import open_local_file
from core.services.storage_service import storage_service
from moduly.koordinace_bozp.constants import (
    ATTACHMENT_TYPE_CONTRACTOR_RISKS,
    ATTACHMENT_TYPES,
    COORDINATION_ATTACHMENT_ALLOWED_SUFFIXES,
)
from moduly.koordinace_bozp.modely.coordination_attachment import CoordinationAttachment
from moduly.koordinace_bozp.repository.coordination_attachment_repository import (
    CoordinationAttachmentRepository,
)
from moduly.koordinace_bozp.repository.coordination_employer_repository import (
    CoordinationEmployerRepository,
)


class CoordinationAttachmentError(ValueError):
    pass


class CoordinationAttachmentService:
    ENTITY_TYPE = "coordination"

    def __init__(self) -> None:
        self.repository = CoordinationAttachmentRepository()
        self.employer_repository = CoordinationEmployerRepository()

    def list_for_employer(
        self,
        coordination_employer_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationAttachment]:
        return self.repository.list_for_employer(
            coordination_employer_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, attachment_id: int | None) -> CoordinationAttachment | None:
        if not attachment_id:
            return None
        return self.repository.get_by_id(attachment_id)

    def add_file(
        self,
        *,
        coordination_id: int,
        coordination_employer_id: int,
        source_path: str | Path,
        attachment_type: str = ATTACHMENT_TYPE_CONTRACTOR_RISKS,
        description: str = "",
    ) -> CoordinationAttachment:
        employer = self.employer_repository.get_by_id(coordination_employer_id)
        if employer is None:
            raise CoordinationAttachmentError("Zaměstnavatel nebyl nalezen.")
        if employer.is_main:
            raise CoordinationAttachmentError(
                "Přílohy rizik dodavatele nelze vázat na hlavního zaměstnavatele."
            )
        if employer.coordination_id != coordination_id:
            raise CoordinationAttachmentError(
                "Zaměstnavatel nepatří k této koordinaci."
            )
        if attachment_type not in ATTACHMENT_TYPES:
            raise CoordinationAttachmentError("Neplatný typ přílohy.")

        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise CoordinationAttachmentError("Vybraný soubor neexistuje.")

        suffix = source.suffix.lower()
        if suffix not in COORDINATION_ATTACHMENT_ALLOWED_SUFFIXES:
            allowed = ", ".join(COORDINATION_ATTACHMENT_ALLOWED_SUFFIXES)
            raise CoordinationAttachmentError(
                f"Nepodporovaný formát souboru. Povolené: {allowed}."
            )

        original_filename = Path(source.name).name
        target_dir = storage_service.attachment_dir(
            self.ENTITY_TYPE,
            coordination_id,
        ) / f"employer_{coordination_employer_id}"
        try:
            target_dir_resolved = target_dir.resolve()
            target_dir_resolved.relative_to(storage_service.attachments_dir.resolve())
        except ValueError as exc:
            raise CoordinationAttachmentError(
                "Cílová cesta přílohy musí zůstat v adresáři prilohy."
            ) from exc
        target_dir.mkdir(parents=True, exist_ok=True)
        target = self._unique_target(target_dir / original_filename)
        try:
            storage_service.attachment_absolute(
                str(target.resolve().relative_to(storage_service.attachments_dir.resolve()))
            )
        except ValueError as exc:
            raise CoordinationAttachmentError(
                "Cílová cesta přílohy musí zůstat v adresáři prilohy."
            ) from exc
        shutil.copy2(source, target)

        relative_path = target.resolve().relative_to(
            storage_service.attachments_dir.resolve()
        ).as_posix()
        attachment = CoordinationAttachment(
            coordination_id=coordination_id,
            coordination_employer_id=coordination_employer_id,
            attachment_type=attachment_type,
            original_filename=original_filename,
            stored_filename=target.name,
            file_path=str(relative_path),
            description=(description or "").strip(),
            active=True,
        )
        return self.repository.add(attachment)

    def resolve_path(self, attachment: CoordinationAttachment) -> Path:
        try:
            return storage_service.attachment_absolute(attachment.file_path)
        except ValueError as exc:
            raise CoordinationAttachmentError(
                "Cesta přílohy je mimo úložiště."
            ) from exc

    def open_attachment(self, attachment_id: int, parent=None) -> bool:
        attachment = self.repository.get_by_id(attachment_id)
        if attachment is None:
            raise CoordinationAttachmentError("Příloha nebyla nalezena.")
        path = self.resolve_path(attachment)
        if not path.exists():
            raise CoordinationAttachmentError("Soubor přílohy nebyl v úložišti nalezen.")
        return bool(open_local_file(path, parent=parent, title="Příloha koordinace"))

    def activate(self, attachment_id: int) -> bool:
        attachment = self.repository.get_by_id(attachment_id)
        if attachment is None:
            return False
        attachment.active = True
        attachment.updated_at = datetime.now()
        self.repository.update(attachment)
        return True

    def deactivate(self, attachment_id: int) -> bool:
        """Deaktivuje záznam; fyzický soubor zůstává v úložišti."""
        attachment = self.repository.get_by_id(attachment_id)
        if attachment is None:
            return False
        attachment.active = False
        attachment.updated_at = datetime.now()
        self.repository.update(attachment)
        return True

    def _unique_target(self, target: Path) -> Path:
        if not target.exists():
            return target
        counter = 2
        while True:
            candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1


coordination_attachment_service = CoordinationAttachmentService()

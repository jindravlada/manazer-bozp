from datetime import date, datetime

from moduly.pravni_pozadavky.constants import VALID_CHANGE_TYPES
from moduly.pravni_pozadavky.modely.legal_change import LegalChange
from moduly.pravni_pozadavky.repository.legal_change_repository import LegalChangeRepository
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalChangeService:
    def __init__(self):
        self.repository = LegalChangeRepository()

    def list_all(self, *, include_inactive: bool = False) -> list[LegalChange]:
        return self.repository.list_all(include_inactive=include_inactive)

    def list_by_document(
        self,
        document_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalChange]:
        return self.repository.list_by_document(
            document_id,
            include_inactive=include_inactive,
        )

    def list_by_version(
        self,
        version_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalChange]:
        return self.repository.list_by_version(
            version_id,
            include_inactive=include_inactive,
        )

    def list_by_section(
        self,
        section_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalChange]:
        return self.repository.list_by_section(
            section_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, change_id: int) -> LegalChange | None:
        return self.repository.get_by_id(change_id)

    def create(
        self,
        *,
        legal_document_id: int,
        change_type: str,
        title: str,
        legal_document_version_id: int | None = None,
        legal_section_id: int | None = None,
        description: str = "",
        published_at: date | None = None,
        effective_from: date | None = None,
        evaluated: bool = False,
        evaluated_at: datetime | None = None,
        evaluated_by: str = "",
        note: str = "",
        active: bool = True,
    ) -> LegalChange:
        self._validate_document_id(legal_document_id)
        self._validate_version_id(legal_document_version_id)
        self._validate_section_id(legal_section_id)
        normalized_type = change_type.strip()
        self._validate_change_type(normalized_type)
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Název změny je povinný.")

        if evaluated and evaluated_at is None:
            evaluated_at = datetime.now()

        change = LegalChange(
            legal_document_id=legal_document_id,
            legal_document_version_id=legal_document_version_id,
            legal_section_id=legal_section_id,
            change_type=normalized_type,
            title=normalized_title,
            description=description.strip(),
            published_at=published_at,
            effective_from=effective_from,
            evaluated=evaluated,
            evaluated_at=evaluated_at,
            evaluated_by=evaluated_by.strip(),
            note=note.strip(),
            active=active,
        )
        return self.repository.create(change)

    def update(
        self,
        change_id: int,
        *,
        legal_document_id: int,
        change_type: str,
        title: str,
        legal_document_version_id: int | None = None,
        legal_section_id: int | None = None,
        description: str = "",
        published_at: date | None = None,
        effective_from: date | None = None,
        evaluated: bool = False,
        evaluated_at: datetime | None = None,
        evaluated_by: str = "",
        note: str = "",
        active: bool = True,
    ) -> LegalChange | None:
        change = self.repository.get_by_id(change_id)
        if change is None:
            return None

        self._validate_document_id(legal_document_id)
        self._validate_version_id(legal_document_version_id)
        self._validate_section_id(legal_section_id)
        normalized_type = change_type.strip()
        self._validate_change_type(normalized_type)
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Název změny je povinný.")

        if evaluated:
            if evaluated_at is None and change.evaluated_at is None:
                evaluated_at = datetime.now()
        else:
            evaluated_at = None
            evaluated_by = ""

        change.legal_document_id = legal_document_id
        change.legal_document_version_id = legal_document_version_id
        change.legal_section_id = legal_section_id
        change.change_type = normalized_type
        change.title = normalized_title
        change.description = description.strip()
        change.published_at = published_at
        change.effective_from = effective_from
        change.evaluated = evaluated
        change.evaluated_at = evaluated_at
        change.evaluated_by = evaluated_by.strip() if evaluated else ""
        change.note = note.strip()
        change.active = active
        return self.repository.update(change)

    def deactivate(self, change_id: int) -> LegalChange | None:
        return self.repository.deactivate(change_id)

    def restore(self, change_id: int) -> LegalChange | None:
        return self.repository.restore(change_id)

    def mark_evaluated(
        self,
        change_id: int,
        *,
        evaluated_by: str | None = None,
        note: str | None = None,
    ) -> LegalChange | None:
        change = self.repository.get_by_id(change_id)
        if change is None:
            return None
        change.evaluated = True
        change.evaluated_at = datetime.now()
        if evaluated_by is not None:
            change.evaluated_by = evaluated_by.strip()
        if note is not None:
            change.note = note.strip()
        return self.repository.update(change)

    def mark_unevaluated(self, change_id: int) -> LegalChange | None:
        change = self.repository.get_by_id(change_id)
        if change is None:
            return None
        change.evaluated = False
        change.evaluated_at = None
        change.evaluated_by = ""
        return self.repository.update(change)

    def _validate_document_id(self, legal_document_id: int) -> None:
        if not isinstance(legal_document_id, int) or legal_document_id <= 0:
            raise ValueError("Právní předpis je povinný.")
        if legal_document_service.get_by_id(legal_document_id) is None:
            raise ValueError("Právní předpis nebyl nalezen.")

    def _validate_version_id(self, legal_document_version_id: int | None) -> None:
        if legal_document_version_id is None:
            return
        if not isinstance(legal_document_version_id, int) or legal_document_version_id <= 0:
            raise ValueError("Neplatná verze předpisu.")
        if legal_document_version_service.get_by_id(legal_document_version_id) is None:
            raise ValueError("Verze předpisu nebyla nalezena.")

    def _validate_section_id(self, legal_section_id: int | None) -> None:
        if legal_section_id is None:
            return
        if not isinstance(legal_section_id, int) or legal_section_id <= 0:
            raise ValueError("Neplatné ustanovení předpisu.")
        if legal_section_service.get_by_id(legal_section_id) is None:
            raise ValueError("Ustanovení předpisu nebylo nalezeno.")

    def _validate_change_type(self, change_type: str) -> None:
        if not change_type:
            raise ValueError("Typ změny je povinný.")
        if change_type not in VALID_CHANGE_TYPES:
            raise ValueError("Neplatný typ změny.")


legal_change_service = LegalChangeService()

"""Služba zúčastněných zaměstnavatelů koordinace (COORD-002)."""

from __future__ import annotations

from datetime import datetime

from moduly.koordinace_bozp.constants import (
    COORDINATION_EMPLOYER_TYPE_MAIN,
    COORDINATION_EMPLOYER_TYPE_PARTICIPANT,
)
from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
from moduly.koordinace_bozp.repository.coordination_employer_repository import (
    CoordinationEmployerRepository,
)
from moduly.nastaveni.sluzby.settings_service import settings_service


class CoordinationEmployerError(ValueError):
    pass


def default_abbreviation(company_name: str) -> str:
    words = [part for part in (company_name or "").split() if part]
    if not words:
        return "HL"
    if len(words) == 1:
        return words[0][:8].upper()
    return "".join(word[0] for word in words[:4]).upper()


class CoordinationEmployerService:
    def __init__(self) -> None:
        self.repository = CoordinationEmployerRepository()

    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationEmployer]:
        return self.repository.list_for_coordination(
            coordination_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, employer_id: int | None) -> CoordinationEmployer | None:
        if not employer_id:
            return None
        return self.repository.get_by_id(employer_id)

    def ensure_main_employer(self, coordination_id: int) -> CoordinationEmployer:
        """Vloží hlavního zaměstnavatele z nastavení, pokud ještě chybí."""
        existing = self.repository.get_main(coordination_id)
        if existing is not None:
            return existing

        settings_employer = settings_service.get_employer()
        company_name = (
            (settings_employer.name or "").strip()
            if settings_employer is not None
            else ""
        ) or "Hlavní zaměstnavatel"
        ico = (settings_employer.ico or "").strip() if settings_employer else ""
        address = (settings_employer.address or "").strip() if settings_employer else ""

        employer = CoordinationEmployer(
            coordination_id=coordination_id,
            employer_type=COORDINATION_EMPLOYER_TYPE_MAIN,
            company_name=company_name,
            ico=ico,
            address=address,
            abbreviation=default_abbreviation(company_name),
            is_main=True,
            note="",
            active=True,
            sort_order=1,
        )
        return self.repository.add(employer)

    def add_participant(
        self,
        coordination_id: int,
        *,
        company_name: str,
        ico: str = "",
        address: str = "",
        abbreviation: str = "",
        note: str = "",
        active: bool = True,
    ) -> CoordinationEmployer:
        self.ensure_main_employer(coordination_id)
        normalized_name = self._validate_company_name(company_name)
        normalized_abbr = self._validate_abbreviation(
            abbreviation or default_abbreviation(normalized_name),
            coordination_id=coordination_id,
        )
        employer = CoordinationEmployer(
            coordination_id=coordination_id,
            employer_type=COORDINATION_EMPLOYER_TYPE_PARTICIPANT,
            company_name=normalized_name,
            ico=(ico or "").strip(),
            address=(address or "").strip(),
            abbreviation=normalized_abbr,
            is_main=False,
            note=(note or "").strip(),
            active=active,
            sort_order=self.repository.next_sort_order(coordination_id),
        )
        return self.repository.add(employer)

    def update_employer(
        self,
        employer_id: int,
        *,
        company_name: str | None = None,
        ico: str | None = None,
        address: str | None = None,
        abbreviation: str | None = None,
        note: str | None = None,
    ) -> CoordinationEmployer | None:
        employer = self.repository.get_by_id(employer_id)
        if employer is None:
            return None

        if employer.is_main:
            if abbreviation is None:
                raise CoordinationEmployerError(
                    "U hlavního zaměstnavatele lze upravit pouze zkratku."
                )
            employer.abbreviation = self._validate_abbreviation(
                abbreviation,
                coordination_id=employer.coordination_id,
                exclude_employer_id=employer.id,
            )
            employer.updated_at = datetime.now()
            return self.repository.update(employer)

        if company_name is not None:
            employer.company_name = self._validate_company_name(company_name)
        if ico is not None:
            employer.ico = ico.strip()
        if address is not None:
            employer.address = address.strip()
        if abbreviation is not None:
            employer.abbreviation = self._validate_abbreviation(
                abbreviation,
                coordination_id=employer.coordination_id,
                exclude_employer_id=employer.id,
            )
        if note is not None:
            employer.note = note.strip()
        employer.updated_at = datetime.now()
        return self.repository.update(employer)

    def activate(self, employer_id: int) -> bool:
        employer = self.repository.get_by_id(employer_id)
        if employer is None:
            return False
        employer.active = True
        employer.updated_at = datetime.now()
        self.repository.update(employer)
        return True

    def deactivate(self, employer_id: int) -> bool:
        employer = self.repository.get_by_id(employer_id)
        if employer is None:
            return False
        if employer.is_main:
            raise CoordinationEmployerError(
                "Hlavního zaměstnavatele nelze deaktivovat ani odstranit."
            )
        employer.active = False
        employer.updated_at = datetime.now()
        self.repository.update(employer)
        return True

    def _validate_company_name(self, company_name: str) -> str:
        normalized = " ".join((company_name or "").strip().split())
        if not normalized:
            raise CoordinationEmployerError("Název firmy je povinný.")
        return normalized

    def _validate_abbreviation(
        self,
        abbreviation: str,
        *,
        coordination_id: int,
        exclude_employer_id: int | None = None,
    ) -> str:
        normalized = " ".join((abbreviation or "").strip().split())
        if not normalized:
            raise CoordinationEmployerError("Zkratka zaměstnavatele je povinná.")
        if len(normalized) > 32:
            raise CoordinationEmployerError("Zkratka může mít nejvýše 32 znaků.")

        for item in self.repository.list_for_coordination(
            coordination_id,
            include_inactive=True,
        ):
            if exclude_employer_id is not None and item.id == exclude_employer_id:
                continue
            if item.abbreviation.casefold() == normalized.casefold():
                raise CoordinationEmployerError(
                    f"Zkratka „{normalized}“ je u této koordinace již použita."
                )
        return normalized


coordination_employer_service = CoordinationEmployerService()

from decimal import Decimal, InvalidOperation

from moduly.pravni_pozadavky.constants import DEFAULT_SANCTION_CURRENCY
from moduly.pravni_pozadavky.modely.legal_requirement_sanction import LegalRequirementSanction
from moduly.pravni_pozadavky.repository.legal_requirement_sanction_repository import (
    LegalRequirementSanctionRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service


class LegalRequirementSanctionService:
    def __init__(self):
        self.repository = LegalRequirementSanctionRepository()

    def list_by_requirement(
        self,
        requirement_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalRequirementSanction]:
        return self.repository.list_by_requirement(
            requirement_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, sanction_id: int) -> LegalRequirementSanction | None:
        return self.repository.get_by_id(sanction_id)

    def create(
        self,
        *,
        requirement_id: int,
        authority: str = "",
        legal_reference: str = "",
        description: str = "",
        max_amount: Decimal | float | str | None = None,
        currency: str = DEFAULT_SANCTION_CURRENCY,
        note: str = "",
        active: bool = True,
    ) -> LegalRequirementSanction:
        self._validate_requirement_id(requirement_id)
        normalized_description = description.strip()
        if not normalized_description:
            raise ValueError("Popis sankce je povinný.")

        sanction = LegalRequirementSanction(
            requirement_id=requirement_id,
            authority=authority.strip(),
            legal_reference=legal_reference.strip(),
            description=normalized_description,
            max_amount=self._normalize_amount(max_amount),
            currency=self._normalize_currency(currency),
            note=note.strip(),
            active=active,
        )
        return self.repository.create(sanction)

    def update(
        self,
        sanction_id: int,
        *,
        authority: str = "",
        legal_reference: str = "",
        description: str = "",
        max_amount: Decimal | float | str | None = None,
        currency: str = DEFAULT_SANCTION_CURRENCY,
        note: str = "",
        active: bool = True,
    ) -> LegalRequirementSanction | None:
        sanction = self.repository.get_by_id(sanction_id)
        if sanction is None:
            return None

        normalized_description = description.strip()
        if not normalized_description:
            raise ValueError("Popis sankce je povinný.")

        sanction.authority = authority.strip()
        sanction.legal_reference = legal_reference.strip()
        sanction.description = normalized_description
        sanction.max_amount = self._normalize_amount(max_amount)
        sanction.currency = self._normalize_currency(currency)
        sanction.note = note.strip()
        sanction.active = active
        return self.repository.update(sanction)

    def deactivate(self, sanction_id: int) -> LegalRequirementSanction | None:
        sanction = self.repository.get_by_id(sanction_id)
        if sanction is None:
            return None
        sanction.active = False
        return self.repository.update(sanction)

    def restore(self, sanction_id: int) -> LegalRequirementSanction | None:
        sanction = self.repository.get_by_id(sanction_id)
        if sanction is None:
            return None
        sanction.active = True
        return self.repository.update(sanction)

    def _validate_requirement_id(self, requirement_id: int) -> None:
        if not isinstance(requirement_id, int) or requirement_id <= 0:
            raise ValueError("Požadavek je povinný.")
        if legal_requirement_service.get_by_id(requirement_id) is None:
            raise ValueError("Právní požadavek nebyl nalezen.")

    def _normalize_currency(self, currency: str) -> str:
        normalized = (currency or "").strip()
        return normalized or DEFAULT_SANCTION_CURRENCY

    def _normalize_amount(self, value: Decimal | float | str | None) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        text = str(value).strip().replace(" ", "").replace(",", ".")
        if not text:
            return None
        try:
            return Decimal(text)
        except InvalidOperation as exc:
            raise ValueError("Horní hranice pokuty není platné číslo.") from exc


legal_requirement_sanction_service = LegalRequirementSanctionService()

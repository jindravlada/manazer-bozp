"""Služba evidence smluv OZO."""

from __future__ import annotations

from datetime import date, datetime

from moduly.smlouvy_ozo.constants import (
    DEFAULT_NOTIFY_BEFORE_UNIT,
    DEFAULT_NOTIFY_BEFORE_VALUE,
    EMPLOYER_NAME_REQUIRED_MESSAGE,
    NOTIFY_UNITS,
    VALID_FROM_REQUIRED_MESSAGE,
    VALID_TO_REQUIRED_MESSAGE,
)
from moduly.smlouvy_ozo.modely.ozo_contract import OzoContract
from moduly.smlouvy_ozo.repository.ozo_contract_repository import OzoContractRepository
from moduly.smlouvy_ozo.sluzby.ozo_contract_validity import contract_status


class OzoContractValidationError(Exception):
    pass


def relation_date(contract: OzoContract) -> date | None:
    """Datum smluvního vztahu: přednostně uzavření, jinak platnost od."""
    if contract.signed_on is not None:
        return contract.signed_on
    return contract.valid_from


class OzoContractService:
    def __init__(self, repository: OzoContractRepository | None = None):
        self.repository = repository or OzoContractRepository()

    def get_all(self, *, active_only: bool | None = None) -> list[OzoContract]:
        return self.repository.get_all(active_only=active_only)

    def get_by_id(self, contract_id: int) -> OzoContract | None:
        return self.repository.get_by_id(contract_id)

    def available_years(self) -> list[int]:
        years: set[int] = set()
        for contract in self.repository.get_all():
            value = relation_date(contract)
            if value is not None:
                years.add(value.year)
        return sorted(years, reverse=True)

    def list_for_calendar_year(self, year: int) -> list[OzoContract]:
        """Všechny smlouvy (včetně neaktivních) náležící do kalendářního roku."""
        rows = []
        for contract in self.repository.get_all():
            value = relation_date(contract)
            if value is not None and value.year == int(year):
                rows.append(contract)
        rows.sort(
            key=lambda item: (
                relation_date(item) or date.max,
                (item.employer_name or "").casefold(),
                item.id or 0,
            )
        )
        return rows

    def status_for(self, contract: OzoContract, *, today: date | None = None) -> str:
        return contract_status(
            active=bool(contract.active),
            indefinite=bool(contract.indefinite),
            valid_to=contract.valid_to,
            notify_before_value=int(contract.notify_before_value or 0),
            notify_before_unit=contract.notify_before_unit or DEFAULT_NOTIFY_BEFORE_UNIT,
            today=today,
        )

    def create(
        self,
        *,
        employer_name: str,
        valid_from: date,
        ico: str = "",
        address: str = "",
        contact_person: str = "",
        phone: str = "",
        email: str = "",
        contract_number: str = "",
        signed_on: date | None = None,
        valid_to: date | None = None,
        indefinite: bool = False,
        notify_before_value: int = DEFAULT_NOTIFY_BEFORE_VALUE,
        notify_before_unit: str = DEFAULT_NOTIFY_BEFORE_UNIT,
        services_scope: str = "",
        note: str = "",
        active: bool = True,
    ) -> OzoContract:
        data = self._validated(
            employer_name=employer_name,
            valid_from=valid_from,
            ico=ico,
            address=address,
            contact_person=contact_person,
            phone=phone,
            email=email,
            contract_number=contract_number,
            signed_on=signed_on,
            valid_to=valid_to,
            indefinite=indefinite,
            notify_before_value=notify_before_value,
            notify_before_unit=notify_before_unit,
            services_scope=services_scope,
            note=note,
            active=active,
        )
        contract = OzoContract(**data)
        return self.repository.add(contract)

    def update(self, contract_id: int, **fields) -> OzoContract:
        contract = self.repository.get_by_id(contract_id)
        if contract is None:
            raise OzoContractValidationError("Smlouva OZO nebyla nalezena.")
        data = self._validated(
            employer_name=fields.get("employer_name", contract.employer_name),
            valid_from=fields.get("valid_from", contract.valid_from),
            ico=fields.get("ico", contract.ico),
            address=fields.get("address", contract.address),
            contact_person=fields.get("contact_person", contract.contact_person),
            phone=fields.get("phone", contract.phone),
            email=fields.get("email", contract.email),
            contract_number=fields.get("contract_number", contract.contract_number),
            signed_on=fields.get("signed_on", contract.signed_on),
            valid_to=fields.get("valid_to", contract.valid_to),
            indefinite=fields.get("indefinite", contract.indefinite),
            notify_before_value=fields.get(
                "notify_before_value", contract.notify_before_value
            ),
            notify_before_unit=fields.get(
                "notify_before_unit", contract.notify_before_unit
            ),
            services_scope=fields.get("services_scope", contract.services_scope),
            note=fields.get("note", contract.note),
            active=fields.get("active", contract.active),
        )
        for key, value in data.items():
            setattr(contract, key, value)
        contract.updated_at = datetime.now()
        return self.repository.update(contract)

    def activate(self, contract_id: int) -> OzoContract:
        return self.update(contract_id, active=True)

    def deactivate(self, contract_id: int) -> OzoContract:
        return self.update(contract_id, active=False)

    def _validated(
        self,
        *,
        employer_name: str,
        valid_from: date | None,
        ico: str = "",
        address: str = "",
        contact_person: str = "",
        phone: str = "",
        email: str = "",
        contract_number: str = "",
        signed_on: date | None = None,
        valid_to: date | None = None,
        indefinite: bool = False,
        notify_before_value: int = DEFAULT_NOTIFY_BEFORE_VALUE,
        notify_before_unit: str = DEFAULT_NOTIFY_BEFORE_UNIT,
        services_scope: str = "",
        note: str = "",
        active: bool = True,
    ) -> dict:
        name = (employer_name or "").strip()
        if not name:
            raise OzoContractValidationError(EMPLOYER_NAME_REQUIRED_MESSAGE)
        if valid_from is None:
            raise OzoContractValidationError(VALID_FROM_REQUIRED_MESSAGE)

        indefinite = bool(indefinite)
        if indefinite:
            valid_to = None
        elif valid_to is None:
            raise OzoContractValidationError(VALID_TO_REQUIRED_MESSAGE)

        notify_value = int(notify_before_value or 0)
        if notify_value < 0:
            raise OzoContractValidationError(
                "Předstih upozornění nesmí být záporný."
            )
        unit = (notify_before_unit or DEFAULT_NOTIFY_BEFORE_UNIT).strip()
        if unit not in NOTIFY_UNITS:
            raise OzoContractValidationError(
                f"Jednotka předstihu musí být jedna z: {', '.join(NOTIFY_UNITS)}."
            )
        if indefinite:
            notify_value = DEFAULT_NOTIFY_BEFORE_VALUE
            unit = DEFAULT_NOTIFY_BEFORE_UNIT

        return {
            "employer_name": name,
            "ico": (ico or "").strip(),
            "address": (address or "").strip(),
            "contact_person": (contact_person or "").strip(),
            "phone": (phone or "").strip(),
            "email": (email or "").strip(),
            "contract_number": (contract_number or "").strip(),
            "signed_on": signed_on,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "indefinite": indefinite,
            "notify_before_value": notify_value,
            "notify_before_unit": unit,
            "services_scope": (services_scope or "").strip(),
            "note": (note or "").strip(),
            "active": bool(active),
        }


ozo_contract_service = OzoContractService()

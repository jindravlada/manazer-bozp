"""Služba evidence smluv OZO."""

from __future__ import annotations

from datetime import date, datetime

from moduly.smlouvy_ozo.constants import (
    DEFAULT_NOTIFY_BEFORE_UNIT,
    DEFAULT_NOTIFY_BEFORE_VALUE,
    EMPLOYER_NAME_REQUIRED_MESSAGE,
    NOTIFY_UNITS,
    OVERLAP_MESSAGE,
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


def normalize_ico(ico: str | None) -> str:
    return (ico or "").strip()


def validity_end(*, indefinite: bool, valid_to: date | None) -> date | None:
    """Konec intervalu platnosti; None = doba neurčitá (otevřený konec)."""
    if indefinite:
        return None
    return valid_to


def validity_intervals_overlap(
    from_a: date,
    to_a: date | None,
    from_b: date,
    to_b: date | None,
) -> bool:
    """Překryv uzavřených intervalů; None u konce = nekonečno. Navazující OK."""
    # new_from <= existing_to  AND  existing_from <= new_to
    left_ok = True if to_b is None else from_a <= to_b
    right_ok = True if to_a is None else from_b <= to_a
    return left_ok and right_ok


def covers_calendar_year(contract: OzoContract, year: int) -> bool:
    """True, pokud smlouva byla alespoň část kalendářního roku platná.

    Podmínky:
    - valid_from <= 31.12.R
    - doba neurčitá NEBO valid_to >= 1.1.R

    Deaktivace záznamu na výsledek nemá vliv.
    """
    valid_from = contract.valid_from
    if valid_from is None:
        return False
    year = int(year)
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    if valid_from > year_end:
        return False
    if bool(contract.indefinite):
        return True
    valid_to = contract.valid_to
    if valid_to is None:
        return False
    return valid_to >= year_start


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
        """Smlouvy platné alespoň část roku (včetně neaktivních)."""
        rows = [
            contract
            for contract in self.repository.get_all()
            if covers_calendar_year(contract, year)
        ]
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
            exclude_id=contract_id,
        )
        for key, value in data.items():
            setattr(contract, key, value)
        contract.updated_at = datetime.now()
        return self.repository.update(contract)

    def activate(self, contract_id: int) -> OzoContract:
        """Výjimečná obnova archivovaného záznamu (ne běžné UI)."""
        return self.update(contract_id, active=True)

    def deactivate(self, contract_id: int) -> OzoContract:
        """Výjimečná technická archivace chybného záznamu (ne ukončení smlouvy)."""
        return self.update(contract_id, active=False)

    def find_overlapping_contract(
        self,
        *,
        ico: str,
        valid_from: date,
        valid_to: date | None,
        indefinite: bool,
        exclude_id: int | None = None,
    ) -> OzoContract | None:
        """První aktivní smlouva se stejným IČO a překryvem platnosti."""
        ico_norm = normalize_ico(ico)
        if not ico_norm:
            return None
        new_to = validity_end(indefinite=indefinite, valid_to=valid_to)
        for other in self.repository.get_all(active_only=True):
            if exclude_id is not None and other.id == exclude_id:
                continue
            if normalize_ico(other.ico) != ico_norm:
                continue
            other_to = validity_end(
                indefinite=bool(other.indefinite),
                valid_to=other.valid_to,
            )
            if validity_intervals_overlap(
                valid_from,
                new_to,
                other.valid_from,
                other_to,
            ):
                return other
        return None

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
        exclude_id: int | None = None,
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

        ico_norm = normalize_ico(ico)
        if bool(active) and ico_norm:
            overlapping = self.find_overlapping_contract(
                ico=ico_norm,
                valid_from=valid_from,
                valid_to=valid_to,
                indefinite=indefinite,
                exclude_id=exclude_id,
            )
            if overlapping is not None:
                raise OzoContractValidationError(OVERLAP_MESSAGE)

        return {
            "employer_name": name,
            "ico": ico_norm,
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

"""Služba kontaktů koordinace (COORD-010 / UX-COORD-12d)."""

from __future__ import annotations

from datetime import datetime

from moduly.koordinace_bozp.constants import (
    CONTACT_TYPES,
    CONTACT_TYPE_LABELS,
    DEFAULT_CONTACT_TYPE,
)
from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
from moduly.koordinace_bozp.repository.coordination_contact_repository import (
    CoordinationContactRepository,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
    employer_abbreviation,
    employer_tooltip_name,
    resolve_abbreviation,
)
from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
    coordination_participant_service,
)

CONTACT_EMPLOYER_UNSPECIFIED = "Neuvedeno"


class CoordinationContactError(ValueError):
    pass


def normalize_contact_name(value: str) -> str:
    return " ".join((value or "").strip().split())


class CoordinationContactService:
    def __init__(self) -> None:
        self.repository = CoordinationContactRepository()

    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationContact]:
        return self.repository.list_for_coordination(
            coordination_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, contact_id: int | None) -> CoordinationContact | None:
        if not contact_id:
            return None
        return self.repository.get_by_id(contact_id)

    def contact_type_label(self, contact_type: str) -> str:
        return CONTACT_TYPE_LABELS.get(contact_type, contact_type or "")

    def employer_display_label(self, contact: CoordinationContact | None) -> str:
        """Stručné označení zaměstnavatele pro tabulku / výstup."""
        if contact is None:
            return CONTACT_EMPLOYER_UNSPECIFIED
        if contact.employer_id:
            employer = coordination_employer_service.get_by_id(contact.employer_id)
            if employer is not None:
                label = employer_abbreviation(employer).strip()
                if not label:
                    label = (employer.company_name or "").strip()
                if label:
                    return label
        name = (contact.employer_name or "").strip()
        if name:
            return resolve_abbreviation("", name) or name
        return CONTACT_EMPLOYER_UNSPECIFIED

    def employer_display_tooltip(self, contact: CoordinationContact | None) -> str:
        """Celý název zaměstnavatele pro tooltip."""
        if contact is None:
            return ""
        if contact.employer_id:
            employer = coordination_employer_service.get_by_id(contact.employer_id)
            if employer is not None:
                return employer_tooltip_name(employer)
        return (contact.employer_name or "").strip()

    def list_selectable_participants(self, coordination_id: int):
        """Aktivní účastníci schůzky pro výběr do kontaktu."""
        employers = coordination_employer_service.list_for_coordination(
            coordination_id,
            include_inactive=True,
        )
        participants = []
        for employer in employers:
            participants.extend(
                coordination_participant_service.list_for_employer(
                    employer.id,
                    include_inactive=False,
                )
            )
        participants.sort(key=lambda item: ((item.full_name or "").casefold(), item.id))
        return participants

    def list_selectable_employers(self, coordination_id: int):
        """Aktivní zúčastnění zaměstnavatelé koordinace."""
        return [
            item
            for item in coordination_employer_service.list_for_coordination(
                coordination_id,
                include_inactive=False,
            )
            if item.active
        ]

    def add(
        self,
        coordination_id: int,
        *,
        contact_type: str = DEFAULT_CONTACT_TYPE,
        participant_id: int | None = None,
        employer_id: int | None = None,
        custom_name: str = "",
        role: str = "",
        phone: str = "",
        email: str = "",
        note: str = "",
        active: bool = True,
    ) -> CoordinationContact:
        if not coordination_id:
            raise CoordinationContactError("Koordinace je povinná.")
        resolved_participant_id = self._validate_participant_selection(
            participant_id,
        )
        resolved_employer_id, employer_name = self._resolve_employer(
            coordination_id,
            employer_id=employer_id,
            participant_id=resolved_participant_id,
            require=True,
        )
        name, role_value, phone_value, email_value = self._normalize_identity(
            custom_name=custom_name,
            role=role,
            phone=phone,
            email=email,
        )
        contact = CoordinationContact(
            coordination_id=coordination_id,
            participant_id=resolved_participant_id,
            employer_id=resolved_employer_id,
            contact_type=self._validate_contact_type(contact_type),
            custom_name=name,
            employer_name=employer_name,
            role=role_value,
            phone=phone_value,
            email=email_value,
            note=(note or "").strip(),
            active=active,
            sort_order=self.repository.next_sort_order(coordination_id),
        )
        return self.repository.add(contact)

    def update(
        self,
        contact_id: int,
        *,
        contact_type: str = DEFAULT_CONTACT_TYPE,
        participant_id: int | None = None,
        employer_id: int | None = None,
        custom_name: str = "",
        role: str = "",
        phone: str = "",
        email: str = "",
        note: str = "",
    ) -> CoordinationContact | None:
        contact = self.repository.get_by_id(contact_id)
        if contact is None:
            return None
        resolved_participant_id = self._validate_participant_selection(
            participant_id,
            allow_inactive_id=contact.participant_id,
        )
        resolved_employer_id, employer_name = self._resolve_employer(
            contact.coordination_id,
            employer_id=employer_id,
            participant_id=resolved_participant_id,
            require=True,
            allow_inactive_id=contact.employer_id,
        )
        name, role_value, phone_value, email_value = self._normalize_identity(
            custom_name=custom_name,
            role=role,
            phone=phone,
            email=email,
        )
        contact.participant_id = resolved_participant_id
        contact.employer_id = resolved_employer_id
        contact.contact_type = self._validate_contact_type(contact_type)
        contact.custom_name = name
        contact.employer_name = employer_name
        contact.role = role_value
        contact.phone = phone_value
        contact.email = email_value
        contact.note = (note or "").strip()
        contact.updated_at = datetime.now()
        return self.repository.update(contact)

    def activate(self, contact_id: int) -> bool:
        contact = self.repository.get_by_id(contact_id)
        if contact is None:
            return False
        contact.active = True
        contact.updated_at = datetime.now()
        self.repository.update(contact)
        return True

    def deactivate(self, contact_id: int) -> bool:
        contact = self.repository.get_by_id(contact_id)
        if contact is None:
            return False
        contact.active = False
        contact.updated_at = datetime.now()
        self.repository.update(contact)
        return True

    def move_up(self, contact_id: int) -> bool:
        return self._move(contact_id, direction=-1)

    def move_down(self, contact_id: int) -> bool:
        return self._move(contact_id, direction=1)

    def snapshot_from_participant(self, participant_id: int) -> dict:
        """Vrátí snapshot aktivního účastníka pro předvyplnění dialogu."""
        participant = self._require_active_participant(participant_id)
        employer = coordination_employer_service.get_by_id(
            participant.coordination_employer_id
        )
        if employer is None:
            raise CoordinationContactError("Zaměstnavatel účastníka nebyl nalezen.")
        return {
            "participant_id": participant.id,
            "employer_id": employer.id,
            "employer_name": employer.company_name or "",
            "custom_name": participant.full_name or "",
            "role": participant.role or "",
            "phone": participant.phone or "",
            "email": participant.email or "",
        }

    def _move(self, contact_id: int, *, direction: int) -> bool:
        contact = self.repository.get_by_id(contact_id)
        if contact is None:
            return False
        items = self.repository.list_for_coordination(
            contact.coordination_id,
            include_inactive=True,
        )
        index = next((i for i, item in enumerate(items) if item.id == contact.id), None)
        if index is None:
            return False
        new_index = index + direction
        if new_index < 0 or new_index >= len(items):
            return False
        items[index], items[new_index] = items[new_index], items[index]
        for order, item in enumerate(items, start=1):
            if item.sort_order == order:
                continue
            item.sort_order = order
            item.updated_at = datetime.now()
            self.repository.update(item)
        return True

    def _resolve_employer(
        self,
        coordination_id: int,
        *,
        employer_id: int | None,
        participant_id: int | None,
        require: bool,
        allow_inactive_id: int | None = None,
    ) -> tuple[int | None, str]:
        resolved_id = employer_id
        if participant_id and not resolved_id:
            participant = coordination_participant_service.get_by_id(participant_id)
            if participant is not None:
                resolved_id = participant.coordination_employer_id
        if not resolved_id:
            if require:
                raise CoordinationContactError("Zaměstnavatel je povinný.")
            return None, ""
        employer = coordination_employer_service.get_by_id(resolved_id)
        if employer is None:
            raise CoordinationContactError("Zaměstnavatel nebyl nalezen.")
        if employer.coordination_id != coordination_id:
            raise CoordinationContactError(
                "Zaměstnavatel nepatří k této koordinaci."
            )
        if not employer.active and employer.id != allow_inactive_id:
            raise CoordinationContactError(
                "Nelze vybrat deaktivovaného zaměstnavatele."
            )
        if participant_id:
            participant = coordination_participant_service.get_by_id(participant_id)
            if (
                participant is not None
                and participant.coordination_employer_id != employer.id
            ):
                raise CoordinationContactError(
                    "Účastník nepatří k vybranému zaměstnavateli."
                )
        return employer.id, (employer.company_name or "").strip()

    def _validate_participant_selection(
        self,
        participant_id: int | None,
        *,
        allow_inactive_id: int | None = None,
    ) -> int | None:
        if not participant_id:
            return None
        participant = coordination_participant_service.get_by_id(participant_id)
        if participant is None:
            raise CoordinationContactError("Účastník schůzky nebyl nalezen.")
        if not participant.active and participant.id != allow_inactive_id:
            raise CoordinationContactError(
                "Nelze vybrat deaktivovaného účastníka schůzky."
            )
        return participant.id

    def _require_active_participant(self, participant_id: int):
        participant = coordination_participant_service.get_by_id(participant_id)
        if participant is None:
            raise CoordinationContactError("Účastník schůzky nebyl nalezen.")
        if not participant.active:
            raise CoordinationContactError(
                "Nelze vybrat deaktivovaného účastníka schůzky."
            )
        return participant

    def _normalize_identity(
        self,
        *,
        custom_name: str,
        role: str,
        phone: str,
        email: str,
    ) -> tuple[str, str, str, str]:
        name = normalize_contact_name(custom_name)
        phone_value = (phone or "").strip()
        email_value = (email or "").strip()
        if not name:
            raise CoordinationContactError("Jméno kontaktu je povinné.")
        if not phone_value and not email_value:
            raise CoordinationContactError(
                "Kontakt musí mít alespoň telefon nebo e-mail."
            )
        return name, (role or "").strip(), phone_value, email_value

    def _validate_contact_type(self, contact_type: str) -> str:
        normalized = (contact_type or "").strip()
        if normalized not in CONTACT_TYPES:
            raise CoordinationContactError("Neplatný typ kontaktu.")
        return normalized


coordination_contact_service = CoordinationContactService()

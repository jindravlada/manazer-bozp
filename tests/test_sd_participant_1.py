"""SD-PARTICIPANT-1: doplnění údajů z evidence a zákaz duplicity účastníka."""

from __future__ import annotations

import importlib
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.statni_dozor.constants import (
        PARTICIPANT_CATALOG_DUPLICATE_MESSAGE,
        PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE,
        PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE,
        PARTICIPANT_ROLE_INSPECTOR,
        PARTICIPANT_ROLE_OTHER,
        PARTICIPANT_SOURCE_PERSON,
        PARTICIPANT_SOURCE_THP_WORKER,
    )
    from moduly.statni_dozor.modely.state_supervision_participant import (
        StateSupervisionParticipant,
    )
    from moduly.statni_dozor.modely.state_supervision_participant_draft import (
        StateSupervisionParticipantDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_participant_catalog import (
        catalog_participant_autofill,
        format_participant_contact,
    )
    from moduly.statni_dozor.sluzby.state_supervision_participant_service import (
        state_supervision_participant_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_participant_dialog import (
        StateSupervisionParticipantDialog,
    )


EMPLOYER_NAME = "Testovací zaměstnavatel a.s."


class SdParticipant1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        settings_service.save_employer(name=EMPLOYER_NAME, ico="12345678")
        self.supervision = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}"
        )
        self.employee = person_service.create_person(
            first_name="Interní",
            last_name=f"Zaměstnanec-{self.marker}",
            is_employee=True,
            email="interni@firma.test",
            phone="777111222",
        )
        self.external_person = person_service.create_person(
            first_name="Externí",
            last_name=f"Dodavatel-{self.marker}",
            organization="Dodavatel s.r.o.",
            email="ext@dodavatel.test",
            phone="608000111",
        )
        self.worker = settings_service.save_worker(
            first_name="Petr",
            last_name=f"THP-{self.marker}",
            email="thp@firma.test",
            phone="602333444",
        )

    def _dialog(self, **kwargs) -> StateSupervisionParticipantDialog:
        return StateSupervisionParticipantDialog(is_new=True, **kwargs)

    def _select_catalog(self, dialog, source_type: str, source_id: int) -> None:
        dialog.person_selector.set_ref(
            {"source_type": source_type, "source_id": int(source_id)}
        )

    def test_internal_person_without_organization_uses_employer(self) -> None:
        organization, contact = catalog_participant_autofill(
            PARTICIPANT_SOURCE_PERSON,
            self.employee.id,
        )
        self.assertEqual(organization, EMPLOYER_NAME)
        self.assertEqual(
            contact,
            format_participant_contact(self.employee.email, self.employee.phone),
        )

        dialog = self._dialog()
        self._select_catalog(dialog, PARTICIPANT_SOURCE_PERSON, self.employee.id)
        self.assertEqual(dialog.organization_edit.text(), EMPLOYER_NAME)
        self.assertFalse(dialog.organization_edit.isReadOnly())
        dialog._on_save()
        self.assertEqual(dialog.result_draft.organization_snapshot, EMPLOYER_NAME)
        dialog.close()

        thp_org, _contact = catalog_participant_autofill(
            PARTICIPANT_SOURCE_THP_WORKER,
            self.worker.id,
        )
        self.assertEqual(thp_org, EMPLOYER_NAME)
        dialog = self._dialog()
        self._select_catalog(dialog, PARTICIPANT_SOURCE_THP_WORKER, self.worker.id)
        self.assertEqual(dialog.organization_edit.text(), EMPLOYER_NAME)
        dialog.close()

    def test_person_with_own_organization_keeps_it(self) -> None:
        organization, _contact = catalog_participant_autofill(
            PARTICIPANT_SOURCE_PERSON,
            self.external_person.id,
        )
        self.assertEqual(organization, "Dodavatel s.r.o.")
        self.assertNotEqual(organization, EMPLOYER_NAME)

        dialog = self._dialog()
        self._select_catalog(dialog, PARTICIPANT_SOURCE_PERSON, self.external_person.id)
        self.assertEqual(dialog.organization_edit.text(), "Dodavatel s.r.o.")
        dialog.close()

    def test_catalog_contact_is_prefilled(self) -> None:
        _organization, contact = catalog_participant_autofill(
            PARTICIPANT_SOURCE_THP_WORKER,
            self.worker.id,
        )
        self.assertEqual(contact, "602333444 · thp@firma.test")

        dialog = self._dialog()
        self._select_catalog(dialog, PARTICIPANT_SOURCE_THP_WORKER, self.worker.id)
        self.assertEqual(dialog.contact_edit.text(), "602333444 · thp@firma.test")
        self.assertFalse(dialog.contact_edit.isReadOnly())
        dialog.contact_edit.setText("jiný kontakt")
        dialog._on_save()
        self.assertEqual(dialog.result_draft.contact_note, "jiný kontakt")
        dialog.close()

    def test_same_catalog_person_cannot_be_added_twice(self) -> None:
        first = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE,
            source_type=PARTICIPANT_SOURCE_THP_WORKER,
            source_id=self.worker.id,
        )
        self.assertEqual(first.source_id, self.worker.id)

        occupied = {(PARTICIPANT_SOURCE_THP_WORKER, int(self.worker.id))}
        dialog = self._dialog(occupied_catalog_identities=occupied)
        self._select_catalog(dialog, PARTICIPANT_SOURCE_THP_WORKER, self.worker.id)
        dialog.role_combo.setCurrentIndex(
            dialog.role_combo.findData(PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE)
        )
        with patch.object(QMessageBox, "warning") as warning:
            dialog._on_save()
            warning.assert_called()
            self.assertIn(
                PARTICIPANT_CATALOG_DUPLICATE_MESSAGE,
                warning.call_args.args,
            )
        self.assertIsNone(dialog.result_draft)
        dialog.close()

        with self.assertRaises(StateSupervisionError) as raised:
            state_supervision_participant_service.create_participant(
                self.supervision.id,
                role=PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE,
                source_type=PARTICIPANT_SOURCE_THP_WORKER,
                source_id=self.worker.id,
            )
        self.assertEqual(str(raised.exception), PARTICIPANT_CATALOG_DUPLICATE_MESSAGE)
        rows = state_supervision_participant_service.list_participants(
            self.supervision.id
        )
        self.assertEqual(len(rows), 1)

    def test_same_person_cannot_be_added_with_another_role(self) -> None:
        state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE,
            source_type=PARTICIPANT_SOURCE_PERSON,
            source_id=self.employee.id,
        )
        with self.assertRaises(StateSupervisionError) as raised:
            state_supervision_participant_service.create_participant(
                self.supervision.id,
                role=PARTICIPANT_ROLE_INSPECTOR,
                source_type=PARTICIPANT_SOURCE_PERSON,
                source_id=self.employee.id,
            )
        self.assertEqual(str(raised.exception), PARTICIPANT_CATALOG_DUPLICATE_MESSAGE)

    def test_editing_own_row_is_not_duplicate(self) -> None:
        row = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE,
            source_type=PARTICIPANT_SOURCE_PERSON,
            source_id=self.external_person.id,
            organization_snapshot="Původní org",
            contact_note="původní@test",
        )
        draft = StateSupervisionParticipantDraft(
            id=row.id,
            role=PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE,
            source_type=PARTICIPANT_SOURCE_PERSON,
            source_id=self.external_person.id,
            name_snapshot=row.name_snapshot,
            organization_snapshot="Upravená org",
            contact_note="novy@test",
            client_key="own-row",
        )
        dialog = StateSupervisionParticipantDialog(
            draft=draft,
            is_new=False,
            occupied_catalog_identities=set(),
        )
        self.assertEqual(dialog.organization_edit.text(), "Upravená org")
        self.assertEqual(dialog.contact_edit.text(), "novy@test")
        dialog._on_save()
        self.assertIsNotNone(dialog.result_draft)
        self.assertEqual(dialog.result_draft.source_id, self.external_person.id)
        dialog.close()

        updated = state_supervision_participant_service.update_participant(
            row.id,
            role=PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE,
            organization_snapshot="Upravená org",
        )
        self.assertEqual(updated.role, PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE)
        self.assertEqual(updated.source_id, self.external_person.id)

        other = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            source_type=PARTICIPANT_SOURCE_THP_WORKER,
            source_id=self.worker.id,
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.update_participant(
                other.id,
                source_type=PARTICIPANT_SOURCE_PERSON,
                source_id=self.external_person.id,
            )

    def test_manual_external_persons_are_not_deduplicated_by_name(self) -> None:
        first = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Ing. Novák",
        )
        second = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_OTHER,
            name_snapshot="Ing. Novák",
        )
        self.assertIsNone(first.source_type)
        self.assertIsNone(second.source_type)
        self.assertEqual(first.name_snapshot, second.name_snapshot)
        self.assertNotEqual(first.id, second.id)

        dialog = self._dialog(
            occupied_catalog_identities={
                (PARTICIPANT_SOURCE_PERSON, int(self.employee.id))
            }
        )
        dialog.external_name_edit.setText("Ing. Novák")
        dialog._on_save()
        self.assertIsNotNone(dialog.result_draft)
        self.assertIsNone(dialog.result_draft.source_id)
        dialog.close()

    def test_existing_duplicate_rows_can_still_be_saved(self) -> None:
        first = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE,
            source_type=PARTICIPANT_SOURCE_PERSON,
            source_id=self.employee.id,
        )
        twin = StateSupervisionParticipant(
            state_supervision_id=self.supervision.id,
            role=PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE,
            source_type=PARTICIPANT_SOURCE_PERSON,
            source_id=self.employee.id,
            name_snapshot=first.name_snapshot,
            display_order=10,
            active=True,
        )
        twin = state_supervision_participant_service.repository.add(twin)
        drafts = [
            state_supervision_participant_service._draft_from_record(first),
            state_supervision_participant_service._draft_from_record(twin),
        ]
        saved = state_supervision_participant_service.save_participant_batch(
            self.supervision.id,
            drafts,
        )
        self.assertEqual(len(saved), 2)
        self.assertEqual({row.source_id for row in saved}, {self.employee.id})


if __name__ == "__main__":
    unittest.main()

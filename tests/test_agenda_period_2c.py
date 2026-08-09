"""AGENDA-PERIOD-2c: přílohy historie periodických činností."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.attachment_service import attachment_service
    from moduly.periodicke_cinnosti.constants import (
        ENTITY_PERIODIC_OCCURRENCE,
        NEXT_FROM_PLANNED,
        UNIT_YEARS,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import PeriodicActivityDialog
    from moduly.periodicke_cinnosti.ui.periodic_performance_dialog import (
        PeriodicPerformanceDialog,
    )


class AgendaPeriod2cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for activity in list(periodic_activity_service.get_all()):
            periodic_activity_service.update_activity(
                activity.id,
                title=f"OLD-{activity.id}-{activity.title}",
                active=False,
                next_due_date=activity.next_due_date,
                repeat_every=activity.repeat_every,
                repeat_unit=activity.repeat_unit,
                notify_every=activity.notify_every,
                notify_unit=activity.notify_unit,
                next_from=activity.next_from,
                place_kind=activity.place_kind,
            )

    def _create_activity(self, title: str = "Měření hluku"):
        return periodic_activity_service.create_activity(
            title=title,
            next_due_date=date(2026, 6, 1),
            repeat_every=3,
            repeat_unit=UNIT_YEARS,
            next_from=NEXT_FROM_PLANNED,
            active=True,
        )

    def _temp_file(self, name: str, content: str = "protokol") -> Path:
        path = _TMP / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_add_attachment_to_occurrence(self) -> None:
        activity = self._create_activity()
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
            result_note="OK 2026",
        )
        source = self._temp_file("protokol_2026.pdf")
        attachment = attachment_service.add_file(
            ENTITY_PERIODIC_OCCURRENCE,
            occurrence.id,
            str(source),
        )
        self.assertIsNotNone(attachment)
        rows = attachment_service.get_for_entity(ENTITY_PERIODIC_OCCURRENCE, occurrence.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].filename, "protokol_2026.pdf")
        resolved = attachment_service.resolve_path(rows[0])
        self.assertTrue(resolved.exists())
        self.assertEqual(resolved.read_text(encoding="utf-8"), "protokol")

    def test_attachments_are_separated_per_occurrence(self) -> None:
        activity = self._create_activity()
        occ_2026 = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
            result_note="2026",
        )
        activity = periodic_activity_service.get_by_id(activity.id)
        occ_2029 = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2029, 5, 20),
            result_note="2029",
        )
        attachment_service.add_file(
            ENTITY_PERIODIC_OCCURRENCE,
            occ_2026.id,
            str(self._temp_file("protokol_2026.pdf", "2026")),
        )
        attachment_service.add_file(
            ENTITY_PERIODIC_OCCURRENCE,
            occ_2029.id,
            str(self._temp_file("protokol_2029.pdf", "2029")),
        )

        files_2026 = [
            item.filename
            for item in attachment_service.get_for_entity(
                ENTITY_PERIODIC_OCCURRENCE,
                occ_2026.id,
            )
        ]
        files_2029 = [
            item.filename
            for item in attachment_service.get_for_entity(
                ENTITY_PERIODIC_OCCURRENCE,
                occ_2029.id,
            )
        ]
        self.assertEqual(files_2026, ["protokol_2026.pdf"])
        self.assertEqual(files_2029, ["protokol_2029.pdf"])
        self.assertNotIn("protokol_2029.pdf", files_2026)
        self.assertNotIn("protokol_2026.pdf", files_2029)

    def test_open_and_remove_attachment(self) -> None:
        activity = self._create_activity()
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
        )
        attachment_service.add_file(
            ENTITY_PERIODIC_OCCURRENCE,
            occurrence.id,
            str(self._temp_file("ke_smazani.pdf")),
        )
        dialog = PeriodicActivityDialog(activity=periodic_activity_service.get_by_id(activity.id))
        self.assertEqual(dialog.history_table.rowCount(), 1)
        dialog.history_table.selectRow(0)
        self.assertEqual(dialog.history_attachments.list.count(), 1)
        self.assertEqual(dialog.history_attachments.entity_id, occurrence.id)

        with patch(
            "core.widgets.attachment_widget.open_local_file"
        ) as open_file:
            dialog.history_attachments.list.setCurrentRow(0)
            dialog.history_attachments.open_selected()
            open_file.assert_called_once()
            opened_path = open_file.call_args.args[0]
            self.assertTrue(Path(opened_path).exists())

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.history_attachments.list.setCurrentRow(0)
            dialog.history_attachments.remove_selected()

        self.assertEqual(
            attachment_service.get_for_entity(ENTITY_PERIODIC_OCCURRENCE, occurrence.id),
            [],
        )
        self.assertEqual(dialog.history_attachments.list.count(), 0)
        dialog._editor._closing = True
        dialog.close()

    def test_attachments_survive_deactivation(self) -> None:
        activity = self._create_activity()
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
        )
        attachment_service.add_file(
            ENTITY_PERIODIC_OCCURRENCE,
            occurrence.id,
            str(self._temp_file("zachovat.pdf")),
        )
        periodic_activity_service.update_activity(
            activity.id,
            title=activity.title,
            place_kind=activity.place_kind,
            next_due_date=activity.next_due_date,
            repeat_every=activity.repeat_every,
            repeat_unit=activity.repeat_unit,
            notify_every=activity.notify_every,
            notify_unit=activity.notify_unit,
            next_from=activity.next_from,
            note=activity.note or "",
            active=False,
            responsible_person_id=activity.responsible_person_id,
            responsible_person_name=activity.responsible_person_name or "",
            workplace_id=activity.workplace_id,
            workplace_name=activity.workplace_name or "",
            place_text=activity.place_text or "",
        )
        history = periodic_activity_service.list_occurrences(activity.id)
        self.assertEqual(len(history), 1)
        files = attachment_service.get_for_entity(ENTITY_PERIODIC_OCCURRENCE, occurrence.id)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].filename, "zachovat.pdf")
        self.assertTrue(attachment_service.resolve_path(files[0]).exists())

    def test_performance_dialog_enables_attachments_after_save(self) -> None:
        activity = self._create_activity("Provedeno s přílohou")
        dialog = PeriodicPerformanceDialog(
            activity_id=activity.id,
            activity_title=activity.title,
        )
        self.assertIsNone(dialog.attachments.entity_id)
        self.assertFalse(dialog.attachments.btn_add.isEnabled())
        self.assertTrue(dialog._editor._run_save())
        self.assertIsNotNone(dialog.occurrence)
        self.assertEqual(dialog.attachments.entity_id, dialog.occurrence.id)
        self.assertTrue(dialog.attachments.btn_add.isEnabled())

        source = self._temp_file("po_ulozeni.pdf")
        with patch.object(
            dialog.attachments,
            "add_attachment",
            wraps=dialog.attachments.add_attachment,
        ):
            attachment_service.add_file(
                ENTITY_PERIODIC_OCCURRENCE,
                dialog.occurrence.id,
                str(source),
            )
            dialog.attachments.reload()
        self.assertEqual(dialog.attachments.list.count(), 1)
        dialog._editor._closing = True
        dialog.close()


if __name__ == "__main__":
    unittest.main()

"""Vznik události ve Spisu vyšetřování MU (4.2.2)."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import text

_TMP = Path(tempfile.mkdtemp(prefix="mu-event-origin-422-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _ensure_mu_investigation_columns,
        _table_columns,
        initialize_database,
    )
    from core.database.session import get_session

    initialize_database()

    from core.utils.casove_rozdily import datetime_from_date_and_time
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.vysetrovani_mu.constants import SOURCE_TYPE_ACCIDENT, SOURCE_TYPE_MANUAL
    from moduly.vysetrovani_mu.sluzby.mu_chronologie_events import build_system_chronologie_events
    from moduly.vysetrovani_mu.sluzby.mu_investigation_service import mu_investigation_service
    from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog


class MuEventOrigin422TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _accident(self, *, accident_date: date | None, accident_time: str) -> object:
        return accident_service.create_accident(
            jmeno_prijmeni="Jan Novák",
            popis_urazoveho_deje="Pád na pracovišti",
            accident_date=accident_date,
            accident_time=accident_time,
        )

    def _open(self, investigation=None, *, accident_id: int | None = None) -> MuInvestigationDialog:
        dialog = MuInvestigationDialog(investigation=investigation, accident_id=accident_id)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: MuInvestigationDialog) -> None:
        dialog._closing = True
        dialog.close()
        dialog.deleteLater()
        self.app.processEvents()

    def _reload(self, investigation_id: int):
        return mu_investigation_service.get_by_id(investigation_id)

    def _clear_stored_origin(self, investigation_id: int) -> None:
        with get_session() as session:
            session.execute(
                text(
                    "UPDATE mu_investigations "
                    "SET event_date = NULL, event_time = NULL "
                    "WHERE id = :id"
                ),
                {"id": investigation_id},
            )
            session.commit()

    def _raw_origin(self, investigation_id: int) -> tuple:
        with get_session() as session:
            row = session.execute(
                text(
                    "SELECT event_date, event_time, updated_at "
                    "FROM mu_investigations WHERE id = :id"
                ),
                {"id": investigation_id},
            ).one()
            return row.event_date, row.event_time, row.updated_at

    def _vznik(self, events: list[dict]) -> dict | None:
        for event in events:
            if event.get("typ") == "Událost":
                return event
        return None

    def _assert_same_origin(self, dialog: MuInvestigationDialog) -> None:
        form_date, form_time = dialog._form_event_origin()
        snapshot = dialog.build_check_snapshot()
        self.assertEqual(snapshot["event_datum"], form_date)
        self.assertEqual(snapshot["event_cas"], form_time)

        widget_event = self._vznik(dialog.casova_osa_widget._system_chronologie_events())
        check_event = self._vznik(
            build_system_chronologie_events(
                started_at=snapshot.get("started_at"),
                source_type=snapshot.get("source_type") or "",
                source_id=snapshot.get("source_id"),
                oznameni_datum=(snapshot.get("oznameni") or {}).get("oznameni_datum"),
                oznameni_cas=(snapshot.get("oznameni") or {}).get("oznameni_cas") or "",
                event_datum=snapshot.get("event_datum"),
                event_cas=snapshot.get("event_cas") or "",
                event_origin_from_spis=True,
            )
        )
        self.assertEqual(widget_event, check_event)
        self.assertEqual(
            dialog.casova_osa_widget._reference_event_datetime(),
            datetime_from_date_and_time(form_date, form_time),
        )

    def test_manual_investigation_keeps_empty_origin_until_filled(self) -> None:
        dialog = self._open()
        try:
            dialog._set_source_type(SOURCE_TYPE_MANUAL)
            self.assertIsNone(dialog.event_date_edit.get_date())
            self.assertEqual(dialog.event_time_edit.text(), "")
            self.assertIs(dialog.event_date_edit.parentWidget(), dialog.event_time_edit.parentWidget())
            self.assertIsNone(dialog.casova_osa_widget._reference_event_datetime())
            dialog.title_edit.setText("Ruční vyšetřování")
            self.assertTrue(dialog._persist())
            investigation_id = dialog.investigation.id
        finally:
            self._close(dialog)

        stored = self._reload(investigation_id)
        self.assertEqual(stored.source_type, SOURCE_TYPE_MANUAL)
        self.assertIsNone(stored.event_date)
        self.assertEqual(stored.event_time, "")

        reopened = self._open(stored)
        try:
            self.assertIsNone(reopened.event_date_edit.get_date())
            self.assertEqual(reopened.event_time_edit.text(), "")
            reopened.event_date_edit.set_date_value(date(2026, 5, 2))
            reopened.event_time_edit.setText("8:15")
            self._assert_same_origin(reopened)
            vznik = self._vznik(reopened.casova_osa_widget._system_chronologie_events())
            self.assertIsNotNone(vznik)
            self.assertEqual(vznik["datum"], "2026-05-02")
            self.assertEqual(vznik["cas"], "08:15")
            self.assertEqual(vznik["popis"], "Vznik události.")
            self.assertEqual(
                reopened.casova_osa_widget._reference_event_datetime(),
                datetime(2026, 5, 2, 8, 15),
            )
            self.assertTrue(reopened._persist())
        finally:
            self._close(reopened)

        saved = self._reload(investigation_id)
        self.assertEqual(saved.event_date, date(2026, 5, 2))
        self.assertEqual(saved.event_time, "08:15")

    def test_new_investigation_from_accident_copies_origin_once(self) -> None:
        accident = self._accident(accident_date=date(2026, 3, 4), accident_time="7:05")
        dialog = self._open(accident_id=accident.id)
        try:
            self.assertEqual(dialog.event_date_edit.get_date(), date(2026, 3, 4))
            self.assertEqual(dialog.event_time_edit.text(), "07:05")
            self._assert_same_origin(dialog)
            dialog.title_edit.setText("Vyšetřování z úrazu")
            self.assertTrue(dialog._persist())
            investigation_id = dialog.investigation.id
        finally:
            self._close(dialog)

        stored = self._reload(investigation_id)
        self.assertEqual(stored.event_date, date(2026, 3, 4))
        self.assertEqual(stored.event_time, "07:05")
        self.assertEqual(stored.source_type, SOURCE_TYPE_ACCIDENT)
        self.assertEqual(stored.source_id, accident.id)

        unchanged = accident_service.get_by_id(accident.id)
        self.assertEqual(unchanged.accident_date, date(2026, 3, 4))
        self.assertEqual(unchanged.accident_time, "7:05")

        accident_service.update_accident(
            accident.id,
            accident_date=date(2026, 1, 1),
            accident_time="23:59",
        )
        reopened = self._open(self._reload(investigation_id))
        try:
            self.assertEqual(reopened.event_date_edit.get_date(), date(2026, 3, 4))
            self.assertEqual(reopened.event_time_edit.text(), "07:05")
            self.assertEqual(
                reopened.casova_osa_widget._reference_event_datetime(),
                datetime(2026, 3, 4, 7, 5),
            )
            self._assert_same_origin(reopened)
        finally:
            self._close(reopened)

        still = self._reload(investigation_id)
        self.assertEqual(still.event_date, date(2026, 3, 4))
        self.assertEqual(still.event_time, "07:05")

    def test_legacy_accident_investigation_shows_source_without_writing(self) -> None:
        accident = self._accident(accident_date=date(2026, 4, 8), accident_time="16:40")
        created = mu_investigation_service.create_investigation(
            title="Starší spis",
            source_type=SOURCE_TYPE_ACCIDENT,
            source_id=accident.id,
            source_label="Úraz 16:40",
            started_at=date(2026, 4, 9),
        )
        self._clear_stored_origin(created.id)
        before_date, before_time, before_updated = self._raw_origin(created.id)
        self.assertIsNone(before_date)
        self.assertIsNone(before_time)

        dialog = self._open(self._reload(created.id))
        try:
            self.assertEqual(dialog.event_date_edit.get_date(), date(2026, 4, 8))
            self.assertEqual(dialog.event_time_edit.text(), "16:40")
            self.assertFalse(dialog._is_dirty())
            self._assert_same_origin(dialog)
            self.assertEqual(
                dialog.casova_osa_widget._reference_event_datetime(),
                datetime(2026, 4, 8, 16, 40),
            )
            dialog.reject()
        finally:
            self._close(dialog)

        after_date, after_time, after_updated = self._raw_origin(created.id)
        self.assertIsNone(after_date)
        self.assertIsNone(after_time)
        self.assertEqual(after_updated, before_updated)

    def test_legacy_origin_is_stored_on_first_save_and_then_independent(self) -> None:
        accident = self._accident(accident_date=date(2026, 6, 1), accident_time="9:30")
        created = mu_investigation_service.create_investigation(
            title="Starší spis k uložení",
            source_type=SOURCE_TYPE_ACCIDENT,
            source_id=accident.id,
            source_label="Úraz 9:30",
            started_at=date(2026, 6, 2),
        )
        self._clear_stored_origin(created.id)

        dialog = self._open(self._reload(created.id))
        try:
            self.assertEqual(dialog.event_date_edit.get_date(), date(2026, 6, 1))
            self.assertEqual(dialog.event_time_edit.text(), "09:30")
            self.assertTrue(dialog._persist())
        finally:
            self._close(dialog)

        stored = self._reload(created.id)
        self.assertEqual(stored.event_date, date(2026, 6, 1))
        self.assertEqual(stored.event_time, "09:30")

        accident_service.update_accident(
            accident.id,
            accident_date=date(2025, 12, 31),
            accident_time="01:00",
        )
        reopened = self._open(self._reload(created.id))
        try:
            self.assertEqual(reopened.event_date_edit.get_date(), date(2026, 6, 1))
            self.assertEqual(reopened.event_time_edit.text(), "09:30")
            self._assert_same_origin(reopened)
        finally:
            self._close(reopened)

    def test_missing_date_or_time_is_not_replaced_by_midnight(self) -> None:
        dialog = self._open()
        try:
            dialog.event_date_edit.set_date_value(date(2026, 7, 3))
            dialog.event_time_edit.setText("")
            self.assertIsNone(dialog.casova_osa_widget._reference_event_datetime())
            vznik = self._vznik(dialog.casova_osa_widget._system_chronologie_events())
            self.assertEqual(vznik["datum"], "2026-07-03")
            self.assertEqual(vznik["cas"], "")
            label = dialog.casova_osa_widget.navaznost_rozdil_oznameni_label.text()
            self.assertIn("nelze spočítat", label)
            self.assertNotIn("00:00", label)
            self._assert_same_origin(dialog)

            dialog.event_date_edit.clear_date()
            dialog.event_time_edit.setText("11:20")
            self.assertIsNone(dialog.event_date_edit.get_date())
            self.assertEqual(dialog.event_time_edit.text(), "11:20")
            self.assertIsNone(dialog.casova_osa_widget._reference_event_datetime())
            self.assertIsNone(self._vznik(dialog.casova_osa_widget._system_chronologie_events()))
            self._assert_same_origin(dialog)
        finally:
            self._close(dialog)

        without_time = self._accident(accident_date=date(2026, 8, 1), accident_time="")
        from_accident = self._open(accident_id=without_time.id)
        try:
            self.assertEqual(from_accident.event_date_edit.get_date(), date(2026, 8, 1))
            self.assertEqual(from_accident.event_time_edit.text(), "")
            self.assertIsNone(from_accident.casova_osa_widget._reference_event_datetime())
            vznik = self._vznik(from_accident.casova_osa_widget._system_chronologie_events())
            self.assertEqual(vznik["cas"], "")
            self.assertNotEqual(vznik["cas"], "00:00")
        finally:
            self._close(from_accident)

        without_date = self._accident(accident_date=None, accident_time="06:45")
        time_only = self._open(accident_id=without_date.id)
        try:
            self.assertIsNone(time_only.event_date_edit.get_date())
            self.assertEqual(time_only.event_time_edit.text(), "06:45")
            self.assertIsNone(time_only.casova_osa_widget._reference_event_datetime())
            self.assertIsNone(self._vznik(time_only.casova_osa_widget._system_chronologie_events()))
        finally:
            self._close(time_only)

    def test_added_columns_leave_existing_rows_empty(self) -> None:
        accident = self._accident(accident_date=date(2026, 2, 2), accident_time="12:00")
        created = mu_investigation_service.create_investigation(
            title="Řádek před doplněním sloupců",
            source_type=SOURCE_TYPE_ACCIDENT,
            source_id=accident.id,
            started_at=date(2026, 2, 2),
        )
        with get_session() as session:
            session.execute(text("ALTER TABLE mu_investigations DROP COLUMN event_date"))
            session.execute(text("ALTER TABLE mu_investigations DROP COLUMN event_time"))
            session.commit()
        try:
            self.assertNotIn("event_date", _table_columns("mu_investigations"))
            _ensure_mu_investigation_columns()
            self.assertIn("event_date", _table_columns("mu_investigations"))
            self.assertIn("event_time", _table_columns("mu_investigations"))
            event_date, event_time, _updated = self._raw_origin(created.id)
            self.assertIsNone(event_date)
            self.assertIsNone(event_time)
        finally:
            _ensure_mu_investigation_columns()

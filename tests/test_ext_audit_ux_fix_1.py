"""EXT-AUDIT-UX-FIX-1: řazení Připomínek a přehled programu návštěv."""

from __future__ import annotations

import importlib
import os
import re
import tempfile
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QHeaderView, QSizePolicy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="ext-audit-ux-fix-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.widget_today import (
        TodayWidget,
        reminder_display_sort_key,
    )
    from core.widgets.dialog_utils import prepare_work_dialog_maximized
    from moduly.externi_audity.constants import (
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
        EXTERNAL_AUDIT_SOURCE_PERSON,
        EXTERNAL_AUDIT_SOURCE_THP_WORKER,
        EXTERNAL_AUDIT_STATUS_PLANNED,
        EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
        format_display_date,
    )
    from moduly.externi_audity.sluzby.external_audit_draft import (
        ExternalAuditDraft,
        ParticipantDraft,
        VisitDraft,
        new_client_key,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
        external_audit_service,
    )
    from moduly.externi_audity.ui.external_audit_editor_dialog import (
        ExternalAuditEditorDialog,
    )
    from moduly.externi_audity.ui.external_audit_visit_dialog import (
        ExternalAuditVisitDialog,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import NEXT_FROM_PLANNED, UNIT_DAYS, UNIT_YEARS
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.schuzky.constants import STATUS_CANCELLED, STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.agenda.constants import PRIORITY_CRITICAL, PRIORITY_NORMAL
    from moduly.ukoly.sluzby.task_service import task_service


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _displayed_dates(html: str) -> list[date]:
    found: list[date] = []
    for raw in re.findall(r"<b>(\d{2}\.\d{2}\.\d{4})</b>", html):
        day, month, year = (int(part) for part in raw.split("."))
        found.append(date(year, month, day))
    return found


class ExtAuditUxFix1RemindersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)
        for meeting in list(meeting_service.get_all()):
            if (meeting.status or "") != STATUS_PLANNED:
                continue
            meeting_service.update_meeting(
                meeting.id,
                title=meeting.title or "",
                starts_at=meeting.starts_at,
                ends_at=meeting.ends_at,
                location=meeting.location or "",
                organizer_person_id=meeting.organizer_person_id,
                participant_ids=meeting_service.parse_participant_ids(meeting),
                agenda=meeting.agenda or "",
                status=STATUS_CANCELLED,
            )
        for activity in list(periodic_activity_service.get_all()):
            if activity.active:
                periodic_activity_service.update_activity(
                    activity.id,
                    title=activity.title,
                    active=False,
                    next_due_date=activity.next_due_date,
                    repeat_every=activity.repeat_every,
                    repeat_unit=activity.repeat_unit,
                    notify_every=activity.notify_every,
                    notify_unit=activity.notify_unit,
                    next_from=activity.next_from,
                    place_kind=activity.place_kind,
                )
        if not yearly_plan_service.is_month_processed(2026, 9):
            yearly_plan_service.mark_month_processed(2026, 9)

    def test_a_09_september_before_10_september(self) -> None:
        today = date(2026, 9, 9)
        task_service.create_task(
            title="Odstranit staré štítky elektrorevizí",
            due_date=date(2026, 9, 9),
            priority=PRIORITY_NORMAL,
        )
        task_service.create_task(
            title="Školení k OOPP",
            due_date=date(2026, 9, 9),
            priority=PRIORITY_NORMAL,
        )
        meeting_service.create_meeting(
            title="Setkání bezpečáků",
            event_type="Schůzka",
            starts_at=datetime(2026, 9, 10, 8, 0),
            ends_at=datetime(2026, 9, 10, 10, 0),
            remind_from=date(2026, 9, 9),
            status=STATUS_PLANNED,
        )
        widget = TodayWidget()
        widget.refresh(today=today)
        html = widget.content.text()
        widget.close()

        self.assertIn("Odstranit staré štítky elektrorevizí", html)
        self.assertIn("Školení k OOPP", html)
        self.assertIn("Setkání bezpečáků", html)
        self.assertLess(html.index("Odstranit staré štítky"), html.index("Setkání bezpečáků"))
        self.assertLess(html.index("Školení k OOPP"), html.index("Setkání bezpečáků"))
        dates = _displayed_dates(html)
        self.assertEqual(dates, sorted(dates))
        self.assertLess(dates.index(date(2026, 9, 9)), dates.index(date(2026, 9, 10)))

    def test_b_mixed_types_sort_by_real_due_not_formatted_text(self) -> None:
        today = date(2026, 9, 9)
        task_service.create_task(
            title="Úkol 10.09",
            due_date=date(2026, 9, 10),
            remind_from=date(2026, 9, 9),
            priority=PRIORITY_CRITICAL,
        )
        meeting_service.create_meeting(
            title="Událost 09.09",
            event_type="Schůzka",
            starts_at=datetime(2026, 9, 9, 15, 0),
            ends_at=datetime(2026, 9, 9, 16, 0),
            remind_from=date(2026, 9, 9),
            status=STATUS_PLANNED,
        )
        periodic_activity_service.create_activity(
            title="Periodika 11.09",
            next_due_date=date(2026, 9, 11),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            notify_every=2,
            notify_unit=UNIT_DAYS,
            next_from=NEXT_FROM_PLANNED,
            active=True,
        )
        later_task = task_service.create_task(
            title="Úkol 02.10",
            due_date=date(2026, 10, 2),
            remind_from=date(2026, 9, 9),
            priority=PRIORITY_NORMAL,
        )
        widget = TodayWidget()
        widget.refresh(today=today)
        html = widget.content.text()
        widget.close()

        order = [
            html.index("Událost 09.09"),
            html.index("Úkol 10.09"),
            html.index("Periodika 11.09"),
            html.index("Úkol 02.10"),
        ]
        self.assertEqual(order, sorted(order))
        # Lexikograficky by „02.10.2026“ bylo před „10.09.2026“.
        self.assertGreater(
            html.index("02.10.2026"),
            html.index("10.09.2026"),
        )
        self.assertIsNotNone(later_task.id)
        later_key = reminder_display_sort_key(
            due_date=date(2026, 10, 2),
            title="Úkol 02.10",
        )
        earlier_key = reminder_display_sort_key(
            due_date=date(2026, 9, 10),
            title="Úkol 10.09",
        )
        self.assertLess(earlier_key, later_key)


class ExtAuditUxFix1ProgramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        suffix = uuid.uuid4().hex[:6]
        self.wp_a = settings_service.save_workplace(
            name=f"Provoz-A-{suffix}",
            address="Hala A",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.wp_b = settings_service.save_workplace(
            name=f"Provoz-B-{suffix}",
            address="Hala B",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.auditor_a = person_service.create_person(
            first_name="Eva",
            last_name=f"AuditorA-{suffix}",
        )
        self.auditor_b = person_service.create_person(
            first_name="Petr",
            last_name=f"AuditorB-{suffix}",
        )
        self.rep_a = settings_service.save_worker(
            first_name="Jana",
            last_name=f"ZastupA-{suffix}",
        )
        self.rep_b = settings_service.save_worker(
            first_name="Karel",
            last_name=f"ZastupB-{suffix}",
        )
        self.invited_a = person_service.create_person(
            first_name="Olga",
            last_name=f"HostA-{suffix}",
        )
        self.invited_b = person_service.create_person(
            first_name="Ivan",
            last_name=f"HostB-{suffix}",
        )

    def _participants(self) -> tuple[list[ParticipantDraft], dict[str, str]]:
        keys = {
            "aud_a": new_client_key(),
            "aud_b": new_client_key(),
            "rep_a": new_client_key(),
            "rep_b": new_client_key(),
            "inv_a": new_client_key(),
            "inv_b": new_client_key(),
        }
        participants = [
            ParticipantDraft(
                client_key=keys["aud_a"],
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
                source_id=int(self.auditor_a.id),
                display_name_snapshot=self.auditor_a.display_name,
                display_order=10,
            ),
            ParticipantDraft(
                client_key=keys["aud_b"],
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
                source_id=int(self.auditor_b.id),
                display_name_snapshot=self.auditor_b.display_name,
                display_order=20,
            ),
            ParticipantDraft(
                client_key=keys["rep_a"],
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
                source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
                source_id=int(self.rep_a.id),
                display_name_snapshot=self.rep_a.display_name,
                display_order=10,
            ),
            ParticipantDraft(
                client_key=keys["rep_b"],
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
                source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
                source_id=int(self.rep_b.id),
                display_name_snapshot=self.rep_b.display_name,
                display_order=20,
            ),
            ParticipantDraft(
                client_key=keys["inv_a"],
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
                source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
                source_id=int(self.invited_a.id),
                display_name_snapshot=self.invited_a.display_name,
                display_order=10,
            ),
            ParticipantDraft(
                client_key=keys["inv_b"],
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
                source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
                source_id=int(self.invited_b.id),
                display_name_snapshot=self.invited_b.display_name,
                display_order=20,
            ),
        ]
        return participants, keys

    def _visit(
        self,
        *,
        visit_date: date,
        workplace,
        time_from: str,
        time_to: str,
        keys: list[str],
        note: str,
        display_order: int,
    ) -> VisitDraft:
        return VisitDraft(
            client_key=new_client_key(),
            visit_date=visit_date,
            workplace_id=int(workplace.id),
            workplace_name_snapshot=workplace.name,
            workplace_address_snapshot=workplace.address or "",
            time_from=time_from,
            time_to=time_to,
            note=note,
            display_order=display_order,
            participant_keys=list(keys),
        )

    def _open_editor(self, participants: list[ParticipantDraft]) -> ExternalAuditEditorDialog:
        editor = ExternalAuditEditorDialog()
        editor.ico.setText("12345678")
        editor.organization_name.setText("CertOrg UX")
        editor.organization_address.setText("Praha")
        editor._draft.participants = list(participants)
        editor._refresh_participant_lists()
        return editor

    def _close_editor(self, editor: ExternalAuditEditorDialog) -> None:
        editor._draft.attachments.clear()
        editor._closing = True
        editor.close()

    def _row_by_date(self, editor: ExternalAuditEditorDialog, visit_date: date) -> int:
        wanted = format_display_date(visit_date)
        for row in range(editor.visits_table.rowCount()):
            item = editor.visits_table.item(row, 0)
            if item is not None and item.text() == wanted:
                return row
        self.fail(f"Řádek {wanted} v programu chybí.")

    def _row_payload(self, editor: ExternalAuditEditorDialog, visit_date: date) -> dict:
        row = self._row_by_date(editor, visit_date)
        return {
            "date": editor.visits_table.item(row, 0).text(),
            "time_from": editor.visits_table.item(row, 1).text(),
            "time_to": editor.visits_table.item(row, 2).text(),
            "workplace": editor.visits_table.item(row, 3).text(),
            "auditors": editor.visits_table.item(row, 4).text(),
            "reps": editor.visits_table.item(row, 5).text(),
            "invited": editor.visits_table.item(row, 6).text(),
            "note": editor.visits_table.item(row, 7).text(),
            "key": editor.visits_table.item(row, 0).data(Qt.ItemDataRole.UserRole),
        }

    def _assert_first_row(self, payload: dict) -> None:
        self.assertEqual(payload["date"], "25.03.2026")
        self.assertEqual(payload["time_from"], "08:00")
        self.assertEqual(payload["time_to"], "14:00")
        self.assertEqual(payload["workplace"], self.wp_a.name)
        self.assertIn(self.auditor_a.display_name, payload["auditors"])
        self.assertNotIn(self.auditor_b.display_name, payload["auditors"])
        self.assertIn(self.rep_a.display_name, payload["reps"])
        self.assertNotIn(self.rep_b.display_name, payload["reps"])
        self.assertIn(self.invited_a.display_name, payload["invited"])
        self.assertEqual(payload["note"], "První den")

    def _assert_second_row(self, payload: dict) -> None:
        self.assertEqual(payload["date"], "26.03.2026")
        self.assertEqual(payload["time_from"], "08:00")
        self.assertEqual(payload["time_to"], "09:00")
        self.assertEqual(payload["workplace"], self.wp_b.name)
        self.assertIn(self.auditor_b.display_name, payload["auditors"])
        self.assertNotIn(self.auditor_a.display_name, payload["auditors"])
        self.assertIn(self.rep_b.display_name, payload["reps"])
        self.assertNotIn(self.rep_a.display_name, payload["reps"])
        self.assertIn(self.invited_b.display_name, payload["invited"])
        self.assertEqual(payload["note"], "Druhý den")

    def test_c_d_e_two_visits_keep_independent_rows(self) -> None:
        participants, keys = self._participants()
        editor = self._open_editor(participants)
        first = self._visit(
            visit_date=date(2026, 3, 25),
            workplace=self.wp_a,
            time_from="08:00",
            time_to="14:00",
            keys=[keys["aud_a"], keys["rep_a"], keys["inv_a"]],
            note="První den",
            display_order=10,
        )
        editor._draft.visits.append(first)
        editor.visits_table.horizontalHeader().setSortIndicator(
            0, Qt.SortOrder.DescendingOrder
        )
        editor._refresh_visits_table()
        self.assertEqual(editor.visits_table.rowCount(), 1)
        self._assert_first_row(self._row_payload(editor, date(2026, 3, 25)))

        second = self._visit(
            visit_date=date(2026, 3, 26),
            workplace=self.wp_b,
            time_from="08:00",
            time_to="09:00",
            keys=[keys["aud_b"], keys["rep_b"], keys["inv_b"]],
            note="Druhý den",
            display_order=20,
        )
        editor._draft.visits.append(second)
        editor._refresh_visits_table()
        self.assertEqual(editor.visits_table.rowCount(), 2)
        self._assert_first_row(self._row_payload(editor, date(2026, 3, 25)))
        self._assert_second_row(self._row_payload(editor, date(2026, 3, 26)))
        self.assertNotEqual(
            self._row_payload(editor, date(2026, 3, 25))["key"],
            self._row_payload(editor, date(2026, 3, 26))["key"],
        )
        self._close_editor(editor)

    def test_db_keeps_independent_visits_after_save(self) -> None:
        participants, keys = self._participants()
        editor = self._open_editor(participants)
        editor._draft.visits = [
            self._visit(
                visit_date=date(2026, 3, 25),
                workplace=self.wp_a,
                time_from="08:00",
                time_to="14:00",
                keys=[keys["aud_a"], keys["rep_a"], keys["inv_a"]],
                note="První den",
                display_order=10,
            ),
            self._visit(
                visit_date=date(2026, 3, 26),
                workplace=self.wp_b,
                time_from="08:00",
                time_to="09:00",
                keys=[keys["aud_b"], keys["rep_b"], keys["inv_b"]],
                note="Druhý den",
                display_order=20,
            ),
        ]
        editor._refresh_visits_table()
        self.assertTrue(editor._persist())
        audit_id = int(editor._draft.audit_id)
        self._close_editor(editor)

        detail = external_audit_service.get_detail(audit_id)
        by_date = {visit.visit_date: visit for visit in detail.visits}
        self.assertEqual(set(by_date), {date(2026, 3, 25), date(2026, 3, 26)})
        first = by_date[date(2026, 3, 25)]
        second = by_date[date(2026, 3, 26)]
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.time_from, "08:00")
        self.assertEqual(first.time_to, "14:00")
        self.assertEqual(first.workplace_id, int(self.wp_a.id))
        self.assertEqual(first.note, "První den")
        self.assertEqual(second.time_from, "08:00")
        self.assertEqual(second.time_to, "09:00")
        self.assertEqual(second.workplace_id, int(self.wp_b.id))
        self.assertEqual(second.note, "Druhý den")
        first_pids = set(detail.visit_participant_ids.get(int(first.id), []))
        second_pids = set(detail.visit_participant_ids.get(int(second.id), []))
        self.assertTrue(first_pids)
        self.assertTrue(second_pids)
        self.assertFalse(first_pids & second_pids)

        reopened = ExternalAuditEditorDialog(audit_id=audit_id)
        self._assert_first_row(self._row_payload(reopened, date(2026, 3, 25)))
        self._assert_second_row(self._row_payload(reopened, date(2026, 3, 26)))
        self._close_editor(reopened)

    def test_f_opening_row_matches_overview(self) -> None:
        participants, keys = self._participants()
        first = self._visit(
            visit_date=date(2026, 3, 25),
            workplace=self.wp_a,
            time_from="08:00",
            time_to="14:00",
            keys=[keys["aud_a"], keys["rep_a"], keys["inv_a"]],
            note="První den",
            display_order=10,
        )
        second = self._visit(
            visit_date=date(2026, 3, 26),
            workplace=self.wp_b,
            time_from="08:00",
            time_to="09:00",
            keys=[keys["aud_b"], keys["rep_b"], keys["inv_b"]],
            note="Druhý den",
            display_order=20,
        )
        editor = self._open_editor(participants)
        editor._draft.visits = [first, second]
        editor._refresh_visits_table()
        for visit in (first, second):
            row = self._row_by_date(editor, visit.visit_date)
            editor.visits_table.selectRow(row)
            key = editor._selected_visit_key()
            loaded = next(item for item in editor._draft.visits if item.client_key == key)
            payload = self._row_payload(editor, visit.visit_date)
            self.assertEqual(loaded.time_from, payload["time_from"])
            self.assertEqual(loaded.time_to, payload["time_to"])
            self.assertEqual(loaded.workplace_name_snapshot, payload["workplace"])
            self.assertEqual(loaded.note, payload["note"])
            dialog = ExternalAuditVisitDialog(
                editor, visit=loaded, participants=editor._draft.participants
            )
            self.assertEqual(dialog.visit_date.get_date(), visit.visit_date)
            self.assertEqual(dialog.time_from.get_time().strftime("%H:%M"), visit.time_from)
            self.assertEqual(dialog.time_to.get_time().strftime("%H:%M"), visit.time_to)
            dialog.close()
        self._close_editor(editor)

    def test_g_h_editing_one_visit_does_not_change_the_other(self) -> None:
        participants, keys = self._participants()
        editor = self._open_editor(participants)
        first = self._visit(
            visit_date=date(2026, 3, 25),
            workplace=self.wp_a,
            time_from="08:00",
            time_to="14:00",
            keys=[keys["aud_a"], keys["rep_a"], keys["inv_a"]],
            note="První den",
            display_order=10,
        )
        second = self._visit(
            visit_date=date(2026, 3, 26),
            workplace=self.wp_b,
            time_from="08:00",
            time_to="09:00",
            keys=[keys["aud_b"], keys["rep_b"], keys["inv_b"]],
            note="Druhý den",
            display_order=20,
        )
        editor._draft.visits = [first, second]
        editor._refresh_visits_table()

        def _edit_selected(result: VisitDraft):
            def fake_exec(dialog):
                dialog.result_visit = result
                return QDialog.DialogCode.Accepted

            with patch(
                "moduly.externi_audity.ui.external_audit_editor_dialog.exec_maximized",
                side_effect=fake_exec,
            ):
                editor._edit_visit()

        editor.visits_table.selectRow(self._row_by_date(editor, date(2026, 3, 26)))
        edited_second = VisitDraft(
            client_key=second.client_key,
            visit_date=second.visit_date,
            workplace_id=second.workplace_id,
            workplace_name_snapshot=second.workplace_name_snapshot,
            workplace_address_snapshot=second.workplace_address_snapshot,
            time_from="10:00",
            time_to="11:00",
            note="Upravený druhý den",
            display_order=second.display_order,
            participant_keys=list(second.participant_keys),
            db_id=second.db_id,
        )
        _edit_selected(edited_second)
        self._assert_first_row(self._row_payload(editor, date(2026, 3, 25)))
        second_payload = self._row_payload(editor, date(2026, 3, 26))
        self.assertEqual(second_payload["time_from"], "10:00")
        self.assertEqual(second_payload["time_to"], "11:00")
        self.assertEqual(second_payload["note"], "Upravený druhý den")

        editor.visits_table.selectRow(self._row_by_date(editor, date(2026, 3, 25)))
        edited_first = VisitDraft(
            client_key=first.client_key,
            visit_date=first.visit_date,
            workplace_id=first.workplace_id,
            workplace_name_snapshot=first.workplace_name_snapshot,
            workplace_address_snapshot=first.workplace_address_snapshot,
            time_from="07:00",
            time_to="13:00",
            note="Upravený první den",
            display_order=first.display_order,
            participant_keys=list(first.participant_keys),
            db_id=first.db_id,
        )
        _edit_selected(edited_first)
        first_payload = self._row_payload(editor, date(2026, 3, 25))
        self.assertEqual(first_payload["time_from"], "07:00")
        self.assertEqual(first_payload["time_to"], "13:00")
        self.assertEqual(first_payload["note"], "Upravený první den")
        second_payload = self._row_payload(editor, date(2026, 3, 26))
        self.assertEqual(second_payload["time_from"], "10:00")
        self.assertEqual(second_payload["time_to"], "11:00")
        self.assertEqual(second_payload["note"], "Upravený druhý den")
        self._close_editor(editor)

    def test_i_new_visit_opens_maximized_with_single_line_date(self) -> None:
        editor = ExternalAuditEditorDialog()
        opened: list[ExternalAuditVisitDialog] = []

        def fake_exec(dialog):
            with patch.object(dialog, "showMaximized") as mock_show:
                prepare_work_dialog_maximized(dialog)
                mock_show.assert_called()
            dialog.resize(1400, 900)
            dialog.show()
            QApplication.processEvents()
            opened.append(dialog)
            date_h = dialog.visit_date.height()
            time_h = dialog.time_from.parentWidget().height()
            workplace_h = dialog.workplace.height()
            self.assertLessEqual(date_h, 48)
            self.assertLessEqual(time_h, 48)
            self.assertGreaterEqual(date_h, 28)
            self.assertLessEqual(abs(date_h - workplace_h), 16)
            self.assertGreater(dialog.auditor_list.height(), date_h)
            self.assertGreater(dialog.note.height(), date_h)
            return QDialog.DialogCode.Rejected

        with patch(
            "moduly.externi_audity.ui.external_audit_editor_dialog.exec_maximized",
            side_effect=fake_exec,
        ):
            editor._add_visit()
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].windowTitle(), "Nová návštěva")
        opened[0].close()
        self._close_editor(editor)

        dialog = ExternalAuditVisitDialog(participants=[])
        dialog.resize(1400, 900)
        dialog.show()
        QApplication.processEvents()
        self.assertEqual(
            dialog.visit_date.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Fixed,
        )
        self.assertLessEqual(dialog.visit_date.height(), 48)
        self.assertGreaterEqual(dialog.note.minimumHeight(), 80)
        dialog.close()

    def test_program_table_still_stretches_text_columns(self) -> None:
        participants, keys = self._participants()
        saved = external_audit_service.save_bundle(
            ExternalAuditDraft(
                audit_id=None,
                audit_type=EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
                status=EXTERNAL_AUDIT_STATUS_PLANNED,
                organization_ico="87654321",
                organization_name="Stretch Org",
                organization_address="",
                participants=participants,
                visits=[
                    self._visit(
                        visit_date=date(2026, 3, 25),
                        workplace=self.wp_a,
                        time_from="08:00",
                        time_to="14:00",
                        keys=[keys["aud_a"]],
                        note="Poznámka",
                        display_order=10,
                    )
                ],
            )
        )
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        header = editor.visits_table.horizontalHeader()
        for col in (0, 1, 2):
            self.assertEqual(
                header.sectionResizeMode(col),
                QHeaderView.ResizeMode.ResizeToContents,
            )
        self._close_editor(editor)


if __name__ == "__main__":
    unittest.main()

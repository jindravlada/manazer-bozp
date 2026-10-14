"""KOORD-OSTRY-TEST-1 – průběžné ukládání textů koordinační schůzky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="koord-ostry-test-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        BOZP_COORDINATION_STATUS_CLOSED,
        BOZP_COORDINATION_STATUS_DRAFT,
        PROTOCOL_FINAL_PROVISIONS_CONTINUATION,
        RISK_SUBMISSION_STATUS_LABELS,
        RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
        RISK_SUBMISSION_STATUS_WILL_EMAIL,
        TAB_BASICS,
        TAB_MEASURES,
        TAB_RISK_SUBMISSIONS,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
        CoordinationRiskSubmissionHistory,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
        coordination_coordinator_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
        coordination_lifecycle_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
        render_blocks_to_plain_lines,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
        coordination_risk_submission_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
        coordination_workplace_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.modely.task import Task


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


AGREEMENT = {
    "work_intent_information_text": "Informovat o vstupu techniky.",
    "ppe_text": "Přilba a výstražná vesta.",
    "workplace_handover_text": "Pracoviště předat zápisem.",
    "final_provisions_text": "Dohoda platí podpisem.",
}


class KoordOstryTest1TextPersistTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(CoordinationRiskSubmissionHistory))
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
            abbreviation="HL",
        )

    def _coordination(self, subject: str = "Ostrý test") -> BozpCoordination:
        return bozp_coordination_service.create_coordination(
            subject=subject,
            meeting_date=date(2026, 10, 14),
            place="Jednací místnost",
        )

    def _contractors(self, coordination_id: int):
        first = coordination_employer_service.add_participant(
            coordination_id,
            company_name="Dodavatel A s.r.o.",
            abbreviation="DA",
        )
        second = coordination_employer_service.add_participant(
            coordination_id,
            company_name="Dodavatel B s.r.o.",
            abbreviation="DB",
        )
        return first, second

    def _open(self, coordination: BozpCoordination) -> BozpCoordinationDialog:
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _tab_index(self, dialog: BozpCoordinationDialog, title: str) -> int:
        for index in range(dialog.tabs.count()):
            if dialog.tabs.tabText(index) == title:
                return index
        raise AssertionError(title)

    def _show_tab(self, dialog: BozpCoordinationDialog, title: str) -> None:
        dialog.tabs.setCurrentIndex(self._tab_index(dialog, title))
        self.app.processEvents()

    def _fill_agreement(self, dialog: BozpCoordinationDialog, values: dict) -> None:
        self._show_tab(dialog, TAB_MEASURES)
        tab = dialog.measures_tab
        tab.work_intent_information_text.setPlainText(
            values["work_intent_information_text"]
        )
        tab.ppe_text.setPlainText(values["ppe_text"])
        tab.workplace_handover_text.setPlainText(values["workplace_handover_text"])
        tab.final_provisions_text.setPlainText(values["final_provisions_text"])

    def _assert_agreement(self, coordination_id: int, values: dict) -> None:
        reloaded = bozp_coordination_service.get_by_id(coordination_id)
        assert reloaded is not None
        self.assertEqual(
            reloaded.work_intent_information_text,
            values["work_intent_information_text"],
        )
        self.assertEqual(reloaded.ppe_text, values["ppe_text"])
        self.assertEqual(
            reloaded.workplace_handover_text,
            values["workplace_handover_text"],
        )
        self.assertEqual(
            reloaded.final_provisions_text,
            values["final_provisions_text"],
        )

    def _select_employer(self, dialog: BozpCoordinationDialog, employer_id: int) -> None:
        self._show_tab(dialog, TAB_RISK_SUBMISSIONS)
        tab = dialog.risk_submissions_tab
        index = tab.employer_combo.findData(employer_id)
        self.assertGreaterEqual(index, 0)
        tab.employer_combo.setCurrentIndex(index)
        self.app.processEvents()

    def _fill_risk(
        self,
        dialog: BozpCoordinationDialog,
        employer_id: int,
        *,
        risks_text: str,
        note: str,
    ) -> None:
        self._select_employer(dialog, employer_id)
        tab = dialog.risk_submissions_tab
        tab.submission_method.setCurrentIndex(
            tab.submission_method.findData(RISK_SUBMISSION_STATUS_STATED_AT_MEETING)
        )
        tab.risks_text.setPlainText(risks_text)
        tab.note.setPlainText(note)

    def test_a_save_all_agreement_texts_without_closing(self) -> None:
        coordination = self._coordination()
        dialog = self._open(coordination)
        self._fill_agreement(dialog, AGREEMENT)
        self.assertTrue(dialog.is_dirty())
        self.assertTrue(dialog.measures_tab.agreement_is_dirty())
        self.assertTrue(dialog._save())
        self.assertFalse(dialog.is_dirty())
        reloaded = bozp_coordination_service.get_by_id(coordination.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)
        self._assert_agreement(coordination.id, AGREEMENT)
        dialog.close()

    def test_b_tab_switch_keeps_unsaved_and_saved_agreement(self) -> None:
        coordination = self._coordination()
        dialog = self._open(coordination)
        self._fill_agreement(dialog, AGREEMENT)
        self._show_tab(dialog, TAB_BASICS)
        self._show_tab(dialog, TAB_MEASURES)
        tab = dialog.measures_tab
        self.assertEqual(
            tab.work_intent_information_text.toPlainText(),
            AGREEMENT["work_intent_information_text"],
        )
        self.assertEqual(tab.ppe_text.toPlainText(), AGREEMENT["ppe_text"])
        self.assertEqual(
            tab.workplace_handover_text.toPlainText(),
            AGREEMENT["workplace_handover_text"],
        )
        self.assertEqual(
            tab.final_provisions_text.toPlainText(),
            AGREEMENT["final_provisions_text"],
        )
        self.assertTrue(dialog._save())
        self._show_tab(dialog, TAB_RISK_SUBMISSIONS)
        self._show_tab(dialog, TAB_MEASURES)
        self.assertEqual(
            tab.final_provisions_text.toPlainText(),
            AGREEMENT["final_provisions_text"],
        )
        dialog.close()

    def test_c_reopen_keeps_saved_agreement_and_risks(self) -> None:
        coordination = self._coordination()
        contractor, _other = self._contractors(coordination.id)
        dialog = self._open(coordination)
        self._fill_agreement(dialog, AGREEMENT)
        self._fill_risk(
            dialog,
            contractor.id,
            risks_text="Pád z lešení",
            note="Sděleno na schůzce",
        )
        self.assertTrue(dialog._save())
        dialog.close()

        again = self._open(
            bozp_coordination_service.get_by_id(coordination.id)
        )
        self._show_tab(again, TAB_MEASURES)
        self.assertEqual(
            again.measures_tab.work_intent_information_text.toPlainText(),
            AGREEMENT["work_intent_information_text"],
        )
        self.assertEqual(
            again.measures_tab.workplace_handover_text.toPlainText(),
            AGREEMENT["workplace_handover_text"],
        )
        self._select_employer(again, contractor.id)
        self.assertEqual(
            again.risk_submissions_tab.risks_text.toPlainText(),
            "Pád z lešení",
        )
        self.assertEqual(
            again.risk_submissions_tab.note.toPlainText(),
            "Sděleno na schůzce",
        )
        self.assertEqual(
            again.risk_submissions_tab.submission_method.currentData(),
            RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
        )
        again.close()

    def test_d_draft_save_persists_risk_for_selected_employer(self) -> None:
        coordination = self._coordination()
        contractor, _other = self._contractors(coordination.id)
        dialog = self._open(coordination)
        self._fill_risk(
            dialog,
            contractor.id,
            risks_text="Hluk a prach",
            note="Bez přílohy",
        )
        self.assertTrue(dialog.is_dirty())
        self.assertTrue(dialog._save())
        saved = coordination_risk_submission_service.get_for_employer(contractor.id)
        assert saved is not None
        self.assertEqual(saved.coordination_employer_id, contractor.id)
        self.assertEqual(saved.submission_method, RISK_SUBMISSION_STATUS_STATED_AT_MEETING)
        self.assertEqual(saved.risks_text, "Hluk a prach")
        self.assertEqual(saved.note, "Bez přílohy")
        reloaded = bozp_coordination_service.get_by_id(coordination.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)
        dialog.close()

    def test_e_two_employers_do_not_overwrite(self) -> None:
        coordination = self._coordination()
        first, second = self._contractors(coordination.id)
        dialog = self._open(coordination)
        self._fill_risk(
            dialog,
            first.id,
            risks_text="Riziko dodavatele A",
            note="Poznámka A",
        )
        self._fill_risk(
            dialog,
            second.id,
            risks_text="Riziko dodavatele B",
            note="Poznámka B",
        )
        self.assertTrue(dialog._save())
        saved_a = coordination_risk_submission_service.get_for_employer(first.id)
        saved_b = coordination_risk_submission_service.get_for_employer(second.id)
        assert saved_a is not None and saved_b is not None
        self.assertEqual(saved_a.risks_text, "Riziko dodavatele A")
        self.assertEqual(saved_a.note, "Poznámka A")
        self.assertEqual(saved_b.risks_text, "Riziko dodavatele B")
        self.assertEqual(saved_b.note, "Poznámka B")
        self.assertNotEqual(saved_a.coordination_employer_id, saved_b.coordination_employer_id)

        self._select_employer(dialog, first.id)
        self.assertEqual(
            dialog.risk_submissions_tab.risks_text.toPlainText(),
            "Riziko dodavatele A",
        )
        self._select_employer(dialog, second.id)
        self.assertEqual(
            dialog.risk_submissions_tab.risks_text.toPlainText(),
            "Riziko dodavatele B",
        )
        dialog.close()

    def test_f_close_keeps_texts_in_protocol_and_fixes_typo(self) -> None:
        self.assertIn("zákoníku práce", PROTOCOL_FINAL_PROVISIONS_CONTINUATION)
        self.assertNotIn("zakoníku práce", PROTOCOL_FINAL_PROVISIONS_CONTINUATION)

        coordination = self._coordination("Uzavření s texty")
        contractor, _other = self._contractors(coordination.id)
        operation = settings_service.save_workplace(
            name="Provoz ostrý test",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Hala ostrý test",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Jana Koordinátorová",
            employer_name="Hlavní firma s.r.o.",
        )

        dialog = self._open(coordination)
        self._fill_agreement(dialog, AGREEMENT)
        self._fill_risk(
            dialog,
            contractor.id,
            risks_text="Zakopnutí o materiál",
            note="Doplnit zábranu",
        )
        self.assertTrue(dialog._save())
        draft = bozp_coordination_service.get_by_id(coordination.id)
        assert draft is not None
        self.assertEqual(draft.status, BOZP_COORDINATION_STATUS_DRAFT)

        coordination_lifecycle_service.transition(
            coordination.id,
            BOZP_COORDINATION_STATUS_CLOSED,
            confirm_warnings=True,
        )

        closed = bozp_coordination_service.get_by_id(coordination.id)
        assert closed is not None
        self.assertEqual(closed.status, BOZP_COORDINATION_STATUS_CLOSED)
        self._assert_agreement(coordination.id, AGREEMENT)
        saved = coordination_risk_submission_service.get_for_employer(contractor.id)
        assert saved is not None
        self.assertEqual(saved.risks_text, "Zakopnutí o materiál")

        result = coordination_protocol_builder.build(coordination.id)
        lines = render_blocks_to_plain_lines(result.protocol_data["document"]["blocks"])
        joined = "\n".join(lines)
        self.assertIn(AGREEMENT["work_intent_information_text"], joined)
        self.assertIn(AGREEMENT["ppe_text"], joined)
        self.assertIn(AGREEMENT["workplace_handover_text"], joined)
        self.assertIn("Předání pracoviště:", joined)
        self.assertIn(AGREEMENT["final_provisions_text"], joined)
        self.assertIn("zákoníku práce", joined)
        self.assertNotIn("zakoníku práce", joined)
        self.assertIn("DA", joined)
        self.assertIn(
            RISK_SUBMISSION_STATUS_LABELS[RISK_SUBMISSION_STATUS_STATED_AT_MEETING],
            joined,
        )
        self.assertIn("Zakopnutí o materiál", joined)
        self.assertIn("Poznámka: Doplnit zábranu", joined)

        target = _TMP / "protokol.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        content = _odt_content(target)
        self.assertIn("zákoníku práce", content)
        self.assertNotIn("zakoníku práce", content)
        self.assertIn("Zakopnutí o materiál", content)
        self.assertIn(AGREEMENT["workplace_handover_text"], content)

        dialog.close()
        readonly = self._open(closed)
        readonly.measures_tab.work_intent_information_text.setPlainText(
            "Toto se nesmí uložit"
        )
        self.assertFalse(readonly._save())
        self._assert_agreement(coordination.id, AGREEMENT)
        readonly.mark_clean()
        readonly.close()

    def test_g_failed_save_keeps_typed_text(self) -> None:
        coordination = self._coordination()
        contractor, _other = self._contractors(coordination.id)
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
            risks_text="Původní text rizik",
            note="Původní poznámka",
        )
        dialog = self._open(coordination)
        self._fill_agreement(dialog, AGREEMENT)
        self._select_employer(dialog, contractor.id)
        tab = dialog.risk_submissions_tab
        tab.risks_text.setPlainText("Nový text, který nesmí zmizet")
        tab.note.setPlainText("Nová poznámka")
        tab.submission_method.setCurrentIndex(
            tab.submission_method.findData(RISK_SUBMISSION_STATUS_WILL_EMAIL)
        )
        with patch(
            "moduly.koordinace_bozp.ui.coordination_risk_submissions_tab.QMessageBox.warning"
        ) as warning:
            self.assertFalse(dialog._save())
        self.assertTrue(warning.called)
        self.assertEqual(
            tab.risks_text.toPlainText(),
            "Nový text, který nesmí zmizet",
        )
        self.assertEqual(tab.note.toPlainText(), "Nová poznámka")
        self.assertTrue(dialog.is_dirty())
        kept = coordination_risk_submission_service.get_for_employer(contractor.id)
        assert kept is not None
        self.assertEqual(kept.risks_text, "Původní text rizik")
        self.assertEqual(kept.note, "Původní poznámka")
        self.assertEqual(kept.submission_method, RISK_SUBMISSION_STATUS_STATED_AT_MEETING)

        self._show_tab(dialog, TAB_BASICS)
        self._show_tab(dialog, TAB_RISK_SUBMISSIONS)
        self.assertEqual(
            dialog.risk_submissions_tab.risks_text.toPlainText(),
            "Nový text, který nesmí zmizet",
        )
        self.assertEqual(
            dialog.measures_tab.work_intent_information_text.toPlainText(),
            AGREEMENT["work_intent_information_text"],
        )
        dialog.mark_clean()
        dialog.close()

    def test_h_older_meeting_data_survives_unrelated_save(self) -> None:
        older = bozp_coordination_service.update_coordination(
            self._coordination("Starší schůzka").id,
            meeting_date=date(2026, 5, 1),
            place="Archiv",
            subject="Starší schůzka",
            note="Původní poznámka schůzky",
            work_intent_information_text="Starý záměr",
            ppe_text="Staré OOPP",
            workplace_handover_text="Staré předání",
            final_provisions_text="Starý závěr",
        )
        assert older is not None
        contractor, _other = self._contractors(older.id)
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
            risks_text="Starý text rizik",
            note="Stará poznámka rizik",
        )
        other = bozp_coordination_service.update_coordination(
            self._coordination("Jiná schůzka").id,
            meeting_date=date(2026, 6, 1),
            place="Jinde",
            subject="Jiná schůzka",
            work_intent_information_text="Cizí záměr",
            ppe_text="Cizí OOPP",
            workplace_handover_text="Cizí předání",
            final_provisions_text="Cizí závěr",
        )
        assert other is not None

        dialog = self._open(older)
        dialog.subject.setText("Starší schůzka – doplněno")
        self.assertTrue(dialog._save())
        dialog.close()

        self._assert_agreement(
            older.id,
            {
                "work_intent_information_text": "Starý záměr",
                "ppe_text": "Staré OOPP",
                "workplace_handover_text": "Staré předání",
                "final_provisions_text": "Starý závěr",
            },
        )
        kept = coordination_risk_submission_service.get_for_employer(contractor.id)
        assert kept is not None
        self.assertEqual(kept.risks_text, "Starý text rizik")
        self.assertEqual(kept.note, "Stará poznámka rizik")
        self._assert_agreement(
            other.id,
            {
                "work_intent_information_text": "Cizí záměr",
                "ppe_text": "Cizí OOPP",
                "workplace_handover_text": "Cizí předání",
                "final_provisions_text": "Cizí závěr",
            },
        )
        untouched = bozp_coordination_service.get_by_id(other.id)
        assert untouched is not None
        self.assertEqual(untouched.subject, "Jiná schůzka")


if __name__ == "__main__":
    unittest.main()

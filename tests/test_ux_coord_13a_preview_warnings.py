"""UX-COORD-13a – zobrazení upozornění v náhledu protokolu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-13a-"))
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
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        ProtocolBuildResult,
        ProtocolSummary,
        ProtocolWarning,
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
        build_protocol_document,
        render_blocks_to_plain_lines,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog import (
        CoordinationProtocolPreviewDialog,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _minimal_protocol_data(*, warnings: list[dict] | None = None) -> dict:
    data = {
        "basics": {
            "coordination_number": "K-13a",
            "subject": "UX-COORD-13a",
            "meeting_date": "2026-07-20",
            "place": "Praha",
            "status": "draft",
        },
        "employers": [],
        "participants_by_employer": [],
        "coordinator": None,
        "workplaces": [],
        "activities_by_employer": [],
        "measures_by_category": [],
        "contacts": [],
        "emergency_procedures": {},
        "risk_handovers": [],
        "pbp_snapshot": None,
        "attachments_by_group": [],
        "warnings": list(warnings or []),
    }
    data["document"] = build_protocol_document(data)
    return data


class UxCoord13aPreviewWarningsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
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

    def _open_preview(self, result: ProtocolBuildResult) -> CoordinationProtocolPreviewDialog:
        with patch(
            "moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog."
            "coordination_protocol_builder.build",
            return_value=result,
        ):
            dialog = CoordinationProtocolPreviewDialog(None, coordination_id=1)
        return dialog

    def test_warnings_panel_hidden_when_empty(self) -> None:
        result = ProtocolBuildResult(
            protocol_data=_minimal_protocol_data(warnings=[]),
            warnings=[],
            summary=ProtocolSummary(),
        )
        dialog = self._open_preview(result)
        self.assertTrue(dialog.warnings_panel.isHidden())
        self.assertIn("bez upozornění", dialog.status_label.text())
        dialog.close()

    def test_warnings_panel_visible_with_messages(self) -> None:
        warning_dicts = [
            {
                "code": "missing_coordinator",
                "severity": "critical",
                "message": "Nebyl určen koordinátor BOZP.",
            },
            {
                "code": "missing_risks",
                "severity": "warning",
                "message": "Zaměstnavatel TD dosud nepředal rizika.",
            },
            {
                "code": "missing_contact",
                "severity": "warning",
                "message": "Chybí důležitý kontakt.",
            },
        ]
        warnings = [
            ProtocolWarning(
                code=item["code"],
                severity=item["severity"],
                message=item["message"],
            )
            for item in warning_dicts
        ]
        summary = ProtocolSummary(warnings_critical=1, warnings_warning=2)
        result = ProtocolBuildResult(
            protocol_data=_minimal_protocol_data(warnings=warning_dicts),
            warnings=warnings,
            summary=summary,
        )
        dialog = self._open_preview(result)
        self.assertFalse(dialog.warnings_panel.isHidden())
        self.assertEqual(dialog.warnings_title.text(), "Upozornění (3)")
        self.assertIn("3 upozornění", dialog.status_label.text())

        labels = [
            label.text()
            for label in dialog.warnings_body.findChildren(QLabel)
            if (label.text() or "").startswith("• ")
        ]
        self.assertEqual(len(labels), 3)
        self.assertIn("• Nebyl určen koordinátor BOZP.", labels)
        self.assertIn("• Zaměstnavatel TD dosud nepředal rizika.", labels)
        self.assertIn("• Chybí důležitý kontakt.", labels)
        dialog.close()

    def test_warnings_not_in_document_or_odt(self) -> None:
        message = "Nebyl určen koordinátor BOZP."
        warning_dicts = [
            {
                "code": "missing_coordinator",
                "severity": "critical",
                "message": message,
            }
        ]
        data = _minimal_protocol_data(warnings=warning_dicts)
        lines = render_blocks_to_plain_lines(data["document"]["blocks"])
        self.assertNotIn(message, lines)

        target = _TMP / "no-warnings-in-odt.odt"
        coordination_protocol_odt_renderer.render(
            target,
            protocol_data=data,
            warnings=warning_dicts,
            summary={"warnings_total": 1},
        )
        content = _odt_content(target)
        self.assertNotIn(message, content)
        self.assertNotIn("Upozornění", content)

    def test_builder_puts_warnings_into_protocol_data(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-13a builder",
            meeting_date=date.today(),
        )
        result = coordination_protocol_builder.build(coordination.id)
        self.assertIn("warnings", result.protocol_data)
        self.assertIsInstance(result.protocol_data["warnings"], list)
        self.assertEqual(
            len(result.protocol_data["warnings"]),
            len(result.warnings),
        )
        if result.warnings:
            self.assertEqual(
                result.protocol_data["warnings"][0]["message"],
                result.warnings[0].message,
            )


if __name__ == "__main__":
    unittest.main()

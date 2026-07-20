"""Fáze COORD-011b – export koordinačního protokolu do ODT."""

from __future__ import annotations

import importlib
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from moduly.koordinace_bozp.constants import (
    ATTACHMENT_TYPE_CONTRACTOR_RISKS,
    ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
    ATTACHMENT_TYPE_OTHER,
    PROTOCOL_TITLE,
    PROTOCOL_WARNING_MISSING_COORDINATOR,
    PROTOCOL_WARNING_SEVERITY_CRITICAL,
    PROTOCOL_WARNING_SEVERITY_WARNING,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
    ProtocolBuildResult,
    ProtocolSummary,
    ProtocolWarning,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
    build_protocol_document,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
    PROTOCOL_ODT_CHAPTER_TITLES,
    coordination_protocol_odt_renderer,
)


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _with_document(data: dict) -> dict:
    payload = dict(data)
    payload["document"] = build_protocol_document(payload)
    return payload


def _chapter_positions(content: str) -> list[tuple[str, int]]:
    found = []
    for title in PROTOCOL_ODT_CHAPTER_TITLES:
        needle = f">{title}</text:p>"
        pos = content.find(needle)
        if pos >= 0:
            found.append((title, pos))
    found.sort(key=lambda item: item[1])
    return found


class KoordinaceBozpPhaseCoord011bTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = TemporaryDirectory(prefix="coord-011b-")
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _complete_protocol_data(self) -> dict:
        data = {
            "basics": {
                "id": 1,
                "coordination_number": "K-2026-001",
                "meeting_date": "2026-07-10",
                "place": "Praha",
                "subject": "Koordinace stavby",
                "status": "draft",
                "status_label": "Rozpracováno",
                "note": "Poznámka protokolu",
                "valid_from": "2026-07-01",
                "valid_to": "2027-07-01",
                "active": True,
                "validity_state": "valid",
            },
            "employers": [
                {
                    "id": 10,
                    "abbreviation": "HL",
                    "company_name": "Hlavní firma s.r.o.",
                    "display_name": "HL – Hlavní firma s.r.o.",
                    "ico": "12345678",
                    "is_main": True,
                    "sort_order": 0,
                    "active": True,
                },
                {
                    "id": 11,
                    "abbreviation": "DOD",
                    "company_name": "Dodavatel s.r.o.",
                    "display_name": "DOD – Dodavatel s.r.o.",
                    "ico": "87654321",
                    "is_main": False,
                    "sort_order": 1,
                    "active": True,
                },
            ],
            "participants_by_employer": [
                {
                    "employer": {
                        "id": 10,
                        "display_name": "HL – Hlavní firma s.r.o.",
                        "is_main": True,
                    },
                    "participants": [
                        {
                            "id": 100,
                            "full_name": "Jan Koordinátor",
                            "role": "koordinátor BOZP",
                            "phone": "+420111",
                            "email": "jan@example.com",
                            "sort_order": 0,
                        }
                    ],
                },
                {
                    "employer": {
                        "id": 11,
                        "display_name": "DOD – Dodavatel s.r.o.",
                        "is_main": False,
                    },
                    "participants": [
                        {
                            "id": 101,
                            "full_name": "Petr Dodavatel",
                            "role": "vedoucí",
                            "phone": "+420222",
                            "email": "petr@example.com",
                            "sort_order": 0,
                        }
                    ],
                },
            ],
            "coordinator": {
                "id": 1,
                "participant_id": 100,
                "employer_id": 10,
                "full_name": "Jan Koordinátor",
                "role": "koordinátor BOZP",
                "phone": "+420111",
                "email": "jan@example.com",
                "employer_name": "Hlavní firma s.r.o.",
                "note": "",
            },
            "workplaces": [
                {
                    "id": 50,
                    "operation_name": "Provoz A",
                    "workplace_name": "Hala 1",
                    "workplace_part_name": "",
                    "label": "Provoz A / Hala 1",
                    "note": "",
                    "sort_order": 0,
                }
            ],
            "activities_by_employer": [
                {
                    "employer": {
                        "id": 10,
                        "display_name": "HL – Hlavní firma s.r.o.",
                        "is_main": True,
                    },
                    "activities": [
                        {
                            "id": 1,
                            "activity_name": "Údržba",
                            "description": "",
                            "workplace_label": "Provoz A / Hala 1",
                            "sort_order": 0,
                        }
                    ],
                },
                {
                    "employer": {
                        "id": 11,
                        "display_name": "DOD – Dodavatel s.r.o.",
                        "is_main": False,
                    },
                    "activities": [
                        {
                            "id": 2,
                            "activity_name": "Svařování",
                            "description": "",
                            "workplace_label": "Provoz A / Hala 1",
                            "sort_order": 0,
                        }
                    ],
                },
            ],
            "measures_by_category": [
                {
                    "category": "communication",
                    "category_label": "Komunikace",
                    "measures": [
                        {
                            "id": 1,
                            "title": "Hlásit události",
                            "description": "",
                            "category": "communication",
                            "sort_order": 0,
                        }
                    ],
                }
            ],
            "coordination_agreement": {
                "work_intent_information_text": "Informovat o vstupu na pracoviště.",
                "ppe_text": "Používat přilbu a výstražnou vestu.",
                "workplace_handover_text": "Předání pracoviště potvrdit zápisem.",
                "final_provisions_text": "Tato dohoda nabývá účinnosti podpisem.",
            },
            "contacts": [
                {
                    "id": 1,
                    "contact_type": "emergency",
                    "contact_type_label": "Mimořádná událost",
                    "custom_name": "Ohlašovna",
                    "role": "",
                    "phone": "+420999",
                    "email": "",
                    "sort_order": 0,
                }
            ],
            "emergency_procedures": {
                "emergency_reporting": "Oznámit koordinátorovi.",
                "accident_reporting": "Oznámit vedoucímu.",
                "fire_reporting": "Volat hasiče.",
                "evacuation_instructions": "Na shromaždiště.",
            },
            "risk_handovers": [
                {
                    "employer": {
                        "id": 11,
                        "display_name": "DOD – Dodavatel s.r.o.",
                        "is_main": False,
                    },
                    "handover_status": "with_attachment",
                    "handover_status_label": "Předáno s přílohou",
                    "submission": {
                        "id": 1,
                        "submission_method": "email",
                        "submission_date": "2026-07-09",
                        "document_reference": "e-mail 12",
                        "note": "",
                    },
                }
            ],
            "pbp_snapshot": {
                "id": 7,
                "revision_number": 1,
                "title": "Pravidla bezpečné práce",
                "content_hash": "abc",
                "rules_count": 1,
                "created_at": "2026-07-10 12:00",
                "created_by": "tester",
                "stored_filename": "pbp-rev1.odt",
                "content_lines": [
                    "Dodržujte následující pravidla bezpečné práce.",
                    "",
                    "1. Práce ve výškách provádějte s ochranou proti pádu.",
                ],
            },
            "attachments_by_group": [
                {
                    "attachment_type": ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
                    "attachment_type_label": "Příloha PBP hlavního zaměstnavatele",
                    "attachments": [
                        {
                            "id": 7,
                            "source": "pbp_revision",
                            "original_filename": "pbp-rev1.odt",
                            "description": "Pravidla bezpečné práce",
                        }
                    ],
                },
                {
                    "attachment_type": ATTACHMENT_TYPE_CONTRACTOR_RISKS,
                    "attachment_type_label": "Rizika dodavatele",
                    "attachments": [
                        {
                            "id": 20,
                            "source": "attachment",
                            "original_filename": "rizika-dodavatele.pdf",
                            "description": "",
                        }
                    ],
                },
                {
                    "attachment_type": ATTACHMENT_TYPE_OTHER,
                    "attachment_type_label": "Jiná příloha",
                    "attachments": [
                        {
                            "id": 21,
                            "source": "attachment",
                            "original_filename": "mapa.pdf",
                            "description": "Mapa",
                        }
                    ],
                },
            ],
        }
        return _with_document(data)

    def _complete_summary(self) -> ProtocolSummary:
        return ProtocolSummary(
            active_employers=2,
            active_participants=2,
            active_workplaces=1,
            active_activities=2,
            active_measures=1,
            active_contacts=1,
            pbp_rules_count=3,
            active_attachments=3,
            warnings_info=0,
            warnings_warning=0,
            warnings_critical=0,
        )

    def test_export_complete_coordination(self) -> None:
        target = self.tmp / "kompletni.odt"
        path = coordination_protocol_odt_renderer.render(
            target,
            protocol_data=self._complete_protocol_data(),
            warnings=[],
            summary=self._complete_summary(),
        )
        self.assertTrue(path.exists())
        content = _odt_content(path)
        self.assertIn(PROTOCOL_TITLE, content)
        self.assertIn("K-2026-001", content)
        self.assertIn("Koordinace stavby", content)
        self.assertIn("Jan Koordinátor", content)
        self.assertIn("Provoz A / Hala 1", content)
        self.assertIn("Svařování", content)
        self.assertIn("Ohlašovna", content)
        self.assertIn("Oznámit koordinátorovi.", content)
        self.assertIn("Předáno s přílohou", content)
        self.assertIn("Práce ve výškách provádějte s ochranou proti pádu.", content)
        self.assertIn("mapa.pdf", content)
        self.assertNotIn("Upozornění", content)
        self.assertNotIn("pbp-rev1.odt", content)
        self.assertNotIn("Stav:", content)
        self.assertNotIn("Souhrn", content)

    def test_export_with_warnings(self) -> None:
        data = self._complete_protocol_data()
        data["coordinator"] = None
        warnings = [
            ProtocolWarning(
                code=PROTOCOL_WARNING_MISSING_COORDINATOR,
                severity=PROTOCOL_WARNING_SEVERITY_CRITICAL,
                message="Není určen koordinátor BOZP.",
                related_entity_type="bozp_coordination",
                related_entity_id=1,
            ),
            ProtocolWarning(
                code="missing_measures",
                severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                message="Nejsou evidována žádná aktivní organizační opatření.",
            ),
        ]
        summary = self._complete_summary()
        summary.warnings_critical = 1
        summary.warnings_warning = 1
        target = self.tmp / "s-varovanim.odt"
        coordination_protocol_odt_renderer.render(
            target,
            protocol_data=data,
            warnings=warnings,
            summary=summary,
        )
        content = _odt_content(target)
        self.assertNotIn("Upozornění", content)
        self.assertNotIn("Není určen koordinátor BOZP.", content)
        self.assertNotIn("Počet upozornění", content)
        self.assertIn(PROTOCOL_TITLE, content)

    def test_chapter_order(self) -> None:
        target = self.tmp / "poradi.odt"
        coordination_protocol_odt_renderer.render(
            target,
            protocol_data=self._complete_protocol_data(),
            warnings=[
                ProtocolWarning(
                    code=PROTOCOL_WARNING_MISSING_COORDINATOR,
                    severity=PROTOCOL_WARNING_SEVERITY_CRITICAL,
                    message="Chybí koordinátor.",
                )
            ],
            summary=self._complete_summary(),
        )
        content = _odt_content(target)
        positions = _chapter_positions(content)
        titles = [title for title, _ in positions]
        self.assertEqual(titles, list(PROTOCOL_ODT_CHAPTER_TITLES))
        for index in range(1, len(positions)):
            self.assertLess(positions[index - 1][1], positions[index][1])

    def test_summary_content(self) -> None:
        summary = ProtocolSummary(
            active_employers=4,
            active_participants=5,
            active_workplaces=3,
            active_activities=6,
            active_measures=7,
            active_contacts=2,
            pbp_rules_count=9,
            active_attachments=8,
            warnings_info=1,
            warnings_warning=2,
            warnings_critical=3,
        )
        target = self.tmp / "souhrn.odt"
        coordination_protocol_odt_renderer.render(
            target,
            protocol_data=_with_document(
                {"basics": {"coordination_number": "X", "subject": "Y"}}
            ),
            warnings=[],
            summary=summary,
        )
        content = _odt_content(target)
        self.assertNotIn("Počet zaměstnavatelů", content)
        self.assertNotIn("Souhrn", content)
        self.assertIn("X", content)

    def test_export_without_database_access(self) -> None:
        def _forbid_db(*_args, **_kwargs):
            raise AssertionError("Export ODT nesmí přistupovat k databázi.")

        target = self.tmp / "bez-db.odt"
        with (
            patch(
                "core.database.session.get_session",
                side_effect=_forbid_db,
            ),
            patch(
                "moduly.koordinace_bozp.sluzby.bozp_coordination_service."
                "bozp_coordination_service.get_by_id",
                side_effect=_forbid_db,
            ),
            patch(
                "moduly.koordinace_bozp.sluzby.coordination_protocol_builder."
                "coordination_protocol_builder.build",
                side_effect=_forbid_db,
            ),
        ):
            path = coordination_protocol_odt_renderer.render(
                target,
                protocol_data=self._complete_protocol_data(),
                warnings=[],
                summary=self._complete_summary(),
            )
        self.assertTrue(path.exists())
        self.assertIn(PROTOCOL_TITLE, _odt_content(path))

    def test_renderer_uses_only_protocol_data(self) -> None:
        """Renderer bere hodnoty z protocol_data, ne z DB / builderu."""
        data = {
            "basics": {
                "coordination_number": "ONLY-FROM-DATA",
                "subject": "Předmět jen z dat",
                "meeting_date": "2026-01-15",
                "place": "Brno",
            },
            "employers": [
                {
                    "display_name": "Firma Ze Dat",
                    "is_main": True,
                    "ico": "",
                }
            ],
            "participants_by_employer": [],
            "coordinator": {
                "full_name": "Osoba Ze Dat",
                "role": "role",
                "employer_name": "Firma Ze Dat",
            },
            "workplaces": [{"label": "Místo Ze Dat"}],
            "activities_by_employer": [],
            "measures_by_category": [],
            "contacts": [],
            "emergency_procedures": {
                "emergency_reporting": "Postup ze dat",
            },
            "risk_handovers": [],
            "pbp_snapshot": None,
            "attachments_by_group": [],
        }
        with patch(
            "moduly.koordinace_bozp.sluzby.coordination_protocol_builder."
            "coordination_protocol_builder.build",
            side_effect=AssertionError("Renderer nesmí volat builder."),
        ):
            coordination_protocol_odt_renderer.render(
                self.tmp / "jen-data.odt",
                protocol_data=_with_document(data),
                warnings=[],
                summary={"active_employers": 1, "warnings_total": 0},
            )
        content = _odt_content(self.tmp / "jen-data.odt")
        self.assertIn("ONLY-FROM-DATA", content)
        self.assertIn("Předmět jen z dat", content)
        self.assertIn("Firma Ze Dat", content)
        self.assertIn("Osoba Ze Dat", content)
        self.assertIn("Místo Ze Dat", content)
        self.assertIn("Postup ze dat", content)

    def test_render_from_result_reuses_prepared_payload(self) -> None:
        result = ProtocolBuildResult(
            protocol_data=self._complete_protocol_data(),
            warnings=[],
            summary=self._complete_summary(),
        )
        with patch.object(
            coordination_protocol_odt_renderer,
            "render",
            wraps=coordination_protocol_odt_renderer.render,
        ) as mocked:
            path = coordination_protocol_odt_renderer.render_from_result(
                self.tmp / "from-result.odt",
                result,
            )
        mocked.assert_called_once()
        kwargs = mocked.call_args.kwargs
        self.assertIs(kwargs["protocol_data"], result.protocol_data)
        self.assertTrue(path.exists())

    def test_preview_dialog_keeps_cached_result_for_export(self) -> None:
        """UI drží sestavený výsledek; export ho použije bez nového sestavení."""
        result = ProtocolBuildResult(
            protocol_data=self._complete_protocol_data(),
            warnings=[],
            summary=self._complete_summary(),
        )
        # Simulace dialogu: export volá renderer s uloženým výsledkem.
        with patch(
            "moduly.koordinace_bozp.sluzby.coordination_protocol_builder."
            "coordination_protocol_builder.build",
            side_effect=AssertionError("Export nesmí znovu sestavovat protokol."),
        ):
            path = coordination_protocol_odt_renderer.render_from_result(
                self.tmp / "ui-export.odt",
                result,
            )
        self.assertTrue(path.exists())
        self.assertIn("K-2026-001", _odt_content(path))

        # Kontrola textu tlačítka bez spouštění celého Qt dialogu (stabilita offscreen).
        source = Path(
            importlib.import_module(
                "moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog"
            ).__file__
        ).read_text(encoding="utf-8")
        self.assertIn('QPushButton("Export ODT")', source)
        self.assertIn("render_from_result", source)
        self.assertIn("self._build_result", source)


if __name__ == "__main__":
    unittest.main()

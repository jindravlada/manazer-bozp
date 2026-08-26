"""PROVERKY-SECTION-SUMMARY-UX1: rozložení okruhu a terénní checklist."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="proverky-section-summary-ux1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.section_summary import (
        NOTES_MODE_SECTION_SUMMARY_V1,
        SECTION_SUMMARY_LABEL,
    )
    from core.widgets.control_result_selector import ControlResultSelectorWidget
    from core.widgets.section_summary_edit import (
        SUMMARY_EDIT_COMPACT_HEIGHT,
        SUMMARY_EDIT_DEFAULT_HEIGHT,
        SectionSummaryEdit,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import (
        TERRAIN_CHECKLIST_NO_TERRAIN_POINTS_TOOLTIP,
        TERRAIN_CHECKLIST_SAVE_FIRST_TOOLTIP,
        TERRAIN_CHECKLIST_TOOLTIP,
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.inspection_deferred_edits import InspectionDeferredEdits
    from moduly.proverky.sluzby.inspection_section_summary_service import (
        inspection_section_summary_service,
    )
    from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
    from moduly.proverky.sluzby.terrain_checklist_service import terrain_checklist_service
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
    from moduly.proverky.ui.bozp_inspection_terrain_widget import BozpInspectionTerrainWidget
    from moduly.proverky.ui.bozp_knowledge_section_widget import (
        _COLUMN_LEFT_STRETCH,
        _COLUMN_RIGHT_STRETCH,
        BozpKnowledgeSectionWidget,
    )

_REMOVED_HINTS = (
    "Vyberte sekci v seznamu vlevo.",
    "Vyberte kontrolní bod v seznamu vlevo.",
    "Vyberte auditní tvrzení v seznamu vlevo.",
)


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_module.storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _section(
    *,
    point_count: int = 1,
    verification_type: str = VERIFICATION_TYPE_DOCUMENTATION,
    photos: list[dict] | None = None,
    defects: list[dict] | None = None,
) -> dict:
    points = []
    for index in range(point_count):
        points.append(
            {
                "id": f"k{index + 1}",
                "nazev": f"Bod {index + 1} " + ("dlouhý text karty. " * 10),
                "popis": "Popis kontrolního bodu " * 8,
                "aktivni": True,
                "poradi": (index + 1) * 10,
                "verification_type": verification_type,
                "zavaznost": "stredni",
            }
        )
    return {
        "id": "s1",
        "nazev": "Okruh",
        "popis": "Popis kontrolované oblasti pro UX1.",
        "aktivni": True,
        "kontrolni_body": points,
        "typicke_zavady": defects
        if defects is not None
        else [{"id": "z1", "nazev": "Typická závada A", "aktivni": True}],
        "doporucene_postupy": [],
        "legislativa": [],
        "historie": [],
        "referencni_fotografie": photos or [],
        "postup_kontroly": [],
    }


class ProverkySectionSummaryUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)
        proverky_knowledge_service.ensure_catalogs()

    def _commission_ids(self):
        suffix = uuid.uuid4().hex[:6]
        leader = settings_service.save_worker(
            first_name="Jan", last_name=f"L-{suffix}"
        ).id
        workplace = settings_service.save_worker(
            first_name="Eva", last_name=f"W-{suffix}"
        ).id
        union = person_service.create_person(
            first_name="Lucie", last_name=f"U-{suffix}"
        ).id
        return leader, workplace, union

    def _fill_commission(self, dialog: BozpInspectionDialog, ids) -> None:
        leader, workplace, union = ids
        dialog.commission_widget.leader_selector.set_person_id(leader)
        dialog.commission_widget.workplace_selector.set_person_id(workplace)
        dialog.commission_widget.union_selector.set_person_id(union)

    def _show(
        self,
        *,
        point_count: int = 8,
        notes_mode: str | None = NOTES_MODE_SECTION_SUMMARY_V1,
        verification_type: str = VERIFICATION_TYPE_DOCUMENTATION,
        photos: list[dict] | None = None,
        deferred: InspectionDeferredEdits | None = None,
    ) -> BozpKnowledgeSectionWidget:
        widget = BozpKnowledgeSectionWidget()
        widget.set_verification_filter(verification_type)
        widget.set_deferred_edits(deferred or InspectionDeferredEdits())
        widget.set_notes_mode(notes_mode)
        widget.set_section(
            _section(
                point_count=point_count,
                verification_type=verification_type,
                photos=photos,
            ),
            area_id="a1",
            area_label="Oblast",
            section_label="Okruh",
        )
        widget.resize(1100, 720)
        widget.show()
        self._app.processEvents()
        return widget

    def _label_texts(self, widget) -> list[str]:
        return [label.text() for label in widget.findChildren(QLabel)]

    def test_helper_text_removed_heading_kept(self) -> None:
        docs = self._show()
        terrain = self._show(verification_type=VERIFICATION_TYPE_TERRAIN)
        for widget in (docs, terrain):
            texts = self._label_texts(widget)
            for hint in _REMOVED_HINTS:
                self.assertNotIn(hint, texts)
            self.assertIn("Kontrolní body", texts)
            self.assertEqual(widget._control_points_heading.text(), "Kontrolní body")

        docs.set_section(None)
        self._app.processEvents()
        for hint in _REMOVED_HINTS:
            self.assertNotIn(hint, self._label_texts(docs))

    def test_two_column_stretch_and_right_stack(self) -> None:
        widget = self._show()
        layout = widget._columns_layout
        self.assertIsNotNone(layout)
        self.assertEqual(layout.stretch(0), _COLUMN_LEFT_STRETCH)
        self.assertEqual(layout.stretch(1), _COLUMN_RIGHT_STRETCH)
        self.assertEqual(_COLUMN_LEFT_STRETCH, 7)
        self.assertEqual(_COLUMN_RIGHT_STRETCH, 3)

        left = widget.findChild(QWidget, "InspectionSectionLeftColumn")
        photos = widget.findChild(QWidget, "InspectionReferencePhotos")
        defects = widget.findChild(QWidget, "InspectionTypicalDefects")
        self.assertIsNotNone(left)
        self.assertIsNotNone(photos)
        self.assertIsNotNone(defects)

        left_pos = left.mapTo(widget, QPoint(0, 0))
        photos_pos = photos.mapTo(widget, QPoint(0, 0))
        defects_pos = defects.mapTo(widget, QPoint(0, 0))
        self.assertGreater(photos_pos.x(), left_pos.x() + 40)
        self.assertGreater(defects_pos.y(), photos_pos.y() + 8)
        texts = self._label_texts(widget)
        self.assertIn("Typické závady", texts)
        self.assertTrue(any("Typická závada A" in text for text in texts))

    def test_summary_compact_height_and_own_scrollbar(self) -> None:
        widget = self._show()
        summary = widget.findChild(SectionSummaryEdit)
        self.assertIsNotNone(summary)
        self.assertEqual(summary._label.text(), SECTION_SUMMARY_LABEL)
        self.assertEqual(summary._edit.height(), SUMMARY_EDIT_COMPACT_HEIGHT)
        self.assertLess(summary._edit.height(), SUMMARY_EDIT_DEFAULT_HEIGHT)
        self.assertEqual(
            summary._edit.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        heading = widget._control_points_heading
        self.assertFalse(summary.geometry().intersects(heading.geometry()))

        summary.set_text("Odstavec.\n" * 40)
        self._app.processEvents()
        bar = summary._edit.verticalScrollBar()
        self.assertGreater(bar.maximum(), bar.minimum())

    def test_control_points_scroll_does_not_move_header(self) -> None:
        widget = self._show(point_count=12)
        summary = widget.findChild(SectionSummaryEdit)
        photos = widget.findChild(QWidget, "InspectionReferencePhotos")
        scroll = widget._control_points_scroll
        self.assertIsInstance(scroll, QScrollArea)
        self.assertEqual(scroll.objectName(), "ControlPointsPanel")
        self.assertFalse(scroll.isAncestorOf(summary))
        self.assertFalse(scroll.isAncestorOf(widget._control_points_heading))
        self.assertFalse(scroll.isAncestorOf(photos))

        before = (
            summary.mapTo(widget, QPoint(0, 0)),
            widget._control_points_heading.mapTo(widget, QPoint(0, 0)),
            photos.mapTo(widget, QPoint(0, 0)),
        )
        bar = scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(bar.maximum())
        self._app.processEvents()
        after = (
            summary.mapTo(widget, QPoint(0, 0)),
            widget._control_points_heading.mapTo(widget, QPoint(0, 0)),
            photos.mapTo(widget, QPoint(0, 0)),
        )
        self.assertEqual(before, after)

    def test_empty_reference_photos_are_compact(self) -> None:
        empty = self._show(photos=[])
        empty_block = empty.findChild(QWidget, "InspectionReferencePhotos")
        empty_label = empty.findChild(QLabel, "ReferencePhotosEmpty")
        self.assertIsNotNone(empty_label)
        self.assertEqual(
            empty_label.text(),
            "Referenční fotografie budou doplněny.",
        )
        self.assertLess(empty_block.height(), 90)

        filled = self._show(
            photos=[
                {
                    "id": "f1",
                    "soubor": "neexistuje.jpg",
                    "aktivni": True,
                    "poradi": 10,
                },
                {
                    "id": "f2",
                    "soubor": "dalsi.jpg",
                    "aktivni": True,
                    "poradi": 20,
                },
            ]
        )
        photos = filled.findChild(QWidget, "InspectionReferencePhotos")
        self.assertIsNone(filled.findChild(QLabel, "ReferencePhotosEmpty"))
        gallery = photos.findChild(QScrollArea)
        self.assertIsNotNone(gallery)
        self.assertEqual(
            gallery.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.assertGreater(photos.height(), empty_block.height())

    def test_documentation_and_terrain_share_working_value(self) -> None:
        deferred = InspectionDeferredEdits()
        docs = self._show(deferred=deferred)
        terrain = self._show(
            verification_type=VERIFICATION_TYPE_TERRAIN,
            deferred=deferred,
        )
        docs._section_summary_edit.set_text("Společný text")
        docs._on_section_summary_changed()
        terrain.reload_section_summary()
        self.assertEqual(terrain._section_summary_edit.text(), "Společný text")
        self.assertEqual(_count("inspection_section_summaries"), 0)

    def test_save_and_discard_unchanged(self) -> None:
        ids = self._commission_ids()
        inspection = bozp_inspection_service.create_inspection(title="UX1 save")
        dialog = BozpInspectionDialog(inspection=inspection)
        self._fill_commission(dialog, ids)
        section = dialog.areas_widget.knowledge_widget.section_widget
        section.set_section(
            _section(),
            area_id="a1",
            area_label="Oblast",
            section_label="Okruh",
        )
        section._section_summary_edit.set_text("Uložený text")
        section._on_section_summary_changed()
        self.assertTrue(dialog._persist())
        self.assertEqual(
            inspection_section_summary_service.get_text(
                inspection.id, area_id="a1", section_id="s1"
            ),
            "Uložený text",
        )

        section = dialog.areas_widget.knowledge_widget.section_widget
        section.set_section(
            _section(),
            area_id="a1",
            area_label="Oblast",
            section_label="Okruh",
        )
        section._section_summary_edit.set_text("Zahodit")
        section._on_section_summary_changed()
        with patch(
            "moduly.proverky.ui.bozp_inspection_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            dialog._request_close()
        self.assertEqual(
            inspection_section_summary_service.get_text(
                inspection.id, area_id="a1", section_id="s1"
            ),
            "Uložený text",
        )

    def test_legacy_inspection_keeps_question_notes(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            title="Legacy UX1", notes_mode=None
        )
        widget = self._show(notes_mode=inspection.notes_mode, point_count=1)
        widget.set_inspection_id(inspection.id)
        self.assertIsNone(inspection.notes_mode)
        self.assertIsNone(widget.findChild(SectionSummaryEdit))
        selectors = widget.findChildren(ControlResultSelectorWidget)
        self.assertTrue(selectors)
        self.assertFalse(selectors[0]._note_edit.isHidden())
        self.assertEqual(widget._control_points_heading.text(), "Kontrolní body")

    def test_unsaved_inspection_checklist_disabled(self) -> None:
        before = len(bozp_inspection_service.get_all())
        dialog = BozpInspectionDialog()
        button = dialog.terrain_widget.checklist_btn
        self.assertIsNotNone(button)
        self.assertFalse(button.isEnabled())
        self.assertEqual(button.toolTip(), TERRAIN_CHECKLIST_SAVE_FIRST_TOOLTIP)
        self.assertEqual(len(bozp_inspection_service.get_all()), before)
        dialog._closing = True
        dialog.close()
        self.assertEqual(len(bozp_inspection_service.get_all()), before)

    def test_first_save_enables_checklist_when_terrain_points_exist(self) -> None:
        ids = self._commission_ids()
        dialog = BozpInspectionDialog()
        button = dialog.terrain_widget.checklist_btn
        self.assertFalse(button.isEnabled())
        self._fill_commission(dialog, ids)
        self.assertTrue(dialog._persist())
        self.assertIsNotNone(dialog.inspection)
        self.assertTrue(terrain_checklist_service.has_terrain_points(dialog.inspection.id))
        self.assertTrue(button.isEnabled())
        self.assertEqual(button.toolTip(), TERRAIN_CHECKLIST_TOOLTIP)

    def test_saved_inspection_with_terrain_points_enables_checklist(self) -> None:
        inspection = bozp_inspection_service.create_inspection(title="UX1 terrain")
        widget = BozpInspectionTerrainWidget()
        widget.set_inspection_id(inspection.id)
        self.assertTrue(terrain_checklist_service.has_terrain_points(inspection.id))
        self.assertTrue(widget.checklist_btn.isEnabled())
        self.assertEqual(widget.checklist_btn.toolTip(), TERRAIN_CHECKLIST_TOOLTIP)

    def test_saved_inspection_without_terrain_points_disables_checklist(self) -> None:
        inspection = bozp_inspection_service.create_inspection(title="UX1 no terrain")
        widget = BozpInspectionTerrainWidget()
        with patch.object(
            terrain_checklist_service, "has_terrain_points", return_value=False
        ):
            widget.set_inspection_id(inspection.id)
            self.assertFalse(widget.checklist_btn.isEnabled())
            self.assertEqual(
                widget.checklist_btn.toolTip(),
                TERRAIN_CHECKLIST_NO_TERRAIN_POINTS_TOOLTIP,
            )

    def test_open_scroll_and_checklist_refresh_do_not_write(self) -> None:
        inspection = bozp_inspection_service.create_inspection(title="UX1 open")
        before = _count("inspection_section_summaries")
        dialog = BozpInspectionDialog(inspection=inspection)
        dialog.tabs.setCurrentWidget(dialog.areas_widget)
        section = dialog.areas_widget.knowledge_widget.section_widget
        section.set_section(
            _section(point_count=10),
            area_id="a1",
            area_label="Oblast",
            section_label="Okruh",
        )
        section.resize(1100, 720)
        section.show()
        self._app.processEvents()
        bar = section._control_points_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        dialog.tabs.setCurrentWidget(dialog.terrain_widget)
        dialog.terrain_widget.refresh_checklist_button()
        after = _count("inspection_section_summaries")
        self.assertEqual(before, after)
        dialog._closing = True
        dialog.close()

    def test_audit_summary_widget_untouched_default_height(self) -> None:
        compact = SectionSummaryEdit(compact=True)
        default = SectionSummaryEdit()
        self.assertEqual(compact._edit.minimumHeight(), SUMMARY_EDIT_COMPACT_HEIGHT)
        self.assertEqual(compact._edit.maximumHeight(), SUMMARY_EDIT_COMPACT_HEIGHT)
        self.assertEqual(default._edit.minimumHeight(), SUMMARY_EDIT_DEFAULT_HEIGHT)
        self.assertNotEqual(default._edit.maximumHeight(), SUMMARY_EDIT_COMPACT_HEIGHT)


if __name__ == "__main__":
    unittest.main()

"""METHODOLOGY-PDF-1 – PDF přehled auditních a prověrkových otázek."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)
_HOME_PATCHER.start()


def _bootstrap() -> None:
    import core.services.editable_catalog_service as editable_catalog_module
    import core.services.storage_service as storage_module
    import core.database.session as session_module
    import moduly.audity.sluzby.audit_knowledge_editor_service as audity_editor_module
    import moduly.audity.sluzby.audit_knowledge_service as audity_knowledge_module
    import moduly.proverky.sluzby.proverky_knowledge_service as proverky_knowledge_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(editable_catalog_module)
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()
    importlib.reload(audity_knowledge_module)
    importlib.reload(audity_editor_module)
    importlib.reload(proverky_knowledge_module)


_bootstrap()

from core.export.methodology_questions_pdf import (
    METHODOLOGY_PDF_AUDIT_TITLE,
    METHODOLOGY_PDF_EMPTY_NOTE,
    METHODOLOGY_PDF_FAILED,
    METHODOLOGY_PDF_PROVERKY_TITLE,
    METHODOLOGY_PDF_SAVED,
    PARAM_DESCRIPTION,
    PARAM_SEVERITY,
    PARAM_VERIFICATION_TYPE,
    choose_pdf_save_path,
    methodology_questions_plain_text,
    write_methodology_questions_pdf,
)
from core.widgets.knowledge_editor_actions import KNOWLEDGE_EDITOR_EXPORT_PDF_BUTTON
from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
    CONTROL_POINT_SEVERITY_KRITICKA,
    CONTROL_POINT_SEVERITY_VYSOKA,
)
from moduly.audity.sluzby.audit_knowledge_service import (
    KNOWLEDGE_NODE_PROCESS,
    KNOWLEDGE_NODE_SECTION,
    KnowledgeTreeNode as AuditTreeNode,
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_methodology_questions_export import (
    build_audit_methodology_questions_document,
    build_audit_methodology_questions_document_from_editor,
)
from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
from moduly.proverky.constants import (
    CONTROL_POINT_SEVERITY_STREDNI,
    KNOWLEDGE_EDITOR_DEFAULT_AREA_ID,
    KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID,
)
from moduly.proverky.sluzby.proverky_knowledge_service import (
    KNOWLEDGE_NODE_AREA,
    KNOWLEDGE_NODE_SECTION as PROVERKY_NODE_SECTION,
    KnowledgeTreeNode as ProverkyTreeNode,
    proverky_knowledge_service,
)
from moduly.proverky.sluzby.proverky_methodology_questions_export import (
    build_proverky_methodology_questions_document,
    build_proverky_methodology_questions_document_from_editor,
)
from moduly.proverky.ui.proverky_knowledge_editor_dialog import ProverkyKnowledgeEditorDialog
from core.shared.verification_type import (
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
)

_CREATED = date(2026, 8, 17)
_PROCESS_ID = "urazy_mimo_udalosti"


def _audit_question(
    item_id: str,
    text: str,
    *,
    poradi: int = 10,
    aktivni: bool = True,
    verification_type: str = VERIFICATION_TYPE_DOCUMENTATION,
    zavaznost: str = CONTROL_POINT_SEVERITY_STREDNI,
    question_kind: str | None = AUDIT_QUESTION_KIND_OPERATION,
    popis: str = "",
) -> dict:
    item = {
        "id": item_id,
        "text": text,
        "nazev": text,
        "aktivni": aktivni,
        "poradi": poradi,
        "verification_type": verification_type,
        "zavaznost": zavaznost,
        "popis": popis,
    }
    if question_kind is not None:
        item["question_kind"] = question_kind
    return item


def _audit_section_node(
    section_id: str,
    title: str,
    process_id: str,
    questions: list[dict],
    *,
    poradi: int = 10,
    aktivni: bool = True,
    children: tuple[AuditTreeNode, ...] = (),
) -> AuditTreeNode:
    return AuditTreeNode(
        node_type=KNOWLEDGE_NODE_SECTION,
        node_id=section_id,
        label=title,
        process_id=process_id,
        process_label=process_id,
        section={
            "id": section_id,
            "nazev": title,
            "aktivni": aktivni,
            "poradi": poradi,
            "auditni_tvrzeni": questions,
        },
        children=children,
    )


def _audit_process_node(
    process_id: str,
    title: str,
    children: tuple[AuditTreeNode, ...],
) -> AuditTreeNode:
    return AuditTreeNode(
        node_type=KNOWLEDGE_NODE_PROCESS,
        node_id=process_id,
        label=title,
        process_id=process_id,
        process_label=title,
        children=children,
    )


def _proverky_question(
    item_id: str,
    nazev: str,
    *,
    poradi: int = 10,
    aktivni: bool = True,
    verification_type: str = VERIFICATION_TYPE_TERRAIN,
    zavaznost: str = CONTROL_POINT_SEVERITY_VYSOKA,
    popis: str = "",
    vysledek: str | None = None,
) -> dict:
    item = {
        "id": item_id,
        "nazev": nazev,
        "aktivni": aktivni,
        "poradi": poradi,
        "verification_type": verification_type,
        "zavaznost": zavaznost,
        "popis": popis,
    }
    if vysledek is not None:
        item["vysledek"] = vysledek
        item["hodnoceni"] = vysledek
    return item


def _proverky_section_node(
    section_id: str,
    title: str,
    area_id: str,
    questions: list[dict],
    *,
    poradi: int = 10,
    aktivni: bool = True,
    children: tuple[ProverkyTreeNode, ...] = (),
) -> ProverkyTreeNode:
    return ProverkyTreeNode(
        node_type=PROVERKY_NODE_SECTION,
        node_id=section_id,
        label=title,
        area_id=area_id,
        area_label=area_id,
        section={
            "id": section_id,
            "nazev": title,
            "aktivni": aktivni,
            "poradi": poradi,
            "kontrolni_body": questions,
        },
        children=children,
    )


def _proverky_area_node(
    area_id: str,
    title: str,
    children: tuple[ProverkyTreeNode, ...],
) -> ProverkyTreeNode:
    return ProverkyTreeNode(
        node_type=KNOWLEDGE_NODE_AREA,
        node_id=area_id,
        label=title,
        area_id=area_id,
        area_label=title,
        children=children,
    )


def _pdf_page_count(path: Path) -> int:
    data = path.read_bytes()
    return data.count(b"/Type /Page") - data.count(b"/Type /Pages")


def _pdf_haystack(path: Path) -> str:
    data = path.read_bytes()
    parts = [data.decode("latin-1", errors="ignore")]
    for encoding in ("utf-8", "utf-16-be", "utf-16-le"):
        parts.append(data.decode(encoding, errors="ignore"))
    return "\n".join(parts)


def _catalog_fingerprint() -> dict[str, tuple[int, bytes]]:
    files: dict[str, tuple[int, bytes]] = {}
    for folder in (
        audit_knowledge_service.audity_dir,
        proverky_knowledge_service.proverky_dir,
    ):
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.json")):
            files[str(path)] = (path.stat().st_mtime_ns, path.read_bytes())
    return files


class AuditMethodologyQuestionsExportTestCase(unittest.TestCase):
    def _document(self, tree, **kwargs):
        kwargs.setdefault("created_on", _CREATED)
        kwargs.setdefault("process_active", {node.process_id: True for node in tree})
        return build_audit_methodology_questions_document(
            knowledge_tree=tree,
            **kwargs,
        )

    def test_exports_only_active_ordinary_questions_in_order(self) -> None:
        nested = _audit_section_node(
            "sec_a1_child",
            "Podsekce A1",
            "proc_a",
            [_audit_question("id-child", "Otázka podsekce")],
        )
        tree = [
            _audit_process_node(
                "proc_a",
                "Proces A",
                (
                    _audit_section_node(
                        "sec_a1",
                        "Sekce A1",
                        "proc_a",
                        [
                            _audit_question(
                                "id-a1",
                                "Otázka A1",
                                verification_type=VERIFICATION_TYPE_TERRAIN,
                                zavaznost=CONTROL_POINT_SEVERITY_KRITICKA,
                                question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                                popis="POZNAMKA-NEEXPORT",
                            ),
                            _audit_question(
                                "id-extra",
                                "Mimořádná otázka XY",
                                question_kind=AUDIT_QUESTION_KIND_EXTRAORDINARY,
                            ),
                        ],
                        children=(nested,),
                    ),
                ),
            ),
            _audit_process_node(
                "proc_b",
                "Proces B",
                (
                    _audit_section_node(
                        "sec_b1",
                        "Sekce B1",
                        "proc_b",
                        [
                            _audit_question("id-b2", "Otázka B2", poradi=20),
                            _audit_question("id-b1", "Otázka B1", poradi=10),
                            _audit_question(
                                "id-b-off",
                                "Neaktivní B",
                                poradi=5,
                                aktivni=False,
                            ),
                        ],
                    ),
                ),
            ),
        ]
        document = self._document(tree)
        text = methodology_questions_plain_text(document)

        self.assertEqual(document.question_count, 4)
        self.assertEqual([group.title for group in document.groups], ["Proces A", "Proces B"])
        self.assertEqual(
            [section.title for section in document.groups[0].sections],
            ["Sekce A1", "Podsekce A1"],
        )
        self.assertEqual(document.groups[0].sections[0].questions[0].text, "Otázka A1")
        self.assertEqual(
            dict(document.groups[0].sections[0].questions[0].params),
            {
                PARAM_VERIFICATION_TYPE: "Terén",
                PARAM_SEVERITY: "Kritická",
            },
        )
        self.assertEqual(
            [q.text for q in document.groups[1].sections[0].questions],
            ["Otázka B1", "Otázka B2"],
        )
        self.assertNotIn("Neaktivní B", text)
        self.assertNotIn("Mimořádná otázka XY", text)
        self.assertNotIn("POZNAMKA-NEEXPORT", text)
        self.assertNotIn("Druh otázky", text)
        self.assertNotIn("Systém", text)
        self.assertNotIn("id-a1", text)
        self.assertNotIn("sec_a1", text)
        self.assertNotIn("proc_a", text)

    def test_skips_inactive_process_and_section(self) -> None:
        tree = [
            _audit_process_node(
                "p-off",
                "Vypnutý proces",
                (
                    _audit_section_node(
                        "s1",
                        "Sekce",
                        "p-off",
                        [_audit_question("q1", "Skrytá otázka")],
                    ),
                ),
            ),
            _audit_process_node(
                "p-on",
                "Aktivní proces",
                (
                    _audit_section_node(
                        "s-off",
                        "Vypnutá sekce",
                        "p-on",
                        [_audit_question("q2", "Otázka vypnuté sekce")],
                        aktivni=False,
                    ),
                    _audit_section_node(
                        "s-on",
                        "Aktivní sekce",
                        "p-on",
                        [_audit_question("q3", "Viditelná otázka")],
                    ),
                ),
            ),
        ]
        document = self._document(
            tree,
            process_active={"p-off": False, "p-on": True},
        )
        text = methodology_questions_plain_text(document)
        self.assertEqual(document.question_count, 1)
        self.assertIn("Viditelná otázka", text)
        self.assertNotIn("Skrytá otázka", text)
        self.assertNotIn("Otázka vypnuté sekce", text)

    def test_overlays_unsaved_process_and_section_metadata(self) -> None:
        tree = [
            _audit_process_node(
                "p1",
                "Původní proces",
                (
                    _audit_section_node(
                        "s1",
                        "Původní sekce",
                        "p1",
                        [_audit_question("q1", "Otázka 1")],
                    ),
                ),
            )
        ]
        document = self._document(
            tree,
            process_drafts={"p1": {"nazev": "Pracovní proces", "aktivni": True}},
            section_drafts={("p1", "s1"): {"nazev": "Pracovní sekce", "aktivni": True}},
        )
        self.assertEqual(document.groups[0].title, "Pracovní proces")
        self.assertEqual(document.groups[0].sections[0].title, "Pracovní sekce")

    def test_empty_methodology_has_zero_count(self) -> None:
        document = self._document([])
        self.assertEqual(document.question_count, 0)
        self.assertIn(METHODOLOGY_PDF_EMPTY_NOTE, methodology_questions_plain_text(document))
        self.assertEqual(document.title, METHODOLOGY_PDF_AUDIT_TITLE)


class ProverkyMethodologyQuestionsExportTestCase(unittest.TestCase):
    def _document(self, tree, **kwargs):
        kwargs.setdefault("created_on", _CREATED)
        kwargs.setdefault("area_active", {node.area_id: True for node in tree})
        return build_proverky_methodology_questions_document(
            knowledge_tree=tree,
            **kwargs,
        )

    def test_exports_active_questions_with_user_params(self) -> None:
        tree = [
            _proverky_area_node(
                "area_a",
                "Oblast A",
                (
                    _proverky_section_node(
                        "sec_a",
                        "Sekce A",
                        "area_a",
                        [
                            _proverky_question(
                                "kb-internal-99",
                                "Kontrola lékárničky",
                                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                                zavaznost=CONTROL_POINT_SEVERITY_VYSOKA,
                                popis="Zkontrolovat exspiraci.",
                                vysledek="neshoda",
                            ),
                            _proverky_question(
                                "kb-off",
                                "Neaktivní bod",
                                aktivni=False,
                            ),
                        ],
                    ),
                    _proverky_section_node(
                        "sec_off",
                        "Neaktivní sekce",
                        "area_a",
                        [_proverky_question("kb-hidden", "Skrytý bod")],
                        aktivni=False,
                    ),
                ),
            )
        ]
        document = self._document(tree)
        text = methodology_questions_plain_text(document)
        self.assertEqual(document.question_count, 1)
        question = document.groups[0].sections[0].questions[0]
        self.assertEqual(question.text, "Kontrola lékárničky")
        self.assertEqual(
            dict(question.params),
            {
                PARAM_VERIFICATION_TYPE: "Dokumentace",
                PARAM_SEVERITY: "Vysoká",
                PARAM_DESCRIPTION: "Zkontrolovat exspiraci.",
            },
        )
        self.assertNotIn("Neaktivní bod", text)
        self.assertNotIn("Skrytý bod", text)
        self.assertNotIn("kb-internal-99", text)
        self.assertNotIn("neshoda", text)
        self.assertNotIn("hodnoceni", text)
        self.assertEqual(document.title, METHODOLOGY_PDF_PROVERKY_TITLE)

    def test_overlays_unsaved_section_draft_including_questions(self) -> None:
        tree = [
            _proverky_area_node(
                "area_a",
                "Oblast A",
                (
                    _proverky_section_node(
                        "sec_a",
                        "Původní sekce",
                        "area_a",
                        [_proverky_question("kb1", "Původní otázka")],
                    ),
                ),
            )
        ]
        draft = {
            "id": "sec_a",
            "nazev": "Pracovní sekce",
            "aktivni": True,
            "kontrolni_body": [
                _proverky_question("kb1", "Pracovní otázka PDF"),
            ],
        }
        document = self._document(tree, section_drafts={("area_a", "sec_a"): draft})
        self.assertEqual(document.groups[0].sections[0].title, "Pracovní sekce")
        self.assertEqual(
            document.groups[0].sections[0].questions[0].text,
            "Pracovní otázka PDF",
        )

    def test_grouping_order_follows_tree(self) -> None:
        tree = [
            _proverky_area_node(
                "area_1",
                "Oblast 1",
                (
                    _proverky_section_node(
                        "s1",
                        "Sekce 1",
                        "area_1",
                        [
                            _proverky_question("q2", "Druhá", poradi=20),
                            _proverky_question("q1", "První", poradi=10),
                        ],
                    ),
                    _proverky_section_node(
                        "s2",
                        "Sekce 2",
                        "area_1",
                        [_proverky_question("q3", "Třetí")],
                    ),
                ),
            ),
            _proverky_area_node(
                "area_2",
                "Oblast 2",
                (
                    _proverky_section_node(
                        "s3",
                        "Sekce 3",
                        "area_2",
                        [_proverky_question("q4", "Čtvrtá")],
                    ),
                ),
            ),
        ]
        document = self._document(tree)
        self.assertEqual([g.title for g in document.groups], ["Oblast 1", "Oblast 2"])
        self.assertEqual(
            [s.title for s in document.groups[0].sections],
            ["Sekce 1", "Sekce 2"],
        )
        self.assertEqual(
            [q.text for q in document.groups[0].sections[0].questions],
            ["První", "Druhá"],
        )


class MethodologyQuestionsPdfRenderTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_writes_valid_pdf_with_czech_title_and_long_question(self) -> None:
        long_text = "Žluťoučký kůň " + ("úrazová otázka č. 15 — kontrola " * 40)
        document = build_audit_methodology_questions_document(
            knowledge_tree=[
                _audit_process_node(
                    "p1",
                    "Řízení rizik",
                    (
                        _audit_section_node(
                            "s1",
                            "Identifikace rizik",
                            "p1",
                            [_audit_question("q1", long_text)],
                        ),
                    ),
                )
            ],
            process_active={"p1": True},
            created_on=_CREATED,
        )
        path = Path(tempfile.mkdtemp()) / "prehled.pdf"
        write_methodology_questions_pdf(document, path)
        data = path.read_bytes()
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertIn(b"%%EOF", data[-1024:])
        haystack = _pdf_haystack(path)
        self.assertIn(METHODOLOGY_PDF_AUDIT_TITLE, haystack)
        self.assertIn("Žluťoučký kůň", methodology_questions_plain_text(document))
        self.assertIn(long_text[-40:], methodology_questions_plain_text(document))
        self.assertGreater(path.stat().st_size, 1500)

    def test_multipage_pdf_and_empty_methodology(self) -> None:
        questions = [
            _audit_question(f"q{i}", f"Otázka číslo {i} — příliš dlouhý text ke zalamování " * 8)
            for i in range(80)
        ]
        document = build_audit_methodology_questions_document(
            knowledge_tree=[
                _audit_process_node(
                    "p1",
                    "Proces",
                    (_audit_section_node("s1", "Sekce", "p1", questions),),
                )
            ],
            process_active={"p1": True},
            created_on=_CREATED,
        )
        path = Path(tempfile.mkdtemp()) / "multi.pdf"
        write_methodology_questions_pdf(document, path)
        self.assertGreaterEqual(_pdf_page_count(path), 2)

        empty = build_audit_methodology_questions_document(
            knowledge_tree=[],
            process_active={},
            created_on=_CREATED,
        )
        empty_path = Path(tempfile.mkdtemp()) / "empty.pdf"
        write_methodology_questions_pdf(empty, empty_path)
        self.assertTrue(empty_path.read_bytes().startswith(b"%PDF"))
        self.assertEqual(empty.question_count, 0)

    def test_cancel_save_dialog_creates_nothing(self) -> None:
        with patch(
            "core.export.methodology_questions_pdf.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ):
            path = choose_pdf_save_path(None, default_filename="x.pdf")
        self.assertIsNone(path)


class MethodologyPdfEditorUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _bootstrap()
        audit_knowledge_service.ensure_catalogs()
        proverky_knowledge_service.ensure_catalogs()

    def test_audit_editor_exports_unsaved_working_copy_without_writing(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertEqual(dialog._export_pdf_btn.text(), KNOWLEDGE_EDITOR_EXPORT_PDF_BUTTON)
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        working_name = "Pracovní název procesu PDF"
        dialog.process_editor._nazev_edit.setText(working_name)
        self.assertTrue(dialog._has_unsaved_changes())
        fingerprint = _catalog_fingerprint()

        with patch.object(audit_knowledge_service, "get_knowledge_tree") as mock_tree:
            document = build_audit_methodology_questions_document_from_editor(dialog)
        mock_tree.assert_not_called()
        self.assertIn(working_name, methodology_questions_plain_text(document))
        self.assertTrue(dialog._has_unsaved_changes())
        self.assertEqual(dialog._process_drafts, {})
        self.assertEqual(_catalog_fingerprint(), fingerprint)

        target = Path(tempfile.mkdtemp()) / "audit.pdf"
        with (
            patch(
                "moduly.audity.ui.audity_knowledge_editor_dialog.choose_pdf_save_path",
                return_value=str(target),
            ),
            patch.object(QMessageBox, "information") as mock_info,
            patch.object(QMessageBox, "warning") as mock_warn,
        ):
            dialog._export_questions_pdf()
        mock_warn.assert_not_called()
        mock_info.assert_called_once()
        self.assertEqual(mock_info.call_args[0][2], METHODOLOGY_PDF_SAVED)
        self.assertTrue(target.is_file())
        self.assertTrue(dialog._has_unsaved_changes())
        self.assertEqual(_catalog_fingerprint(), fingerprint)

    def test_audit_editor_cancel_does_not_create_file_or_error(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        with (
            patch(
                "moduly.audity.ui.audity_knowledge_editor_dialog.choose_pdf_save_path",
                return_value=None,
            ),
            patch(
                "moduly.audity.ui.audity_knowledge_editor_dialog.write_methodology_questions_pdf"
            ) as mock_write,
            patch.object(QMessageBox, "information") as mock_info,
            patch.object(QMessageBox, "warning") as mock_warn,
        ):
            dialog._export_questions_pdf()
        mock_write.assert_not_called()
        mock_info.assert_not_called()
        mock_warn.assert_not_called()

    def test_audit_export_error_shows_message_without_traceback(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        with (
            patch(
                "moduly.audity.ui.audity_knowledge_editor_dialog.choose_pdf_save_path",
                return_value="/tmp/x.pdf",
            ),
            patch(
                "moduly.audity.ui.audity_knowledge_editor_dialog.write_methodology_questions_pdf",
                side_effect=OSError("disk full TRACEBACK"),
            ),
            patch.object(QMessageBox, "warning") as mock_warn,
        ):
            dialog._export_questions_pdf()
        mock_warn.assert_called_once()
        self.assertEqual(mock_warn.call_args[0][2], METHODOLOGY_PDF_FAILED)

    def test_proverky_editor_exports_unsaved_question_without_writing(self) -> None:
        dialog = ProverkyKnowledgeEditorDialog()
        self.assertEqual(dialog._export_pdf_btn.text(), KNOWLEDGE_EDITOR_EXPORT_PDF_BUTTON)
        self.assertTrue(
            dialog.knowledge_tree.select_node(
                KNOWLEDGE_EDITOR_DEFAULT_AREA_ID,
                KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID,
            )
        )
        editor = dialog._section_editor
        self.assertIsNotNone(editor)
        list_widget = editor._lists_by_field["kontrolni_body"]
        self.assertGreater(list_widget.count(), 0)
        item = list_widget.item(0)
        data = dict(item.data(Qt.ItemDataRole.UserRole))
        working_text = "Pracovní otázka prověrky PDF"
        data["nazev"] = working_text
        item.setData(Qt.ItemDataRole.UserRole, data)
        editor._nazev_edit.setText("Pracovní sekce PDF")
        self.assertTrue(dialog._has_unsaved_changes())
        fingerprint = _catalog_fingerprint()

        with patch.object(proverky_knowledge_service, "get_knowledge_tree") as mock_tree:
            document = build_proverky_methodology_questions_document_from_editor(dialog)
        mock_tree.assert_not_called()
        text = methodology_questions_plain_text(document)
        self.assertIn(working_text, text)
        self.assertIn("Pracovní sekce PDF", text)
        self.assertTrue(dialog._has_unsaved_changes())
        self.assertEqual(_catalog_fingerprint(), fingerprint)

        target = Path(tempfile.mkdtemp()) / "proverky.pdf"
        with (
            patch(
                "moduly.proverky.ui.proverky_knowledge_editor_dialog.choose_pdf_save_path",
                return_value=str(target),
            ),
            patch.object(QMessageBox, "information") as mock_info,
            patch.object(QMessageBox, "warning") as mock_warn,
        ):
            dialog._export_questions_pdf()
        mock_warn.assert_not_called()
        mock_info.assert_called_once()
        self.assertTrue(target.is_file())
        self.assertEqual(_catalog_fingerprint(), fingerprint)

    def test_proverky_cancel_does_not_create_file_or_error(self) -> None:
        dialog = ProverkyKnowledgeEditorDialog()
        with (
            patch(
                "moduly.proverky.ui.proverky_knowledge_editor_dialog.choose_pdf_save_path",
                return_value=None,
            ),
            patch(
                "moduly.proverky.ui.proverky_knowledge_editor_dialog.write_methodology_questions_pdf"
            ) as mock_write,
            patch.object(QMessageBox, "information") as mock_info,
            patch.object(QMessageBox, "warning") as mock_warn,
        ):
            dialog._export_questions_pdf()
        mock_write.assert_not_called()
        mock_info.assert_not_called()
        mock_warn.assert_not_called()

    def test_live_export_loads_methodology_at_most_once(self) -> None:
        audit_knowledge_service.ensure_catalogs()
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            wraps=audit_knowledge_service.get_knowledge_tree,
        ) as mock_tree:
            document = build_audit_methodology_questions_document()
        self.assertEqual(mock_tree.call_count, 1)
        self.assertGreaterEqual(document.question_count, 0)

        proverky_knowledge_service.ensure_catalogs()
        with patch.object(
            proverky_knowledge_service,
            "get_knowledge_tree",
            wraps=proverky_knowledge_service.get_knowledge_tree,
        ) as mock_tree:
            document = build_proverky_methodology_questions_document()
        self.assertEqual(mock_tree.call_count, 1)
        self.assertGreaterEqual(document.question_count, 0)


if __name__ == "__main__":
    unittest.main()

"""METHODOLOGY-PDF-1-UX1 – tučný text otázek v PDF přehledu metodiky."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QFont, QFontMetricsF
from PySide6.QtWidgets import QApplication

from core.export.methodology_questions_pdf import (
    METHODOLOGY_PDF_AUDIT_TITLE,
    METHODOLOGY_PDF_PROVERKY_TITLE,
    PARAM_DESCRIPTION,
    PARAM_SEVERITY,
    PARAM_VERIFICATION_TYPE,
    MethodologyGroup,
    MethodologyQuestion,
    MethodologyQuestionsDocument,
    MethodologySection,
    _MethodologyPdfRenderer,
    _wrap_text,
    write_methodology_questions_pdf,
)

_CREATED = date(2026, 8, 17)


def _document(
    title: str,
    questions: tuple[MethodologyQuestion, ...],
    *,
    group: str = "Řízení rizik",
    section: str = "Identifikace rizik",
) -> MethodologyQuestionsDocument:
    return MethodologyQuestionsDocument(
        title=title,
        created_on=_CREATED,
        question_count=len(questions),
        groups=(
            MethodologyGroup(
                title=group,
                sections=(MethodologySection(title=section, questions=questions),),
            ),
        ),
    )


def _audit_question(text: str, **kwargs) -> MethodologyQuestion:
    return MethodologyQuestion(
        text=text,
        params=(
            (PARAM_VERIFICATION_TYPE, kwargs.get("verification", "Terén")),
            (PARAM_SEVERITY, kwargs.get("severity", "Vysoká")),
        ),
    )


def _proverky_question(text: str, **kwargs) -> MethodologyQuestion:
    params = [
        (PARAM_VERIFICATION_TYPE, kwargs.get("verification", "Dokumentace")),
        (PARAM_SEVERITY, kwargs.get("severity", "Střední")),
    ]
    popis = kwargs.get("popis")
    if popis:
        params.append((PARAM_DESCRIPTION, popis))
    return MethodologyQuestion(text=text, params=tuple(params))


def _pdf_page_count(path: Path) -> int:
    data = path.read_bytes()
    return data.count(b"/Type /Page") - data.count(b"/Type /Pages")


class _DrawTrace:
    def __init__(self) -> None:
        self.paragraphs: list[dict] = []

    def install(self):
        orig_draw = _MethodologyPdfRenderer._draw_paragraph

        def _draw_paragraph(renderer, text: str, font: QFont):
            y_before = renderer._y
            page_before = renderer._page_no
            self.paragraphs.append(
                {
                    "text": text,
                    "bold": bool(font.bold()),
                    "size": font.pointSizeF(),
                    "page": page_before,
                    "y_before": y_before,
                    "expected_height": renderer._paragraph_height(text, font),
                    "line_h": QFontMetricsF(font).lineSpacing(),
                }
            )
            orig_draw(renderer, text, font)
            self.paragraphs[-1]["y_after"] = renderer._y
            self.paragraphs[-1]["page_after"] = renderer._page_no

        return patch.object(
            _MethodologyPdfRenderer,
            "_draw_paragraph",
            _draw_paragraph,
        )


class MethodologyPdf1Ux1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _write(self, document: MethodologyQuestionsDocument, *, trace: _DrawTrace | None = None) -> Path:
        path = Path(tempfile.mkdtemp()) / "prehled.pdf"
        if trace is None:
            write_methodology_questions_pdf(document, path)
            return path
        with trace.install():
            write_methodology_questions_pdf(document, path)
        return path

    def test_audit_question_text_is_bold_params_are_regular(self) -> None:
        question_text = "Žluťoučký kůň ověřuje, že hasicí přístroj je připraven."
        document = _document(
            METHODOLOGY_PDF_AUDIT_TITLE,
            (_audit_question(question_text),),
        )
        fonts: dict[str, QFont] = {}
        orig_init = _MethodologyPdfRenderer.__init__

        def _init(renderer, *args, **kwargs):
            orig_init(renderer, *args, **kwargs)
            fonts["question"] = QFont(renderer._question_font)
            fonts["param"] = QFont(renderer._param_font)

        trace = _DrawTrace()
        with patch.object(_MethodologyPdfRenderer, "__init__", _init):
            path = self._write(document, trace=trace)

        self.assertTrue(path.read_bytes().startswith(b"%PDF"))
        self.assertTrue(fonts["question"].bold())
        self.assertGreaterEqual(int(fonts["question"].weight()), int(QFont.Weight.Bold))
        self.assertFalse(fonts["param"].bold())

        question_para = next(p for p in trace.paragraphs if p["text"] == question_text)
        self.assertTrue(question_para["bold"])
        self.assertEqual(question_para["size"], 9)

        param_para = next(p for p in trace.paragraphs if PARAM_VERIFICATION_TYPE in p["text"])
        self.assertFalse(param_para["bold"])
        self.assertEqual(param_para["size"], 8)
        self.assertIn(PARAM_SEVERITY, param_para["text"])
        self.assertNotIn(PARAM_DESCRIPTION, param_para["text"])

    def test_proverky_question_text_is_bold_description_stays_regular(self) -> None:
        question_text = "Kontrola lékárničky — obvazový materiál a exspirace."
        popis = "Zkontrolovat české příbalové letáky a záznamy o doplnění."
        document = _document(
            METHODOLOGY_PDF_PROVERKY_TITLE,
            (_proverky_question(question_text, popis=popis),),
            group="První pomoc",
            section="Lékárnička",
        )
        trace = _DrawTrace()
        path = self._write(document, trace=trace)
        self.assertTrue(path.read_bytes().startswith(b"%PDF"))

        question_para = next(p for p in trace.paragraphs if p["text"] == question_text)
        self.assertTrue(question_para["bold"])
        param_para = next(p for p in trace.paragraphs if PARAM_DESCRIPTION in p["text"])
        self.assertFalse(param_para["bold"])
        self.assertIn(PARAM_VERIFICATION_TYPE, param_para["text"])
        self.assertIn(PARAM_SEVERITY, param_para["text"])
        self.assertIn(popis, param_para["text"])

    def test_long_bold_question_wraps_without_losing_text(self) -> None:
        long_text = (
            "Žluťoučký kůň úpěl ďábelské ódy — ověřit, že dokumentace rizika "
            "a terénní opatření jsou úplné, aktuální a srozumitelné. "
        ) * 12
        document = _document(
            METHODOLOGY_PDF_AUDIT_TITLE,
            (_audit_question(long_text.strip()),),
        )
        fonts: dict[str, QFont] = {}
        width = {"value": 0.0}
        orig_init = _MethodologyPdfRenderer.__init__

        def _init(renderer, *args, **kwargs):
            orig_init(renderer, *args, **kwargs)
            fonts["question"] = QFont(renderer._question_font)
            width["value"] = renderer._width

        trace = _DrawTrace()
        with patch.object(_MethodologyPdfRenderer, "__init__", _init):
            path = self._write(document, trace=trace)

        self.assertTrue(path.is_file())
        self.assertTrue(fonts["question"].bold())
        lines = _wrap_text(long_text.strip(), fonts["question"], width["value"])
        self.assertGreater(len(lines), 1)
        self.assertEqual("".join(lines), long_text.strip())

        question_para = next(p for p in trace.paragraphs if p["text"] == long_text.strip())
        self.assertTrue(question_para["bold"])
        if question_para["page"] == question_para["page_after"]:
            self.assertAlmostEqual(
                question_para["y_after"] - question_para["y_before"],
                question_para["expected_height"],
                delta=0.05,
            )

    def test_multipage_bold_export_does_not_overlap_or_clip(self) -> None:
        questions = tuple(
            _audit_question(
                f"Otázka číslo {index} — žluťoučký kůň a dlouhé ověření dokumentace "
                f"i terénu, aby se text zalomil přes více řádků. "
                * 6
            )
            for index in range(60)
        )
        document = _document(METHODOLOGY_PDF_AUDIT_TITLE, questions)
        trace = _DrawTrace()
        path = self._write(document, trace=trace)
        self.assertGreaterEqual(_pdf_page_count(path), 2)

        recorded_questions = [p["text"] for p in trace.paragraphs if p["bold"] and p["size"] == 9]
        for question in questions:
            self.assertIn(question.text, recorded_questions)

        same_page = [
            p
            for p in trace.paragraphs
            if p["page"] == p["page_after"] and p["size"] in (8, 9)
        ]
        for paragraph in same_page:
            self.assertGreaterEqual(paragraph["y_after"], paragraph["y_before"])
            self.assertAlmostEqual(
                paragraph["y_after"] - paragraph["y_before"],
                paragraph["expected_height"],
                delta=0.05,
            )

        by_page: dict[int, list[dict]] = {}
        for paragraph in same_page:
            by_page.setdefault(paragraph["page"], []).append(paragraph)
        for paragraphs in by_page.values():
            ordered = sorted(paragraphs, key=lambda item: item["y_before"])
            for previous, current in zip(ordered, ordered[1:]):
                self.assertGreaterEqual(current["y_before"] + 0.05, previous["y_after"])

    def test_audit_and_proverky_pdf_export_remain_functional(self) -> None:
        audit = _document(
            METHODOLOGY_PDF_AUDIT_TITLE,
            (_audit_question("Auditní tvrzení s českými znaky řěščž."),),
        )
        proverky = _document(
            METHODOLOGY_PDF_PROVERKY_TITLE,
            (
                _proverky_question(
                    "Otázka prověrky s českými znaky ůúďť.",
                    popis="Popis k ověření v terénu.",
                ),
            ),
            group="Oblast",
            section="Sekce",
        )
        audit_path = self._write(audit)
        proverky_path = self._write(proverky)
        self.assertTrue(audit_path.read_bytes().startswith(b"%PDF"))
        self.assertTrue(proverky_path.read_bytes().startswith(b"%PDF"))
        self.assertIn(b"%%EOF", audit_path.read_bytes()[-1024:])
        self.assertIn(b"%%EOF", proverky_path.read_bytes()[-1024:])


if __name__ == "__main__":
    unittest.main()
